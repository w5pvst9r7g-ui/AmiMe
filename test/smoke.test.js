/*
 * AmiMe smoke tests — no dependencies, run with `node test/smoke.test.js`.
 * Validates the catalogue's integrity and that the local matcher returns
 * sensible, story-relevant charms.
 */
"use strict";

const assert = require("assert");
const { CHARMS, SHEETS } = require("../catalog.js");
const matcher = require("../matcher.js");

let passed = 0;
function ok(name, cond) {
  assert.ok(cond, name);
  passed++;
  console.log("  ✓ " + name);
}

console.log("Catalogue integrity");
ok("has a healthy number of charms", CHARMS.length >= 80);
ok("every charm has required fields", CHARMS.every((c) =>
  c.id && c.name && c.emoji && c.sheet && c.meaning && Array.isArray(c.tags) && c.tags.length));
const ids = CHARMS.map((c) => c.id);
ok("charm ids are unique", new Set(ids).size === ids.length);
ok("every charm points at a real sheet", CHARMS.every((c) => SHEETS[c.sheet]));
ok("all five sheets are represented",
  [1, 2, 3, 4, 5].every((s) => CHARMS.some((c) => String(c.sheet) === String(s))));

const fs = require("fs");
const path = require("path");
const cropDir = path.join(__dirname, "..", "charms", "crops");
if (fs.existsSync(cropDir)) {
  console.log("\nCharm crops");
  ok("every charm has a cropped image",
    CHARMS.every((c) => fs.existsSync(path.join(cropDir, c.id + ".webp"))));
}

console.log("\nLocal matcher relevance");
function topIds(story, n) {
  return matcher.recommend(story, n, CHARMS).charms.map((c) => c.id);
}
function includesAny(story, n, candidates) {
  const got = topIds(story, n);
  return candidates.some((id) => got.indexOf(id) >= 0);
}

ok("a seaside story surfaces a sea charm",
  includesAny("a summer romance by the sea", 5,
    ["scallop-shell", "coral-heart", "pink-crab", "whimsical-fish", "blue-sardine"]));
ok("a mum story surfaces a mama charm",
  includesAny("a gift for my mum, the strongest woman I know", 5,
    ["mama-stars", "super-mama", "one-moms-strength", "mama-hearts"]));
ok("a music story surfaces the guitar",
  topIds("she travels the world playing her guitar", 5).indexOf("acoustic-guitar") >= 0);
ok("a luck story surfaces a luck charm",
  includesAny("wishing you good luck on the new adventure", 5,
    ["clover-sprig-navy", "shamrock-check", "gold-ladybug"]));
ok("an Italian-summer story surfaces lemons",
  includesAny("lazy Italian summers eating lemons in the sun", 6,
    ["lemon-oval", "flowers-lemons-oval", "our-sunshine"]));

console.log("\nMatcher contract");
const r = matcher.recommend("anything at all", 3, CHARMS);
ok("returns exactly the requested count", r.charms.length === 3);
ok("each result carries a reason", r.charms.every((c) => typeof c.reason === "string" && c.reason.length));
ok("returns a summary", typeof r.summary === "string" && r.summary.length > 0);
ok("respects an empty/vague story with defaults", matcher.recommend("", 4, CHARMS).charms.length === 4);

console.log("\nAll " + passed + " checks passed.");
