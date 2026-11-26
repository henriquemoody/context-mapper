// The panel cases over the split modules, against the pre-split goldens: the
// panel renders through preact, and the test DOM reads the panel's DOM back
// out of #info, so the goldens pin the panel's exact DOM.
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import test from "node:test";
import { installDom } from "./dom-env.mjs";

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
  ...(await import("../../src/context_mapper/template/core/state.js")),
  ...(await import("../../src/context_mapper/template/core/attributes.js")),
  ...(await import("../../src/context_mapper/template/components/attributes.js")),
  ...(await import("../../src/context_mapper/template/core/diagram.js")),
  ...(await import("../../src/context_mapper/template/components/panel.js")),
};
installDom();
const { CASES } = await import("./cases.mjs");
for (const { name, fn } of CASES.panel)
  test(`panel: ${name}`, () =>
    assert.deepEqual(fn(api), expected[`panel/${name}`]));
