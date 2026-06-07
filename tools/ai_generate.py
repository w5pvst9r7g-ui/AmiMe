#!/usr/bin/env python3
"""Optional AI image generation — true-to-original upscales + a worn mock-up.

This needs a generative-image API. It is NOT run automatically (the build
sandbox has no image-model access). Set ONE of these env vars and run locally:

    export GEMINI_API_KEY=...        # uses google-genai (Gemini 2.x image)
    # or
    export OPENAI_API_KEY=...        # uses OpenAI gpt-image-1

Usage:
    python3 tools/ai_generate.py upscale [id ...]   # hi-res, true-to-original
    python3 tools/ai_generate.py mockup  <bracelet-id> [charm-id ...]

`upscale` sends each existing cut-out back to the model asking for a faithful,
higher-resolution rendering (same charm, same colours — just sharper/bigger).
`mockup` composes the chosen bracelet + charms and asks for a lifestyle photo
of someone wearing it. Outputs go to charms/hires/ and mockups/.
"""
import os, sys, base64, io, json, glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CROPS = os.path.join(ROOT, "charms", "crops")

UPSCALE_PROMPT = (
    "Re-render THIS exact hand-painted enamel charm as a clean, high-resolution "
    "product image on a transparent/white background. Keep it perfectly faithful: "
    "identical shape, colours, painted details and the gold bail — do not redesign "
    "or add anything. Just a crisper, higher-resolution, studio-quality version, "
    "centred, soft shadow, e-commerce ready."
)

MOCKUP_PROMPT = (
    "A warm, natural lifestyle product photo: a woman's wrist wearing a delicate "
    "gold charm bracelet hung with these hand-painted enamel charms. Soft daylight, "
    "shallow depth of field, neutral cafe/outdoor background, tasteful and premium. "
    "The charms should match the references in shape and colour. Square crop."
)


def load_png(path):
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    buf = io.BytesIO(); bg.convert("RGB").save(buf, "PNG")
    return buf.getvalue()


def gemini_image(prompt, images, out_path):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    parts = [types.Part.from_text(prompt)]
    for img in images:
        parts.append(types.Part.from_bytes(data=img, mime_type="image/png"))
    resp = client.models.generate_content(
        model="gemini-2.0-flash-preview-image-generation",
        contents=parts,
        config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
    )
    for part in resp.candidates[0].content.parts:
        if getattr(part, "inline_data", None):
            open(out_path, "wb").write(part.inline_data.data)
            return out_path
    raise RuntimeError("no image returned")


def openai_image(prompt, images, out_path):
    from openai import OpenAI
    client = OpenAI()
    # gpt-image-1 supports image edits with reference images
    files = [("image[]", ("ref%d.png" % i, im, "image/png")) for i, im in enumerate(images)]
    res = client.images.edit(model="gpt-image-1", prompt=prompt,
                             image=[io.BytesIO(im) for im in images], size="1024x1024")
    open(out_path, "wb").write(base64.b64decode(res.data[0].b64_json))
    return out_path


def generate(prompt, images, out_path):
    if os.environ.get("GEMINI_API_KEY"):
        return gemini_image(prompt, images, out_path)
    if os.environ.get("OPENAI_API_KEY"):
        return openai_image(prompt, images, out_path)
    sys.exit("Set GEMINI_API_KEY or OPENAI_API_KEY first (see file header).")


def cmd_upscale(ids):
    out_dir = os.path.join(ROOT, "charms", "hires"); os.makedirs(out_dir, exist_ok=True)
    if not ids:
        ids = [os.path.basename(p)[:-5] for p in sorted(glob.glob(os.path.join(CROPS, "*.webp")))
               if not os.path.basename(p).startswith("bracelet-")]
    for cid in ids:
        src = os.path.join(CROPS, cid + ".webp")
        if not os.path.exists(src):
            print("skip (no crop):", cid); continue
        out = os.path.join(out_dir, cid + ".png")
        print("upscaling", cid, "->", out)
        generate(UPSCALE_PROMPT, [load_png(src)], out)


def cmd_mockup(args):
    if not args:
        sys.exit("usage: ai_generate.py mockup <bracelet-id> [charm-id ...]")
    bracelet, charms = args[0], args[1:]
    imgs = [load_png(os.path.join(CROPS, bracelet + ".webp"))]
    for c in charms:
        imgs.append(load_png(os.path.join(CROPS, c + ".webp")))
    out_dir = os.path.join(ROOT, "mockups"); os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, "worn-" + bracelet + ".png")
    print("generating worn mock-up ->", out)
    generate(MOCKUP_PROMPT, imgs, out)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == "upscale":
        cmd_upscale(sys.argv[2:])
    elif sys.argv[1] == "mockup":
        cmd_mockup(sys.argv[2:])
    else:
        sys.exit(__doc__)
