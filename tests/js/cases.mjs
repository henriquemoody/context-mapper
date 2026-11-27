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

// The edges behind a relation list carry the roles: a context's own, a
// domain's merged — kept only where every dependency it stands for agrees.
add("graph", "relation-edges", (api) => {
  const shape = (edges) =>
    edges.map((e) => ({
      from: e.from,
      to: e.to,
      upstream: e.upstream,
      downstream: e.downstream,
    }));
  return Object.fromEntries(
    ["checkout", "fulfillment", "orders", "crm"].map((id) => {
      const { ups, downs } = api.relationEdges(id);
      return [id, { ups: shape(ups), downs: shape(downs) }];
    }),
  );
});

add("graph", "role-text", (api) => ({
  both: api.roleText({
    upstream: ["OpenHostService", "PublishedLanguage"],
    downstream: ["AnticorruptionLayer"],
  }),
  "upstream-only": api.roleText({
    upstream: ["Supplier"],
    downstream: [],
  }),
  "downstream-only": api.roleText({ downstream: ["Conformist"] }),
  none: api.roleText({ upstream: [], downstream: [] }),
  codes: api.roleCodes({
    upstream: ["OpenHostService", "PublishedLanguage"],
    downstream: ["AnticorruptionLayer"],
  }),
}));

// A merged edge keeps roles only when every dependency carries the same ones.
add("graph", "shared-roles", (api) => {
  const same = { upstream: ["Supplier"], downstream: ["Customer"] };
  const none = { upstream: [], downstream: [] };
  return {
    same: api.sharedRoles([same, { ...same }]),
    "one-with-one-without": api.sharedRoles([same, none]),
    "no-roles-at-all": api.sharedRoles([none, none]),
    "different-roles": api.sharedRoles([
      same,
      { upstream: ["OpenHostService"], downstream: ["Customer"] },
    ]),
    single: api.sharedRoles([same]),
  };
});

// Partnerships and shared kernels: at context level as written, at domain
// level lifted — the same kind between the same two domains becomes one, with
// every comment kept, and one inside a domain goes.
add("graph", "links", (api) => {
  const shape = (g) =>
    g.links.map((l) => ({
      kind: l.kind,
      a: l.a,
      b: l.b,
      via: l.via.map((r) => r.comment),
    }));
  return {
    context: shape(api.GRAPHS.context),
    domain: shape(api.GRAPHS.domain),
  };
});

// A focus walks across a link in every direction, since it is a dependency
// both ways.
add("graph", "link-walks", (api) => {
  const w = (level, focus, depth, dir) =>
    sorted(
      api.walk(
        api.GRAPHS[level],
        api.focusSet(level, focus),
        depth,
        dir,
        new Set(),
      ),
    );
  return Object.fromEntries(
    ["both", "up", "down"].flatMap((dir) => [
      [`search-${dir}`, w("context", "search", 1, dir)],
      [`crm-${dir}`, w("context", "crm", 1, dir)],
      [`catalog-domain-${dir}`, w("domain", "catalog", 1, dir)],
    ]),
  );
});

add("graph", "link-relations", (api) =>
  Object.fromEntries(
    [
      "search",
      "browsing",
      "checkout",
      "crm",
      "payments",
      "catalog",
      "orders",
    ].map((id) => [id, api.linkRelations(id)]),
  ),
);

// The events of the model as data: a label, and what goes through a set of
// dependencies, each once.
add("graph", "events", (api) => {
  const edge = (from, to) =>
    api.MODEL.edges.find((e) => e.from === from && e.to === to);
  return {
    labels: [
      api.eventLabel({ name: "OrderPlaced", aggregate: "Order" }),
      api.eventLabel({ name: "KeysRotated", aggregate: null }),
    ],
    "checkout-identity": api.crossing([edge("checkout", "identity")]),
    // Several dependencies, an event that goes through two of them once.
    "orders-payments": api.crossing([
      edge("checkout", "payments"),
      edge("fulfillment", "payments"),
    ]),
    none: api.crossing([edge("crm", "identity"), { from: "x", to: "y" }]),
    tip: api.eventsTipEntries([
      edge("checkout", "payments"),
      edge("fulfillment", "payments"),
    ]),
    "no-tip": api.eventsTipEntries([{ from: "x", to: "y" }]),
    "partnership-both-ways": api.crossing(
      api.MODEL.symmetric.filter((r) => r.kind === "partnership"),
    ),
  };
});

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
// The aggregate level travels in the hash like the domain level does.
add("state", "hash-aggregate", (api) => api.hashFor(st("aggregate", "")));
add("state", "hash-aggregate-focused", (api) =>
  api.hashFor(st("aggregate", "checkout", 2)),
);
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
  // An edge to a collapsed container merges what it holds. With the cluster
  // open, Orders folds Checkout and Fulfillment: Identity reaches only
  // Checkout, so it keeps its roles toward Orders; Payments reaches both, one
  // with roles and one without, so it loses them.
  const ordersFolded = { foundations: "expanded", orders: "collapsed" };
  add("diagram", "roles-collapsed-merge", (api) =>
    d(api)(st("context", "", 1, "both", ordersFolded)),
  );
  add("diagram", "roles-collapsed-merge-no-child-labels", (api) => {
    api.DIAGRAM.child_labels = false;
    try {
      return d(api)(st("context", "", 1, "both", ordersFolded));
    } finally {
      api.DIAGRAM.child_labels = true;
    }
  });
  add("diagram", "roles-labels-off", (api) => {
    api.DIAGRAM.relationship_labels = false;
    try {
      return d(api)(st("context", "checkout"));
    } finally {
      api.DIAGRAM.relationship_labels = true;
    }
  });
  // Partnerships and shared kernels: lines with no heads, after the violations,
  // counted by linkStyle like the rest; folded boxes merge the ones of a kind
  // between the same two boxes, and name what they hold.
  add("diagram", "links-focus-search", (api) =>
    d(api)(st("context", "search")),
  );
  add("diagram", "links-both-collapsed", (api) =>
    d(api)(
      st("context", "", 1, "both", {
        catalog: "collapsed",
        orders: "collapsed",
      }),
    ),
  );
  add("diagram", "links-labels-off", (api) => {
    api.DIAGRAM.relationship_labels = false;
    try {
      return d(api)(st("context", "search"));
    } finally {
      api.DIAGRAM.relationship_labels = true;
    }
  });
  add("diagram", "links-child-labels-off", (api) => {
    api.DIAGRAM.child_labels = false;
    try {
      return d(api)(
        st("context", "", 1, "both", {
          catalog: "collapsed",
          orders: "collapsed",
        }),
      );
    } finally {
      api.DIAGRAM.child_labels = true;
    }
  });
  // A shared kernel beside a dependency rides on its arrow: the kernel's
  // style laid over the dependency's own, so a dotted arrow stays dotted, and
  // a mark for the page's badge instead of a middle label.
  add("diagram", "kernel-on-a-dotted-arrow", (api) => {
    const links = api.GRAPHS.context.links;
    links.push({
      kind: "sharedKernel",
      a: "checkout",
      b: "catalog",
      via: [
        { kind: "sharedKernel", a: "checkout", b: "catalog", comment: "x" },
      ],
    });
    try {
      return d(api)(st("context", "checkout"));
    } finally {
      links.pop();
    }
  });
  add("diagram", "kernel-labels-off", (api) => {
    api.DIAGRAM.relationship_labels = false;
    try {
      return d(api)(st("context", "fulfillment"));
    } finally {
      api.DIAGRAM.relationship_labels = true;
    }
  });
  add("diagram", "kernel-on-the-arrow-focus-fulfillment", (api) =>
    d(api)(
      st("context", "fulfillment", 1, "both", { foundations: "expanded" }),
    ),
  );
  // The aggregate level walks the context graph and draws the contexts it
  // reached around their aggregates: the arrows between contexts keep the
  // indexes they have at the context level, and the references between
  // aggregates come after all of them.
  add("diagram", "aggregates-whole-system", (api) =>
    d(api)(st("aggregate", "", 1, "both", { foundations: "expanded" })),
  );
  add("diagram", "aggregates-focus-checkout", (api) =>
    d(api)(st("aggregate", "checkout", 1, "both", { foundations: "expanded" })),
  );
  add("diagram", "aggregates-focus-checkout-collapsed-foundations", (api) =>
    d(api)(st("aggregate", "checkout")),
  );
  add("diagram", "aggregates-focus-fulfillment", (api) =>
    d(api)(
      st("aggregate", "fulfillment", 1, "both", { foundations: "expanded" }),
    ),
  );
  add("diagram", "aggregates-focus-crm-d99", (api) =>
    d(api)(st("aggregate", "crm", 99, "both", { foundations: "expanded" })),
  );
  // A collapsed domain is one box, with no aggregates drawn inside it.
  add("diagram", "aggregates-collapsed-orders", (api) =>
    d(api)(
      st("aggregate", "", 1, "both", {
        foundations: "expanded",
        orders: "collapsed",
      }),
    ),
  );
  add("diagram", "aggregates-contents", (api) =>
    d(api)(
      st("aggregate", "", 1, "both", {
        foundations: "contents",
        catalog: "contents",
      }),
    ),
  );
  add("diagram", "aggregates-hide-checkout", (api) =>
    d(api)(
      st("aggregate", "payments", 99, "both", { foundations: "expanded" }, [
        "checkout",
      ]),
    ),
  );
  add("diagram", "aggregates-labels-off", (api) => {
    api.DIAGRAM.relationship_labels = false;
    try {
      return d(api)(
        st("aggregate", "checkout", 1, "both", { foundations: "expanded" }),
      );
    } finally {
      api.DIAGRAM.relationship_labels = true;
    }
  });
  // The events that cross an arrow are in its tooltip, the dependency's own
  // entries first. At domain level and in a collapsed container they are
  // gathered from every dependency the arrow stands for; a partnership line
  // lists the ones that cross it in either direction.
  add("diagram", "events-focus-checkout", (api) =>
    d(api)(st("context", "checkout", 1, "both", { foundations: "expanded" })),
  );
  add("diagram", "events-domain-level", (api) => d(api)(st("domain", "")));
  add("diagram", "events-collapsed-orders", (api) =>
    d(api)(
      st("context", "", 1, "both", {
        foundations: "expanded",
        orders: "collapsed",
      }),
    ),
  );
  add("diagram", "events-partnership-lines", (api) =>
    d(api)(
      st("context", "fulfillment", 1, "both", { foundations: "expanded" }),
    ),
  );
  add("diagram", "events-aggregates-level", (api) =>
    d(api)(st("aggregate", "checkout", 1, "both", { foundations: "expanded" })),
  );
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

// A tooltip spells out the roles with their display names, with the comment.
add("attributes", "tip-entry-roles", (api) => ({
  both: api.tipEntry({
    from: "identity",
    to: "checkout",
    comment: "Creates an account for guests who check out.",
    upstream: ["OpenHostService", "PublishedLanguage"],
    downstream: ["AnticorruptionLayer"],
  }),
  "roles-only": api.tipEntry({
    from: "payments",
    to: "checkout",
    comment: null,
    upstream: ["Supplier"],
    downstream: ["Customer"],
  }),
}));

// A link's tooltip names its kind and the two ends, and carries the comment.
add("attributes", "link-tip-entry", (api) => ({
  partnership: api.linkTipEntry({
    kind: "partnership",
    a: "search",
    b: "checkout",
    comment: "Search and Checkout plan the cart together.",
  }),
  "shared-kernel-no-comment": api.linkTipEntry({
    kind: "sharedKernel",
    a: "crm",
    b: "payments",
    comment: null,
  }),
}));

// A bounded context's tooltip lists the names of its aggregates after its
// attributes; an aggregate's own tooltip is its description and what it holds.
add("attributes", "aggregate-tips", (api) => {
  const context = (id) => api.boxTipEntries(api.contextById[id]);
  const aggregate = (id, name) =>
    api.aggregateTipEntries(
      api.contextById[id].aggregates.find((a) => a.name === name),
    );
  const off = (fn) => {
    api.DIAGRAM.attribute_tooltips = false;
    try {
      return fn();
    } finally {
      api.DIAGRAM.attribute_tooltips = true;
    }
  };
  return {
    checkout: context("checkout"), // a description, attributes and aggregates
    payments: context("payments"), // a single domain: the aggregates are its context's
    search: context("search"),
    "domain-with-contexts": api.boxTipEntries(api.domainById.orders),
    "tooltips-off": off(() => context("checkout")),
    order: aggregate("checkout", "Order"),
    cart: aggregate("checkout", "Cart"),
    account: aggregate("identity", "Account"),
    "aggregate-tooltips-off": off(() => aggregate("checkout", "Order")),
    "reference-same-context": api.referenceTipEntry(
      "checkout",
      { name: "Cart" },
      { context: "checkout", name: "Order" },
    ),
    "reference-other-context": api.referenceTipEntry(
      "checkout",
      { name: "Cart" },
      { context: "browsing", name: "Session" },
    ),
  };
});

// The tooltip of a box lists the names of the events it publishes and
// consumes; an attribute_tooltips of false takes the rows away.
add("attributes", "event-tips", (api) => {
  const off = (fn) => {
    api.DIAGRAM.attribute_tooltips = false;
    try {
      return fn();
    } finally {
      api.DIAGRAM.attribute_tooltips = true;
    }
  };
  const aggregate = (id, name) =>
    api.aggregateTipEntries(
      api.contextById[id].aggregates.find((a) => a.name === name),
    );
  return {
    "context-checkout": api.boxTipEntries(api.contextById.checkout),
    "context-search": api.boxTipEntries(api.contextById.search),
    "domain-orders": api.boxTipEntries(api.domainById.orders),
    "single-domain-identity": api.boxTipEntries(api.domainById.identity),
    "aggregate-order": aggregate("checkout", "Order"),
    "aggregate-account": aggregate("identity", "Account"),
    "context-off": off(() => api.boxTipEntries(api.contextById.checkout)),
    "aggregate-off": off(() => aggregate("checkout", "Order")),
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
  add("panel", "focus-search", (api) => render(api, st("context", "search")));
  // Events: an aggregate's two lists are rows of its block, a context's and
  // a domain's are sections of their own, each only when it has something.
  add("panel", "focus-orders-events", (api) =>
    render(api, st("context", "orders")),
  );
  add("panel", "focus-identity-events", (api) =>
    render(api, st("context", "identity")),
  );
  add("panel", "focus-browsing-events", (api) =>
    render(api, st("context", "browsing")),
  );
  // The aggregates of a bounded context: a single domain has them too, and a
  // reference to another context's aggregate is a link that focuses it.
  add("panel", "focus-payments-aggregates", (api) =>
    render(api, st("aggregate", "payments")),
  );
  add("panel", "focus-crm-aggregates", (api) =>
    render(api, st("aggregate", "crm")),
  );
  add("panel", "focus-domain-without-aggregates", (api) =>
    render(api, st("aggregate", "orders")),
  );
  add("panel", "focus-catalog-domain", (api) =>
    render(api, st("context", "catalog")),
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
