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
  // Tight against the box at each end, not in the middle of the arrow.
  assert.ok(first.y < 200 && first.y > 200 - 15, `downstream at ${first.y}`);
  assert.ok(second.y > 0 && second.y < 25, `upstream at ${second.y}`);
});

test("roles: a label hugs its end: its near edge a few pixels from the box, past the arrowhead upstream", () => {
  const { svg } = diagramWith([UP]);
  drawRoleLabels(svg, "  %% roles: 0=OHS>ACL");
  const [down, up] = [...svg.querySelectorAll(".role-labels rect")]
    .map((r) => ({
      top: Number(r.getAttribute("y")),
      bottom: Number(r.getAttribute("y")) + Number(r.getAttribute("height")),
    }))
    .sort((a, b) => b.top - a.top);
  // The path starts at y=200 (the downstream box) and ends at y=0 (the upstream).
  assert.ok(
    200 - down.bottom <= 3,
    `${200 - down.bottom}px from the downstream box`,
  );
  assert.ok(up.top >= 6 && up.top <= 12, `${up.top}px from the upstream box`);
});

test("roles: labels at one box that would overlap are nudged apart", () => {
  const { svg } = diagramWith([
    [50, 200, 50, 0],
    [54, 200, 54, 0],
  ]);
  drawRoleLabels(svg, "  %% roles: 0=>CF;1=>CF");
  const [a, b] = [...svg.querySelectorAll(".role-labels rect")].map((r) => ({
    x: Number(r.getAttribute("x")),
    width: Number(r.getAttribute("width")),
  }));
  assert.ok(
    b.x >= a.x + a.width,
    `second box at ${b.x}, first ends at ${a.x + a.width}`,
  );
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

// ---------------------------------------------------------------- kernels ----
// A shared kernel is an `SK` badge at the middle of the arrow. Mermaid's own
// middle label may be there already, so the badge slides along the arrow
// until it clears it.

// An edge label of the given box, as the browser would report it, in a diagram
// whose arrows are in plain coordinates (no transform to undo).
const labelAt = (svg, index, rect) => {
  const labels = svg.querySelectorAll(".edgeLabel");
  let label = labels[index];
  if (!label) {
    const root = svg.firstChild;
    for (let i = labels.length; i <= index; i++) {
      label = document.createElementNS(SVG, "g");
      label.setAttribute("class", "edgeLabel");
      root.appendChild(label);
    }
    label = svg.querySelectorAll(".edgeLabel")[index];
  }
  label.textContent = rect ? "Port Terminals" : "";
  if (rect)
    label.getBoundingClientRect = () => ({
      left: rect.x - rect.width / 2,
      right: rect.x + rect.width / 2,
      top: rect.y - rect.height / 2,
      bottom: rect.y + rect.height / 2,
      width: rect.width,
      height: rect.height,
    });
  return label;
};
const badges = (svg) =>
  [...svg.querySelectorAll(".role-labels rect")].map((r) => ({
    x: Number(r.getAttribute("x")) + Number(r.getAttribute("width")) / 2,
    y: Number(r.getAttribute("y")) + Number(r.getAttribute("height")) / 2,
    width: Number(r.getAttribute("width")),
    height: Number(r.getAttribute("height")),
  }));

test("kernels: the badge sits at the middle of the arrow the source names", () => {
  const { svg } = diagramWith([UP, [10, 0, 10, 100]]);
  drawRoleLabels(svg, "  %% kernels: 1");
  assert.deepEqual(
    texts(svg).map((t) => t.text),
    ["SK"],
  );
  const [at] = badges(svg);
  assert.equal(at.x, 10);
  assert.ok(Math.abs(at.y - 50) < 1, `badge at ${at.y}`);
});

test("kernels: the badge looks like a role code, with inline styles", () => {
  const { svg } = diagramWith([UP]);
  drawRoleLabels(svg, "  %% roles: 0=OHS>ACL\n  %% kernels: 0");
  const group = svg.querySelector(".role-labels");
  assert.equal(group.querySelectorAll("rect").length, 3);
  const [roleBox, , , , kernelBox] = [...group.children];
  assert.equal(kernelBox.getAttribute("style"), roleBox.getAttribute("style"));
  assert.equal(
    group.querySelectorAll("text")[2].getAttribute("style"),
    group.querySelectorAll("text")[0].getAttribute("style"),
  );
});

test("kernels: a badge goes with a roles line, and each on its own arrow", () => {
  const { svg } = diagramWith([UP, [10, 0, 10, 100]]);
  drawRoleLabels(svg, "  %% roles: 0=S>C\n  %% kernels: 0,1");
  assert.deepEqual(
    texts(svg)
      .map((t) => t.text)
      .sort(),
    ["C", "S", "SK", "SK"],
  );
});

test("kernels: a badge slides along the arrow to clear Mermaid's middle label", () => {
  const { svg } = diagramWith([UP]);
  labelAt(svg, 0, { x: 50, y: 100, width: 90, height: 20 });
  drawRoleLabels(svg, "  %% kernels: 0");
  const [at] = badges(svg);
  assert.equal(at.x, 50);
  assert.ok(Math.abs(at.y - 100) >= 20 / 2 + 15 / 2, `badge at ${at.y}`);
});

test("kernels: with no label on the arrow the badge stays in the middle", () => {
  const { svg } = diagramWith([UP]);
  labelAt(svg, 0, null);
  drawRoleLabels(svg, "  %% kernels: 0");
  assert.ok(Math.abs(badges(svg)[0].y - 100) < 1);
});

test("kernels: a badge clears a role code placed before it", () => {
  const { svg } = diagramWith([[50, 0, 50, 30]]);
  drawRoleLabels(svg, "  %% roles: 0=OHS,PL>ACL\n  %% kernels: 0");
  const [a, b, c] = badges(svg);
  [
    [a, c],
    [b, c],
  ].forEach(([one, two]) =>
    assert.ok(
      Math.abs(one.x - two.x) >= (one.width + two.width) / 2 ||
        Math.abs(one.y - two.y) >= (one.height + two.height) / 2,
    ),
  );
});

test("kernels: a DOM that cannot measure a path, or a missing arrow, is left alone", () => {
  const { svg } = diagramWith([UP], { geometry: false });
  assert.doesNotThrow(() => drawRoleLabels(svg, "  %% kernels: 0,3"));
  assert.equal(svg.querySelector(".role-labels"), null);
  const drawn = diagramWith([UP]).svg;
  assert.doesNotThrow(() => drawRoleLabels(drawn, "  %% kernels: 7"));
  assert.equal(drawn.querySelector(".role-labels"), null);
});

test("kernels: on a short arrow with a head the badge stays off the head", () => {
  const { svg } = diagramWith([[50, 40, 50, 0]]); // 40 long, head at y=0
  svg.querySelector("path").setAttribute("marker-end", "url(#arrow)");
  drawRoleLabels(svg, "  %% kernels: 0");
  const [at] = badges(svg);
  assert.ok(
    at.y - at.height / 2 >= 10,
    `badge starts ${at.y - at.height / 2} from the head`,
  );
  const headless = diagramWith([[50, 40, 50, 0]]).svg;
  drawRoleLabels(headless, "  %% kernels: 0");
  assert.ok(Math.abs(badges(headless)[0].y - 20) < 1); // a plain line has no head to keep clear
});

// A path as the hand-drawn look strokes it: twice over, so it is twice as long
// as the line it follows, and the middle of its length is not the line's.
const doubled = (svg, index, [x1, y1, x2, y2]) => {
  const path = svg.querySelectorAll("path.flowchart-link")[index];
  const chord = Math.hypot(x2 - x1, y2 - y1);
  path.getTotalLength = () => chord * 2;
  path.getPointAtLength = (l) => {
    const along = l <= chord ? l : l - chord;
    return {
      x: x1 + ((x2 - x1) * along) / chord,
      y: y1 + ((y2 - y1) * along) / chord,
    };
  };
};

test("kernels: an arrow too short to hold the badge clear of its head gets it beside the line", () => {
  // Tracking → Booking in the example: about 26px between the two boxes,
  // with a head at the upstream end (y=0).
  const { svg } = diagramWith([[50, 26, 50, 0]]);
  svg.querySelector("path").setAttribute("marker-end", "url(#arrow)");
  drawRoleLabels(svg, "  %% kernels: 0");
  const [at] = badges(svg);
  assert.ok(
    at.x - at.width / 2 >= 50,
    `badge starts at ${at.x - at.width / 2}, line at 50`,
  );
  assert.ok(
    Math.abs(at.y - 13) < 1,
    `badge at ${at.y}, the middle of the arrow`,
  );
});

test("kernels: the same on a hand-drawn path, whose length is twice its line", () => {
  const { svg } = diagramWith([[50, 26, 50, 0]]);
  svg.querySelector("path").setAttribute("marker-end", "url(#arrow)");
  doubled(svg, 0, [50, 26, 50, 0]);
  drawRoleLabels(svg, "  %% kernels: 0");
  const [at] = badges(svg);
  assert.ok(at.x - at.width / 2 >= 50);
  assert.ok(Math.abs(at.y - 13) < 1, `badge at ${at.y}`);
});

test("kernels: on a long hand-drawn path the badge is at the middle of the line, not of its length", () => {
  const { svg } = diagramWith([[50, 200, 50, 0]]);
  svg.querySelector("path").setAttribute("marker-end", "url(#arrow)");
  doubled(svg, 0, [50, 200, 50, 0]);
  drawRoleLabels(svg, "  %% kernels: 0");
  const [at] = badges(svg);
  assert.equal(at.x, 50);
  assert.ok(Math.abs(at.y - 100) < 1, `badge at ${at.y}`);
});

test("kernels: an arrow that holds the badge clear of both ends keeps it on the line", () => {
  // 40 long with a head: 4 at the tail, 15 for the badge, 12 for the head.
  const { svg } = diagramWith([[50, 40, 50, 0]]);
  svg.querySelector("path").setAttribute("marker-end", "url(#arrow)");
  drawRoleLabels(svg, "  %% kernels: 0");
  const [at] = badges(svg);
  assert.equal(at.x, 50);
  assert.ok(
    at.y - at.height / 2 >= 12 - 0.5 && at.y + at.height / 2 <= 36 + 0.5,
    `badge at ${at.y}`,
  );
});

test("roles: on a hand-drawn path, twice as long as its line, the codes still hug the two ends", () => {
  const line = [50, 120, 50, 0];
  const plain = diagramWith([line]);
  drawRoleLabels(plain.svg, "  %% roles: 0=OHS>ACL");
  const drawn = diagramWith([line]);
  doubled(drawn.svg, 0, line);
  drawRoleLabels(drawn.svg, "  %% roles: 0=OHS>ACL");
  const close = (one, two) =>
    one.length === two.length &&
    one.every(
      (p, i) => Math.abs(p.x - two[i].x) < 1 && Math.abs(p.y - two[i].y) < 1,
    );
  assert.ok(
    close(texts(plain.svg), texts(drawn.svg)),
    "the same places as on a path of its own length",
  );
  const [down, up] = texts(drawn.svg).sort((a, b) => b.y - a.y);
  assert.ok(
    down.y > 120 - 15,
    `downstream code at ${down.y}, the path starts at 120`,
  );
  assert.ok(up.y < 25, `upstream code at ${up.y}, the path ends at 0`);
});

test("roles: on a short hand-drawn path the codes stay inside the line, not half its doubled length away", () => {
  const line = [50, 30, 50, 0];
  const { svg } = diagramWith([line]);
  doubled(svg, 0, line);
  drawRoleLabels(svg, "  %% roles: 0=OHS>ACL");
  texts(svg).forEach((t) => assert.ok(t.y >= -10 && t.y <= 40, `at ${t.y}`));
});

test("roles: a path that bends leaves each end the way it really goes", () => {
  // Down the left, across, then up: the first and last stretches are vertical
  // although the straight way between the ends is not.
  const points = [
    [10, 100],
    [10, 60],
    [90, 60],
    [90, 0],
  ];
  const { svg } = diagramWith([[10, 100, 90, 0]]);
  const path = svg.querySelector("path");
  const legs = points.slice(1).map((p, i) => ({
    from: points[i],
    to: p,
    length: Math.hypot(p[0] - points[i][0], p[1] - points[i][1]),
  }));
  const total = legs.reduce((sum, l) => sum + l.length, 0);
  path.getTotalLength = () => total;
  path.getPointAtLength = (l) => {
    let left = Math.min(Math.max(l, 0), total);
    for (const leg of legs) {
      if (left <= leg.length)
        return {
          x: leg.from[0] + ((leg.to[0] - leg.from[0]) * left) / leg.length,
          y: leg.from[1] + ((leg.to[1] - leg.from[1]) * left) / leg.length,
        };
      left -= leg.length;
    }
  };
  drawRoleLabels(svg, "  %% roles: 0=OHS>ACL");
  const [down, up] = texts(svg).sort((a, b) => b.y - a.y);
  assert.ok(
    Math.abs(down.x - 10) > 10 && down.y > 80,
    `downstream at ${down.x},${down.y}`,
  );
  assert.ok(
    Math.abs(up.x - 90) > 10 && up.y < 20,
    `upstream at ${up.x},${up.y}`,
  );
});
