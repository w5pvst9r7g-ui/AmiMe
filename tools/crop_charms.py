#!/usr/bin/env python3
"""Crop individual charms from the product sheets into charms/crops/<id>.webp.

Approach:
  1. Background-subtract to get a foreground mask.
  2. Find row "cores" by scanning a projection threshold until the natural
     number of rows appears, then expand each core outward to the background.
  3. Within each row, do the same across columns to isolate each charm.
Reading order (top->bottom, left->right) maps 1:1 onto the catalogue `pos`
field, so every crop is matched to the right charm id.
"""
import json, collections, os
import numpy as np
from PIL import Image

SHEETS = {
    1: "charms/sheet-1-blue-white.jpeg",
    2: "charms/sheet-2-dolce-vita.jpeg",
    3: "charms/sheet-3-mama.jpeg",
    4: "charms/sheet-4-folk-oval.jpeg",
    5: "charms/sheet-5-terracotta.jpeg",
}
OUT_DIR = "charms/crops"
MAX_DIM = 360

catalog = json.load(open("/tmp/catalog.json"))
layout = collections.defaultdict(lambda: collections.defaultdict(dict))  # sheet->row->col->id
for x in catalog:
    r, c = map(int, x["pos"].split(","))
    layout[x["sheet"]][r][c] = x["id"]


def foreground_mask(arr):
    h, w, _ = arr.shape
    rgb = arr.astype(np.int32)
    m = max(6, h // 60)
    border = np.concatenate([
        rgb[:m].reshape(-1, 3), rgb[-m:].reshape(-1, 3),
        rgb[:, :m].reshape(-1, 3), rgb[:, -m:].reshape(-1, 3),
    ])
    bg = np.median(border, axis=0)
    dist = np.sqrt(((rgb - bg) ** 2).sum(axis=2))
    sat = rgb.max(axis=2) - rgb.min(axis=2)
    dark = rgb.sum(axis=2) < 230 * 3 * 0.62
    return (dist > 46) | (sat > 42) | dark


def raw_segments(profile, thresh, min_len, min_gap):
    on = profile > thresh
    segs, i, n = [], 0, len(on)
    while i < n:
        if on[i]:
            j = i
            while j < n and on[j]:
                j += 1
            segs.append([i, j]); i = j
        else:
            i += 1
    merged = []
    for s in segs:
        if merged and s[0] - merged[-1][1] < min_gap:
            merged[-1][1] = s[1]
        else:
            merged.append(s)
    return [tuple(s) for s in merged if s[1] - s[0] >= min_len]


def find_cores(profile, want, span, min_gap_frac=0.006):
    """Scan threshold (high->low) until exactly `want` segments appear."""
    best = None
    for t in range(40, 2, -1):
        th = t / 100.0
        segs = raw_segments(profile, th, span * 0.03, span * min_gap_frac)
        if len(segs) == want:
            return sorted(segs)
        if best is None or abs(len(segs) - want) < abs(len(best) - want):
            best = sorted(segs)
    # couldn't hit it exactly — force from the closest attempt
    return best


def walk_out(profile, start, direction, floor):
    i = start
    n = len(profile)
    while 0 <= i + direction < n and profile[i + direction] > floor:
        i += direction
    return i


def expand(cores, profile, length, floor):
    """Turn dense cores into full bands: midpoints between, background at edges."""
    bands = []
    for k, (s, e) in enumerate(cores):
        lo = walk_out(profile, s, -1, floor) if k == 0 else (cores[k - 1][1] + s) // 2
        hi = walk_out(profile, e - 1, +1, floor) if k == len(cores) - 1 else (e + cores[k + 1][0]) // 2
        bands.append((max(0, lo), min(length, hi)))
    return bands


def split_to_count(row_mask, segs, want):
    segs = [list(s) for s in segs]
    guard = 0
    while len(segs) < want and guard < 60:
        guard += 1
        wi = max(range(len(segs)), key=lambda k: segs[k][1] - segs[k][0])
        a, b = segs[wi]
        sub = row_mask[:, a:b].sum(axis=0)
        lo, hi = a + int((b - a) * 0.25), a + int((b - a) * 0.75)
        if hi <= lo:
            break
        cut = lo + int(np.argmin(sub[lo - a:hi - a]))
        segs[wi:wi + 1] = [[a, cut], [cut, b]]
    while len(segs) > want:
        wi = min(range(len(segs)), key=lambda k: segs[k][1] - segs[k][0])
        if wi == 0:
            segs[0:2] = [[segs[0][0], segs[1][1]]]
        elif wi == len(segs) - 1:
            segs[-2:] = [[segs[-2][0], segs[-1][1]]]
        else:
            l = segs[wi - 1][1] - segs[wi - 1][0]; r = segs[wi + 1][1] - segs[wi + 1][0]
            if l <= r:
                segs[wi - 1:wi + 1] = [[segs[wi - 1][0], segs[wi][1]]]
            else:
                segs[wi:wi + 2] = [[segs[wi][0], segs[wi + 1][1]]]
    return [tuple(s) for s in sorted(segs)]


def process(sheet, save=True):
    img = Image.open(SHEETS[sheet]).convert("RGB")
    arr = np.asarray(img)
    h, w, _ = arr.shape
    mask = foreground_mask(arr)
    rows = layout[sheet]
    nrows = len(rows)

    rprof = mask.sum(axis=1).astype(float) / w
    rcores = find_cores(rprof, nrows, h)
    rbands = expand(rcores, rprof, h, floor=0.02)

    results = []
    for ri, (y0, y1) in enumerate(rbands, start=1):
        want = len(rows.get(ri, {}))
        rm = mask[y0:y1]
        cprof = rm.sum(axis=0).astype(float) / (y1 - y0)
        ccores = find_cores(cprof, want, w)
        if ccores is None or len(ccores) != want:
            ccores = split_to_count(rm, ccores or [(0, w)], want)
        cbands = expand(sorted(ccores), cprof, w, floor=0.02)
        for ci, (x0, x1) in enumerate(cbands, start=1):
            cid = rows[ri].get(ci)
            results.append((cid, ri, ci, x0, y0, x1, y1))
            if save and cid:
                save_crop(img, cid, x0, y0, x1, y1)
    return results


def save_crop(img, cid, x0, y0, x1, y1):
    pad_x = int((x1 - x0) * 0.04) + 4
    pad_y = int((y1 - y0) * 0.04) + 4
    box = (max(0, x0 - pad_x), max(0, y0 - pad_y),
           min(img.width, x1 + pad_x), min(img.height, y1 + pad_y))
    crop = img.crop(box)
    crop.thumbnail((MAX_DIM, MAX_DIM), Image.LANCZOS)
    os.makedirs(OUT_DIR, exist_ok=True)
    crop.save(os.path.join(OUT_DIR, cid + ".webp"), "WEBP", quality=82, method=6)


if __name__ == "__main__":
    total = 0
    for s in sorted(SHEETS):
        res = process(s, save=True)
        per_row = collections.Counter(r for _, r, *_ in res)
        print(f"sheet {s}: {len(res)} charms, rows " +
              ", ".join(f"r{r}={per_row[r]}" for r in sorted(per_row)))
        total += sum(1 for r in res if r[0])
    print(f"saved {total} crops to {OUT_DIR}/")
