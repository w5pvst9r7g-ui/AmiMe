#!/usr/bin/env python3
"""Real-ESRGAN super-resolution for the charm cut-outs (CPU, torch-only).

Why inline nets: the `realesrgan`/`basicsr` packages break against current
torchvision (`functional_tensor` removed), so we define the two architectures
here and load the official weights directly. Faithful upscale — it sharpens the
real pixels, it does not invent new content.

Pipeline per charm: cut the charm from the SOURCE sheet at native resolution
(max detail), run x4 SR on the RGB, bicubic-upscale the alpha to match,
recompose RGBA, then body-aware normalise to a high-res square.

    python3 tools/realesrgan_upscale.py            # all charms
    python3 tools/realesrgan_upscale.py id1 id2     # just these

Weights auto-download from GitHub (reachable here) to tools/weights/.
"""
import os, sys, json, urllib.request
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import ai_crop as ac

WEIGHTS = {
    # compact, fast, great general model — good for CPU
    "x4v3": ("https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth",
             os.path.join(ROOT, "tools", "weights", "realesr-general-x4v3.pth")),
    # heavier RRDBNet — best quality, slower
    "x4plus": ("https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
               os.path.join(ROOT, "tools", "weights", "RealESRGAN_x4plus.pth")),
}
MODEL = os.environ.get("ESRGAN_MODEL", "x4v3")
OUT_CANVAS = int(os.environ.get("ESRGAN_CANVAS", "1024"))
OUT_DIR = os.environ.get("ESRGAN_OUT", os.path.join(ROOT, "charms", "crops"))
TILE = 256          # tile size to bound CPU memory


def fetch(url, path):
    if os.path.exists(path):
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    print("downloading", url)
    urllib.request.urlretrieve(url, path)
    return path


def build_model(state):
    import torch.nn as nn
    import torch.nn.functional as F

    class SRVGGNetCompact(nn.Module):
        def __init__(self, num_feat=64, num_conv=32, upscale=4):
            super().__init__()
            self.body = nn.ModuleList()
            self.body.append(nn.Conv2d(3, num_feat, 3, 1, 1))
            self.body.append(nn.PReLU(num_parameters=num_feat))
            for _ in range(num_conv):
                self.body.append(nn.Conv2d(num_feat, num_feat, 3, 1, 1))
                self.body.append(nn.PReLU(num_parameters=num_feat))
            self.body.append(nn.Conv2d(num_feat, 3 * upscale * upscale, 3, 1, 1))
            self.up = nn.PixelShuffle(upscale)
            self.upscale = upscale

        def forward(self, x):
            out = x
            for layer in self.body:
                out = layer(out)
            out = self.up(out)
            return out + F.interpolate(x, scale_factor=self.upscale, mode="nearest")

    # RRDBNet (x4plus) — names match the official basicsr checkpoint
    import torch

    class ResidualDenseBlock(nn.Module):
        def __init__(self, nf=64, gc=32):
            super().__init__()
            self.conv1 = nn.Conv2d(nf, gc, 3, 1, 1); self.conv2 = nn.Conv2d(nf + gc, gc, 3, 1, 1)
            self.conv3 = nn.Conv2d(nf + 2 * gc, gc, 3, 1, 1); self.conv4 = nn.Conv2d(nf + 3 * gc, gc, 3, 1, 1)
            self.conv5 = nn.Conv2d(nf + 4 * gc, nf, 3, 1, 1); self.lrelu = nn.LeakyReLU(0.2, True)

        def forward(self, x):
            x1 = self.lrelu(self.conv1(x)); x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
            x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
            x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
            x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
            return x5 * 0.2 + x

    class RRDB(nn.Module):
        def __init__(self, nf, gc=32):
            super().__init__()
            self.rdb1 = ResidualDenseBlock(nf, gc); self.rdb2 = ResidualDenseBlock(nf, gc)
            self.rdb3 = ResidualDenseBlock(nf, gc)
        def forward(self, x):
            return self.rdb3(self.rdb2(self.rdb1(x))) * 0.2 + x

    class RRDBNet(nn.Module):
        def __init__(self, nf=64, nb=23, gc=32, scale=4):
            super().__init__()
            import torch
            self.scale = scale
            self.conv_first = nn.Conv2d(3, nf, 3, 1, 1)
            self.body = nn.Sequential(*[RRDB(nf, gc) for _ in range(nb)])
            self.conv_body = nn.Conv2d(nf, nf, 3, 1, 1)
            self.conv_up1 = nn.Conv2d(nf, nf, 3, 1, 1); self.conv_up2 = nn.Conv2d(nf, nf, 3, 1, 1)
            self.conv_hr = nn.Conv2d(nf, nf, 3, 1, 1); self.conv_last = nn.Conv2d(nf, 3, 3, 1, 1)
            self.l = nn.LeakyReLU(0.2, True)

        def forward(self, x):
            import torch.nn.functional as F
            feat = self.conv_first(x)
            feat = feat + self.conv_body(self.body(feat))
            feat = self.l(self.conv_up1(F.interpolate(feat, scale_factor=2, mode="nearest")))
            feat = self.l(self.conv_up2(F.interpolate(feat, scale_factor=2, mode="nearest")))
            return self.conv_last(self.l(self.conv_hr(feat)))

    keys = list(state.keys())
    if any(k.startswith("conv_first") for k in keys):
        m = RRDBNet()
    else:
        # conv layers carry a bias; PReLU layers only a weight. body = first conv
        # + (num_conv * conv) + last conv  => num_conv = (#conv) - 2
        n_conv_layers = len([k for k in keys if k.startswith("body.") and k.endswith(".bias")])
        num_conv = max(1, n_conv_layers - 2)
        m = SRVGGNetCompact(num_conv=num_conv)
    return m


def upscale_rgb(model, torch, rgb):
    """rgb: HxWx3 uint8 -> 4x uint8, tiled."""
    h, w, _ = rgb.shape
    out = np.zeros((h * 4, w * 4, 3), dtype=np.float32)
    pad = 16
    for y in range(0, h, TILE):
        for x in range(0, w, TILE):
            y0, x0 = max(0, y - pad), max(0, x - pad)
            y1, x1 = min(h, y + TILE + pad), min(w, x + TILE + pad)
            tile = rgb[y0:y1, x0:x1].astype(np.float32) / 255.0
            t = torch.from_numpy(tile.transpose(2, 0, 1)[None])
            with torch.no_grad():
                o = model(t).clamp(0, 1)[0].numpy().transpose(1, 2, 0)
            # remove pad (scaled x4)
            ty0, tx0 = (y - y0) * 4, (x - x0) * 4
            yy1, xx1 = min(TILE, h - y), min(TILE, w - x)
            out[y * 4:(y + yy1) * 4, x * 4:(x + xx1) * 4] = o[ty0:ty0 + yy1 * 4, tx0:tx0 + xx1 * 4]
    return (out * 255).round().astype(np.uint8)


def main(ids):
    import torch
    url, path = WEIGHTS[MODEL]
    fetch(url, path)
    # weights_only=True => only tensors are unpickled (no arbitrary code), so a
    # downloaded checkpoint can't execute anything on load.
    sd = torch.load(path, map_location="cpu", weights_only=True)
    sd = sd.get("params_ema", sd.get("params", sd))
    model = build_model(sd)
    model.load_state_dict(sd, strict=True)
    model.eval()

    centers = json.load(open(os.path.join(ROOT, "tools", "charm_centers.json")))
    sheets = {1:"sheet-1-blue-white",2:"sheet-2-dolce-vita",3:"sheet-3-mama",4:"sheet-4-folk-oval",
              5:"sheet-5-terracotta",6:"sheet-6-vintage-miniatures",7:"sheet-7-retro-childhood",
              8:"sheet-8-teacup-critters",9:"sheet-9-sweetheart"}
    out_dir = OUT_DIR; os.makedirs(out_dir, exist_ok=True)
    if not ids:
        ids = list(centers.keys())

    # group by sheet, cut native RGBA per id, SR, normalise
    import collections
    by_sheet = collections.defaultdict(list)
    for cid in ids:
        if cid in centers:
            by_sheet[centers[cid]["sheet"]].append(cid)

    done = 0
    for s, cids in sorted(by_sheet.items()):
        orig, alpha = ac.cut(os.path.join(ROOT, "charms", sheets[s] + ".jpeg"))
        lbl, comps = ac.components(alpha)
        for cid in cids:
            c = centers[cid]
            li = ac.label_at(lbl, comps, c["cx"], c["cy"])
            if li is None:
                print("  no blob for", cid); continue
            ys, xs = np.where(lbl == li)
            x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
            rgb = orig[y0:y1, x0:x1].copy()
            a = np.where(lbl[y0:y1, x0:x1] == li, alpha[y0:y1, x0:x1], 0).astype(np.uint8)
            big = upscale_rgb(model, torch, rgb)
            a_big = np.asarray(Image.fromarray(a).resize((big.shape[1], big.shape[0]), Image.BICUBIC))
            rgba = Image.fromarray(np.dstack([big, a_big]).astype(np.uint8), "RGBA")
            canvas = ac.normalize_crop(rgba, OUT_CANVAS, target_w=ac.NORM_TARGET_W, center_y=ac.NORM_CENTER_Y)
            canvas.save(os.path.join(out_dir, cid + ".webp"), "WEBP", quality=92, method=6)
            done += 1
            if done % 10 == 0:
                print("  ...", done, "done")
        print("sheet", s, "complete", flush=True)

    # bracelets (only on a full run, i.e. no explicit id list)
    if not sys.argv[1:]:
        bc = os.path.join(ROOT, "tools", "bracelet_centers.json")
        if os.path.exists(bc):
            bcent = json.load(open(bc))
            orig, alpha = ac.cut(os.path.join(ROOT, "charms", "bracelets-aceworks.jpeg"))
            lbl, comps = ac.components(alpha)
            for bid, c in bcent.items():
                li = ac.label_at(lbl, comps, c["cx"], c["cy"])
                if li is None:
                    continue
                ys, xs = np.where(lbl == li)
                x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
                rgb = orig[y0:y1, x0:x1].copy()
                a = np.where(lbl[y0:y1, x0:x1] == li, alpha[y0:y1, x0:x1], 0).astype(np.uint8)
                big = upscale_rgb(model, torch, rgb)
                a_big = np.asarray(Image.fromarray(a).resize((big.shape[1], big.shape[0]), Image.BICUBIC))
                rgba = Image.fromarray(np.dstack([big, a_big]).astype(np.uint8), "RGBA")
                canvas = ac.normalize_crop(rgba, OUT_CANVAS, target_w=0.9, center_y=0.5)
                canvas.save(os.path.join(out_dir, bid + ".webp"), "WEBP", quality=92, method=6)
                done += 1
            print("bracelets complete", flush=True)
    print("upscaled", done, "items to", OUT_CANVAS, "px (model:", MODEL + ")", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
