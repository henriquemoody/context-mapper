// The script that drops the head a violation does not have: the diagram's
// source says which arrows, and only those lose the head at their end.
import assert from "node:assert/strict";
import test from "node:test";
import { Window } from "happy-dom";
import { dropViolationHeads } from "../../src/context_mapper/template/arrowheads.js";

const svgWith = (count) => {
  const document = new Window().document;
  const svg = document.createElement("div");
  svg.innerHTML = Array.from(
    { length: count },
    () => '<path class="flowchart-link" marker-end="url(#end)"></path>',
  ).join("");
  return svg;
};
const heads = (svg) =>
  [...svg.querySelectorAll("path")].map((p) => p.hasAttribute("marker-end"));

test("arrowheads: only the arrows the source names lose their end head", () => {
  const svg = svgWith(4);
  dropViolationHeads(svg, "flowchart BT\n  a --> b\n  %% violations: 1,3\n");
  assert.deepEqual(heads(svg), [true, false, true, false]);
});

test("arrowheads: a source with no violations changes nothing", () => {
  const svg = svgWith(2);
  dropViolationHeads(svg, "flowchart BT\n  a --> b\n");
  assert.deepEqual(heads(svg), [true, true]);
});

test("arrowheads: a diagram that did not render is left alone", () => {
  assert.doesNotThrow(() => dropViolationHeads(null, "  %% violations: 0"));
});

test("arrowheads: an index past the last arrow is ignored", () => {
  const svg = svgWith(1);
  assert.doesNotThrow(() => dropViolationHeads(svg, "  %% violations: 5"));
  assert.deepEqual(heads(svg), [true]);
});
