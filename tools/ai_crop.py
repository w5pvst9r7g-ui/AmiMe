#!/usr/bin/env python3
"""AI-assisted charm cutter.

Pipeline per sheet:
  1. Run rembg (isnet-general-use) on the full sheet -> clean RGBA matte that
     drops the photographic background entirely.
  2. Label connected components of the alpha matte; each charm is one blob.
  3. Assign every catalogue id to the blob it sits on (by known centre point).
     - Decorations / un-catalogued blobs get no id and are ignored.
     - If two ids land on one blob (charms that touch), the blob's pixels are
       split between them by nearest-centre (Voronoi).
  4. Emit a square, centred, transparent WebP per id at a consistent size.

This produces clean, website-ready cut-outs with no neighbour intrusion and no
sandy background.

Usage:
  ai_crop.py centers <centers.json> <out_dir>      # known id->centre mapping
  ai_crop.py detect  <sheet_path> <out_prefix>     # auto reading-order detect
"""
import json, os, sys, math
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage
from rembg import remove, new_session

SHEETS = {
    1: "charms/sheet-1-blue-white.jpeg",
    2: "charms/sheet-2-dolce-vita.jpeg",
    3: "charms/sheet-3-mama.jpeg",
    4: "charms/sheet-4-folk-oval.jpeg",
    5: "charms/sheet-5-terracotta.jpeg",
}
CANVAS = 512          # output square size (higher-res, crisper on the site)
FILL = 0.86           # legacy longest-side fraction (unused once normalised)
MIN_AREA = 0.0012     # ignore blobs smaller than this fraction of the sheet
ALPHA_FLOOR = 30      # alpha below this is treated as background
NORM_TARGET_W = 0.66  # body width as a fraction of the canvas (alignment)
NORM_CENTER_Y = 0.52  # where the body's centre of mass sits vertically
NORM_SHARPEN = True   # light unsharp mask to crispen the upscaled cut-out

_session = None
def session():
    global _session
    if _session is None:
        _session = new_session("isnet-general-use")
    return _session


def cut(path):
    """Return (orig_rgb ndarray, alpha ndarray uint8) for a sheet."""
    img = Image.open(path).convert("RGB")
    out = remove(img, session=session())
    arr = np.asarray(out)
    return np.asarray(img), arr[:, :, 3].copy()


def components(alpha):
    mask = alpha > ALPHA_FLOOR
    lbl, n = ndimage.label(mask)
    area = mask.shape[0] * mask.shape[1]
    comps = {}
    for i, sl in enumerate(ndimage.find_objects(lbl), start=1):
        if sl is None:
            continue
        sz = int((lbl[sl] == i).sum())
        if sz <= area * MIN_AREA:
            continue
        y, x = sl
        comps[i] = dict(box=(x.start, y.start, x.stop, y.stop),
                        cx=(x.start + x.stop) / 2, cy=(y.start + y.stop) / 2, sz=sz)
    return lbl, comps


def label_at(lbl, comps, cx, cy):
    """Label id under (cx,cy); if on background, nearest blob centre."""
    h, w = lbl.shape
    xi, yi = int(round(cx)), int(round(cy))
    if 0 <= yi < h and 0 <= xi < w and lbl[yi, xi] in comps:
        return lbl[yi, xi]
    # search a small window
    best, bestd = None, 1e18
    for li, c in comps.items():
        d = (c["cx"] - cx) ** 2 + (c["cy"] - cy) ** 2
        if d < bestd:
            best, bestd = li, d
    return best


def square_from(orig, alpha_mask, box):
    """Crop to box, place charm centred on a transparent CANVAS square."""
    x0, y0, x1, y1 = box
    rgb = orig[y0:y1, x0:x1]
    a = alpha_mask[y0:y1, x0:x1]
    # tighten to actual alpha bounds
    ys, xs = np.where(a > ALPHA_FLOOR)
    if len(xs) == 0:
        return None
    bx0, bx1 = xs.min(), xs.max() + 1
    by0, by1 = ys.min(), ys.max() + 1
    rgb = rgb[by0:by1, bx0:bx1]
    a = a[by0:by1, bx0:bx1]
    rgba = np.dstack([rgb, a]).astype(np.uint8)
    im = Image.fromarray(rgba, "RGBA")
    # soften the matte edge a touch to remove any fringe
    alpha_ch = im.split()[3].filter(ImageFilter.GaussianBlur(0.6))
    im.putalpha(alpha_ch)
    # body-aware normalisation: consistent size + centre-of-mass alignment
    return normalize_crop(im, CANVAS, target_w=NORM_TARGET_W, center_y=NORM_CENTER_Y)


def normalize_crop(rgba, N=None, target_w=0.66, center_y=0.52, max_w=0.96, max_h=0.92):
    """Re-centre/scale a transparent charm so every charm reads as the same
    visual size and its body sits on the same line.

    - scale so the body *width* is a consistent fraction (round pendants then
      match), capped so nothing overflows — tall pieces (guitar) cap on height;
    - align by alpha centre-of-mass, not bbox, so a long jump-ring/bail pushes
      *up* off the body instead of dragging the body downward.
    """
    N = N or CANVAS
    arr = np.asarray(rgba)
    a = arr[:, :, 3]
    ys, xs = np.where(a > ALPHA_FLOOR)
    if len(xs) == 0:
        return rgba.resize((N, N))
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    content = rgba.crop((x0, y0, x1, y1))
    cw, ch = content.size
    scale = (N * target_w) / cw
    if ch * scale > N * max_h:
        scale = (N * max_h) / ch
    if cw * scale > N * max_w:
        scale = (N * max_w) / cw
    nw, nh = max(1, round(cw * scale)), max(1, round(ch * scale))
    content = content.resize((nw, nh), Image.LANCZOS)
    if NORM_SHARPEN:
        r, g, b, al = content.split()
        rgb = Image.merge("RGB", (r, g, b)).filter(
            ImageFilter.UnsharpMask(radius=1.4, percent=85, threshold=2))
        content = Image.merge("RGBA", (*rgb.split(), al))
    # centre of mass within the resized content
    ca = np.asarray(content)[:, :, 3]
    cys, cxs = np.where(ca > ALPHA_FLOOR)
    com_x, com_y = cxs.mean(), cys.mean()
    ox = int(round(N / 2 - com_x))
    oy = int(round(N * center_y - com_y))
    ox = max(min(ox, N - nw), 0) if nw <= N else (N - nw) // 2
    oy = max(min(oy, N - nh), 0) if nh <= N else (N - nh) // 2
    canvas = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    canvas.alpha_composite(content, (ox, oy))
    return canvas


def save(canvas, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    canvas.save(out_path, "WEBP", quality=90, method=6)


def crop_ids(sheet_path, id_centers, out_dir):
    """id_centers: {id: (cx, cy)} on one sheet. Clean cut-outs into out_dir."""
    orig, alpha = cut(sheet_path)
    lbl, comps = components(alpha)
    id_label = {cid: label_at(lbl, comps, cx, cy) for cid, (cx, cy) in id_centers.items()}
    per_label = {}
    for cid, li in id_label.items():
        per_label.setdefault(li, []).append(cid)
    n = 0
    for li, cids in per_label.items():
        if li is None:
            continue
        comp_mask = (lbl == li)
        if len(cids) == 1:
            amask = np.where(comp_mask, alpha, 0)
            canvas = square_from(orig, amask, comps[li]["box"])
            if canvas:
                save(canvas, os.path.join(out_dir, cids[0] + ".webp")); n += 1
        else:
            ys, xs = np.where(comp_mask)
            cs = np.array([id_centers[cid] for cid in cids])
            owner = (((xs[:, None] - cs[None, :, 0]) ** 2 +
                      (ys[:, None] - cs[None, :, 1]) ** 2)).argmin(axis=1)
            for k, cid in enumerate(cids):
                sub = np.zeros_like(alpha); sel = owner == k
                sub[ys[sel], xs[sel]] = alpha[ys[sel], xs[sel]]
                yy, xx = np.where(sub > ALPHA_FLOOR)
                if len(xx) == 0:
                    continue
                box = (xx.min(), yy.min(), xx.max() + 1, yy.max() + 1)
                canvas = square_from(orig, sub, box)
                if canvas:
                    save(canvas, os.path.join(out_dir, cid + ".webp")); n += 1
    return n


def run_centers(centers_path, out_dir):
    centers = json.load(open(centers_path))
    by_sheet = {}
    for cid, c in centers.items():
        by_sheet.setdefault(c["sheet"], {})[cid] = (c["cx"], c["cy"])
    total = 0
    for s in sorted(by_sheet):
        orig, alpha = cut(SHEETS[s])
        lbl, comps = components(alpha)
        # map id -> label
        id_label = {cid: label_at(lbl, comps, cx, cy)
                    for cid, (cx, cy) in by_sheet[s].items()}
        # group ids per label (for Voronoi splits)
        per_label = {}
        for cid, li in id_label.items():
            per_label.setdefault(li, []).append(cid)
        for li, cids in per_label.items():
            if li is None:
                continue
            comp_mask = (lbl == li)
            if len(cids) == 1:
                amask = np.where(comp_mask, alpha, 0)
                box = comps[li]["box"]
                canvas = square_from(orig, amask, box)
                if canvas:
                    save(canvas, os.path.join(out_dir, cids[0] + ".webp")); total += 1
            else:
                # Voronoi: assign each blob pixel to nearest id centre
                ys, xs = np.where(comp_mask)
                cs = np.array([by_sheet[s][cid] for cid in cids])  # (k,2) x,y
                d = ((xs[:, None] - cs[None, :, 0]) ** 2 +
                     (ys[:, None] - cs[None, :, 1]) ** 2)
                owner = d.argmin(axis=1)
                for k, cid in enumerate(cids):
                    sub = np.zeros_like(alpha)
                    sel = owner == k
                    sub[ys[sel], xs[sel]] = alpha[ys[sel], xs[sel]]
                    yy, xx = np.where(sub > ALPHA_FLOOR)
                    if len(xx) == 0:
                        continue
                    box = (xx.min(), yy.min(), xx.max() + 1, yy.max() + 1)
                    canvas = square_from(orig, sub, box)
                    if canvas:
                        save(canvas, os.path.join(out_dir, cid + ".webp")); total += 1
        print(f"sheet {s}: {len(by_sheet[s])} ids placed")
    print(f"saved {total} crops -> {out_dir}")


def cluster_rows(comps, nrows):
    ys = np.array([c["cy"] for c in comps])
    cs = np.linspace(ys.min(), ys.max(), nrows)
    for _ in range(80):
        groups = [[] for _ in range(nrows)]
        for c in comps:
            k = int(np.argmin([abs(c["cy"] - z) for z in cs]))
            groups[k].append(c)
        newcs = [np.mean([c["cy"] for c in g]) if g else cs[i] for i, g in enumerate(groups)]
        if np.allclose(newcs, cs):
            break
        cs = newcs
    return [sorted(g, key=lambda c: c["cx"]) for g in groups]


def run_detect(sheet_path, out_prefix, nrows=None):
    """Auto-detect charms in reading order; save as <out_prefix><n>.webp.
    Returns list of (index, box) so a caller can map names."""
    orig, alpha = cut(sheet_path)
    lbl, comps = components(alpha)
    items = list(comps.values())
    items.sort(key=lambda c: (c["cy"], c["cx"]))
    print(f"{sheet_path}: {len(items)} components")
    return orig, alpha, lbl, comps


if __name__ == "__main__":
    if sys.argv[1] == "centers":
        run_centers(sys.argv[2], sys.argv[3])
