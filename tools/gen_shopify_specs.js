/*
 * Generates Shopify product specs from the AmiMe catalogue.
 * Mirrors the pricing + image logic the website uses, and emits a single
 * JSON array that drives the Shopify store build. Read-only against the repo.
 */
const fs = require("fs");
const path = require("path");
const { SHEETS, CHARMS, BRACELETS } = require("../catalog.js");

const REPO = "w5pvst9r7g-ui/AmiMe";
const BRANCH = "claude/charm-story-matcher-poc-BpNJF";
const RAW = `https://raw.githubusercontent.com/${REPO}/${BRANCH}/charms/crops`;
const cropsDir = path.join(__dirname, "..", "charms", "crops");

// --- pricing, identical to index.html -------------------------------------
function hashStr(s) { let h = 0; s = String(s || ""); for (let i = 0; i < s.length; i++) { h = (h * 31 + s.charCodeAt(i)) >>> 0; } return h; }
const priceOfCharm = (c) => 35 + (hashStr(c.id) % 5) * 5;            // €35–€55
const BRACELET_PRICE = { classic:78, station:88, elegant:98, minimal:68, beaded:82,
  dainty:72, modern:90, adjustable:74, bold:96, sleek:92, paperclip:84 };
const priceOfBracelet = (b) => BRACELET_PRICE[b.style] || 79;        // €68–€98

const slug = (s) => s.toLowerCase().replace(/&/g, "and").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

const missing = [];
const haveCrop = (id) => { const ok = fs.existsSync(path.join(cropsDir, id + ".webp")); if (!ok) missing.push(id); return ok; };

const specs = [];

// --- charms ---------------------------------------------------------------
for (const c of CHARMS) {
  haveCrop(c.id);
  const sheet = SHEETS[c.sheet];
  const themeTag = "theme:" + slug(sheet.name);
  const desc =
    `<p><em>${esc(cap(c.meaning))}.</em></p>` +
    `<p>A hand-painted charm from the <strong>${esc(sheet.name)}</strong> collection — ` +
    `one small, meaningful piece to add to your Ami &amp; Me bracelet and tell your story.</p>` +
    `<p><strong>Wears well with:</strong> ${esc(c.tags.slice(0, 6).join(", "))}.</p>`;
  specs.push({
    kind: "charm",
    id: c.id,
    title: c.name,
    descriptionHtml: desc,
    productType: "Charm",
    vendor: "Ami & Me",
    price: String(priceOfCharm(c)),
    sku: c.id,
    image: `${RAW}/${c.id}.webp`,
    altText: c.name + " — hand-painted charm",
    themeName: sheet.name,
    tags: Array.from(new Set([
      "Charm", themeTag, "category:" + c.category, ...c.tags.slice(0, 8),
    ])),
  });
}

// --- bracelets ------------------------------------------------------------
for (const b of BRACELETS) {
  haveCrop(b.id);
  const desc =
    `<p><em>${esc(b.blurb)}</em></p>` +
    `<p>Designed to hold <strong>${b.fit[0]}–${b.fit[1]} charms</strong>. ` +
    `Choose your charms and we hand-finish the piece to order.</p>` +
    `<p><strong>Style:</strong> ${esc(cap(b.style))}.</p>`;
  specs.push({
    kind: "bracelet",
    id: b.id,
    title: b.name,
    descriptionHtml: desc,
    productType: "Bracelet",
    vendor: "Ami & Me",
    price: String(priceOfBracelet(b)),
    sku: b.id,
    image: `${RAW}/${b.id}.webp`,
    altText: b.name + " — charm bracelet base",
    themeName: "Bracelets",
    tags: Array.from(new Set([
      "Bracelet", "style:" + b.style, ...b.vibe.slice(0, 8),
    ])),
  });
}

// --- collections (smart, by tag / type) -----------------------------------
const collections = Object.values(SHEETS).map((s) => ({
  title: s.name,
  tag: "theme:" + slug(s.name),
  type: "charm",
}));
collections.push({ title: "Bracelets", productType: "Bracelet", type: "bracelet" });

fs.writeFileSync("/tmp/amime_specs.json", JSON.stringify({ specs, collections }, null, 2));

console.log("charms:", CHARMS.length, " bracelets:", BRACELETS.length, " total specs:", specs.length);
console.log("collections:", collections.length);
console.log("missing crop images:", missing.length, missing.slice(0, 20).join(", "));
console.log("sample charm:", JSON.stringify(specs[0], null, 2));
console.log("sample bracelet:", JSON.stringify(specs.find(s => s.kind === "bracelet"), null, 2));
const prices = specs.map(s => +s.price);
console.log("charm price range:", Math.min(...specs.filter(s=>s.kind==='charm').map(s=>+s.price)), "-", Math.max(...specs.filter(s=>s.kind==='charm').map(s=>+s.price)));
