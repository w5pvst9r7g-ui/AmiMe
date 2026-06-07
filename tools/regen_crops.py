#!/usr/bin/env python3
"""Regenerate every charm + bracelet cut-out from the source sheets at higher
resolution with body-aware alignment (see ai_crop.normalize_crop)."""
import sys, json, collections
sys.path.insert(0, "tools")
import ai_crop as ac

SHEET_FILES = {
    1:"charms/sheet-1-blue-white.jpeg",2:"charms/sheet-2-dolce-vita.jpeg",
    3:"charms/sheet-3-mama.jpeg",4:"charms/sheet-4-folk-oval.jpeg",
    5:"charms/sheet-5-terracotta.jpeg",6:"charms/sheet-6-vintage-miniatures.jpeg",
    7:"charms/sheet-7-retro-childhood.jpeg",8:"charms/sheet-8-teacup-critters.jpeg",
    9:"charms/sheet-9-sweetheart.jpeg",
}
OUT = "charms/crops"
centers = json.load(open("tools/charm_centers.json"))
by_sheet = collections.defaultdict(dict)
for cid, v in centers.items():
    by_sheet[v["sheet"]][cid] = (v["cx"], v["cy"])

total = 0
for s in sorted(by_sheet):
    n = ac.crop_ids(SHEET_FILES[s], by_sheet[s], OUT)
    total += n
    print(f"sheet {s}: {n} charms")

# bracelets — wider fill, no bail, centred
ac.NORM_TARGET_W = 0.9
ac.NORM_CENTER_Y = 0.5
bcent = json.load(open("tools/bracelet_centers.json"))
bn = ac.crop_ids("charms/bracelets-aceworks.jpeg",
                 {k: (v["cx"], v["cy"]) for k, v in bcent.items()}, OUT)
print(f"bracelets: {bn}")
print(f"TOTAL: {total + bn} crops at {ac.CANVAS}px")
