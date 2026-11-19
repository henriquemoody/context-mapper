// Regenerates expected.json from the modules as they stand. The goldens are
// the contract the panel and the pure core must keep; when a rendering change
// is deliberate, this writes the new contract — after the tests have said
// their piece about the difference.
import { readFileSync, writeFileSync } from "node:fs";
import assert from "node:assert/strict";
import { installDom } from "./dom-env.mjs";
import { CASES } from "./cases.mjs";

globalThis.contextMapperModel = JSON.parse(readFileSync(new URL("./fixture.json", import.meta.url), "utf8"));
installDom();
const api = {
  ...(await import("../../src/context_mapper/template/core/model.js")),
  ...(await import("../../src/context_mapper/template/core/graph.js")),
  ...(await import("../../src/context_mapper/template/core/state.js")),
  ...(await import("../../src/context_mapper/template/core/attributes.js")),
  ...(await import("../../src/context_mapper/template/components/attributes.js")),
  ...(await import("../../src/context_mapper/template/core/diagram.js")),
  ...(await import("../../src/context_mapper/template/components/panel.js")),
};

// Nothing JSON-hostile may reach expected.json: a Set would quietly become
// {}, and the case would pass forever after, whatever it returned.
const plain = (v, path) => {
  if (v instanceof Set || v instanceof Map || typeof v === "function")
    throw new Error(`not JSON-shaped at ${path}`);
  if (Array.isArray(v)) v.forEach((x, i) => plain(x, `${path}[${i}]`));
  else if (v && typeof v === "object") Object.entries(v).forEach(([k, x]) => plain(x, `${path}.${k}`));
};

const out = {};
for (const [group, cases] of Object.entries(CASES))
  for (const { name, fn } of cases) {
    const result = fn(api);
    plain(result, `${group}/${name}`);
    out[`${group}/${name}`] = result;
  }
const file = new URL("./expected.json", import.meta.url);
writeFileSync(process.argv[2] ?? file, JSON.stringify(out, null, 2) + "\n");
console.log(`captured ${Object.keys(out).length} cases`);
