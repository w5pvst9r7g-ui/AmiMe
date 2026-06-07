# AmiMe — Charm Story Matcher (POC)

Enter a sentence about a person, a memory or a moment, choose how many charms you
want, and AmiMe picks the hand-painted charms that, strung together, **tell that
story** — each with a short reason for why it belongs.

This is a proof of concept built from five product photo sheets. It identifies
**every charm** into a structured catalogue, then matches a customer's story
against it.

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
(catalogue, matcher, and all 95 charm images embedded). To test on an iPhone:
AirDrop / email / save it to iCloud Drive, then open it in **Files → tap → it
opens in Safari**. Or just double-click it on any computer. ~2.9 MB, fully
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

## What's in here

| File | Purpose |
|---|---|
| `catalog.js` | **The charm catalogue** — every charm from the 5 sheets, with name, meaning, source photo + position, and matching tags. Works in the browser and Node. |
| `matcher.js` | Zero-dependency, offline matcher. Tokenises the story, expands it with a synonym map, scores every charm, diversifies, returns the best `N` with reasons. |
| `index.html` | Self-contained front-end: story composer, charm-count slider, results, and a browsable catalogue showing the original product sheets. |
| `server.js` | Optional Node backend. Serves the page and a `POST /api/recommend` endpoint that asks **Claude (`claude-opus-4-8`)** to pick charms with structured-output JSON. |
| `amime-charm-matcher.html` | **The whole app as one self-contained file** (built artifact) — best for offline / iOS testing. |
| `charms/` | The five source product photos + `charms/crops/` (one cropped image per charm). |
| `tools/crop_charms.py` | Auto-crops each charm from the sheets and matches it to its catalogue id by position. |
| `tools/build_standalone.py` | Bundles everything into `amime-charm-matcher.html`. |
| `test/smoke.test.js` | Catalogue integrity, crop coverage, and matcher relevance checks (`npm run check`). |

## The catalogue

Charms are grouped by the photo (“collection”) they came from:

1. **Blue & White Riviera** — delft-style flowers, shell, olive branch, "joie de vivre"…
2. **La Dolce Vita** — little houses, Amalfi lemons, grapes, bows, ginger jar…
3. **Mama & Family** — "Mama", "Super Mama", nest, lavender, "Our Sunshine"…
4. **Hand-Painted Folk** — crab, snail, butterfly, dragonfly, strawberries, tulips…
5. **Terracotta & Treasures** — guitar, camera, cactus, mountains, bell, magic 8-ball…

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
