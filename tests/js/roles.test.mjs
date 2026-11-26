// The script that draws the roles next to the ends of an arrow: the diagram's
// source says which arrows carry roles, and this puts a label near each end,
// inside the SVG. A test DOM has no layout, so the arrows get a stubbed
// geometry: straight lines that know their length and their points.
import assert from "node:assert/strict";
import test from "node:test";
import { installDom } from "./dom-env.mjs";
import { drawRoleLabels } from "../../src/context_mapper/template/roles.js";

installDom();
const SVG = "http://www.w3.org/2000/svg";

// A diagram with one straight arrow per [x1, y1, x2, y2]: it starts at the
// first point and finishes at the second, as an arrow does from its
// downstream to its upstream.
const diagramWith = (lines, { geometry = true } = {}) => {
  const svg = document.createElementNS(SVG, "svg");
  const root = document.createElementNS(SVG, "g");
  const edgePaths = document.createElementNS(SVG, "g");
  root.appendChild(edgePaths);
  svg.appendChild(root);
  lines.forEach(([x1, y1, x2, y2]) => {
    const path = document.createElementNS(SVG, "path");
    path.setAttribute("class", "flowchart-link");
    if (geometry) {
      const length = Math.hypot(x2 - x1, y2 - y1);
      path.getTotalLength = () => length;
      path.getPointAtLength = (l) => ({
        x: x1 + ((x2 - x1) * l) / length,
        y: y1 + ((y2 - y1) * l) / length,
      });
    }
    edgePaths.appendChild(path);
  });
  return { svg, root };
};
const texts = (svg) =>
  [...svg.querySelectorAll(".role-labels text")].map((t) => ({
    text: t.textContent,
    x: Number(t.getAttribute("x")),
    y: Number(t.getAttribute("y")),
  }));

// Bottom to top: the downstream is at the bottom of the diagram, upstream on top.
const UP = [50, 200, 50, 0];

test("roles: the upstream's roles sit near the path's end, the downstream's near its start", () => {
  const { svg } = diagramWith([UP]);
  drawRoleLabels(svg, "flowchart BT\n  a --> b\n  %% roles: 0=OHS,PL>ACL\n");
  const [first, second] = texts(svg).sort((a, b) => b.y - a.y);
  assert.equal(first.text, "ACL");
  assert.equal(second.text, "OHS, PL");
  // A short way in from each end, not in the middle of the arrow.
  assert.ok(first.y < 200 && first.y > 200 - 40, `downstream at ${first.y}`);
  assert.ok(second.y > 0 && second.y < 40, `upstream at ${second.y}`);
});

test("roles: a label sits beside the line, clear of it", () => {
  const { svg } = diagramWith([UP]);
  drawRoleLabels(svg, "  %% roles: 0=OHS>ACL");
  const rects = [...svg.querySelectorAll(".role-labels rect")];
  assert.equal(rects.length, 2);
  rects.forEach((rect) => {
    const left = Number(rect.getAttribute("x"));
    assert.ok(left > 50, `the box starts at ${left}, right of the line at 50`);
  });
});

test("roles: every label has a background box, inline styles and no pointer events", () => {
  const { svg } = diagramWith([UP]);
  drawRoleLabels(svg, "  %% roles: 0=S>C");
  const group = svg.querySelector(".role-labels");
  assert.equal(group.querySelectorAll("rect").length, 2);
  assert.match(group.getAttribute("style"), /pointer-events:\s*none/);
  // Styles are the elements' own, so a download — which has no page CSS — keeps them.
  group
    .querySelectorAll("rect, text")
    .forEach((el) =>
      assert.ok(el.getAttribute("style"), `${el.tagName} has an inline style`),
    );
});

test("roles: the labels go in the diagram's root group, over the arrows", () => {
  const { svg, root } = diagramWith([UP]);
  drawRoleLabels(svg, "  %% roles: 0=S>C");
  assert.equal(svg.querySelector(".role-labels").parentNode, root);
  assert.equal(root.lastChild, svg.querySelector(".role-labels"));
});

test("roles: a side with no roles has no label", () => {
  const { svg } = diagramWith([UP]);
  drawRoleLabels(svg, "  %% roles: 0=>CF");
  assert.deepEqual(
    texts(svg).map((t) => t.text),
    ["CF"],
  );
  const again = diagramWith([UP]);
  drawRoleLabels(again.svg, "  %% roles: 0=S>");
  assert.deepEqual(
    texts(again.svg).map((t) => t.text),
    ["S"],
  );
});

test("roles: only the arrows the source names get labels, by their index", () => {
  const { svg } = diagramWith([UP, [0, 0, 100, 0], [10, 10, 10, 90]]);
  drawRoleLabels(svg, "  %% roles: 0=OHS>ACL;2=S>C");
  assert.deepEqual(
    texts(svg)
      .map((t) => t.text)
      .sort(),
    ["ACL", "C", "OHS", "S"],
  );
});

test("roles: a sideways arrow gets its labels at its ends too", () => {
  const { svg } = diagramWith([[0, 50, 300, 50]]);
  drawRoleLabels(svg, "  %% roles: 0=OHS>ACL");
  const [start, end] = texts(svg).sort((a, b) => a.x - b.x);
  assert.equal(start.text, "ACL");
  assert.equal(end.text, "OHS");
  assert.ok(start.x < 60 && end.x > 240);
});

test("roles: a very short arrow keeps its labels inside it", () => {
  const { svg } = diagramWith([[0, 0, 0, 20]]);
  drawRoleLabels(svg, "  %% roles: 0=OHS>ACL");
  texts(svg).forEach((t) => assert.ok(t.y >= -10 && t.y <= 30, `at ${t.y}`));
});

test("roles: a source with no roles changes nothing", () => {
  const { svg } = diagramWith([UP]);
  drawRoleLabels(svg, "flowchart BT\n  a --> b\n  %% violations: 0\n");
  assert.equal(svg.querySelector(".role-labels"), null);
});

test("roles: an index past the last arrow is ignored", () => {
  const { svg } = diagramWith([UP]);
  assert.doesNotThrow(() => drawRoleLabels(svg, "  %% roles: 5=OHS>ACL"));
  assert.equal(svg.querySelector(".role-labels"), null);
});

test("roles: a DOM that cannot measure a path is left alone", () => {
  const { svg } = diagramWith([UP], { geometry: false });
  assert.doesNotThrow(() => drawRoleLabels(svg, "  %% roles: 0=OHS>ACL"));
  assert.equal(svg.querySelector(".role-labels"), null);
});

test("roles: a diagram that did not render is left alone", () => {
  assert.doesNotThrow(() => drawRoleLabels(null, "  %% roles: 0=OHS>ACL"));
});
