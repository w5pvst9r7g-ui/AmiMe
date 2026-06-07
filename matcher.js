/*
 * AmiMe — Local Story Matcher
 * -----------------------------------------------------------------------------
 * A zero-dependency, offline matcher that scores every charm against a
 * customer's sentence and returns the best `count` of them, each with a short
 * reason. It works instantly in the browser with no API key.
 *
 * It is intentionally simple and transparent:
 *   1. Normalise + tokenise the story into words (and 2-word phrases).
 *   2. Expand those words with a synonym/concept map so "ocean" also reaches
 *      "sea", "beach", "shell", "wave"...
 *   3. Score each charm by how many of its tags the expanded story hits,
 *      weighting exact phrase hits higher than single-word hits.
 *   4. Rank, then gently diversify so the result isn't five near-identical
 *      flowers, and return the top `count`.
 *
 * For richer, genuinely semantic understanding, run server.js (Claude-powered).
 * The browser falls back to this matcher whenever the backend isn't available.
 */
(function (root) {
  "use strict";

  // Concept expansion: a word in the story also "lights up" these related
  // ideas. Keys and values are matched against charm tags.
  var SYNONYMS = {
    love: ["heart", "romance", "adore", "valentine", "sweetheart", "devotion", "affection"],
    romance: ["love", "heart", "rose", "romantic", "date"],
    wedding: ["bell", "church", "bow", "ring", "marriage", "bride", "celebrate", "ceremony"],
    married: ["wedding", "bell", "ring", "anniversary"],
    anniversary: ["heart", "rose", "love", "celebrate", "ring"],
    engaged: ["wedding", "ring", "love", "heart"],
    ocean: ["sea", "beach", "shell", "wave", "coast", "fish", "coral", "crab", "seaside", "sail"],
    sea: ["ocean", "beach", "shell", "fish", "coral", "crab", "sail", "coast", "seaside"],
    beach: ["sea", "ocean", "shell", "sun", "summer", "crab", "coast", "seaside"],
    sailing: ["sea", "ocean", "shell", "sail", "boat", "coast"],
    summer: ["sun", "beach", "lemon", "strawberry", "cherry", "sea", "sunshine", "holiday"],
    holiday: ["travel", "sea", "beach", "summer", "sun", "adventure"],
    vacation: ["travel", "beach", "sea", "summer", "holiday", "sun"],
    travel: ["adventure", "journey", "trip", "explore", "camera", "boot", "mountain", "wander"],
    adventure: ["travel", "mountain", "journey", "explore", "boot", "wild", "outdoors"],
    hiking: ["mountain", "outdoors", "nature", "adventure", "summit", "climb"],
    mountains: ["mountain", "hike", "outdoors", "adventure", "summit", "nature"],
    music: ["guitar", "song", "sing", "band", "melody", "musician", "festival"],
    sing: ["guitar", "music", "song", "melody"],
    photography: ["camera", "photo", "memories", "picture", "capture", "moment"],
    photos: ["camera", "memories", "picture", "moment", "capture"],
    memories: ["camera", "photo", "keepsake", "remember", "moment"],
    luck: ["clover", "shamrock", "ladybug", "fortune", "lucky", "four leaf"],
    lucky: ["clover", "shamrock", "ladybug", "luck", "fortune"],
    happy: ["joy", "sunshine", "smile", "sun", "sunflower", "cheer", "happiness"],
    happiness: ["joy", "sunshine", "smile", "sunflower", "sun", "cheer"],
    joy: ["happy", "sunshine", "smile", "joie", "celebrate", "cheer"],
    calm: ["lavender", "moon", "peace", "soothe", "serenity", "gentle", "relax"],
    peace: ["olive", "lavender", "calm", "dove", "soothe", "serenity"],
    sad: ["forget me not", "moon", "comfort", "soothe"],
    grief: ["forget me not", "remember", "lavender", "comfort"],
    remember: ["forget me not", "memory", "keepsake", "poppy"],
    mother: ["mama", "mom", "mum", "nest", "family", "parent"],
    mom: ["mama", "mother", "mum", "family"],
    mum: ["mama", "mother", "mom", "family"],
    mama: ["mom", "mother", "mum", "family"],
    family: ["home", "mama", "nest", "house", "together", "generations", "kin"],
    baby: ["nest", "sunshine", "new baby", "beginning", "family"],
    children: ["family", "sunshine", "baby", "home"],
    kids: ["family", "sunshine", "baby", "home"],
    daughter: ["family", "love", "mama", "blooming"],
    son: ["family", "love", "mama"],
    grandmother: ["lavender", "violet", "garden", "family", "nurture"],
    home: ["house", "cottage", "family", "cozy", "belonging", "garden"],
    moving: ["house", "home", "new home", "chapter", "townhouse"],
    house: ["home", "cottage", "family", "belonging"],
    garden: ["flower", "bloom", "tulip", "daisy", "plant", "grow", "violet"],
    gardening: ["flower", "plant", "grow", "garden", "bloom", "pot"],
    flowers: ["flower", "bloom", "tulip", "daisy", "rose", "poppy", "garden"],
    spring: ["tulip", "daisy", "flower", "bloom", "fresh", "new beginning"],
    cooking: ["spoon", "kitchen", "food", "nourish", "recipe", "baking"],
    baking: ["spoon", "kitchen", "food", "cook", "sweet"],
    food: ["spoon", "lemon", "cherry", "kitchen", "cook"],
    italy: ["lemon", "dolce vita", "grapes", "mediterranean", "church", "olive"],
    france: ["joie", "joie de vivre", "bow", "perfume", "parisian"],
    wine: ["grapes", "vineyard", "harvest", "celebrate"],
    change: ["butterfly", "dragonfly", "transformation", "new self", "renewal"],
    transformation: ["butterfly", "dragonfly", "change", "rebirth", "growth"],
    growth: ["bloom", "grow", "butterfly", "plant", "blooming", "growing"],
    grow: ["grow", "bloom", "plant", "growing", "growth"],
    strength: ["strong", "super", "resilience", "cactus", "courage"],
    strong: ["strength", "cactus", "super", "resilience"],
    resilience: ["cactus", "strength", "strong", "endure", "survive"],
    dream: ["moon", "star", "wish", "pegasus", "imagination"],
    dreams: ["moon", "star", "wish", "pegasus", "imagination"],
    freedom: ["horse", "pegasus", "boot", "wild", "fly", "free spirit"],
    patience: ["snail", "slow", "take your time", "calm"],
    celebrate: ["bell", "confetti", "bow", "joy", "party", "champagne"],
    celebration: ["bell", "confetti", "bow", "joy", "party"],
    birthday: ["confetti", "celebrate", "bell", "joy", "bow"],
    gift: ["bow", "ribbon", "present"],
    faith: ["church", "spiritual", "ceremony"],
    new: ["new beginning", "fresh", "nest", "beginning", "chapter"],
    sweet: ["strawberry", "cherry", "sugar", "candy", "honey", "sweetness"],
    "long distance": ["letter", "envelope", "forget me not", "moon"]
  };

  // Words too generic to be useful as match tokens.
  var STOP = ("a an the and or but of for to in on at with my our we i you he she " +
    "they it is was were be been being this that these those her his their your our " +
    "me us them as so very really just about into over after before from by who whom " +
    "when where while because about up down out off then than too also each every all " +
    "had has have do does did will would can could should").split(" ");
  var STOPSET = {};
  STOP.forEach(function (w) { STOPSET[w] = true; });

  function normalise(text) {
    return (text || "").toLowerCase().replace(/[^a-z0-9\s'-]/g, " ").replace(/\s+/g, " ").trim();
  }

  function singularise(w) {
    if (w.length > 4 && /ies$/.test(w)) return w.slice(0, -3) + "y";
    if (w.length > 3 && /([^s])s$/.test(w)) return w.slice(0, -1);
    return w;
  }

  // Turn a story into a set of concept tokens (words, their singulars,
  // adjacent 2-word phrases, and synonym expansions).
  function expand(story) {
    var clean = normalise(story);
    var words = clean.split(" ").filter(Boolean);
    var concepts = {}; // token -> weight contributed when matched

    function add(tok, w) {
      if (!tok) return;
      concepts[tok] = Math.max(concepts[tok] || 0, w);
    }

    for (var i = 0; i < words.length; i++) {
      var w = words[i];
      if (STOPSET[w]) continue;
      add(w, 1);
      var s = singularise(w);
      if (s !== w) add(s, 1);
      // 2-word phrase
      if (i + 1 < words.length && !STOPSET[words[i + 1]]) {
        add(w + " " + words[i + 1], 2);
        add(s + " " + singularise(words[i + 1]), 2);
      }
    }

    // Synonym expansion (lower weight — it's an inferred connection).
    Object.keys(concepts).slice().forEach(function (tok) {
      var syns = SYNONYMS[tok];
      if (syns) syns.forEach(function (s) { add(s, 0.6); });
    });

    return concepts;
  }

  function scoreCharm(charm, concepts) {
    var hits = [];
    var score = 0;
    charm.tags.forEach(function (tag) {
      var t = tag.toLowerCase();
      if (concepts[t]) {
        score += concepts[t] * (t.indexOf(" ") >= 0 ? 1.6 : 1.0);
        hits.push(tag);
      } else {
        var st = singularise(t);
        if (st !== t && concepts[st]) {
          score += concepts[st];
          hits.push(tag);
        }
      }
    });
    // small bonus for matching the charm's category name directly
    if (concepts[charm.category]) score += 0.5;
    return { score: score, hits: hits };
  }

  function reasonFor(charm, hits) {
    if (hits.length) {
      var shown = hits.slice(0, 3).join(", ");
      return "Picks up on " + shown + " — " + charm.meaning + ".";
    }
    return "A complementary piece: " + charm.meaning + ".";
  }

  /**
   * recommend(story, count, catalog) -> { summary, charms: [{...charm, reason, score}] }
   */
  function recommend(story, count, catalog) {
    catalog = catalog || root.CHARM_CATALOG || [];
    count = Math.max(1, Math.min(count || 5, catalog.length));
    var concepts = expand(story);

    var scored = catalog.map(function (c) {
      var r = scoreCharm(c, concepts);
      return { charm: c, score: r.score, hits: r.hits };
    }).sort(function (a, b) { return b.score - a.score; });

    var picked = [];
    var usedCats = {};

    // First pass: take strong matches, lightly avoiding category repeats.
    for (var i = 0; i < scored.length && picked.length < count; i++) {
      var s = scored[i];
      if (s.score <= 0) break;
      var catCount = usedCats[s.charm.category] || 0;
      // allow up to 2 per category while we have other options
      if (catCount >= 2 && picked.length < count && hasOtherCategories(scored, i, usedCats)) continue;
      usedCats[s.charm.category] = catCount + 1;
      picked.push(s);
    }

    // Second pass: if the story was vague and nothing scored, fall back to a
    // pleasant, varied default selection.
    if (picked.length < count) {
      var defaults = pleasantDefaults(catalog, count - picked.length, picked);
      defaults.forEach(function (c) { picked.push({ charm: c, score: 0, hits: [] }); });
    }

    var result = picked.slice(0, count).map(function (s) {
      var out = {};
      for (var k in s.charm) out[k] = s.charm[k];
      out.reason = reasonFor(s.charm, s.hits);
      out.score = Math.round(s.score * 100) / 100;
      out.matched = s.hits;
      return out;
    });

    return {
      summary: buildSummary(story, result),
      charms: result,
      engine: "local"
    };
  }

  function hasOtherCategories(scored, fromIndex, usedCats) {
    for (var j = fromIndex; j < scored.length; j++) {
      if (scored[j].score <= 0) return false;
      if ((usedCats[scored[j].charm.category] || 0) < 2) return true;
    }
    return false;
  }

  function pleasantDefaults(catalog, n, already) {
    var have = {};
    already.forEach(function (s) { have[s.charm.id] = true; });
    var wishlist = ["white-quilted-heart", "scallop-shell", "lemon-oval", "crescent-moon",
      "clover-sprig-navy", "sunflower-round", "butterfly-cream", "gold-bell"];
    var out = [];
    wishlist.forEach(function (id) {
      if (out.length >= n) return;
      var c = catalog.filter(function (x) { return x.id === id && !have[x.id]; })[0];
      if (c) { out.push(c); have[c.id] = true; }
    });
    for (var i = 0; i < catalog.length && out.length < n; i++) {
      if (!have[catalog[i].id]) { out.push(catalog[i]); have[catalog[i].id] = true; }
    }
    return out;
  }

  function buildSummary(story, charms) {
    if (!charms.length) return "";
    var names = charms.map(function (c) { return c.name; });
    var list = names.length === 1 ? names[0]
      : names.slice(0, -1).join(", ") + " and " + names[names.length - 1];
    return "To tell this story we'd string together " + list +
      " — each charm carries a thread of what you described.";
  }

  var API = { recommend: recommend, expand: expand, SYNONYMS: SYNONYMS };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = API;
  } else {
    root.CharmMatcher = API;
  }
})(typeof window !== "undefined" ? window : globalThis);
