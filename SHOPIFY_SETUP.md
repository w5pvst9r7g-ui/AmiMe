# Ami & Me — Shopify Store Setup

This documents how the **Ami & Me** Shopify store (`550asa-iz.myshopify.com`) was
populated from this repo's catalogue, and the few manual finishing touches left
to the store owner.

## What was set up automatically

Built from `catalog.js` via `tools/gen_shopify_specs.js` →
`tools/gen_shopify_batches.js`, then pushed through the Shopify Admin API
(`productSet`, smart `collectionCreate`, `pageCreate`, `menuUpdate`).

- **183 products** — all 167 charms + 16 bracelets, each with:
  - the real hand-painted cut-out image (served from this public repo via
    `raw.githubusercontent.com/.../charms/crops/<id>.webp`, ingested onto
    Shopify's CDN),
  - price in **EUR** matching the website (charms €35–€55, bracelets €68–€98),
  - SKU = the catalogue `id`, the charm's `meaning` as description, and
    matcher tags for search/merchandising,
  - product type `Charm` / `Bracelet`, vendor `Ami & Me`,
  - **status: DRAFT** (hidden until reviewed).
- **12 smart collections** that auto-populate by tag/type:
  - the 9 source themes (Blue & White Riviera, La Dolce Vita, Mama & Family,
    Hand-Painted Folk, Terracotta & Treasures, Vintage Everyday Miniatures,
    Retro Childhood Whimsy, Teacup Cozy Critters, Sweetheart Gallery),
  - **Bracelets** (all type:Bracelet) and **All Charms** (all type:Charm).
- **Pages**: `Our Story` and `How It Works` (brand voice from the website).
- **Navigation** (main menu): Home · Bracelets · Charms (with the 9 themes
  nested) · Our Story · How It Works.

Re-run the generators any time the catalogue changes:

```sh
node tools/gen_shopify_specs.js     # -> /tmp/amime_specs.json
node tools/gen_shopify_batches.js   # -> /tmp/batch_*.json (productSet payloads)
```

## Finishing touches for the store owner (≈10 min)

These need the Shopify admin / theme editor — the API can't change the **live**
theme or take a store off trial.

1. **Go live.** Plan: **Trial** — you'll need to upgrade before you can start
   selling and unlock full features. Then flip products from Draft → Active
   (Products → select all → Set as active).

2. **Skin the Horizon theme to match the website** (Online Store → Themes →
   Customize). The site's identity:
   - **Colours** — Background / ivory `#FAF7F2`, surface `#FFFFFF`,
     text / ink `#1B1A18`, primary accent (gold) `#B0863F`, deep gold
     `#8C6A30`, secondary accent (muted rose) `#B07A72`, hairline `#ECE5D8`.
   - **Typography** — Headings: **Cormorant Garamond** (elegant serif).
     Body: **Jost** (clean geometric sans). Both are on Shopify Fonts.
   - **Announcement bar** — “Complimentary shipping & gift wrapping · Each
     piece hand-finished to order · Styled by AI, made by hand”.
   - **Homepage** — Hero headline **“Wear your story.”** with the lead
     “Tell us about a person, a place, a moment that matters — and our atelier
     composes a bracelet of meaningful hand-painted charms.” Add featured-
     collection sections for **Bracelets** and a few themed charm collections.

3. **(Optional) The story-matcher experience.** The website's “tell us your
   story” composer can be embedded later as a custom section / app block backed
   by a Shopify App Proxy in front of `server.js` (`/api/recommend`), keeping
   `ANTHROPIC_API_KEY` server-side. See the “Wiring this into Shopify” notes in
   `README.md`.
