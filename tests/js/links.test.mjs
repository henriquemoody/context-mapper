// The post-render scripts count arrows the way linkStyle does, by position in
// the source. Partnerships and shared kernels are links too: they come after
// the dependencies and the violations, so the indexes the `%% violations` and
// `%% roles` lines name still point at the arrows they mean.
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import test from "node:test";
import { Window } from "happy-dom";

globalThis.contextMapperModel = JSON.parse(
  readFileSync(new URL("./fixture.json", import.meta.url), "utf8"),
);
const { mermaidSource } =
  await import("../../src/context_mapper/template/core/diagram.js");
const { dropViolationHeads } =
  await import("../../src/context_mapper/template/arrowheads.js");
const { drawRoleLabels } =
  await import("../../src/context_mapper/template/roles.js");
const { installDom } = await import("./dom-env.mjs");
installDom();

const view = {
  level: "context",
  focus: "orders",
  depth: 99,
  dir: "both",
  display: {},
  hide: new Set(),
};
const { source, tips } = mermaidSource(view);
const statements = source
  .split("\n")
  .filter((line) => /^ {2}\w+ (-->|-\.->|<-->|---|===)/.test(line))
  .map((line) => line.trim());
const kindOf = (line) =>
  line.includes("<-->")
    ? "violation"
    : /---|===/.test(line)
      ? "link"
      : "dependency";

test("links: they come after the dependencies and the violations", () => {
  const kinds = statements.map(kindOf);
  assert.ok(kinds.includes("link") && kinds.includes("violation"));
  assert.deepEqual(
    kinds,
    [...kinds].sort(
      (a, b) =>
        ["dependency", "violation", "link"].indexOf(a) -
        ["dependency", "violation", "link"].indexOf(b),
    ),
  );
});

test("links: every statement gets a tooltip, in the order they are drawn", () => {
  assert.equal(tips.length, statements.length);
  statements.forEach((line, i) => {
    if (kindOf(line) === "link")
      assert.match(tips[i][0].title, /↔ .*\((Partnership|Shared Kernel)\)$/);
  });
});

test("links: every statement is styled once, links by their own kind", () => {
  const styled = {};
  source.split("\n").forEach((line) => {
    const found = /^ {2}linkStyle ([\d,]+) interpolate \w+ ?(.*)$/.exec(line);
    if (found)
      found[1].split(",").forEach((i) => (styled[Number(i)] = found[2]));
  });
  assert.deepEqual(
    Object.keys(styled).map(Number),
    statements.map((_, i) => i),
  );
});

// An SVG with one arrow per statement, each knowing its own statement.
const SVG = "http://www.w3.org/2000/svg";
const drawn = () => {
  const svg = document.createElementNS(SVG, "svg");
  const root = document.createElementNS(SVG, "g");
  svg.appendChild(root);
  statements.forEach((line, i) => {
    const path = document.createElementNS(SVG, "path");
    path.setAttribute("class", "flowchart-link");
    path.setAttribute("data-statement", line);
    if (kindOf(line) !== "link") path.setAttribute("marker-end", "url(#end)");
    path.getTotalLength = () => 100;
    path.getPointAtLength = (l) => ({ x: 10 + i * 20, y: 100 - l });
    root.appendChild(path);
  });
  return svg;
};

test("links: the violation heads go from the arrows the source names", () => {
  const svg = drawn();
  dropViolationHeads(svg, source);
  const lost = [...svg.querySelectorAll("path")]
    .filter(
      (p) =>
        !p.hasAttribute("marker-end") && !/---|===/.test(p.dataset.statement),
    )
    .map((p) => kindOf(p.dataset.statement));
  assert.ok(lost.length > 0);
  assert.ok(lost.every((kind) => kind === "violation"));
});

test("links: the role labels sit on the dependencies the source names", () => {
  const svg = drawn();
  drawRoleLabels(svg, source);
  const rects = svg.querySelectorAll(".role-labels rect");
  assert.ok(rects.length > 0);
  const named = /%% roles: (.+)/.exec(source)[1].split(";");
  named.forEach((mark) =>
    assert.equal(kindOf(statements[Number(mark.split("=")[0])]), "dependency"),
  );
});
