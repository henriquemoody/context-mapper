// The cases the JavaScript tests run, over the example model's real payload
// (fixture.json, written by the same code the build uses). Each case calls a
// piece of the page's pure logic through `api` — the model indexes, the graph
// walk, the URL-hash codec, the Mermaid source generator, the attribute
// rendering — and returns something JSON-shaped: no Sets, no Maps, no
// functions. expected.json holds what the code produced before the template
// was split into modules, so a test fails if the split changes any behavior.
//
// `api` carries the module surface under test; cases may set DIAGRAM flags or
// DEFAULT_HIDE to reach a branch the example model leaves untaken, restoring
// them before they return.

import { render } from "htm/preact/standalone";

export const CASES = {
  graph: [],
  state: [],
  diagram: [],
  attributes: [],
  panel: [],
};

const add = (group, name, fn) => CASES[group].push({ name, fn });

// Sets read best sorted, and sorted() keeps expected.json free of them.
const sorted = (set) => [...set].sort();
// The result of a view function, as comparable text: the old code returned
// an HTML string, the new code returns DOM nodes, and ser() reads both the
// same way, against the same golden.
const ser = (v) => {
  if (typeof v === "string") return v;
  if (Array.isArray(v)) return v.map(ser).join("");
  if (v && v.nodeType) return v.outerHTML; // a DOM node
  const host = document.createElement("div"); // a preact vnode
  render(v, host);
  return host.innerHTML;
};
const serGraph = (g) => ({
  nodes: sorted(g.nodes),
  childOf: g.childOf,
  edges: g.edges.map((e) => ({
    from: e.from,
    to: e.to,
    styles: sorted(e.styles),
    via: e.via,
  })),
});
// The state a view of the page is in, shaped like state() builds it.
const st = (
  level,
  focus,
  depth = 1,
  dir = "both",
  display = {},
  hide = [],
) => ({ level, focus, depth, dir, display, hide: new Set(hide) });
const serDiagram = (api) => (s) => {
  const { source, visible, tips } = api.mermaidSource(s);
  return { source, visible: sorted(visible), tips };
};

// ---------------------------------------------------------------- graph ----

add("graph", "graphs", (api) => ({
  context: serGraph(api.GRAPHS.context),
  domain: serGraph(api.GRAPHS.domain),
  "levelGraph-domain": serGraph(api.levelGraph("domain")),
}));

add("graph", "descendants", (api) => {
  const at = (g, ids) =>
    Object.fromEntries(ids.map((id) => [id, sorted(api.descendants(g, [id]))]));
  return {
    context: at(api.GRAPHS.context, ["catalog", "orders", "foundations"]),
    domain: at(api.GRAPHS.domain, ["foundations"]),
  };
});

add("graph", "focus-sets", (api) => {
  const at = (level, ids) =>
    Object.fromEntries(ids.map((id) => [id, sorted(api.focusSet(level, id))]));
  return {
    context: at("context", [
      "foundations",
      "identity",
      "payments",
      "catalog",
      "browsing",
      "checkout",
      "crm",
    ]),
    domain: at("domain", ["foundations", "catalog", "checkout", "crm"]),
  };
});

add("graph", "walks", (api) => {
  const g = api.GRAPHS.context;
  const w = (starts, depth, dir, hidden) =>
    sorted(api.walk(g, starts, depth, dir, new Set(hidden)));
  return {
    "whole-system": w(new Set(), 1, "both", []),
    "checkout-d1": w(api.focusSet("context", "checkout"), 1, "both", []),
    "checkout-d2": w(api.focusSet("context", "checkout"), 2, "both", []),
    "checkout-d99": w(api.focusSet("context", "checkout"), 99, "both", []),
    "checkout-up-d99": w(api.focusSet("context", "checkout"), 99, "up", []),
    "checkout-down-d99": w(api.focusSet("context", "checkout"), 99, "down", []),
    "catalog-d1": w(api.focusSet("context", "catalog"), 1, "both", []),
    "foundations-d1": w(api.focusSet("context", "foundations"), 1, "both", []),
    "orders-d99-hide-crm": w(api.focusSet("context", "orders"), 99, "both", [
      "crm",
    ]),
    "orders-d99-hide-payments": w(
      api.focusSet("context", "orders"),
      99,
      "both",
      ["payments"],
    ),
    // A start is never hidden, not even by `hide`.
    "start-in-hidden": w(new Set(["payments"]), 99, "both", ["payments"]),
    "domain-orders-d99": sorted(
      api.walk(
        api.GRAPHS.domain,
        api.focusSet("domain", "orders"),
        99,
        "both",
        new Set(),
      ),
    ),
  };
});

add("graph", "relations", (api) =>
  Object.fromEntries(
    ["checkout", "browsing", "orders", "crm"].map((id) => [
      id,
      api.relations(id),
    ]),
  ),
);

add("graph", "node-items", (api) =>
  Object.fromEntries(
    Object.entries(api.itemOfNode).map(([node, item]) => [node, item.name]),
  ),
);

// ---------------------------------------------------------------- state ----

add("state", "hash-defaults", (api) => api.hashFor(st("context", "")) || "");
add("state", "hash-focused", (api) =>
  api.hashFor(
    st("context", "checkout", 2, "up", { foundations: "contents" }, ["crm"]),
  ),
);
add("state", "hash-domain", (api) => api.hashFor(st("domain", "orders")));
add("state", "hash-depth", (api) => api.hashFor(st("context", "", 3)));
// A display only travels when it deviates from the default: foundations
// defaults to collapsed, so expanded goes in the URL.
add("state", "hash-display-deviation", (api) =>
  api.hashFor(st("context", "", 1, "both", { foundations: "expanded" })),
);
add("state", "hash-default-hide", (api) => {
  api.DEFAULT_HIDE.add("crm");
  try {
    return {
      // What `hide` keeps out comes back as `hide.<id>=0`, and a default
      // hide that holds stays silent.
      "un-hidden-default": api.hashFor(
        st("context", "", 1, "both", {}, ["checkout"]),
      ),
      "re-hidden-default": api.hashFor(
        st("context", "", 1, "both", {}, ["checkout", "crm"]),
      ),
    };
  } finally {
    api.DEFAULT_HIDE.delete("crm");
  }
});
add("state", "clamp-depth", (api) =>
  Object.fromEntries(
    ["", "abc", "0", "-2", "2.7", "3", null, undefined, "  4 "].map((raw) => [
      JSON.stringify(raw),
      api.clampDepth(raw),
    ]),
  ),
);

// -------------------------------------------------------------- diagram ----

{
  const d = serDiagram;
  add("diagram", "whole-system-context", (api) => d(api)(st("context", "")));
  add("diagram", "whole-system-domain", (api) => d(api)(st("domain", "")));
  add("diagram", "focus-checkout-d1", (api) =>
    d(api)(st("context", "checkout")),
  );
  add("diagram", "focus-checkout-d99", (api) =>
    d(api)(st("context", "checkout", 99)),
  );
  add("diagram", "focus-catalog-d1", (api) => d(api)(st("context", "catalog")));
  add("diagram", "focus-foundations-d1", (api) =>
    d(api)(st("context", "foundations")),
  );
  add("diagram", "cluster-contents", (api) =>
    d(api)(st("context", "", 1, "both", { foundations: "contents" })),
  );
  add("diagram", "catalog-collapsed", (api) =>
    d(api)(st("context", "", 1, "both", { catalog: "collapsed" })),
  );
  add("diagram", "hide-crm", (api) =>
    d(api)(st("context", "", 1, "both", {}, ["crm"])),
  );
  add("diagram", "hide-catalog", (api) =>
    d(api)(st("context", "", 1, "both", {}, ["catalog"])),
  );
  // The focus itself is never hidden.
  add("diagram", "focus-never-hidden", (api) =>
    d(api)(st("context", "checkout", 1, "both", {}, ["checkout"])),
  );
  add("diagram", "single-domain-domain-level", (api) =>
    d(api)(st("domain", "crm")),
  );
  add("diagram", "group-by-type", (api) => {
    api.DIAGRAM.group_by_type = true;
    try {
      return d(api)(st("domain", ""));
    } finally {
      api.DIAGRAM.group_by_type = false;
    }
  });
  add("diagram", "child-labels-off", (api) => {
    api.DIAGRAM.child_labels = false;
    try {
      return d(api)(st("context", "", 1, "both", { catalog: "collapsed" }));
    } finally {
      api.DIAGRAM.child_labels = true;
    }
  });
}

// ------------------------------------------------------------ attributes ----

add("attributes", "text", (api) => ({
  text: api.attributeText("identity-service"),
  list: api.attributeText(["Order", "Cart"]),
  map: api.attributeText(api.contextById.payments.attributes.metadata),
  nested: api.attributeText([["a", "b"], { x: "y" }]),
  number: api.attributeText(3),
  deep: api.attributeText({ a: { b: 1 } }),
}));

add("attributes", "entries", (api) =>
  Object.fromEntries(
    ["checkout", "identity", "payments"].map((id) => [
      id,
      api.attributeEntries(api.contextById[id]),
    ]),
  ),
);

add("attributes", "rows", (api) => ({
  checkout: ser(api.attributeRows(api.contextById.checkout)),
  payments: ser(api.attributeRows(api.contextById.payments)),
}));

add("attributes", "section", (api) => ({
  checkout: ser(api.attributeSection(api.contextById.checkout)),
  crm: ser(api.attributeSection(api.domainById.crm)),
}));

add("attributes", "box-tips", (api) => {
  const entries = (id) =>
    api.boxTipEntries(
      api.contextById[id] || api.domainById[id] || api.clusterById[id],
    );
  return {
    checkout: entries("checkout"), // a description and two attributes
    browsing: entries("browsing"), // attributes only
    search: entries("search"), // neither
    cluster: entries("foundations"),
    "tooltips-off": (() => {
      api.DIAGRAM.attribute_tooltips = false;
      try {
        return entries("browsing");
      } finally {
        api.DIAGRAM.attribute_tooltips = true;
      }
    })(),
  };
});

add("attributes", "tip-entry", (api) =>
  api.tipEntry({
    from: "catalog",
    to: "checkout",
    style: "dotted",
    comment: "Reads prices and availability at checkout time.",
  }),
);

// ---------------------------------------------------------------- panel ----
// renderInfo renders the side panel into #info; the panel cases read the
// DOM back from there, so the goldens pin the panel's exact DOM through the
// rewrite. The block keeps the panel's own render out of the way of the
// preact one the ser() helper above uses.

{
  const render = (api, s) => {
    api.renderInfo(s, api.mermaidSource(s).visible);
    return document.getElementById("info").innerHTML;
  };

  add("panel", "whole-system", (api) => render(api, st("context", "")));
  add("panel", "focus-checkout", (api) =>
    render(api, st("context", "checkout")),
  );
  add("panel", "focus-checkout-hidden-neighbor", (api) =>
    render(api, st("context", "checkout", 1, "both", {}, ["payments"])),
  );
  add("panel", "focus-orders", (api) =>
    render(api, st("context", "orders", 99)),
  );
  add("panel", "focus-crm", (api) => render(api, st("context", "crm")));
  add("panel", "focus-fulfillment", (api) =>
    render(api, st("context", "fulfillment", 99)),
  );
  add("panel", "focus-foundations-hidden-member", (api) =>
    render(api, st("context", "foundations", 1, "both", {}, ["identity"])),
  );
}
