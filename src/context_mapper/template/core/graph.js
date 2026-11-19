import {
  MODEL,
  domainById,
  clusterById,
  owner,
  nameOf,
  isMulti,
} from "./model.js";

// Same graphs as graph.py: context level as written, domain level lifted and merged.
// childOf says which container a node renders inside: a context inside its domain, a member inside its cluster.
export function levelGraph(level) {
  const childOf = {};
  MODEL.domains
    .filter((d) => d.cluster)
    .forEach((d) => (childOf[d.id] = d.cluster));
  if (level === "context") {
    const nodes = new Set([
      ...MODEL.contexts.map((c) => c.id),
      ...MODEL.domains.filter((d) => !d.single).map((d) => d.id),
    ]);
    MODEL.contexts
      .filter((c) => !domainById[c.domain].single)
      .forEach((c) => (childOf[c.id] = c.domain));
    return {
      nodes,
      childOf,
      edges: MODEL.edges.map((e) => ({
        from: e.from,
        to: e.to,
        styles: new Set([e.style]),
        via: [e],
      })),
    };
  }
  const merged = new Map();
  MODEL.edges.forEach((e) => {
    const a = owner[e.from],
      b = owner[e.to];
    if (a === b) return;
    const key = a + "|" + b;
    if (!merged.has(key))
      merged.set(key, { from: a, to: b, styles: new Set(), via: [] });
    merged.get(key).styles.add(e.style);
    merged.get(key).via.push(e);
  });
  return {
    nodes: new Set(MODEL.domains.map((d) => d.id)),
    childOf,
    edges: [...merged.values()],
  };
}
export const GRAPHS = {
  context: levelGraph("context"),
  domain: levelGraph("domain"),
};

// A container and everything rendered inside it.
export function descendants(g, ids) {
  const kids = {};
  Object.entries(g.childOf).forEach(([c, p]) =>
    (kids[p] = kids[p] || []).push(c),
  );
  const out = new Set();
  const stack = [...ids];
  while (stack.length) {
    const n = stack.pop();
    if (out.has(n)) continue;
    out.add(n);
    stack.push(...(kids[n] || []));
  }
  return out;
}

export function focusSet(level, focus) {
  if (!focus) return new Set();
  if (clusterById[focus]) {
    const starts = new Set([focus, ...clusterById[focus].members]);
    if (level === "context")
      clusterById[focus].members.forEach((m) =>
        domainById[m].contexts.forEach((c) => starts.add(c)),
      );
    return starts;
  }
  if (level === "domain") return new Set([owner[focus]]);
  if (isMulti(focus)) return new Set([focus, ...domainById[focus].contexts]);
  return new Set([focus]);
}

export function walk(g, starts, depth, dir, hidden) {
  const allowed = (n) => starts.has(n) || !hidden.has(n);
  if (!starts.size) return new Set([...g.nodes].filter(allowed));
  const up = {},
    down = {};
  g.nodes.forEach((n) => {
    up[n] = [];
    down[n] = [];
  });
  g.edges.forEach((e) => {
    up[e.from].push(e.to);
    down[e.to].push(e.from);
  });
  const seen = new Set(starts);
  const go = (next) => {
    let frontier = [...starts];
    for (let i = 0; i < depth && frontier.length; i++) {
      const nf = [];
      // Reaching a container reaches what it holds, at the same hop.
      frontier.forEach((n) =>
        (next[n] || []).forEach((m) =>
          descendants(g, [m]).forEach((r) => {
            if (!seen.has(r) && allowed(r)) {
              seen.add(r);
              nf.push(r);
            }
          }),
        ),
      );
      frontier = nf;
    }
  };
  if (dir !== "down") go(up);
  if (dir !== "up") go(down);
  return seen;
}

export function relations(id) {
  const g = isMulti(id) ? GRAPHS.domain : GRAPHS.context;
  const byName = (a, b) => nameOf(a).localeCompare(nameOf(b));
  return {
    ups: g.edges
      .filter((e) => e.from === id)
      .map((e) => e.to)
      .sort(byName),
    downs: g.edges
      .filter((e) => e.to === id)
      .map((e) => e.from)
      .sort(byName),
  };
}
