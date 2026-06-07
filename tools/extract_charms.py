#!/usr/bin/env python3
"""Extract charm blobs from a new sheet in reading order.

Filters connected-component matte blobs to real charms (size gap + optional
decoration exclusion), splits vertically-merged blobs, and orders them
top->bottom, left->right. Saves per-sheet:
  /tmp/charm_centers_<s>.json   list of {cx,cy} in reading order
  /tmp/detect_charms_<s>.png    numbered montage for visual authoring
"""
import sys, json
sys.path.insert(0, "tools")
import ai_crop as ac
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def reading_order(items, med_h):
    items = sorted(items, key=lambda c: c["cy"])
    rows, cur = [], []
    for c in items:
        if cur and c["cy"] - cur[-1]["cy"] > med_h * 0.55:
            rows.append(cur); cur = []
        cur.append(c)
    if cur:
        rows.append(cur)
    out = []
    for r in rows:
        out.extend(sorted(r, key=lambda c: c["cx"]))
    return out, [len(r) for r in rows]


def extract(s, path, min_sz, exclude=None):
    orig, alpha = ac.cut(path)
    lbl, comps = ac.components(alpha)
    items = [c for c in comps.values() if c["sz"] >= min_sz]
    # drop decoration regions: exclude = list of (x0,y0,x1,y1) normalized boxes
    if exclude:
        h, w = alpha.shape
        keep = []
        for c in items:
            cxn, cyn = c["cx"] / w, c["cy"] / h
            if any(bx0 <= cxn <= bx1 and by0 <= cyn <= by1 for bx0, by0, bx1, by1 in exclude):
                continue
            keep.append(c)
        items = keep
    med_h = np.median([c["box"][3] - c["box"][1] for c in items])
    # split tall merged blobs
    expanded = []
    for c in items:
        x0, y0, x1, y1 = c["box"]; hh = y1 - y0
        if hh > med_h * 1.55:
            mid = (y0 + y1) // 2
            expanded.append(dict(cx=c["cx"], cy=(y0 + mid) // 2, sz=c["sz"] // 2, box=(x0, y0, x1, mid)))
            expanded.append(dict(cx=c["cx"], cy=(mid + y1) // 2, sz=c["sz"] // 2, box=(x0, mid, x1, y1)))
        else:
            expanded.append(c)
    ordered, rowsizes = reading_order(expanded, med_h)
    json.dump([dict(cx=int(c["cx"]), cy=int(c["cy"])) for c in ordered],
              open(f"/tmp/charm_centers_{s}.json", "w"))
    # montage
    im = Image.fromarray(np.dstack([orig, alpha]).astype("uint8"), "RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255)); bg.alpha_composite(im); bg = bg.convert("RGB")
    d = ImageDraw.Draw(bg)
    try:
        fnt = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
    except Exception:
        fnt = None
    for i, c in enumerate(ordered, 1):
        x0, y0, x1, y1 = c["box"]
        d.rectangle([x0, y0, x1, y1], outline=(255, 0, 0), width=3)
        d.text((x0 + 4, y0 + 2), str(i), fill=(255, 0, 0), font=fnt)
    bg.save(f"/tmp/detect_charms_{s}.png")
    print(f"sheet {s}: {len(ordered)} charms, rows={rowsizes}")
    return rowsizes


if __name__ == "__main__":
    # min_sz chosen from the size-gap analysis; exclude decoration corners.
    extract(6, "charms/sheet-6-vintage-miniatures.jpeg", 11000,
            exclude=[(0.0, 0.0, 0.16, 0.16)])           # "take what you need" tag (top-left)
    extract(7, "charms/sheet-7-retro-childhood.jpeg", 10500)
    extract(8, "charms/sheet-8-teacup-critters.jpeg", 28000,
            exclude=[(0.82, 0.0, 1.0, 0.18)])           # "9 charms" badge (top-right)
    extract(9, "charms/sheet-9-sweetheart.jpeg", 15000)
