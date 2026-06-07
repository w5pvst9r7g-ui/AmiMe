/*
 * Turns /tmp/amime_specs.json into batched productSet GraphQL payloads.
 * Each batch is written to /tmp/batch_<n>.json as { query, variables }.
 */
const fs = require("fs");
const { specs } = JSON.parse(fs.readFileSync("/tmp/amime_specs.json", "utf8"));

const BATCH = 16;
const batches = [];
for (let i = 0; i < specs.length; i += BATCH) batches.push(specs.slice(i, i + BATCH));

batches.forEach((batch, bi) => {
  const variables = {};
  const decls = [];
  const bodies = [];
  batch.forEach((s, j) => {
    const v = "p" + j;
    decls.push(`$${v}: ProductSetInput!`);
    bodies.push(
      `${v}: productSet(synchronous: true, input: $${v}) { product { id handle } userErrors { field message } }`
    );
    variables[v] = {
      title: s.title,
      descriptionHtml: s.descriptionHtml,
      productType: s.productType,
      vendor: s.vendor,
      status: "DRAFT",
      tags: s.tags,
      productOptions: [{ name: "Title", values: [{ name: "Default Title" }] }],
      files: [{ originalSource: s.image, contentType: "IMAGE", alt: s.altText }],
      variants: [
        {
          optionValues: [{ optionName: "Title", name: "Default Title" }],
          price: s.price,
          sku: s.sku,
          inventoryPolicy: "CONTINUE",
        },
      ],
    };
  });
  const query = `mutation Batch(${decls.join(", ")}) {\n  ${bodies.join("\n  ")}\n}`;
  fs.writeFileSync(`/tmp/batch_${bi}.json`, JSON.stringify({ query, variables }));
});

console.log("batches:", batches.length, "of up to", BATCH, "products each");
console.log("sizes:", batches.map((b) => b.length).join(","));
