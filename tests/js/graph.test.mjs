// The graph cases over the split modules, against the pre-split goldens.
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import test from "node:test";

globalThis.contextMapperModel = JSON.parse(
  readFileSync(new URL("./fixture.json", import.meta.url), "utf8"),
);
const expected = JSON.parse(
  readFileSync(new URL("./expected.json", import.meta.url), "utf8"),
);
const api = {
  ...(await import("../../src/context_mapper/template/core/model.js")),
  ...(await import("../../src/context_mapper/template/core/graph.js")),
  ...(await import("../../src/context_mapper/template/core/roles.js")),
  ...(await import("../../src/context_mapper/template/core/events.js")),
  ...(await import("../../src/context_mapper/template/core/state.js")),
  ...(await import("../../src/context_mapper/template/core/attributes.js")),
  ...(await import("../../src/context_mapper/template/components/attributes.js")),
  ...(await import("../../src/context_mapper/template/core/diagram.js")),
};
const { CASES } = await import("./cases.mjs");
for (const { name, fn } of CASES.graph)
  test(`graph: ${name}`, () =>
    assert.deepEqual(fn(api), expected[`graph/${name}`]));
