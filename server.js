/*
 * AmiMe — Charm Story Matcher (optional Claude-powered backend)
 * -----------------------------------------------------------------------------
 * Serves the static front-end AND a /api/recommend endpoint that uses Claude
 * to read a customer's sentence and pick the charms that best tell that story.
 *
 * The front-end works perfectly well WITHOUT this server (it falls back to the
 * on-device keyword matcher in matcher.js). Run this when you want genuine
 * semantic understanding — Claude grasps mood, subtext and metaphor that a
 * keyword matcher can't.
 *
 * Run:
 *   npm install
 *   export ANTHROPIC_API_KEY=sk-ant-...
 *   npm start            # -> http://localhost:3000
 *
 * In production (a Shopify app), the same /api/recommend handler lives behind
 * your app proxy so the API key stays server-side and never reaches the browser.
 */
"use strict";

const http = require("http");
const https = require("https");
const fs = require("fs");
const path = require("path");
const Anthropic = require("@anthropic-ai/sdk");

const PORT = process.env.PORT || 3000;
const MODEL = "claude-opus-4-8";
const { CHARMS, BRACELETS } = require("./catalog.js");

const hasKey = !!(process.env.ANTHROPIC_API_KEY || process.env.ANTHROPIC_AUTH_TOKEN);
const client = hasKey ? new Anthropic() : null;

/* ---- optional Gemini-powered "on the wrist" mock-up ----------------------- *
 * If GEMINI_API_KEY is set, /api/mockup composes the chosen bracelet + charms
 * and asks Gemini's image model to render a lifestyle photo of a hand wearing
 * them. The key stays server-side, exactly like ANTHROPIC_API_KEY.            */
const GEMINI_API_KEY = process.env.GEMINI_API_KEY || "";
// Known-good, generally-available image model. Used as the default and as an
// automatic fallback if a configured/retired model name is rejected (404).
const DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-image";
// Retired aliases we transparently upgrade so a stale env var still works.
const RETIRED_GEMINI_MODELS = new Set(["gemini-2.5-flash-image-preview"]);
let GEMINI_MODEL = process.env.GEMINI_IMAGE_MODEL || DEFAULT_GEMINI_MODEL;
if (RETIRED_GEMINI_MODELS.has(GEMINI_MODEL)) {
  console.warn("GEMINI_IMAGE_MODEL '" + GEMINI_MODEL + "' is retired — using '" + DEFAULT_GEMINI_MODEL + "' instead.");
  GEMINI_MODEL = DEFAULT_GEMINI_MODEL;
}
const hasGemini = !!GEMINI_API_KEY;

const CROPS_DIR = path.join(__dirname, "charms", "crops");
const VALID_BRACELET_IDS = new Set(BRACELETS.map((b) => b.id));
const CHARM_BY_ID = new Map(CHARMS.map((c) => [c.id, c]));
const BRACELET_BY_ID = new Map(BRACELETS.map((b) => [b.id, b]));

// Built per request so we can pin the EXACT number of charms (the model
// otherwise invents extra ones) and demand even spacing (it otherwise clusters
// them). `names` is the ordered list of the picked charms.
function buildMockupPrompt(names) {
  const n = names.length;
  const list = names.map((nm, i) => "  " + (i + 2) + ". " + nm).join("\n");
  return (
    "A warm, natural lifestyle product photo of a woman's hand and wrist wearing " +
    "ONE delicate gold charm bracelet.\n\n" +
    "Reference images, in order:\n" +
    "  1. the bracelet base (the chain/clasp to use)\n" +
    list + "\n\n" +
    "These " + n + " charms are the ONLY charms on the bracelet:\n" +
    "- Show EXACTLY " + n + " charm" + (n === 1 ? "" : "s") + " — the ones provided as references — and NO others. " +
    "Do not invent, add, duplicate, swap or omit any charm. Exactly " + n + " charm" + (n === 1 ? "" : "s") + ", no more, no fewer.\n" +
    "- Keep each charm faithful to its reference in shape, colour and painted detail.\n" +
    "- Hang the charms in a single row along the front of the bracelet, EVENLY SPACED " +
    "with clear, equal gaps between them. Each charm must be fully visible and separated — " +
    "they must NOT bunch up, overlap, touch or cluster together.\n" +
    "- The bracelet is a SINGLE band that encircles the wrist exactly once, sitting " +
    "naturally flat against the skin. It must look like one normal bracelet — do NOT " +
    "wrap it around the wrist multiple times, and do NOT add extra strands, loops, " +
    "layers or chains beyond the single bracelet shown in the reference.\n" +
    "- Exactly one bracelet, worn on the wrist; no extra jewellery.\n\n" +
    "Style: soft natural daylight, shallow depth of field, tasteful neutral background " +
    "(cafe table or outdoors), premium editorial product photography. Square crop, photorealistic."
  );
}

/* ---- the catalogue, compacted for the model ------------------------------ */
const CATALOG_FOR_MODEL = CHARMS.map((c) => ({
  id: c.id,
  name: c.name,
  meaning: c.meaning,
  tags: c.tags.join(", ")
}));
const VALID_IDS = new Set(CHARMS.map((c) => c.id));

const SYSTEM_PROMPT =
  "You are the charm stylist for AmiMe, a brand of hand-painted enamel charm " +
  "bracelets. A customer describes a person, memory, relationship or moment in " +
  "a sentence or two. Your job is to choose the charms from the catalogue that, " +
  "strung together, best tell that story.\n\n" +
  "Read for mood, subtext and metaphor — not just literal nouns. 'She finally " +
  "found her footing again' might call for the butterfly (transformation) and " +
  "the cactus (resilience). Favour a varied, meaningful set over five near-" +
  "identical charms. Only ever choose charms by their exact `id` from the " +
  "catalogue below. Write each `reason` as one warm sentence addressed to the " +
  "customer, naming what in their story the charm reflects. Write `summary` as " +
  "one sentence describing the bracelet as a whole.\n\n" +
  "CATALOGUE (JSON):\n" + JSON.stringify(CATALOG_FOR_MODEL);

const OUTPUT_SCHEMA = {
  type: "object",
  additionalProperties: false,
  properties: {
    summary: { type: "string" },
    charms: {
      type: "array",
      items: {
        type: "object",
        additionalProperties: false,
        properties: {
          id: { type: "string" },
          reason: { type: "string" }
        },
        required: ["id", "reason"]
      }
    }
  },
  required: ["summary", "charms"]
};

async function recommendWithClaude(story, count) {
  const response = await client.messages.create({
    model: MODEL,
    max_tokens: 2000,
    thinking: { type: "adaptive" },
    output_config: {
      effort: "medium",
      format: { type: "json_schema", schema: OUTPUT_SCHEMA }
    },
    system: SYSTEM_PROMPT,
    messages: [
      {
        role: "user",
        content:
          'Choose exactly ' + count + ' charms for this story:\n\n"' + story + '"'
      }
    ]
  });

  const textBlock = response.content.find((b) => b.type === "text");
  if (!textBlock) throw new Error("no text block in response");
  const parsed = JSON.parse(textBlock.text);

  // Validate ids and trim to the requested count.
  const seen = new Set();
  const charms = (parsed.charms || [])
    .filter((c) => c && VALID_IDS.has(c.id) && !seen.has(c.id) && seen.add(c.id))
    .slice(0, count)
    .map((c) => ({ id: c.id, reason: c.reason }));

  return { summary: parsed.summary || "", charms, engine: "claude" };
}

/* ---- Gemini image mock-up ------------------------------------------------- */

// Read a charm/bracelet cut-out from disk as base64. Returns null if missing.
function loadCropBase64(id) {
  const file = path.join(CROPS_DIR, id + ".webp");
  // Guard against any path tricks sneaking in via the id.
  if (!file.startsWith(CROPS_DIR)) return null;
  try {
    return fs.readFileSync(file).toString("base64");
  } catch (e) {
    return null;
  }
}

// Build an Error carrying the upstream status + a plain-English message so the
// route handler can surface a useful reason to the browser (not a generic 502).
function geminiError(status, message) {
  const err = new Error(message);
  err.status = status;
  return err;
}

// Translate a raw Gemini/error message into a one-line, non-technical next step.
function mockupHint(msg, status) {
  const m = (msg || "").toLowerCase();
  if (status === 401 || status === 403 || m.indexOf("api key") !== -1 ||
      m.indexOf("api_key") !== -1 || m.indexOf("permission") !== -1 || m.indexOf("unauthor") !== -1) {
    return "Check GEMINI_API_KEY in your Render dashboard (Environment tab) — it may be missing, mistyped, or not enabled for image generation.";
  }
  if (status === 404 || m.indexOf("not found") !== -1 || m.indexOf("is not supported") !== -1 ||
      m.indexOf("not supported for generatecontent") !== -1) {
    return "The image model name may be wrong or retired. Set GEMINI_IMAGE_MODEL to 'gemini-2.5-flash-image' in Render (Environment tab) and redeploy.";
  }
  if (status === 429 || m.indexOf("quota") !== -1 || m.indexOf("exhausted") !== -1 || m.indexOf("rate") !== -1) {
    return "You've hit Gemini's rate limit or free-tier quota. Wait a minute and try again, or check your quota/billing in Google AI Studio.";
  }
  if (m.indexOf("billing") !== -1) {
    return "Image generation may require billing enabled on your Google AI / Cloud project.";
  }
  return "";
}

// POST the prompt + reference images to Gemini and resolve the first image part.
function callGemini(parts, model) {
  return new Promise((resolve, reject) => {
    const body = JSON.stringify({
      contents: [{ parts }],
      generationConfig: { responseModalities: ["IMAGE", "TEXT"] }
    });
    const options = {
      method: "POST",
      hostname: "generativelanguage.googleapis.com",
      path: "/v1beta/models/" + encodeURIComponent(model) +
        ":generateContent?key=" + encodeURIComponent(GEMINI_API_KEY),
      headers: {
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(body)
      }
    };
    const req = https.request(options, (resp) => {
      let data = "";
      resp.on("data", (chunk) => { data += chunk; });
      resp.on("end", () => {
        let json;
        try {
          json = JSON.parse(data);
        } catch (e) {
          return reject(geminiError(resp.statusCode,
            "Gemini returned an unexpected (non-JSON) response."));
        }
        if (resp.statusCode < 200 || resp.statusCode >= 300) {
          const msg = (json && json.error && json.error.message) || ("HTTP " + resp.statusCode);
          return reject(geminiError(resp.statusCode, msg));
        }
        const cand = json.candidates && json.candidates[0];
        const respParts = (cand && cand.content && cand.content.parts) || [];
        for (const part of respParts) {
          const inline = part.inlineData || part.inline_data;
          if (inline && inline.data) {
            return resolve({ data: inline.data, mime: inline.mimeType || inline.mime_type || "image/png" });
          }
        }
        // A 200 with no image usually means the model declined the prompt.
        const blocked = cand && (cand.finishReason || (cand.safetyRatings ? "safety" : ""));
        reject(geminiError(502, blocked
          ? "Gemini returned no image (finishReason: " + blocked + ")."
          : "Gemini returned no image."));
      });
    });
    req.on("error", reject);
    req.write(body);
    req.end();
  });
}

async function generateMockup(braceletId, charmIds) {
  const bracelet = BRACELET_BY_ID.get(braceletId);
  const bImg = loadCropBase64(braceletId);
  if (!bracelet || !bImg) throw new Error("unknown or missing bracelet image");

  // Collect only the valid, image-backed picked charms first, so the prompt can
  // state their exact count and names (and so we send no stray references).
  const usedCharms = [];
  const charmImages = [];
  for (const id of charmIds) {
    const charm = CHARM_BY_ID.get(id);
    if (!charm) continue;
    const img = loadCropBase64(id);
    if (!img) continue;
    usedCharms.push(id);
    charmImages.push({ name: charm.name, data: img });
  }

  const parts = [
    { text: buildMockupPrompt(charmImages.map((c) => c.name)) },
    { inline_data: { mime_type: "image/webp", data: bImg } }
  ];
  for (const c of charmImages) {
    parts.push({ inline_data: { mime_type: "image/webp", data: c.data } });
  }

  // Try the configured model; if the name is rejected (404 / unsupported),
  // transparently fall back to the known-good GA model so a stale env var or
  // retired alias never breaks the feature.
  let model = GEMINI_MODEL;
  let result;
  try {
    result = await callGemini(parts, model);
  } catch (err) {
    if (err && err.status === 404 && model !== DEFAULT_GEMINI_MODEL) {
      console.warn("model '" + model + "' rejected (404) — retrying with '" + DEFAULT_GEMINI_MODEL + "'.");
      model = DEFAULT_GEMINI_MODEL;
      result = await callGemini(parts, model);
    } else {
      throw err;
    }
  }
  return {
    image: "data:" + result.mime + ";base64," + result.data,
    bracelet: braceletId,
    charms: usedCharms,
    engine: "gemini",
    model: model
  };
}

/* ---- tiny static file server + API --------------------------------------- */
const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".jpeg": "image/jpeg", ".jpg": "image/jpeg", ".png": "image/png", ".svg": "image/svg+xml"
};

function sendJson(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, { "Content-Type": "application/json; charset=utf-8" });
  res.end(body);
}

function serveStatic(req, res) {
  let urlPath = decodeURIComponent(req.url.split("?")[0]);
  if (urlPath === "/") urlPath = "/index.html";
  // prevent path traversal
  const safe = path.normalize(urlPath).replace(/^(\.\.[/\\])+/, "");
  const filePath = path.join(__dirname, safe);
  if (!filePath.startsWith(__dirname)) { res.writeHead(403); return res.end("forbidden"); }

  fs.readFile(filePath, (err, data) => {
    if (err) { res.writeHead(404); return res.end("not found"); }
    res.writeHead(200, { "Content-Type": MIME[path.extname(filePath)] || "application/octet-stream" });
    res.end(data);
  });
}

const server = http.createServer((req, res) => {
  if (req.method === "GET" && req.url === "/api/health") {
    return sendJson(res, 200, { ok: true, claude: hasKey, model: MODEL, gemini: hasGemini, geminiModel: GEMINI_MODEL });
  }

  if (req.method === "POST" && req.url === "/api/recommend") {
    let body = "";
    req.on("data", (chunk) => { body += chunk; if (body.length > 1e5) req.destroy(); });
    req.on("end", async () => {
      let payload;
      try { payload = JSON.parse(body || "{}"); } catch (e) { return sendJson(res, 400, { error: "bad json" }); }
      const story = (payload.story || "").toString().slice(0, 4000).trim();
      let count = parseInt(payload.count, 10); if (!(count >= 1 && count <= 10)) count = 5;
      if (!story) return sendJson(res, 400, { error: "story required" });
      if (!client) return sendJson(res, 503, { error: "claude not configured" });

      try {
        const result = await recommendWithClaude(story, count);
        return sendJson(res, 200, result);
      } catch (err) {
        console.error("recommend error:", err && err.message ? err.message : err);
        return sendJson(res, 502, { error: "claude request failed" });
      }
    });
    return;
  }

  if (req.method === "POST" && req.url === "/api/mockup") {
    let body = "";
    req.on("data", (chunk) => { body += chunk; if (body.length > 1e5) req.destroy(); });
    req.on("end", async () => {
      let payload;
      try { payload = JSON.parse(body || "{}"); } catch (e) { return sendJson(res, 400, { error: "bad json" }); }
      const braceletId = (payload.bracelet || "").toString();
      const charmIds = Array.isArray(payload.charms)
        ? payload.charms.map((c) => (c == null ? "" : c.toString())).filter(Boolean).slice(0, 12)
        : [];
      if (!braceletId || !VALID_BRACELET_IDS.has(braceletId)) {
        return sendJson(res, 400, { error: "valid bracelet id required" });
      }
      if (!hasGemini) return sendJson(res, 503, { error: "gemini not configured" });

      try {
        const result = await generateMockup(braceletId, charmIds);
        return sendJson(res, 200, result);
      } catch (err) {
        const detail = err && err.message ? err.message : String(err);
        const status = err && err.status ? err.status : 502;
        console.error("mockup error (model " + GEMINI_MODEL + "):", detail);
        return sendJson(res, 502, {
          error: "mockup generation failed",
          detail: detail,
          hint: mockupHint(detail, status),
          model: GEMINI_MODEL
        });
      }
    });
    return;
  }

  if (req.method === "GET") return serveStatic(req, res);
  res.writeHead(405); res.end("method not allowed");
});

server.listen(PORT, () => {
  console.log("AmiMe charm matcher running at http://localhost:" + PORT);
  console.log(hasKey
    ? "Claude matcher: ENABLED (model " + MODEL + ")"
    : "Claude matcher: DISABLED — set ANTHROPIC_API_KEY to enable. Front-end will use the on-device matcher.");
  console.log(hasGemini
    ? "Gemini mock-up: ENABLED (model " + GEMINI_MODEL + ")"
    : "Gemini mock-up: DISABLED — set GEMINI_API_KEY to enable the 'see it on a wrist' preview.");
});
