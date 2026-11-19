// The state cases over the split modules, against the pre-split goldens, plus
// the unit tests for parseHash, the pure half of readHash.
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import test from "node:test";

globalThis.contextMapperModel = JSON.parse(readFileSync(new URL("./fixture.json", import.meta.url), "utf8"));
const expected = JSON.parse(readFileSync(new URL("./expected.json", import.meta.url), "utf8"));
const api = {
  ...(await import("../../src/context_mapper/template/core/model.js")),
  ...(await import("../../src/context_mapper/template/core/graph.js")),
  ...(await import("../../src/context_mapper/template/core/state.js")),
  ...(await import("../../src/context_mapper/template/core/attributes.js")),
  ...(await import("../../src/context_mapper/template/components/attributes.js")),
  ...(await import("../../src/context_mapper/template/core/diagram.js")),
};
const { CASES } = await import("./cases.mjs");
for (const { name, fn } of CASES.state)
  test(`state: ${name}`, () => assert.deepEqual(fn(api), expected[`state/${name}`]));

// The page hands parseHash the hash the way readHash reads it:
// location.hash.slice(1), without the leading "#". The hashes below are
// written as whole hashes, so they lose the "#" on the way in.
const parse = hash => api.parseHash(hash.replace(/^#/, ""));

test("state: parseHash of an empty hash is the whole system", () => {
  assert.deepEqual(parse(""), {
    level: "context",
    focus: "",
    depth: 1,
    dir: "both",
    display: { catalog: "expanded", orders: "expanded", foundations: "collapsed" },
    hide: new Set(),
  });
});

test("state: parseHash reads the level and the focus", () => {
  const s = parse("#level=domain&focus=orders");
  assert.equal(s.level, "domain");
  assert.equal(s.focus, "orders");
  assert.deepEqual(s.display, { catalog: "expanded", orders: "expanded", foundations: "collapsed" });
});

test("state: parseHash falls back to the whole system for an unknown focus", () => {
  assert.equal(parse("#focus=nope").focus, "");
});

test("state: parseHash reads the depth, the direction and the displays", () => {
  const s = parse("#focus=checkout&depth=7&dir=up&display.catalog=collapsed&display.orders=bogus&display.foundations=hidden&hide.crm=1");
  assert.equal(s.depth, 7);
  assert.equal(s.dir, "up");
  assert.equal(s.focus, "checkout");
  // An unknown display mode falls back to the default; a hidden container wins
  // over its mode.
  assert.deepEqual(s.display, { catalog: "collapsed", orders: "expanded", foundations: "hidden" });
  assert.deepEqual([...s.hide].sort(), ["crm"]);
});

test("state: parseHash hides what the hash hides and unhides what it unhides", () => {
  assert.deepEqual([...parse("#hide.payments=1&hide.identity=0").hide].sort(), ["payments"]);
});

test("state: parseHash and hashFor agree on every hash", () => {
  const hashes = Object.entries(expected)
    .filter(([name, value]) => name.startsWith("state/") && typeof value === "string" && value.startsWith("#"))
    .map(([, value]) => value);
  assert.ok(hashes.length, "the state goldens hold hashes to round-trip");
  for (const hash of hashes) {
    const once = parse(hash);
    assert.deepEqual(parse(api.hashFor(once)), once, hash);
  }
});
