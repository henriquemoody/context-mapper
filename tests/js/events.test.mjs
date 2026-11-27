// Events: the tooltip of an arrow lists the events that cross it, gathered
// from every dependency the arrow stands for; a partnership line lists the
// ones that cross it either way; a box lists the events it publishes and
// consumes unless attribute_tooltips says no. The goldens pin the exact
// output; these say what each one is for.
import { readFileSync } from "node:fs";
import assert from "node:assert/strict";
import test from "node:test";
import { installDom } from "./dom-env.mjs";

globalThis.contextMapperModel = JSON.parse(
  readFileSync(new URL("./fixture.json", import.meta.url), "utf8"),
);
const base = "../../src/context_mapper/template/";
const { mermaidSource } = await import(base + "core/diagram.js");
const { eventLabel, crossing, eventsTipEntries } = await import(
  base + "core/events.js"
);
const { boxTipEntries, aggregateTipEntries } = await import(
  base + "core/attributes.js"
);
const { renderInfo } = await import(base + "components/panel.js");
const { MODEL, contextById, DIAGRAM } = await import(base + "core/model.js");
installDom();

const view = (level, focus, display = {}, depth = 1) => ({
  level,
  focus,
  depth,
  dir: "both",
  display: { foundations: "expanded", ...display },
  hide: new Set(),
});
// The arrows of a diagram with their statements, in drawing order.
const arrowsOf = ({ source, tips }) => {
  const statements = source
    .split("\n")
    .filter((line) => /^ {2}\w+ (-->|-\.->|<-->|---)/.test(line))
    .map((line) => line.trim());
  return statements.map((statement, i) => ({ statement, tips: tips[i] }));
};
// The text of an arrow's Events entry, one string per line, never inline: the
// event, then a dash and the consumer's reason, or else the event's own
// description, when there is one.
const linesOf = (arrow) =>
  arrow.tips.find((t) => t.title === "Events")?.text.split("\n") ?? [];
// The events alone, without their reasons.
const eventsOf = (arrow) => linesOf(arrow).map((line) => line.split(" — ")[0]);

test("events: an event is labelled with its aggregate when it has one", () => {
  assert.equal(
    eventLabel({ name: "OrderPlaced", aggregate: "Order" }),
    "Order · OrderPlaced",
  );
  assert.equal(
    eventLabel({ name: "KeysRotated", aggregate: null }),
    "KeysRotated",
  );
});

test("events: crossing gathers the events of several rules once each", () => {
  const rule = (...addresses) => ({
    events: addresses.map((address) => ({
      address,
      name: address,
      aggregate: null,
    })),
  });
  assert.deepEqual(
    crossing([rule("a", "b"), rule("b", "c"), {}]).map((e) => e.address),
    ["a", "b", "c"],
  );
  assert.deepEqual(eventsTipEntries([{}, rule()]), []);
});

test("events: an arrow lists the events that cross the dependency, after its own entries", () => {
  const arrow = arrowsOf(mermaidSource(view("context", "checkout"))).find(
    (a) => a.statement === "checkout --> identity",
  );
  assert.deepEqual(eventsOf(arrow), ["KeysRotated", "Account · AccountOpened"]);
  assert.equal(arrow.tips.at(-1).title, "Events");
  assert.equal(arrow.tips[0].title, "Checkout → Identity");
});

test("events: an event goes through the dependency written against a whole domain", () => {
  const arrow = arrowsOf(mermaidSource(view("context", "crm", {}, 1))).find(
    (a) => a.statement === "crm --> orders",
  );
  assert.deepEqual(eventsOf(arrow), ["OrderSettled", "Order · OrderPlaced"]);
});

test("events: a merged arrow, at domain level or in a collapsed container, gathers them all", () => {
  const collapsed = arrowsOf(
    mermaidSource(view("context", "", { orders: "collapsed" })),
  ).find(
    (a) =>
      a.statement.startsWith("orders -->") && a.statement.endsWith("payments"),
  );
  assert.deepEqual(eventsOf(collapsed), [
    "Payment · PaymentCaptured",
    "Payment · PaymentRefunded",
  ]);
  // At domain level the arrow from Orders to Payments is one, and holds
  // what both Checkout's and Fulfillment's dependency carry.
  const domain = arrowsOf(mermaidSource(view("domain", ""))).find(
    (a) => a.statement === "orders --> payments",
  );
  assert.deepEqual(eventsOf(domain), [
    "Payment · PaymentCaptured",
    "Payment · PaymentRefunded",
  ]);
});

test("events: a partnership line lists the events that cross it in either direction", () => {
  const line = arrowsOf(mermaidSource(view("context", "fulfillment"))).find(
    (a) => a.statement === "fulfillment --- browsing",
  );
  assert.deepEqual(eventsOf(line), [
    "Shipment · ShipmentDispatched",
    "SessionEnded",
  ]);
});

test("events: a shared kernel carries no events", () => {
  const kernel = MODEL.symmetric.filter((r) => r.kind === "sharedKernel");
  assert.ok(kernel.length);
  kernel.forEach((rule) => assert.equal(rule.events, undefined));
});

test("events: the aggregate level puts them on the reference that carries the dependency", () => {
  const arrows = arrowsOf(mermaidSource(view("aggregate", "checkout")));
  const carrier = arrows.find(
    (a) => a.statement === "checkout__Order --> identity__Account",
  );
  assert.deepEqual(eventsOf(carrier), [
    "KeysRotated",
    "Account · AccountOpened",
  ]);
  const plain = arrows.find(
    (a) => a.statement === "checkout__Order --> identity__Identity",
  );
  assert.deepEqual(eventsOf(plain), []);
  // No arrow for an event, and none left out for lack of one.
  arrows.forEach((a) => assert.ok(!/OrderPlaced/.test(a.statement)));
});

test("events: a box lists the names of what it publishes and consumes", () => {
  const rows = (entries) =>
    Object.fromEntries(
      entries.filter((e) => e.kind === "attr").map((e) => [e.title, e.text]),
    );
  // One line per event, never inline: a published one with its description, a
  // consumed one with its reason, and nothing after the name when it has none.
  assert.deepEqual(
    [
      rows(boxTipEntries(contextById.checkout)).Publishes,
      rows(boxTipEntries(contextById.checkout)).Consumes,
    ],
    ["CartAbandoned", "KeysRotated\nQueryRun"],
  );
  const order = contextById.checkout.aggregates[0];
  assert.deepEqual(
    rows(aggregateTipEntries(order)).Publishes,
    "OrderPlaced — Checkout turned a cart into an order.",
  );
  assert.deepEqual(
    rows(aggregateTipEntries(order)).Consumes,
    "AccountOpened — Links the order to the account a guest just got.\nPaymentCaptured",
  );
  assert.ok(
    boxTipEntries(contextById.checkout)
      .filter((e) => /^(Publishes|Consumes)$/.test(e.title))
      .every((e) => e.multiline),
  );
  DIAGRAM.attribute_tooltips = false;
  try {
    assert.equal(
      rows(boxTipEntries(contextById.checkout)).Publishes,
      undefined,
    );
    assert.equal(rows(aggregateTipEntries(order)).Consumes, undefined);
    // The description stays.
    assert.equal(aggregateTipEntries(order)[0].kind, "desc");
  } finally {
    DIAGRAM.attribute_tooltips = true;
  }
});

test("events: the panel has a section for each list that has something in it", () => {
  const panel = (id) => {
    renderInfo(view("context", id), new Set());
    return document.getElementById("info").innerHTML;
  };
  const orders = panel("orders");
  assert.ok(orders.includes("<h3>Publishes (1)</h3>"));
  assert.ok(orders.includes('<a data-go="crm">CRM</a>'));
  const checkout = panel("checkout");
  assert.ok(checkout.includes("<b>Publishes:</b>"));
  assert.ok(
    checkout.includes(
      '<a data-go="identity">identity</a>/Account/AccountOpened',
    ),
  );
  // A domain with contexts that has no events shows no section for them.
  const none = panel("catalog");
  assert.ok(!none.includes("Publishes"));
});

test("events: an arrow gives the consumer's reason after each event it has one for", () => {
  const arrow = arrowsOf(mermaidSource(view("context", "checkout"))).find(
    (a) => a.statement === "checkout --> identity",
  );
  assert.deepEqual(linesOf(arrow), [
    "KeysRotated",
    "Account · AccountOpened — Links the order to the account a guest just got.",
  ]);
  assert.equal(arrow.tips.at(-1).kind, "events");
  // Nothing is said about this one, by the consumer or the publisher: the bare
  // event, still on a line of its own.
  const plain = arrowsOf(mermaidSource(view("context", "checkout"))).find(
    (a) => a.statement === "checkout --> payments",
  );
  assert.equal(plain.tips.at(-1).text, "Payment · PaymentCaptured");
});

test("events: an arrow never lists its events inline, whatever is said about them", () => {
  const all = arrowsOf(mermaidSource(view("domain", ""))).flatMap((a) =>
    a.tips.filter((t) => t.title === "Events"),
  );
  assert.ok(all.length > 3);
  all.forEach((t) => {
    // Each line is an event, `Aggregate · Event`, and what is said about it.
    t.text
      .split("\n")
      .forEach((line) => assert.match(line, /^(\w+ · )?\w+( — .+)?$/, line));
    assert.equal(t.kind, "events");
  });
});

test("events: with no reason from the consumer, the event's own description is said", () => {
  const arrow = arrowsOf(mermaidSource(view("context", "crm"))).find(
    (a) => a.statement === "crm --> orders",
  );
  assert.deepEqual(linesOf(arrow), [
    "OrderSettled — Syncs the order into the ticket system.",
    "Order · OrderPlaced — Checkout turned a cart into an order.",
  ]);
});

test("events: the description is only a fallback: an event someone gives a reason for says the reasons", () => {
  // Orders consumes AccountOpened with no reason, and Checkout with one, on
  // the same arrow at domain level: the reason is what is said, once.
  const arrow = arrowsOf(mermaidSource(view("domain", ""))).find(
    (a) =>
      a.statement === "orders --> foundations" ||
      a.statement === "orders --> identity",
  );
  const lines = linesOf(arrow).filter((line) => line.includes("AccountOpened"));
  assert.deepEqual(lines, [
    "Account · AccountOpened — Links the order to the account a guest just got.",
  ]);
});

test("events: an event says why once per reason, and leaves out a consumer that doesn't say", () => {
  const rule = (reason, consumer) => ({
    events: [{ address: "a/E", name: "E", aggregate: null, consumer, reason }],
  });
  assert.deepEqual(
    eventsTipEntries([
      rule(null, "x"),
      rule("Why one.", "y"),
      rule("Why one.", "z"),
      rule("Why two.", "w"),
    ]),
    [{ kind: "events", title: "Events", text: "E — Why one.\nE — Why two." }],
  );
  assert.deepEqual(eventsTipEntries([rule(null, "x"), rule(null, "y")]), [
    { kind: "events", title: "Events", text: "E" },
  ]);
});

test("events: the panel and the publisher say why an event is consumed", () => {
  const panel = (id) => {
    renderInfo(view("context", id), new Set());
    return document.getElementById("info").innerHTML;
  };
  // The consumer's side: the address, then its reason.
  assert.ok(
    panel("checkout").includes(
      '<a data-go="identity">identity</a>/Account/AccountOpened — Links the order to the account a guest just got.',
    ),
  );
  assert.ok(
    panel("checkout").includes("payments</a>/Payment/PaymentCaptured</li>"),
  );
  // The publisher's side: with a reason, one consumer per line.
  assert.ok(
    panel("fulfillment").includes("Consumed by:") === false,
    "Fulfillment publishes ShipmentDispatched, which Browsing consumes with no reason",
  );
  const shipment = panel("fulfillment");
  assert.ok(
    shipment.includes('Consumed by <a data-go="browsing">Browsing</a>'),
  );
});
