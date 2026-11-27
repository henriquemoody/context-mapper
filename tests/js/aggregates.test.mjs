// The aggregate level: contexts drawn as containers around their aggregates,
// with the references between aggregates after every arrow the page's
// scripts count — so the violation heads, role codes and kernel badges still
// land on the arrows the source names.
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import test from "node:test";
import { Window } from "happy-dom";

globalThis.contextMapperModel = JSON.parse(
  readFileSync(new URL("./fixture.json", import.meta.url), "utf8"),
);
const { mermaidSource } =
  await import("../../src/context_mapper/template/core/diagram.js");
const { parseHash, hashFor } =
  await import("../../src/context_mapper/template/core/state.js");
const { dropViolationHeads } =
  await import("../../src/context_mapper/template/arrowheads.js");
const { drawRoleLabels } =
  await import("../../src/context_mapper/template/roles.js");
const { installDom } = await import("./dom-env.mjs");
installDom();

const view = (level, extra = {}) => ({
  level,
  focus: "orders",
  depth: 99,
  dir: "both",
  display: { foundations: "expanded" },
  hide: new Set(),
  ...extra,
});
const arrows = (source) =>
  source
    .split("\n")
    .filter((line) => /^ {2}\w+ (-->|-\.->|<-->|---|===)/.test(line))
    .map((line) => line.trim());
const isReference = (line) => /^\w+__\w+ --> \w+__\w+$/.test(line);
const kindOf = (line) =>
  isReference(line)
    ? "reference"
    : line.includes("<-->")
      ? "violation"
      : /---|===/.test(line)
        ? "link"
        : "dependency";

const aggregate = mermaidSource(view("aggregate"));
const context = mermaidSource(view("context"));
const statements = arrows(aggregate.source);

test("aggregates: a context with aggregates is a container around a box for each", () => {
  const lines = aggregate.source.split("\n").map((l) => l.trim());
  assert.ok(lines.includes('subgraph checkout["Checkout"]'));
  assert.ok(lines.includes('checkout__Order["Order"]:::aggregate'));
  assert.ok(lines.includes('checkout__Cart["Cart"]:::aggregate'));
  assert.ok(
    lines.includes(
      "classDef aggregate fill:#ffffff,stroke:#6b6b6b,color:#1a1a1a",
    ),
  );
  assert.ok(lines.includes('subgraph orders["Orders"]'));
});

test("aggregates: a container takes the colors of its type, and the focus style when it is the focus", () => {
  const lines = mermaidSource(
    view("aggregate", { focus: "checkout", depth: 1 }),
  )
    .source.split("\n")
    .map((l) => l.trim());
  assert.ok(
    lines.includes(
      "style checkout fill:#dedaff,stroke:#6631d7,color:#1a1a1a,stroke-width:4px,font-weight:bold",
    ),
  );
  assert.ok(
    lines.includes("style payments fill:#adf0c7,stroke:#067429,color:#1a1a1a"),
  );
});

test("aggregates: a context with none is a plain box, as at the context level", () => {
  const { source } = mermaidSource(
    view("aggregate", { focus: "search", depth: 1 }),
  );
  assert.ok(source.includes('search["Search"]:::core'));
  assert.ok(!source.includes("subgraph search"));
});

test("aggregates: a collapsed domain is one box, with no aggregates inside", () => {
  const { source } = mermaidSource(
    view("aggregate", {
      focus: "",
      depth: 1,
      display: { foundations: "expanded", orders: "collapsed" },
    }),
  );
  assert.ok(
    source.includes('orders["<b>Orders</b><br/>Checkout, Fulfillment"]'),
  );
  assert.ok(!source.includes("checkout__Order"));
  assert.ok(!source.includes("fulfillment__Shipment"));
});

test("aggregates: the arrows between containers are the context level's, less what a reference covers", () => {
  const contextArrows = arrows(context.source);
  const kept = statements.filter((line) => kindOf(line) !== "reference");
  // Identity and Payments are upstream of Checkout, Fulfillment and CRM, and
  // their aggregates reference each other: those dependencies are drawn on the
  // references. The rest keeps its arrow, in its order.
  const covered = [
    "checkout --> identity",
    "crm --> identity",
    "checkout --> payments",
    "fulfillment --> payments",
  ];
  covered.forEach((line) => assert.ok(contextArrows.includes(line), line));
  assert.deepEqual(
    kept,
    contextArrows.filter((line) => !covered.includes(line)),
  );
  assert.deepEqual([...aggregate.visible].sort(), [...context.visible].sort());
  // The references come after all of them.
  const firstReference = statements.findIndex(isReference);
  assert.equal(firstReference, kept.length);
  statements
    .slice(firstReference)
    .forEach((line) => assert.equal(kindOf(line), "reference", line));
});

test("aggregates: a covered dependency is drawn on the reference, with its roles and its kernel", () => {
  const source = aggregate.source;
  const roles = Object.fromEntries(
    /%% roles: (.+)/
      .exec(source)[1]
      .split(";")
      .map((mark) => mark.split("=").reverse()),
  );
  assert.equal(
    statements[roles["OHS,PL>ACL"]],
    "checkout__Order --> identity__Account",
  );
  assert.equal(
    statements[roles["S>C"]],
    "checkout__Order --> payments__Payment",
  );
  // A dependency on a whole domain keeps its arrow, and its roles.
  assert.equal(statements[roles[">CF"]], "crm --> orders");
  const kernels = /%% kernels: ([\d,]+)/
    .exec(source)[1]
    .split(",")
    .map((i) => statements[i]);
  assert.deepEqual(kernels, [
    "payments --- crm",
    "fulfillment__Shipment --> payments__Payment",
  ]);
  // A reference a partnership or a kernel covers alone carries nothing.
  assert.ok(statements.includes("fulfillment__Return --> browsing__Session"));
  assert.ok(statements.includes("crm__Ticket --> payments__Payment"));
});

test("aggregates: the first of several references carries the dependency, the others stay plain", () => {
  const carriers = statements.filter(
    (line) =>
      isReference(line) &&
      /^(checkout__\w+ --> (identity__\w+)|crm__Ticket --> identity__Account)$/.test(
        line,
      ),
  );
  assert.deepEqual(carriers, [
    "checkout__Order --> identity__Account",
    "checkout__Order --> identity__Identity",
    "crm__Ticket --> identity__Account",
  ]);
  const roles = /%% roles: (.+)/.exec(aggregate.source)[1].split(";");
  const carried = roles
    .map((mark) => statements[Number(mark.split("=")[0])])
    .filter((line) => line.startsWith("checkout__Order --> identity"));
  assert.deepEqual(carried, ["checkout__Order --> identity__Account"]);
});

test("aggregates: what a collapsed box folds keeps its arrow between containers", () => {
  const { source } = mermaidSource(
    view("aggregate", { focus: "checkout", depth: 1, display: {} }),
  );
  assert.ok(
    arrows(source).some((line) =>
      /^checkout -->\|.*\| foundations$/.test(line),
    ),
  );
});

test("aggregates: every arrow, references included, has a tooltip in the order it is drawn", () => {
  assert.equal(aggregate.tips.length, statements.length);
  statements.forEach((line, i) => {
    if (isReference(line)) {
      assert.match(aggregate.tips[i][0].title, /→ .* \(reference\)$/);
    }
  });
  // A reference that carries a dependency tells it after its own entry.
  const carrier = statements.indexOf("checkout__Order --> identity__Account");
  assert.deepEqual(
    aggregate.tips[carrier].map((t) => t.title),
    ["Order → Account (reference)", "Checkout → Identity", "Events"],
  );
  assert.ok(aggregate.tips[carrier][1].roles);
});

test("aggregates: every arrow is styled once, references with the solid ones", () => {
  const styled = {};
  aggregate.source.split("\n").forEach((line) => {
    const found = /^ {2}linkStyle ([\d,]+) interpolate \w+ ?(.*)$/.exec(line);
    if (found)
      found[1].split(",").forEach((i) => (styled[Number(i)] = found[2]));
  });
  assert.deepEqual(
    Object.keys(styled).map(Number),
    statements.map((_, i) => i),
  );
  statements.forEach((line, i) => {
    if (isReference(line))
      assert.equal(styled[i], "stroke:#313131,stroke-width:1.5px");
  });
});

test("aggregates: a reference runs from the aggregate that holds it to the one it points at", () => {
  assert.ok(statements.includes("checkout__Order --> identity__Account"));
  assert.ok(statements.includes("checkout__Cart --> checkout__Order"));
  // Through a partnership, a shared kernel and a dependency on a whole domain.
  assert.ok(statements.includes("fulfillment__Return --> browsing__Session"));
  assert.ok(statements.includes("crm__Ticket --> payments__Payment"));
  assert.ok(statements.includes("crm__Ticket --> checkout__Order"));
  assert.ok(statements.includes("checkout__Cart --> browsing__Session"));
});

test("aggregates: a reference needs both ends drawn", () => {
  const { source } = mermaidSource(
    view("aggregate", { focus: "payments", hide: new Set(["checkout"]) }),
  );
  assert.ok(!source.includes("checkout__Order"));
  assert.ok(!arrows(source).some((line) => line.startsWith("checkout__")));
});

test("aggregates: clicking an aggregate focuses on its context, at the same level", () => {
  const clicks = aggregate.source
    .split("\n")
    .filter((line) => /^ {2}click \w+__/.test(line));
  assert.ok(clicks.length);
  assert.ok(
    clicks.includes(
      '  click checkout__Order href "#level=aggregate&focus=checkout&depth=99&display.foundations=expanded"',
    ),
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

test("aggregates: the violation heads and the role codes land on the arrows the source names", () => {
  const svg = drawn();
  dropViolationHeads(svg, aggregate.source);
  drawRoleLabels(svg, aggregate.source);
  const lost = [...svg.querySelectorAll("path")]
    .filter(
      (p) =>
        !p.hasAttribute("marker-end") && kindOf(p.dataset.statement) !== "link",
    )
    .map((p) => kindOf(p.dataset.statement));
  assert.ok(lost.length > 0);
  assert.ok(lost.every((kind) => kind === "violation"));
  const named = /%% roles: (.+)/.exec(aggregate.source)[1].split(";");
  named.forEach((mark) =>
    assert.notEqual(
      kindOf(statements[Number(mark.split("=")[0])]),
      "violation",
    ),
  );
  assert.ok(svg.querySelectorAll(".role-labels rect").length > 0);
});

test("aggregates: a kernel badge keeps to the arrow that carries the kernel", () => {
  const { source } = mermaidSource(
    view("aggregate", { focus: "fulfillment", depth: 1 }),
  );
  const lines = arrows(source);
  const kernels = /%% kernels: ([\d,]+)/.exec(source)[1].split(",").map(Number);
  // The kernel rides on the dependency, which Shipment's reference carries.
  assert.deepEqual(
    kernels.map((i) => lines[i]),
    ["fulfillment__Shipment --> payments__Payment"],
  );
  assert.ok(!lines.includes("fulfillment --> payments"));
});

test("aggregates: the level is part of the hash, and a hash brings it back", () => {
  const s = parseHash("level=aggregate&focus=checkout&depth=2");
  assert.equal(s.level, "aggregate");
  assert.equal(s.focus, "checkout");
  assert.equal(hashFor(s), "#level=aggregate&focus=checkout&depth=2");
  assert.equal(parseHash("level=bogus").level, "context");
  assert.equal(parseHash("level=domain").level, "domain");
  assert.equal(parseHash("").level, "context");
});

test("aggregates: an aggregate is not a focus target", () => {
  assert.equal(parseHash("level=aggregate&focus=Order").focus, "");
  assert.equal(parseHash("focus=checkout__Order").focus, "");
});
