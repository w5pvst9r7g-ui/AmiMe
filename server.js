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
const fs = require("fs");
const path = require("path");
const Anthropic = require("@anthropic-ai/sdk");

const PORT = process.env.PORT || 3000;
const MODEL = "claude-opus-4-8";
const { CHARMS } = require("./catalog.js");

const hasKey = !!(process.env.ANTHROPIC_API_KEY || process.env.ANTHROPIC_AUTH_TOKEN);
const client = hasKey ? new Anthropic() : null;

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
    return sendJson(res, 200, { ok: true, claude: hasKey, model: MODEL });
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

  if (req.method === "GET") return serveStatic(req, res);
  res.writeHead(405); res.end("method not allowed");
});

server.listen(PORT, () => {
  console.log("AmiMe charm matcher running at http://localhost:" + PORT);
  console.log(hasKey
    ? "Claude matcher: ENABLED (model " + MODEL + ")"
    : "Claude matcher: DISABLED — set ANTHROPIC_API_KEY to enable. Front-end will use the on-device matcher.");
});
