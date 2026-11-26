import {
  MODEL,
  domainById,
  clusterById,
  owner,
  nameOf,
  isMulti,
} from "./model.js";
import { sharedRoles } from "./roles.js";

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
        upstream: e.upstream,
        downstream: e.downstream,
      })),
      violations: MODEL.violations.map((r) => ({
        from: r.from,
        to: r.to,
        via: [r],
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
  // A merged edge keeps the roles its dependencies all carry, exactly, and
  // none otherwise.
  merged.forEach((entry) => Object.assign(entry, sharedRoles(entry.via)));
  // A violation between two domains stands for the ones between what they
  // hold, and goes when the domains depend that way anyway.
  const violations = new Map();
  MODEL.violations.forEach((r) => {
    const a = owner[r.from],
      b = owner[r.to];
    const key = a + "|" + b;
    if (a === b || merged.has(key)) return;
    if (!violations.has(key)) violations.set(key, { from: a, to: b, via: [] });
    violations.get(key).via.push(r);
  });
  return {
    nodes: new Set(MODEL.domains.map((d) => d.id)),
    childOf,
    edges: [...merged.values()],
    violations: [...violations.values()],
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

// The edges of an item's direct dependencies, each side sorted by the name of
// the one at the other end: the item's upstreams (edges it is the downstream
// of) and its downstreams. A domain's are lifted to domain level.
export function relationEdges(id) {
  const g = isMulti(id) ? GRAPHS.domain : GRAPHS.context;
  const by = (end) => (a, b) => nameOf(a[end]).localeCompare(nameOf(b[end]));
  return {
    ups: g.edges.filter((e) => e.from === id).sort(by("to")),
    downs: g.edges.filter((e) => e.to === id).sort(by("from")),
  };
}

export function relations(id) {
  const { ups, downs } = relationEdges(id);
  return { ups: ups.map((e) => e.to), downs: downs.map((e) => e.from) };
}
