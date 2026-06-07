#!/usr/bin/env python3
"""Bundle the app into ONE self-contained HTML file for easy offline / iOS testing.

Inlines catalog.js + matcher.js, embeds every charm crop and product sheet as a
base64 data URI, and strips the backend probe (standalone = on-device matcher).
Output: amime-charm-matcher.html  (open it anywhere — no server, no internet).
"""
import base64, io, mimetypes, os, re
from PIL import Image

# The hosted site serves full-resolution crops; the single-file build embeds
# down-scaled copies so it stays a reasonable size for offline / iOS testing.
STANDALONE_CROP_MAX = 512

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "amime-charm-matcher.html")


def read(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return f.read()


def data_uri(path):
    full = os.path.join(ROOT, path)
    mime = mimetypes.guess_type(full)[0] or "application/octet-stream"
    with open(full, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return "data:%s;base64,%s" % (mime, b64)


html = read("index.html")
catalog_js = read("catalog.js")
matcher_js = read("matcher.js")

# 1) inline the two script files
html = html.replace('<script src="catalog.js"></script>', "<script>\n" + catalog_js + "\n</script>")
html = html.replace('<script src="matcher.js"></script>', "<script>\n" + matcher_js + "\n</script>")

# 2) build the embedded crop map (id -> data URI), down-scaled to keep the
#    single file lightweight (full-res crops are served by the hosted site).
def crop_data_uri(path):
    im = Image.open(path).convert("RGBA")
    if max(im.size) > STANDALONE_CROP_MAX:
        im.thumbnail((STANDALONE_CROP_MAX, STANDALONE_CROP_MAX), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=86, method=3)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return "data:image/webp;base64," + b64

crops = {}
crop_dir = os.path.join(ROOT, "charms", "crops")
for fn in sorted(os.listdir(crop_dir)):
    if fn.endswith(".webp"):
        crops[fn[:-5]] = crop_data_uri(os.path.join(crop_dir, fn))


def to_js_obj(d):
    parts = ['  %s: "%s"' % (_key(k), v) for k, v in d.items()]
    return "{\n" + ",\n".join(parts) + "\n}"


def _key(k):
    return '"%s"' % k


inject = "<script>window.__CROPS = " + to_js_obj(crops) + ";</script>\n"
html = html.replace("<script>\n" + catalog_js, inject + "<script>\n" + catalog_js, 1)

# 3) embed the full product sheets (used by the catalogue browser)
for sheet in sorted(os.listdir(os.path.join(ROOT, "charms"))):
    if sheet.startswith("sheet-") and sheet.endswith(".jpeg"):
        rel = "charms/" + sheet
        html = html.replace(rel, data_uri(rel))

with open(OUT, "w", encoding="utf-8") as f:
    f.write(html)

size = os.path.getsize(OUT)
print("wrote %s (%d charms embedded, %.1f MB)" % (OUT, len(crops), size / 1e6))
