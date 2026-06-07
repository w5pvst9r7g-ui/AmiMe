# AmiMe — Charm Story Matcher (POC)

Enter a sentence about a person, a memory or a moment, choose how many charms you
want, and AmiMe picks the hand-painted charms that, strung together, **tell that
story** — each with a short reason for why it belongs.

This is a proof of concept built from nine product photo sheets. It identifies
**every charm** (167 of them) into a structured catalogue, then matches a
customer's story against it — and recommends a **bracelet** to hang them on.

Each result also lets you:
- **Swap** any charm for the next-best alternative with one tap,
- open a **"more charms that fit"** menu and drop one in for your weakest match,
- **cycle the recommended bracelet** through other styles that suit the story.

Charm cut-outs are produced with an AI matte (`rembg`) so every charm is a
clean, transparent, website-ready image — no photographic background.

```
┌──────────────┐     ┌─────────────────────────────┐     ┌────────────────────┐
│  Your story  │ ──▶ │  Matcher                    │ ──▶ │  Recommended charms │
│  + how many  │     │  · Claude (semantic)  OR    │     │  + the reason for   │
│              │     │  · on-device keyword engine │     │  each, as a bracelet│
└──────────────┘     └─────────────────────────────┘     └────────────────────┘
```

## Try it

Easiest first.

**A) One file, works on your phone (no server, no internet)** ← simplest for iOS
`amime-charm-matcher.html` is the **entire app in a single self-contained file**
(catalogue, matcher, and all charm + bracelet images embedded). To test on an
iPhone: AirDrop / email / save it to iCloud Drive, then open it in **Files → tap
→ it opens in Safari**. Or just double-click it on any computer. ~10 MB, fully
offline. Rebuild it after changes with `python3 tools/build_standalone.py`.

**B) Shareable URL (GitHub Pages)**
This branch includes a Pages workflow (`.github/workflows/pages.yml`). If Pages
is available for the repo, every push publishes the site to a public URL you can
open in iOS Safari. Check **Actions → Deploy to GitHub Pages** for the link.

**C) Local static server**

```sh
python3 -m http.server 8000      # then open http://localhost:8000
```

(Just opening `index.html` directly also works, though some browsers block the
local `.webp`/`.js` files over `file://` — use option A for offline.)

**D) With Claude (true semantic understanding)**

```sh
npm install
export ANTHROPIC_API_KEY=sk-ant-...
npm start                        # http://localhost:3000
```

The front-end auto-detects the backend: if `server.js` is running with a key,
it uses Claude; otherwise it silently falls back to the on-device matcher. The
little dot under the composer tells you which engine answered.

**E) See it on a wrist (Gemini image mock-up)**

```sh
export GEMINI_API_KEY=...         # Google AI Studio key
# optional: export GEMINI_IMAGE_MODEL=gemini-2.5-flash-image-preview
npm start
```

With `GEMINI_API_KEY` set in the environment, the recommended-bracelet card
gains a **"See it on a wrist ✦"** button. It sends the chosen bracelet cut-out
plus your selected charm cut-outs to Gemini's image model (`POST /api/mockup`)
and renders a lifestyle photo of the piece worn on a hand. The key stays
server-side, just like `ANTHROPIC_API_KEY`; if it isn't set, the button simply
doesn't appear. Each change to the charms/bracelet clears the old mock-up so
you can regenerate it for the new combination.

## What's in here

| File | Purpose |
|---|---|
| `catalog.js` | **The catalogue** — 167 charms across 9 sheets + 16 bracelets, each with name, meaning, source + position, and matching tags/vibe. Works in the browser and Node. |
| `matcher.js` | Zero-dependency, offline matcher. Scores every charm, diversifies, returns the best `N` with reasons, **plus** a swap pool, alternatives, and a bracelet recommendation. |
| `index.html` | Self-contained front-end: story composer, results with per-charm **swap**, an **alternatives** menu, a **recommended bracelet** (cyclable), and a browsable catalogue. |
| `server.js` | Optional Node backend. `POST /api/recommend` asks **Claude (`claude-opus-4-8`)** to pick charms with structured-output JSON; `POST /api/mockup` asks **Gemini** to render the bracelet + charms worn on a wrist (needs `GEMINI_API_KEY`). |
| `amime-charm-matcher.html` | **The whole app as one self-contained file** (built artifact) — best for offline / iOS testing. |
| `charms/` | The nine source product photos + bracelet sheet + `charms/crops/` (one transparent cut-out per charm and bracelet). |
| `tools/ai_crop.py` | **AI cut-out pipeline** — `rembg` matte → connected components → clean, centred, transparent WebP per charm (Voronoi-splits touching charms, ignores decorations). |
| `tools/build_catalog.py` | Generates the new sheet/charm/bracelet entries into `catalog.js`. |
| `tools/build_standalone.py` | Bundles everything into `amime-charm-matcher.html`. |
| `test/smoke.test.js` | Catalogue + bracelet integrity, crop coverage, matcher relevance, and recommendation-extras checks (`npm run check`). |

## The catalogue

Charms are grouped by the photo (“collection”) they came from:

1. **Blue & White Riviera** — delft-style flowers, shell, olive branch, "joie de vivre"…
2. **La Dolce Vita** — little houses, Amalfi lemons, grapes, bows, ginger jar…
3. **Mama & Family** — "Mama", "Super Mama", nest, lavender, "Our Sunshine"…
4. **Hand-Painted Folk** — crab, snail, butterfly, dragonfly, strawberries, tulips…
5. **Terracotta & Treasures** — guitar, camera, cactus, mountains, bell, magic 8-ball…
6. **Vintage Everyday Miniatures** — apple, sardine tins, tulips, mushroom, little houses…
7. **Retro Childhood Whimsy** — handheld game, MASH notebook, gingerbread man, evil-eye heart…
8. **Teacup Cozy Critters** — bear, fox, panda, hedgehog & friends nestled in teacups…
9. **Sweetheart Gallery** — hearts, love monster, penguin, ladybug, sweet-treat charms…

Plus **16 bracelets** (dainty chains, cuban links, pearls, charm stations…) the
matcher pairs to the story and charm count.

Each entry carries an `id` (use it as your Shopify product handle / SKU key), a
plain-language `meaning`, and broad `tags` that mix the literal subject with the
feelings and occasions a customer might describe — this is what lets *"a summer
by the sea where we fell in love"* surface the **shell**, the **lemon** and the
**heart**.

## How matching works

- **On-device (`matcher.js`)** — normalises and tokenises the story, expands it
  through a concept/synonym map (`ocean → sea, beach, shell, wave, coral…`),
  scores each charm by tag overlap (phrases weighted higher than single words),
  then lightly diversifies so you don't get five near-identical flowers. Fully
  transparent and instant; great as a fallback and for offline demos.
- **Claude (`server.js`)** — sends the catalogue + the story to `claude-opus-4-8`
  and asks for exactly `N` charm `id`s plus a one-line reason each and an overall
  bracelet summary, returned as validated JSON (structured outputs). Claude reads
  mood, subtext and metaphor a keyword matcher can't.

## Wiring this into Shopify (next steps)

This POC is intentionally framework-free so it maps cleanly onto a store:

1. **Catalogue → products.** Match each `catalog.js` `id` to a Shopify product
   (the `id`s are designed to be product handles). Replace the emoji/photo-sheet
   stand-ins with each charm's real product image.
2. **Front-end → theme/app block.** Drop the composer UI into a section/app
   block; render results as add-to-cart-able product cards (they already carry
   the charm `id`).
3. **Backend → app proxy.** Move `/api/recommend` behind a Shopify
   [App Proxy](https://shopify.dev/docs/apps/online-store/app-proxies) so the
   `ANTHROPIC_API_KEY` stays server-side. The handler in `server.js` is already
   the right shape.
4. **Build the bracelet.** Let the customer drop recommended charms onto a base
   chain product and add the set to cart as a bundle.

## Notes & limitations (it's a POC)

- Charm images are auto-cropped from the product sheets (`tools/crop_charms.py`).
  They're good enough to test with; for production, swap in clean studio cutouts.
- Charm identification is from photos; double-check names/meanings against your
  actual product copy.
- The on-device synonym map is hand-tuned and English-only; Claude handles the
  long tail far better.
