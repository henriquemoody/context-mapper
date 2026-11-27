var __defProp = Object.defineProperty;
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};

// src/context_mapper/template/app.js
import mermaid, { elkLayouts } from "./mermaid.js";

// src/context_mapper/template/core/model.js
var MODEL = globalThis.contextMapperModel ?? null;
var domainById = Object.fromEntries(
  MODEL.domains.map((d2) => [d2.id, d2])
);
var contextById = Object.fromEntries(
  MODEL.contexts.map((c2) => [c2.id, c2])
);
var clusterById = Object.fromEntries(
  MODEL.clusters.map((c2) => [c2.id, c2])
);
var owner = {};
MODEL.contexts.forEach((c2) => owner[c2.id] = c2.domain);
MODEL.domains.forEach((d2) => owner[d2.id] = d2.id);
var nameOf = (id) => (contextById[id] || domainById[id]).name;
var isMulti = (id) => domainById[id] && !domainById[id].single;
var DIAGRAM = MODEL.mermaid;
var defaultDisplayOf = (id) => (clusterById[id] || domainById[id]).defaultDisplay || "expanded";
var STYLE_HIDE = DIAGRAM.hide || [];
var defaultMode = (id) => {
  const d2 = DIAGRAM.display;
  if (d2 === null || d2 === void 0) return defaultDisplayOf(id);
  return typeof d2 === "object" ? d2[id] || defaultDisplayOf(id) : d2;
};
var MODES = [
  ["expanded", "Expanded"],
  ["collapsed", "Collapsed"],
  ["contents", "Contents"],
  ["hidden", "Hidden"]
];
var DEFAULT_HIDE = /* @__PURE__ */ new Set([
  ...STYLE_HIDE,
  ...MODEL.contexts.filter((c2) => c2.defaultDisplay === "hidden").map((c2) => c2.id)
]);

// src/context_mapper/template/core/state.js
var LEVELS = ["context", "domain", "aggregate"];
var clampDepth = (raw) => Math.max(1, Math.trunc(Number(raw) || 1));
function hashFor(s2) {
  const p2 = new URLSearchParams();
  if (s2.level !== "context") p2.set("level", s2.level);
  if (s2.focus) p2.set("focus", s2.focus);
  if (s2.depth !== 1) p2.set("depth", s2.depth);
  if (s2.dir !== "both") p2.set("dir", s2.dir);
  Object.entries(s2.display).forEach(([id, mode]) => {
    if (mode !== defaultMode(id) && !s2.hide.has(id))
      p2.set("display." + id, mode);
  });
  s2.hide.forEach((id) => {
    if (!DEFAULT_HIDE.has(id)) p2.set("hide." + id, "1");
  });
  DEFAULT_HIDE.forEach((id) => {
    if (!s2.hide.has(id)) p2.set("hide." + id, "0");
  });
  const h2 = p2.toString();
  return h2 ? "#" + h2 : "";
}
function parseHash(hash) {
  const p2 = new URLSearchParams(hash);
  const containers = [
    ...MODEL.domains.filter((d2) => !d2.single).map((d2) => d2.id),
    ...MODEL.clusters.map((c2) => c2.id)
  ];
  const hide = new Set(DEFAULT_HIDE);
  for (const [key, value] of p2) {
    const m2 = /^hide\.(.+)$/.exec(key);
    if (!m2) continue;
    if (value === "1") hide.add(m2[1]);
    else if (value === "0") hide.delete(m2[1]);
  }
  const display = Object.fromEntries(
    containers.map((id) => {
      const m2 = p2.get("display." + id);
      return [id, MODES.some(([value]) => value === m2) ? m2 : defaultMode(id)];
    })
  );
  containers.forEach((id) => {
    if (hide.has(id)) display[id] = "hidden";
  });
  return {
    level: LEVELS.includes(p2.get("level")) ? p2.get("level") : "context",
    focus: p2.has("focus") && (owner[p2.get("focus")] || clusterById[p2.get("focus")]) ? p2.get("focus") : "",
    depth: clampDepth(p2.get("depth")),
    dir: p2.get("dir") || "both",
    display,
    hide
  };
}

// src/context_mapper/template/core/roles.js
var names = (ids) => (ids || []).map((id) => MODEL.roles[id].name).join(", ");
var codes = (ids) => (ids || []).map((id) => MODEL.roles[id].code);
var roleCodes = (edge) => [
  codes(edge.upstream),
  codes(edge.downstream)
];
function roleText(edge) {
  const up = names(edge.upstream);
  const down = names(edge.downstream);
  if (up && down) return `${up} \u2192 ${down}`;
  if (up) return `${up} (upstream)`;
  if (down) return `${down} (downstream)`;
  return "";
}
function sharedRoles(deps) {
  const keys = new Set(
    deps.map((d2) => JSON.stringify([d2.upstream || [], d2.downstream || []]))
  );
  if (keys.size !== 1) return { upstream: [], downstream: [] };
  const [upstream, downstream] = JSON.parse([...keys][0]);
  return { upstream, downstream };
}

// src/context_mapper/template/core/graph.js
function levelGraph(level) {
  const childOf = {};
  MODEL.domains.filter((d2) => d2.cluster).forEach((d2) => childOf[d2.id] = d2.cluster);
  if (level === "context") {
    const nodes = /* @__PURE__ */ new Set([
      ...MODEL.contexts.map((c2) => c2.id),
      ...MODEL.domains.filter((d2) => !d2.single).map((d2) => d2.id)
    ]);
    MODEL.contexts.filter((c2) => !domainById[c2.domain].single).forEach((c2) => childOf[c2.id] = c2.domain);
    return {
      nodes,
      childOf,
      edges: MODEL.edges.map((e2) => ({
        from: e2.from,
        to: e2.to,
        styles: /* @__PURE__ */ new Set([e2.style]),
        via: [e2],
        upstream: e2.upstream,
        downstream: e2.downstream
      })),
      violations: MODEL.violations.map((r2) => ({
        from: r2.from,
        to: r2.to,
        via: [r2]
      })),
      links: MODEL.symmetric.map((r2) => ({
        kind: r2.kind,
        a: r2.a,
        b: r2.b,
        via: [r2]
      }))
    };
  }
  const merged = /* @__PURE__ */ new Map();
  MODEL.edges.forEach((e2) => {
    const a2 = owner[e2.from], b2 = owner[e2.to];
    if (a2 === b2) return;
    const key = a2 + "|" + b2;
    if (!merged.has(key))
      merged.set(key, { from: a2, to: b2, styles: /* @__PURE__ */ new Set(), via: [] });
    merged.get(key).styles.add(e2.style);
    merged.get(key).via.push(e2);
  });
  merged.forEach((entry) => Object.assign(entry, sharedRoles(entry.via)));
  const violations = /* @__PURE__ */ new Map();
  MODEL.violations.forEach((r2) => {
    const a2 = owner[r2.from], b2 = owner[r2.to];
    const key = a2 + "|" + b2;
    if (a2 === b2 || merged.has(key)) return;
    if (!violations.has(key)) violations.set(key, { from: a2, to: b2, via: [] });
    violations.get(key).via.push(r2);
  });
  const links = /* @__PURE__ */ new Map();
  MODEL.symmetric.forEach((r2) => {
    const a2 = owner[r2.a], b2 = owner[r2.b];
    if (a2 === b2) return;
    const key = r2.kind + "|" + [a2, b2].sort().join("|");
    if (!links.has(key)) links.set(key, { kind: r2.kind, a: a2, b: b2, via: [] });
    links.get(key).via.push(r2);
  });
  return {
    nodes: new Set(MODEL.domains.map((d2) => d2.id)),
    childOf,
    edges: [...merged.values()],
    violations: [...violations.values()],
    links: [...links.values()]
  };
}
var GRAPHS = {
  context: levelGraph("context"),
  domain: levelGraph("domain")
};
function descendants(g2, ids) {
  const kids = {};
  Object.entries(g2.childOf).forEach(
    ([c2, p2]) => (kids[p2] = kids[p2] || []).push(c2)
  );
  const out = /* @__PURE__ */ new Set();
  const stack = [...ids];
  while (stack.length) {
    const n2 = stack.pop();
    if (out.has(n2)) continue;
    out.add(n2);
    stack.push(...kids[n2] || []);
  }
  return out;
}
function focusSet(level, focus) {
  if (!focus) return /* @__PURE__ */ new Set();
  if (clusterById[focus]) {
    const starts = /* @__PURE__ */ new Set([focus, ...clusterById[focus].members]);
    if (level === "context")
      clusterById[focus].members.forEach(
        (m2) => domainById[m2].contexts.forEach((c2) => starts.add(c2))
      );
    return starts;
  }
  if (level === "domain") return /* @__PURE__ */ new Set([owner[focus]]);
  if (isMulti(focus)) return /* @__PURE__ */ new Set([focus, ...domainById[focus].contexts]);
  return /* @__PURE__ */ new Set([focus]);
}
function walk(g2, starts, depth, dir, hidden) {
  const allowed = (n2) => starts.has(n2) || !hidden.has(n2);
  if (!starts.size) return new Set([...g2.nodes].filter(allowed));
  const up = {}, down = {};
  g2.nodes.forEach((n2) => {
    up[n2] = [];
    down[n2] = [];
  });
  g2.edges.forEach((e2) => {
    up[e2.from].push(e2.to);
    down[e2.to].push(e2.from);
  });
  g2.links.forEach((l2) => {
    [
      [l2.a, l2.b],
      [l2.b, l2.a]
    ].forEach(([one, other]) => {
      up[one].push(other);
      down[one].push(other);
    });
  });
  const seen = new Set(starts);
  const go = (next) => {
    const been = new Set(starts);
    let frontier = [...starts];
    for (let i2 = 0; i2 < depth && frontier.length; i2++) {
      const nf = [];
      frontier.forEach(
        (n2) => (next[n2] || []).forEach(
          (m2) => descendants(g2, [m2]).forEach((r2) => {
            if (!been.has(r2) && allowed(r2)) {
              been.add(r2);
              seen.add(r2);
              nf.push(r2);
            }
          })
        )
      );
      frontier = nf;
    }
  };
  if (dir !== "down") go(up);
  if (dir !== "up") go(down);
  return seen;
}
function relationEdges(id) {
  const g2 = isMulti(id) ? GRAPHS.domain : GRAPHS.context;
  const by = (end) => (a2, b2) => nameOf(a2[end]).localeCompare(nameOf(b2[end]));
  return {
    ups: g2.edges.filter((e2) => e2.from === id).sort(by("to")),
    downs: g2.edges.filter((e2) => e2.to === id).sort(by("from"))
  };
}
function linkRelations(id) {
  const g2 = isMulti(id) ? GRAPHS.domain : GRAPHS.context;
  const found = {};
  g2.links.filter((l2) => l2.a === id || l2.b === id).forEach(
    (l2) => (found[l2.kind] = found[l2.kind] || []).push(l2.a === id ? l2.b : l2.a)
  );
  Object.values(found).forEach(
    (ids) => ids.sort((x2, y2) => nameOf(x2).localeCompare(nameOf(y2)))
  );
  return found;
}

// src/context_mapper/template/core/events.js
var holderOf = (item) => contextById[item.id] || item;
var eventLabel = (event) => event.aggregate ? `${event.aggregate} \xB7 ${event.name}` : event.name;
function crossing(rules) {
  const byAddress = /* @__PURE__ */ new Map();
  rules.forEach(
    (rule) => (rule.events || []).forEach((event) => {
      if (!byAddress.has(event.address)) {
        const { consumer: consumer2, reason, description, ...own } = event;
        byAddress.set(event.address, {
          ...own,
          description,
          reasons: []
        });
      }
      const seen = byAddress.get(event.address);
      if (event.reason && !seen.reasons.includes(event.reason))
        seen.reasons.push(event.reason);
    })
  );
  return [...byAddress.values()].map(({ description, reasons, ...event }) => ({
    ...event,
    texts: reasons.length ? reasons : description ? [description] : []
  }));
}
function eventsTipEntries(rules) {
  const events = crossing(rules);
  if (!events.length) return [];
  const lines = events.flatMap(
    (event) => event.texts.length ? event.texts.map((text) => `${eventLabel(event)} \u2014 ${text}`) : [eventLabel(event)]
  );
  return [{ kind: "events", title: "Events", text: lines.join("\n") }];
}

// src/context_mapper/template/core/diagram.js
var nodeId = (id) => id.replace(/\W/g, "_");
var quote = (value) => value.replaceAll('"', "#quot;");
var itemOfNode = {};
[...MODEL.contexts, ...MODEL.domains, ...MODEL.clusters].forEach(
  (item) => itemOfNode[nodeId(item.id)] = item
);
var aggregateNode = (contextId, name) => `${nodeId(contextId)}__${nodeId(name)}`;
var aggregateOfNode = {};
MODEL.contexts.forEach(
  (c2) => (c2.aggregates || []).forEach(
    (a2) => aggregateOfNode[aggregateNode(c2.id, a2.name)] = {
      ...a2,
      context: c2.id
    }
  )
);
var AGGREGATE_STYLE = "fill:#ffffff,stroke:#6b6b6b,color:#1a1a1a";
var mergeStyles = (...styles) => {
  const merged = /* @__PURE__ */ new Map();
  styles.forEach(
    (style) => (style || "").split(",").filter(Boolean).forEach((part) => {
      const at = part.indexOf(":");
      merged.set(part.slice(0, at), part.slice(at + 1));
    })
  );
  return [...merged].map(([k2, v2]) => `${k2}:${v2}`).join(",");
};
var styleOf = (kind) => mergeStyles(...kind.split("+").map((k2) => DIAGRAM.edge_styles[k2] || ""));
function mermaidSource(s2) {
  const showAggregates = s2.level === "aggregate";
  const level = showAggregates ? "context" : s2.level;
  const g2 = GRAPHS[level];
  let starts = focusSet(level, s2.focus);
  const containers = [
    ...MODEL.domains.filter((d2) => !d2.single),
    ...MODEL.clusters
  ];
  const state2 = {};
  containers.forEach(
    (d2) => state2[d2.id] = starts.has(d2.id) ? "expanded" : s2.display[d2.id] || defaultMode(d2.id)
  );
  const hidden = descendants(g2, [
    ...containers.filter((d2) => state2[d2.id] === "hidden").map((d2) => d2.id),
    ...s2.hide
  ]);
  if (s2.focus) {
    starts = new Set([...starts].filter((id) => !hidden.has(id)));
    starts.add(s2.focus);
    if (level === "domain" && owner[s2.focus]) starts.add(owner[s2.focus]);
  }
  const visible = walk(g2, starts, s2.depth, s2.dir, hidden);
  const kidsOf = {};
  Object.entries(g2.childOf).forEach(
    ([c2, p2]) => (kidsOf[p2] = kidsOf[p2] || []).push(c2)
  );
  const held = (d2) => (level === "context" ? (d2.contexts || []).filter((c2) => c2 !== d2.id) : []).concat((d2.members || []).filter((m2) => m2 !== d2.id));
  const folded = {};
  const fold = (cid, into) => (kidsOf[cid] || []).forEach((child) => {
    if (starts.has(child)) return;
    if (visible.has(child)) folded[child] = into;
    fold(child, into);
  });
  const collapsedAncestor = (cid) => {
    let p2 = g2.childOf[cid];
    while (p2) {
      if (state2[p2] === "collapsed") return true;
      p2 = g2.childOf[p2];
    }
    return false;
  };
  containers.filter((d2) => state2[d2.id] === "collapsed" && !collapsedAncestor(d2.id)).forEach((d2) => fold(d2.id, d2.id));
  const lines = [
    "---",
    JSON.stringify({ config: DIAGRAM.config }),
    "---",
    `flowchart ${DIAGRAM.direction}`
  ];
  Object.entries(MODEL.types).forEach(
    ([id, t2]) => lines.push(`  classDef ${id} ${t2.mermaid_style}`)
  );
  lines.push(`  classDef focus ${DIAGRAM.focus_style}`);
  if (showAggregates) lines.push(`  classDef aggregate ${AGGREGATE_STYLE}`);
  const plainNodes = [];
  const drawn = /* @__PURE__ */ new Set();
  const aggregateNodes = {};
  const box = (id, label, type, indent) => {
    plainNodes.push(id);
    drawn.add(id);
    return `${indent}${nodeId(id)}["${label}"]${type ? ":::" + type : ""}`;
  };
  const drawAggregates = (item, indent) => {
    const out = [`${indent}subgraph ${nodeId(item.id)}["${quote(item.name)}"]`];
    contextById[item.id].aggregates.forEach((a2) => {
      const node = aggregateNode(item.id, a2.name);
      aggregateNodes[node] = item.id;
      out.push(`${indent}  ${node}["${quote(a2.name)}"]:::aggregate`);
    });
    out.push(`${indent}end`);
    drawn.add(item.id);
    let style = mergeStyles(
      MODEL.types[item.type]?.mermaid_style,
      item.mermaid_style
    );
    if (item.id === s2.focus) style = mergeStyles(style, DIAGRAM.focus_style);
    out.push(`${indent}style ${nodeId(item.id)} ${style}`);
    return out;
  };
  const drawChild = (c2, indent) => {
    if (contextById[c2] && !domainById[c2]) {
      if (showAggregates && contextById[c2].aggregates)
        return drawAggregates(contextById[c2], indent);
      const out = [
        box(c2, quote(contextById[c2].name), contextById[c2].type, indent)
      ];
      if (contextById[c2].mermaid_style)
        out.push(`${indent}style ${nodeId(c2)} ${contextById[c2].mermaid_style}`);
      return out;
    }
    return drawEntry(domainById[c2], indent);
  };
  function drawEntry(d2, indent) {
    if (folded[d2.id] || hidden.has(d2.id) && d2.id !== s2.focus) return [];
    const st = state2[d2.id] || "expanded";
    if (st === "hidden") return [];
    const isCluster = !domainById[d2.id];
    const kids = held(d2);
    const foldedKids = kids.filter((c2) => folded[c2] === d2.id);
    const inside = kids.filter((c2) => visible.has(c2) && !folded[c2]);
    if (isCluster) {
      if (st === "collapsed" && !foldedKids.length) return [];
      if (st === "expanded" && !inside.length && d2.id !== s2.focus) return [];
    } else if (!visible.has(d2.id) && !foldedKids.length && !inside.length && !kids.some((c2) => starts.has(c2))) {
      return [];
    }
    if (st === "contents") return inside.flatMap((c2) => drawChild(c2, indent));
    if (st === "expanded" && kids.length) {
      let show = inside;
      if (!show.length) {
        show = kids.filter(
          (c2) => !folded[c2] && (!hidden.has(c2) || starts.has(c2))
        );
      }
      if (show.length) {
        drawn.add(d2.id);
        const out2 = [`${indent}subgraph ${nodeId(d2.id)}["${quote(d2.name)}"]`];
        show.forEach((c2) => out2.push(...drawChild(c2, indent + "  ")));
        out2.push(`${indent}end`);
        let style = d2.mermaid_style || DIAGRAM.domain_style;
        if (d2.id === s2.focus) style += "," + DIAGRAM.focus_style;
        out2.push(`${indent}style ${nodeId(d2.id)} ${style}`);
        return out2;
      }
    }
    if (showAggregates && d2.single && contextById[d2.id].aggregates)
      return drawAggregates(d2, indent);
    let label = quote(d2.name);
    if (DIAGRAM.child_labels && !d2.single) {
      const named = (d2.contexts || []).filter((c2) => c2 !== d2.id && !hidden.has(c2)).map(nameOf).concat((d2.members || []).filter((m2) => folded[m2] === d2.id).map(nameOf)).sort();
      if (named.length)
        label = `<b>${label}</b><br/>${quote(named.join(", "))}`;
    }
    const out = [box(d2.id, label, d2.type, indent)];
    if (d2.mermaid_style)
      out.push(`${indent}style ${nodeId(d2.id)} ${d2.mermaid_style}`);
    return out;
  }
  const opens = new Set(
    Object.entries(state2).filter(([, st]) => st === "expanded" || st === "contents").map(([id]) => id).filter(
      (id) => (domainById[id] ? visible.has(id) : true) && !folded[id] && !hidden.has(id)
    )
  );
  const atTop = (d2) => !opens.has(g2.childOf[d2.id]);
  if (DIAGRAM.group_by_type) {
    Object.entries(MODEL.types).forEach(([typeId, t2]) => {
      const block = MODEL.domains.filter((d2) => d2.type === typeId && atTop(d2)).flatMap((d2) => drawEntry(d2, "    "));
      if (block.length)
        lines.push(
          `  subgraph type_${typeId}["${quote(t2.name)}"]`,
          ...block,
          "  end"
        );
    });
  } else {
    MODEL.domains.filter(atTop).forEach((d2) => lines.push(...drawEntry(d2, "  ")));
    MODEL.clusters.forEach((c2) => lines.push(...drawEntry(c2, "  ")));
  }
  const target = (n2) => folded[n2] || n2;
  const foldedBoxes = new Set(Object.values(folded));
  const merged = /* @__PURE__ */ new Map();
  g2.edges.forEach((e2) => {
    if (!visible.has(e2.from) || !visible.has(e2.to)) return;
    const a2 = target(e2.from), b2 = target(e2.to);
    if (a2 === b2 || !drawn.has(a2) || !drawn.has(b2)) return;
    const key = a2 + "|" + b2;
    if (!merged.has(key))
      merged.set(key, {
        a: a2,
        b: b2,
        styles: /* @__PURE__ */ new Set(),
        names: /* @__PURE__ */ new Set(),
        roles: /* @__PURE__ */ new Set(),
        via: []
      });
    const entry = merged.get(key);
    e2.styles.forEach((x2) => entry.styles.add(x2));
    entry.roles.add(JSON.stringify([e2.upstream || [], e2.downstream || []]));
    entry.via.push(...e2.via);
    if (foldedBoxes.has(b2)) entry.names.add(nameOf(e2.to));
    else if (foldedBoxes.has(a2)) entry.names.add(nameOf(e2.from));
  });
  const symmetric = /* @__PURE__ */ new Map();
  g2.links.forEach((l2) => {
    if (!visible.has(l2.a) || !visible.has(l2.b)) return;
    const a2 = target(l2.a), b2 = target(l2.b);
    if (a2 === b2 || !drawn.has(a2) || !drawn.has(b2)) return;
    const key = l2.kind + "|" + [a2, b2].sort().join("|");
    if (!symmetric.has(key))
      symmetric.set(key, { kind: l2.kind, a: a2, b: b2, names: /* @__PURE__ */ new Set(), via: [] });
    const entry = symmetric.get(key);
    entry.via.push(...l2.via);
    if (foldedBoxes.has(b2)) entry.names.add(nameOf(l2.b));
    else if (foldedBoxes.has(a2)) entry.names.add(nameOf(l2.a));
  });
  const loneLinks = [];
  symmetric.forEach((entry) => {
    const carrier = entry.kind === "sharedKernel" ? [entry.a + "|" + entry.b, entry.b + "|" + entry.a].find(
      (k2) => merged.has(k2)
    ) : void 0;
    if (carrier) merged.get(carrier).kernel = entry;
    else loneLinks.push(entry);
  });
  const byStyle = {};
  const tips = [];
  const dependencyTips = (entry) => entry.via.filter((e2) => e2.comment || roleText(e2)).map(tipEntry).concat(entry.kernel ? entry.kernel.via.map(linkTipEntry) : []).concat(eventsTipEntries(entry.via));
  const roleMarks = [];
  const kernelMarks = [];
  const references = [];
  const carried = {};
  if (showAggregates) {
    MODEL.contexts.forEach(
      (c2) => (c2.aggregates || []).forEach(
        (a2) => a2.references.forEach((ref) => {
          const from = aggregateNode(c2.id, a2.name), to = aggregateNode(ref.context, ref.name);
          if (aggregateNodes[from] && aggregateNodes[to])
            references.push({
              from,
              to,
              fromContext: c2.id,
              toContext: ref.context,
              aggregate: a2,
              ref
            });
        })
      )
    );
    references.forEach((r2, position) => {
      const key = r2.fromContext + "|" + r2.toContext;
      if (merged.has(key) && !(key in carried)) carried[key] = position;
    });
  }
  const drawDependency = (i2, from, to, entry) => {
    const style = entry.styles.has("solid") ? "solid" : [...entry.styles].sort()[0];
    let up = [], down = [];
    if (entry.roles.size === 1) {
      const [upstream, downstream] = JSON.parse([...entry.roles][0]);
      [up, down] = roleCodes({ upstream, downstream });
    }
    const labelLines = [];
    const names2 = /* @__PURE__ */ new Set([...entry.names, ...entry.kernel?.names || []]);
    if (names2.size && DIAGRAM.child_labels)
      labelLines.push([...names2].sort().join(", "));
    if (entry.kernel && DIAGRAM.relationship_labels) kernelMarks.push(i2);
    if ((up.length || down.length) && DIAGRAM.relationship_labels)
      roleMarks.push(`${i2}=${up.join(",")}>${down.join(",")}`);
    const label = labelLines.length ? `|"${quote(labelLines.join("<br/>"))}"|` : "";
    lines.push(
      `  ${nodeId(from)} ${style === "dotted" ? "-.->" : "-->"}${label} ${nodeId(to)}`
    );
    const key = entry.kernel ? `${style}+sharedKernel` : style;
    (byStyle[key] = byStyle[key] || []).push(i2);
  };
  [...merged].forEach(([key, entry]) => {
    if (key in carried) return;
    const i2 = tips.length;
    tips.push(dependencyTips(entry));
    drawDependency(i2, entry.a, entry.b, entry);
  });
  const violations = /* @__PURE__ */ new Map();
  g2.violations.forEach((r2) => {
    if (!visible.has(r2.from) || !visible.has(r2.to)) return;
    const a2 = target(r2.from), b2 = target(r2.to);
    const key = a2 + "|" + b2;
    if (a2 === b2 || !drawn.has(a2) || !drawn.has(b2) || merged.has(key)) return;
    if (!violations.has(key)) violations.set(key, { a: a2, b: b2, via: [] });
    violations.get(key).via.push(...r2.via);
  });
  [...violations.values()].forEach((entry) => {
    lines.push(`  ${nodeId(entry.b)} <--> ${nodeId(entry.a)}`);
    (byStyle.violation = byStyle.violation || []).push(tips.length);
    tips.push(entry.via.map(violationTipEntry));
  });
  loneLinks.forEach((entry) => {
    const info = MODEL.symmetric_kinds[entry.kind];
    const labelLines = [];
    if (entry.names.size && DIAGRAM.child_labels)
      labelLines.push([...entry.names].sort().join(", "));
    if (entry.kind === "sharedKernel" && DIAGRAM.relationship_labels)
      kernelMarks.push(tips.length);
    const label = labelLines.length ? `|"${quote(labelLines.join("<br/>"))}"|` : "";
    lines.push(`  ${nodeId(entry.b)} ${info.link}${label} ${nodeId(entry.a)}`);
    (byStyle[entry.kind] = byStyle[entry.kind] || []).push(tips.length);
    tips.push(entry.via.map(linkTipEntry).concat(eventsTipEntries(entry.via)));
  });
  references.forEach((r2, position) => {
    const key = r2.fromContext + "|" + r2.toContext;
    const own = referenceTipEntry(r2.fromContext, r2.aggregate, r2.ref);
    if (carried[key] === position) {
      const entry = merged.get(key);
      const i2 = tips.length;
      tips.push([own, ...dependencyTips(entry)]);
      drawDependency(i2, r2.from, r2.to, entry);
    } else {
      lines.push(`  ${r2.from} --> ${r2.to}`);
      (byStyle.solid = byStyle.solid || []).push(tips.length);
      tips.push([own]);
    }
  });
  Object.entries(byStyle).forEach(
    ([style, indexes]) => lines.push(
      `  linkStyle ${indexes.join(",")} interpolate ${DIAGRAM.curve} ${styleOf(style)}`.trimEnd()
    )
  );
  if (byStyle.violation)
    lines.push(`  %% violations: ${byStyle.violation.join(",")}`);
  if (roleMarks.length) lines.push(`  %% roles: ${roleMarks.join(";")}`);
  if (kernelMarks.length) lines.push(`  %% kernels: ${kernelMarks.join(",")}`);
  const highlight = level === "domain" && owner[s2.focus] ? owner[s2.focus] : s2.focus;
  plainNodes.forEach((n2) => {
    if (n2 === highlight) lines.push(`  class ${nodeId(n2)} focus`);
  });
  plainNodes.forEach((n2) => {
    if (owner[n2] || clusterById[n2])
      lines.push(`  click ${nodeId(n2)} href "${hashFor({ ...s2, focus: n2 })}"`);
  });
  Object.entries(aggregateNodes).forEach(
    ([node, contextId]) => lines.push(`  click ${node} href "${hashFor({ ...s2, focus: contextId })}"`)
  );
  return { source: lines.join("\n") + "\n", visible, tips };
}
var violationTipEntry = (dep) => ({
  title: `${nameOf(dep.from)} \u2192 ${nameOf(dep.to)} (violation)`,
  text: dep.comment || "Against the direction of the dependencies."
});
var referenceTipEntry = (contextId, aggregate, ref) => {
  const entry = {
    title: `${aggregate.name} \u2192 ${ref.name} (reference)`
  };
  if (ref.context !== contextId)
    entry.text = `${ref.name} is in ${nameOf(ref.context)}.`;
  return entry;
};
var linkTipEntry = (link2) => {
  const entry = {
    title: `${nameOf(link2.a)} \u2194 ${nameOf(link2.b)} (${MODEL.symmetric_kinds[link2.kind].name})`
  };
  if (link2.comment) entry.text = link2.comment;
  return entry;
};
var tipEntry = (dep) => {
  const entry = { title: `${nameOf(dep.from)} \u2192 ${nameOf(dep.to)}` };
  const roles = roleText(dep);
  if (roles) entry.roles = roles;
  if (dep.comment) entry.text = dep.comment;
  return entry;
};

// src/context_mapper/template/core/attributes.js
var attributeText = (v2) => Array.isArray(v2) ? v2.map(attributeText).join(", ") : v2 && typeof v2 === "object" ? Object.entries(v2).map(([k2, item]) => `${k2}: ${attributeText(item)}`).join(" \xB7 ") : String(v2);
var attributeEntries = (item) => Object.entries(MODEL.attributes || {}).filter(([id]) => item.attributes && id in item.attributes).map(([id, def]) => ({ id, label: def.name, value: item.attributes[id] }));
var boxTipEntries = (item) => {
  if (!item) return [];
  const entries = item.description ? [{ kind: "desc", title: item.name, text: item.description }] : [];
  if (!DIAGRAM.attribute_tooltips) return entries;
  const aggregates = contextById[item.id]?.aggregates || [];
  const holder = holderOf(item);
  return entries.concat(
    attributeEntries(item).map(({ label, value }) => ({
      kind: "attr",
      title: label,
      text: attributeText(value)
    }))
  ).concat(
    aggregates.length ? [
      {
        kind: "attr",
        title: "Aggregates",
        text: aggregates.map((a2) => a2.name).join(", ")
      }
    ] : []
  ).concat(eventTipRows(holder));
};
var eventTipRows = (holder) => [
  ["Publishes", (holder.publishes || []).map((e2) => [e2.name, e2.description])],
  ["Consumes", (holder.consumes || []).map((e2) => [e2.name, e2.reason])]
].filter(([, events]) => events.length).map(([title, events]) => ({
  kind: "attr",
  title,
  multiline: true,
  text: events.map(([name, text]) => text ? `${name} \u2014 ${text}` : name).join("\n")
}));
var aggregateTipEntries = (aggregate) => {
  const entries = aggregate.description ? [{ kind: "desc", title: aggregate.name, text: aggregate.description }] : [];
  if (!DIAGRAM.attribute_tooltips) return entries;
  const names2 = (items) => items.map((m2) => m2.name).join(", ");
  return entries.concat(
    [
      ["Root", aggregate.root],
      ["Entities", names2(aggregate.entities)],
      ["Value objects", names2(aggregate.valueObjects)]
    ].filter(([, text]) => text).map(([title, text]) => ({ kind: "attr", title, text })),
    attributeEntries(aggregate).map(({ label, value }) => ({
      kind: "attr",
      title: label,
      text: attributeText(value)
    })),
    eventTipRows(aggregate)
  );
};

// node_modules/htm/preact/standalone.module.js
var standalone_module_exports = {};
__export(standalone_module_exports, {
  Component: () => d,
  createContext: () => F,
  h: () => a,
  html: () => fe,
  render: () => M,
  useCallback: () => Z,
  useContext: () => ee,
  useDebugValue: () => ne,
  useEffect: () => J,
  useErrorBoundary: () => _e,
  useImperativeHandle: () => X,
  useLayoutEffect: () => K,
  useMemo: () => Y,
  useReducer: () => z,
  useRef: () => Q,
  useState: () => G
});
var e;
var n;
var _;
var t;
var o;
var r;
var u;
var l = {};
var i = [];
var c = /acit|ex(?:s|g|n|p|$)|rph|grid|ows|mnc|ntw|ine[ch]|zoo|^ord|itera/i;
function s(e2, n2) {
  for (var _2 in n2) e2[_2] = n2[_2];
  return e2;
}
function f(e2) {
  var n2 = e2.parentNode;
  n2 && n2.removeChild(e2);
}
function a(n2, _2, t2) {
  var o2, r2, u2, l2 = {};
  for (u2 in _2) "key" == u2 ? o2 = _2[u2] : "ref" == u2 ? r2 = _2[u2] : l2[u2] = _2[u2];
  if (arguments.length > 2 && (l2.children = arguments.length > 3 ? e.call(arguments, 2) : t2), "function" == typeof n2 && null != n2.defaultProps) for (u2 in n2.defaultProps) void 0 === l2[u2] && (l2[u2] = n2.defaultProps[u2]);
  return p(n2, l2, o2, r2, null);
}
function p(e2, t2, o2, r2, u2) {
  var l2 = { type: e2, props: t2, key: o2, ref: r2, __k: null, __: null, __b: 0, __e: null, __d: void 0, __c: null, __h: null, constructor: void 0, __v: null == u2 ? ++_ : u2 };
  return null != n.vnode && n.vnode(l2), l2;
}
function h(e2) {
  return e2.children;
}
function d(e2, n2) {
  this.props = e2, this.context = n2;
}
function v(e2, n2) {
  if (null == n2) return e2.__ ? v(e2.__, e2.__.__k.indexOf(e2) + 1) : null;
  for (var _2; n2 < e2.__k.length; n2++) if (null != (_2 = e2.__k[n2]) && null != _2.__e) return _2.__e;
  return "function" == typeof e2.type ? v(e2) : null;
}
function y(e2) {
  var n2, _2;
  if (null != (e2 = e2.__) && null != e2.__c) {
    for (e2.__e = e2.__c.base = null, n2 = 0; n2 < e2.__k.length; n2++) if (null != (_2 = e2.__k[n2]) && null != _2.__e) {
      e2.__e = e2.__c.base = _2.__e;
      break;
    }
    return y(e2);
  }
}
function m(e2) {
  (!e2.__d && (e2.__d = true) && t.push(e2) && !g.__r++ || r !== n.debounceRendering) && ((r = n.debounceRendering) || o)(g);
}
function g() {
  for (var e2; g.__r = t.length; ) e2 = t.sort(function(e3, n2) {
    return e3.__v.__b - n2.__v.__b;
  }), t = [], e2.some(function(e3) {
    var n2, _2, t2, o2, r2, u2;
    e3.__d && (r2 = (o2 = (n2 = e3).__v).__e, (u2 = n2.__P) && (_2 = [], (t2 = s({}, o2)).__v = o2.__v + 1, P(u2, o2, t2, n2.__n, void 0 !== u2.ownerSVGElement, null != o2.__h ? [r2] : null, _2, null == r2 ? v(o2) : r2, o2.__h), D(_2, o2), o2.__e != r2 && y(o2)));
  });
}
function k(e2, n2, _2, t2, o2, r2, u2, c2, s2, f2) {
  var a2, d2, y2, m2, g2, k2, x2, H2 = t2 && t2.__k || i, E2 = H2.length;
  for (_2.__k = [], a2 = 0; a2 < n2.length; a2++) if (null != (m2 = _2.__k[a2] = null == (m2 = n2[a2]) || "boolean" == typeof m2 ? null : "string" == typeof m2 || "number" == typeof m2 || "bigint" == typeof m2 ? p(null, m2, null, null, m2) : Array.isArray(m2) ? p(h, { children: m2 }, null, null, null) : m2.__b > 0 ? p(m2.type, m2.props, m2.key, null, m2.__v) : m2)) {
    if (m2.__ = _2, m2.__b = _2.__b + 1, null === (y2 = H2[a2]) || y2 && m2.key == y2.key && m2.type === y2.type) H2[a2] = void 0;
    else for (d2 = 0; d2 < E2; d2++) {
      if ((y2 = H2[d2]) && m2.key == y2.key && m2.type === y2.type) {
        H2[d2] = void 0;
        break;
      }
      y2 = null;
    }
    P(e2, m2, y2 = y2 || l, o2, r2, u2, c2, s2, f2), g2 = m2.__e, (d2 = m2.ref) && y2.ref != d2 && (x2 || (x2 = []), y2.ref && x2.push(y2.ref, null, m2), x2.push(d2, m2.__c || g2, m2)), null != g2 ? (null == k2 && (k2 = g2), "function" == typeof m2.type && null != m2.__k && m2.__k === y2.__k ? m2.__d = s2 = b(m2, s2, e2) : s2 = C(e2, m2, y2, H2, g2, s2), f2 || "option" !== _2.type ? "function" == typeof _2.type && (_2.__d = s2) : e2.value = "") : s2 && y2.__e == s2 && s2.parentNode != e2 && (s2 = v(y2));
  }
  for (_2.__e = k2, a2 = E2; a2--; ) null != H2[a2] && ("function" == typeof _2.type && null != H2[a2].__e && H2[a2].__e == _2.__d && (_2.__d = v(t2, a2 + 1)), U(H2[a2], H2[a2]));
  if (x2) for (a2 = 0; a2 < x2.length; a2++) T(x2[a2], x2[++a2], x2[++a2]);
}
function b(e2, n2, _2) {
  var t2, o2;
  for (t2 = 0; t2 < e2.__k.length; t2++) (o2 = e2.__k[t2]) && (o2.__ = e2, n2 = "function" == typeof o2.type ? b(o2, n2, _2) : C(_2, o2, o2, e2.__k, o2.__e, n2));
  return n2;
}
function C(e2, n2, _2, t2, o2, r2) {
  var u2, l2, i2;
  if (void 0 !== n2.__d) u2 = n2.__d, n2.__d = void 0;
  else if (null == _2 || o2 != r2 || null == o2.parentNode) e: if (null == r2 || r2.parentNode !== e2) e2.appendChild(o2), u2 = null;
  else {
    for (l2 = r2, i2 = 0; (l2 = l2.nextSibling) && i2 < t2.length; i2 += 2) if (l2 == o2) break e;
    e2.insertBefore(o2, r2), u2 = r2;
  }
  return void 0 !== u2 ? u2 : o2.nextSibling;
}
function x(e2, n2, _2) {
  "-" === n2[0] ? e2.setProperty(n2, _2) : e2[n2] = null == _2 ? "" : "number" != typeof _2 || c.test(n2) ? _2 : _2 + "px";
}
function H(e2, n2, _2, t2, o2) {
  var r2;
  e: if ("style" === n2) if ("string" == typeof _2) e2.style.cssText = _2;
  else {
    if ("string" == typeof t2 && (e2.style.cssText = t2 = ""), t2) for (n2 in t2) _2 && n2 in _2 || x(e2.style, n2, "");
    if (_2) for (n2 in _2) t2 && _2[n2] === t2[n2] || x(e2.style, n2, _2[n2]);
  }
  else if ("o" === n2[0] && "n" === n2[1]) r2 = n2 !== (n2 = n2.replace(/Capture$/, "")), n2 = n2.toLowerCase() in e2 ? n2.toLowerCase().slice(2) : n2.slice(2), e2.l || (e2.l = {}), e2.l[n2 + r2] = _2, _2 ? t2 || e2.addEventListener(n2, r2 ? S : E, r2) : e2.removeEventListener(n2, r2 ? S : E, r2);
  else if ("dangerouslySetInnerHTML" !== n2) {
    if (o2) n2 = n2.replace(/xlink[H:h]/, "h").replace(/sName$/, "s");
    else if ("href" !== n2 && "list" !== n2 && "form" !== n2 && "tabIndex" !== n2 && "download" !== n2 && n2 in e2) try {
      e2[n2] = null == _2 ? "" : _2;
      break e;
    } catch (e3) {
    }
    "function" == typeof _2 || (null != _2 && (false !== _2 || "a" === n2[0] && "r" === n2[1]) ? e2.setAttribute(n2, _2) : e2.removeAttribute(n2));
  }
}
function E(e2) {
  this.l[e2.type + false](n.event ? n.event(e2) : e2);
}
function S(e2) {
  this.l[e2.type + true](n.event ? n.event(e2) : e2);
}
function P(e2, _2, t2, o2, r2, u2, l2, i2, c2) {
  var f2, a2, p2, v2, y2, m2, g2, b2, C2, x2, H2, E2 = _2.type;
  if (void 0 !== _2.constructor) return null;
  null != t2.__h && (c2 = t2.__h, i2 = _2.__e = t2.__e, _2.__h = null, u2 = [i2]), (f2 = n.__b) && f2(_2);
  try {
    e: if ("function" == typeof E2) {
      if (b2 = _2.props, C2 = (f2 = E2.contextType) && o2[f2.__c], x2 = f2 ? C2 ? C2.props.value : f2.__ : o2, t2.__c ? g2 = (a2 = _2.__c = t2.__c).__ = a2.__E : ("prototype" in E2 && E2.prototype.render ? _2.__c = a2 = new E2(b2, x2) : (_2.__c = a2 = new d(b2, x2), a2.constructor = E2, a2.render = A), C2 && C2.sub(a2), a2.props = b2, a2.state || (a2.state = {}), a2.context = x2, a2.__n = o2, p2 = a2.__d = true, a2.__h = []), null == a2.__s && (a2.__s = a2.state), null != E2.getDerivedStateFromProps && (a2.__s == a2.state && (a2.__s = s({}, a2.__s)), s(a2.__s, E2.getDerivedStateFromProps(b2, a2.__s))), v2 = a2.props, y2 = a2.state, p2) null == E2.getDerivedStateFromProps && null != a2.componentWillMount && a2.componentWillMount(), null != a2.componentDidMount && a2.__h.push(a2.componentDidMount);
      else {
        if (null == E2.getDerivedStateFromProps && b2 !== v2 && null != a2.componentWillReceiveProps && a2.componentWillReceiveProps(b2, x2), !a2.__e && null != a2.shouldComponentUpdate && false === a2.shouldComponentUpdate(b2, a2.__s, x2) || _2.__v === t2.__v) {
          a2.props = b2, a2.state = a2.__s, _2.__v !== t2.__v && (a2.__d = false), a2.__v = _2, _2.__e = t2.__e, _2.__k = t2.__k, _2.__k.forEach(function(e3) {
            e3 && (e3.__ = _2);
          }), a2.__h.length && l2.push(a2);
          break e;
        }
        null != a2.componentWillUpdate && a2.componentWillUpdate(b2, a2.__s, x2), null != a2.componentDidUpdate && a2.__h.push(function() {
          a2.componentDidUpdate(v2, y2, m2);
        });
      }
      a2.context = x2, a2.props = b2, a2.state = a2.__s, (f2 = n.__r) && f2(_2), a2.__d = false, a2.__v = _2, a2.__P = e2, f2 = a2.render(a2.props, a2.state, a2.context), a2.state = a2.__s, null != a2.getChildContext && (o2 = s(s({}, o2), a2.getChildContext())), p2 || null == a2.getSnapshotBeforeUpdate || (m2 = a2.getSnapshotBeforeUpdate(v2, y2)), H2 = null != f2 && f2.type === h && null == f2.key ? f2.props.children : f2, k(e2, Array.isArray(H2) ? H2 : [H2], _2, t2, o2, r2, u2, l2, i2, c2), a2.base = _2.__e, _2.__h = null, a2.__h.length && l2.push(a2), g2 && (a2.__E = a2.__ = null), a2.__e = false;
    } else null == u2 && _2.__v === t2.__v ? (_2.__k = t2.__k, _2.__e = t2.__e) : _2.__e = w(t2.__e, _2, t2, o2, r2, u2, l2, c2);
    (f2 = n.diffed) && f2(_2);
  } catch (e3) {
    _2.__v = null, (c2 || null != u2) && (_2.__e = i2, _2.__h = !!c2, u2[u2.indexOf(i2)] = null), n.__e(e3, _2, t2);
  }
}
function D(e2, _2) {
  n.__c && n.__c(_2, e2), e2.some(function(_3) {
    try {
      e2 = _3.__h, _3.__h = [], e2.some(function(e3) {
        e3.call(_3);
      });
    } catch (e3) {
      n.__e(e3, _3.__v);
    }
  });
}
function w(n2, _2, t2, o2, r2, u2, i2, c2) {
  var s2, a2, p2, h2 = t2.props, d2 = _2.props, y2 = _2.type, m2 = 0;
  if ("svg" === y2 && (r2 = true), null != u2) {
    for (; m2 < u2.length; m2++) if ((s2 = u2[m2]) && (s2 === n2 || (y2 ? s2.localName == y2 : 3 == s2.nodeType))) {
      n2 = s2, u2[m2] = null;
      break;
    }
  }
  if (null == n2) {
    if (null === y2) return document.createTextNode(d2);
    n2 = r2 ? document.createElementNS("http://www.w3.org/2000/svg", y2) : document.createElement(y2, d2.is && d2), u2 = null, c2 = false;
  }
  if (null === y2) h2 === d2 || c2 && n2.data === d2 || (n2.data = d2);
  else {
    if (u2 = u2 && e.call(n2.childNodes), a2 = (h2 = t2.props || l).dangerouslySetInnerHTML, p2 = d2.dangerouslySetInnerHTML, !c2) {
      if (null != u2) for (h2 = {}, m2 = 0; m2 < n2.attributes.length; m2++) h2[n2.attributes[m2].name] = n2.attributes[m2].value;
      (p2 || a2) && (p2 && (a2 && p2.__html == a2.__html || p2.__html === n2.innerHTML) || (n2.innerHTML = p2 && p2.__html || ""));
    }
    if ((function(e2, n3, _3, t3, o3) {
      var r3;
      for (r3 in _3) "children" === r3 || "key" === r3 || r3 in n3 || H(e2, r3, null, _3[r3], t3);
      for (r3 in n3) o3 && "function" != typeof n3[r3] || "children" === r3 || "key" === r3 || "value" === r3 || "checked" === r3 || _3[r3] === n3[r3] || H(e2, r3, n3[r3], _3[r3], t3);
    })(n2, d2, h2, r2, c2), p2) _2.__k = [];
    else if (m2 = _2.props.children, k(n2, Array.isArray(m2) ? m2 : [m2], _2, t2, o2, r2 && "foreignObject" !== y2, u2, i2, u2 ? u2[0] : t2.__k && v(t2, 0), c2), null != u2) for (m2 = u2.length; m2--; ) null != u2[m2] && f(u2[m2]);
    c2 || ("value" in d2 && void 0 !== (m2 = d2.value) && (m2 !== n2.value || "progress" === y2 && !m2) && H(n2, "value", m2, h2.value, false), "checked" in d2 && void 0 !== (m2 = d2.checked) && m2 !== n2.checked && H(n2, "checked", m2, h2.checked, false));
  }
  return n2;
}
function T(e2, _2, t2) {
  try {
    "function" == typeof e2 ? e2(_2) : e2.current = _2;
  } catch (e3) {
    n.__e(e3, t2);
  }
}
function U(e2, _2, t2) {
  var o2, r2;
  if (n.unmount && n.unmount(e2), (o2 = e2.ref) && (o2.current && o2.current !== e2.__e || T(o2, null, _2)), null != (o2 = e2.__c)) {
    if (o2.componentWillUnmount) try {
      o2.componentWillUnmount();
    } catch (e3) {
      n.__e(e3, _2);
    }
    o2.base = o2.__P = null;
  }
  if (o2 = e2.__k) for (r2 = 0; r2 < o2.length; r2++) o2[r2] && U(o2[r2], _2, "function" != typeof e2.type);
  t2 || null == e2.__e || f(e2.__e), e2.__e = e2.__d = void 0;
}
function A(e2, n2, _2) {
  return this.constructor(e2, _2);
}
function M(_2, t2, o2) {
  var r2, u2, i2;
  n.__ && n.__(_2, t2), u2 = (r2 = "function" == typeof o2) ? null : o2 && o2.__k || t2.__k, i2 = [], P(t2, _2 = (!r2 && o2 || t2).__k = a(h, null, [_2]), u2 || l, l, void 0 !== t2.ownerSVGElement, !r2 && o2 ? [o2] : u2 ? null : t2.firstChild ? e.call(t2.childNodes) : null, i2, !r2 && o2 ? o2 : u2 ? u2.__e : t2.firstChild, r2), D(i2, _2);
}
function F(e2, n2) {
  var _2 = { __c: n2 = "__cC" + u++, __: e2, Consumer: function(e3, n3) {
    return e3.children(n3);
  }, Provider: function(e3) {
    var _3, t2;
    return this.getChildContext || (_3 = [], (t2 = {})[n2] = this, this.getChildContext = function() {
      return t2;
    }, this.shouldComponentUpdate = function(e4) {
      this.props.value !== e4.value && _3.some(m);
    }, this.sub = function(e4) {
      _3.push(e4);
      var n3 = e4.componentWillUnmount;
      e4.componentWillUnmount = function() {
        _3.splice(_3.indexOf(e4), 1), n3 && n3.call(e4);
      };
    }), e3.children;
  } };
  return _2.Provider.__ = _2.Consumer.contextType = _2;
}
e = i.slice, n = { __e: function(e2, n2) {
  for (var _2, t2, o2; n2 = n2.__; ) if ((_2 = n2.__c) && !_2.__) try {
    if ((t2 = _2.constructor) && null != t2.getDerivedStateFromError && (_2.setState(t2.getDerivedStateFromError(e2)), o2 = _2.__d), null != _2.componentDidCatch && (_2.componentDidCatch(e2), o2 = _2.__d), o2) return _2.__E = _2;
  } catch (n3) {
    e2 = n3;
  }
  throw e2;
} }, _ = 0, d.prototype.setState = function(e2, n2) {
  var _2;
  _2 = null != this.__s && this.__s !== this.state ? this.__s : this.__s = s({}, this.state), "function" == typeof e2 && (e2 = e2(s({}, _2), this.props)), e2 && s(_2, e2), null != e2 && this.__v && (n2 && this.__h.push(n2), m(this));
}, d.prototype.forceUpdate = function(e2) {
  this.__v && (this.__e = true, e2 && this.__h.push(e2), m(this));
}, d.prototype.render = h, t = [], o = "function" == typeof Promise ? Promise.prototype.then.bind(Promise.resolve()) : setTimeout, g.__r = 0, u = 0;
var L;
var N;
var W;
var R = 0;
var I = [];
var O = n.__b;
var V = n.__r;
var q = n.diffed;
var B = n.__c;
var $ = n.unmount;
function j(e2, _2) {
  n.__h && n.__h(N, e2, R || _2), R = 0;
  var t2 = N.__H || (N.__H = { __: [], __h: [] });
  return e2 >= t2.__.length && t2.__.push({}), t2.__[e2];
}
function G(e2) {
  return R = 1, z(ie, e2);
}
function z(e2, n2, _2) {
  var t2 = j(L++, 2);
  return t2.t = e2, t2.__c || (t2.__ = [_2 ? _2(n2) : ie(void 0, n2), function(e3) {
    var n3 = t2.t(t2.__[0], e3);
    t2.__[0] !== n3 && (t2.__ = [n3, t2.__[1]], t2.__c.setState({}));
  }], t2.__c = N), t2.__;
}
function J(e2, _2) {
  var t2 = j(L++, 3);
  !n.__s && le(t2.__H, _2) && (t2.__ = e2, t2.__H = _2, N.__H.__h.push(t2));
}
function K(e2, _2) {
  var t2 = j(L++, 4);
  !n.__s && le(t2.__H, _2) && (t2.__ = e2, t2.__H = _2, N.__h.push(t2));
}
function Q(e2) {
  return R = 5, Y(function() {
    return { current: e2 };
  }, []);
}
function X(e2, n2, _2) {
  R = 6, K(function() {
    "function" == typeof e2 ? e2(n2()) : e2 && (e2.current = n2());
  }, null == _2 ? _2 : _2.concat(e2));
}
function Y(e2, n2) {
  var _2 = j(L++, 7);
  return le(_2.__H, n2) && (_2.__ = e2(), _2.__H = n2, _2.__h = e2), _2.__;
}
function Z(e2, n2) {
  return R = 8, Y(function() {
    return e2;
  }, n2);
}
function ee(e2) {
  var n2 = N.context[e2.__c], _2 = j(L++, 9);
  return _2.c = e2, n2 ? (null == _2.__ && (_2.__ = true, n2.sub(N)), n2.props.value) : e2.__;
}
function ne(e2, _2) {
  n.useDebugValue && n.useDebugValue(_2 ? _2(e2) : e2);
}
function _e(e2) {
  var n2 = j(L++, 10), _2 = G();
  return n2.__ = e2, N.componentDidCatch || (N.componentDidCatch = function(e3) {
    n2.__ && n2.__(e3), _2[1](e3);
  }), [_2[0], function() {
    _2[1](void 0);
  }];
}
function te() {
  I.forEach(function(e2) {
    if (e2.__P) try {
      e2.__H.__h.forEach(re), e2.__H.__h.forEach(ue), e2.__H.__h = [];
    } catch (_2) {
      e2.__H.__h = [], n.__e(_2, e2.__v);
    }
  }), I = [];
}
n.__b = function(e2) {
  N = null, O && O(e2);
}, n.__r = function(e2) {
  V && V(e2), L = 0;
  var n2 = (N = e2.__c).__H;
  n2 && (n2.__h.forEach(re), n2.__h.forEach(ue), n2.__h = []);
}, n.diffed = function(e2) {
  q && q(e2);
  var _2 = e2.__c;
  _2 && _2.__H && _2.__H.__h.length && (1 !== I.push(_2) && W === n.requestAnimationFrame || ((W = n.requestAnimationFrame) || function(e3) {
    var n2, _3 = function() {
      clearTimeout(t2), oe && cancelAnimationFrame(n2), setTimeout(e3);
    }, t2 = setTimeout(_3, 100);
    oe && (n2 = requestAnimationFrame(_3));
  })(te)), N = void 0;
}, n.__c = function(e2, _2) {
  _2.some(function(e3) {
    try {
      e3.__h.forEach(re), e3.__h = e3.__h.filter(function(e4) {
        return !e4.__ || ue(e4);
      });
    } catch (t2) {
      _2.some(function(e4) {
        e4.__h && (e4.__h = []);
      }), _2 = [], n.__e(t2, e3.__v);
    }
  }), B && B(e2, _2);
}, n.unmount = function(e2) {
  $ && $(e2);
  var _2 = e2.__c;
  if (_2 && _2.__H) try {
    _2.__H.__.forEach(re);
  } catch (e3) {
    n.__e(e3, _2.__v);
  }
};
var oe = "function" == typeof requestAnimationFrame;
function re(e2) {
  var n2 = N;
  "function" == typeof e2.__c && e2.__c(), N = n2;
}
function ue(e2) {
  var n2 = N;
  e2.__c = e2.__(), N = n2;
}
function le(e2, n2) {
  return !e2 || e2.length !== n2.length || n2.some(function(n3, _2) {
    return n3 !== e2[_2];
  });
}
function ie(e2, n2) {
  return "function" == typeof n2 ? n2(e2) : n2;
}
var ce = function(e2, n2, _2, t2) {
  var o2;
  n2[0] = 0;
  for (var r2 = 1; r2 < n2.length; r2++) {
    var u2 = n2[r2++], l2 = n2[r2] ? (n2[0] |= u2 ? 1 : 2, _2[n2[r2++]]) : n2[++r2];
    3 === u2 ? t2[0] = l2 : 4 === u2 ? t2[1] = Object.assign(t2[1] || {}, l2) : 5 === u2 ? (t2[1] = t2[1] || {})[n2[++r2]] = l2 : 6 === u2 ? t2[1][n2[++r2]] += l2 + "" : u2 ? (o2 = e2.apply(l2, ce(e2, l2, _2, ["", null])), t2.push(o2), l2[0] ? n2[0] |= 2 : (n2[r2 - 2] = 0, n2[r2] = o2)) : t2.push(l2);
  }
  return t2;
};
var se = /* @__PURE__ */ new Map();
var fe = function(e2) {
  var n2 = se.get(this);
  return n2 || (n2 = /* @__PURE__ */ new Map(), se.set(this, n2)), (n2 = ce(this, n2.get(e2) || (n2.set(e2, n2 = (function(e3) {
    for (var n3, _2, t2 = 1, o2 = "", r2 = "", u2 = [0], l2 = function(e4) {
      1 === t2 && (e4 || (o2 = o2.replace(/^\s*\n\s*|\s*\n\s*$/g, ""))) ? u2.push(0, e4, o2) : 3 === t2 && (e4 || o2) ? (u2.push(3, e4, o2), t2 = 2) : 2 === t2 && "..." === o2 && e4 ? u2.push(4, e4, 0) : 2 === t2 && o2 && !e4 ? u2.push(5, 0, true, o2) : t2 >= 5 && ((o2 || !e4 && 5 === t2) && (u2.push(t2, 0, o2, _2), t2 = 6), e4 && (u2.push(t2, e4, 0, _2), t2 = 6)), o2 = "";
    }, i2 = 0; i2 < e3.length; i2++) {
      i2 && (1 === t2 && l2(), l2(i2));
      for (var c2 = 0; c2 < e3[i2].length; c2++) n3 = e3[i2][c2], 1 === t2 ? "<" === n3 ? (l2(), u2 = [u2], t2 = 3) : o2 += n3 : 4 === t2 ? "--" === o2 && ">" === n3 ? (t2 = 1, o2 = "") : o2 = n3 + o2[0] : r2 ? n3 === r2 ? r2 = "" : o2 += n3 : '"' === n3 || "'" === n3 ? r2 = n3 : ">" === n3 ? (l2(), t2 = 1) : t2 && ("=" === n3 ? (t2 = 5, _2 = o2, o2 = "") : "/" === n3 && (t2 < 5 || ">" === e3[i2][c2 + 1]) ? (l2(), 3 === t2 && (u2 = u2[0]), t2 = u2, (u2 = u2[0]).push(2, 0, t2), t2 = 0) : " " === n3 || "	" === n3 || "\n" === n3 || "\r" === n3 ? (l2(), t2 = 2) : o2 += n3), 3 === t2 && "!--" === o2 && (t2 = 4, u2 = u2[0]);
    }
    return l2(), u2;
  })(e2)), n2), arguments, [])).length > 1 ? n2 : n2[0];
}.bind(a);

// src/context_mapper/template/components/attributes.js
var attributeValue = (v2) => Array.isArray(v2) ? fe`<ul>
        ${v2.map((item) => fe`<li>${attributeText(item)}</li>`)}
      </ul>` : attributeText(v2);
var attributeRows = (item) => fe`<ul>
    ${attributeEntries(item).map(
  ({ label, value }) => fe`<li class="hint"><b>${label}:</b> ${attributeValue(value)}</li>`
)}
  </ul>`;
var attributeSection = (item) => attributeEntries(item).length ? fe`<h3>Attributes</h3>
        ${attributeRows(item)}` : "";

// src/context_mapper/template/components/events.js
var commaList = (items) => items.map((item, i2) => i2 ? fe`, ${item}` : item);
var consumer = (c2) => fe`<a data-go="${c2.id}">${nameOf(c2.id)}</a>${c2.aggregate ? ` / ${c2.aggregate}` : ""}${c2.reason ? ` \u2014 ${c2.reason}` : ""}`;
var published = (event) => {
  const line = event.name + (event.description ? ` \u2014 ${event.description}` : "");
  if (!event.consumers.length) return line;
  const glue = /[.!?]$/.test(line) ? " " : ". ";
  return event.consumers.some((c2) => c2.reason) ? fe`${line}${glue}Consumed by:
        <ul>
          ${event.consumers.map((c2) => fe`<li>${consumer(c2)}</li>`)}
        </ul>` : fe`${line}${glue}Consumed by${" "}${commaList(event.consumers.map(consumer))}`;
};
var consumed = (item) => fe`<a data-go="${item.publisher}">${item.publisher}</a>/${item.address.split("/").slice(1).join("/")}${item.reason ? ` \u2014 ${item.reason}` : ""}`;
var eventRows = (entry) => [
  ["Publishes", (entry.publishes || []).map(published)],
  ["Consumes", (entry.consumes || []).map(consumed)]
].filter(([, items]) => items.length).map(([label, items]) => [
  label,
  fe`<ul>
        ${items.map((item) => fe`<li>${item}</li>`)}
      </ul>`
]);
var eventSections = (item) => {
  const holder = holderOf(item);
  const section = (label, items) => items.length ? fe`<h3>${label} (${items.length})</h3>
          <ul>
            ${items.map((i2) => fe`<li>${i2}</li>`)}
          </ul>` : null;
  return [
    section("Publishes", (holder.publishes || []).map(published)),
    section("Consumes", (holder.consumes || []).map(consumed))
  ];
};

// src/context_mapper/template/components/aggregates.js
var members = (items) => items.map((m2) => m2.description ? `${m2.name} (${m2.description})` : m2.name).join(", ");
var reference = (contextId, ref) => {
  if (ref.context === contextId) return ref.name;
  const link2 = fe`<a data-go="${ref.context}">${nameOf(ref.context)}</a>`;
  return nameOf(ref.context) === ref.name ? link2 : fe`${link2} / ${ref.name}`;
};
var referenceList = (contextId, refs) => refs.map(
  (ref, i2) => i2 ? fe`, ${reference(contextId, ref)}` : reference(contextId, ref)
);
var aggregateBlock = (contextId, a2) => {
  const rows = [["Root", a2.root]];
  if (a2.entities.length) rows.push(["Entities", members(a2.entities)]);
  if (a2.valueObjects.length)
    rows.push(["Value objects", members(a2.valueObjects)]);
  if (a2.references.length)
    rows.push(["References", referenceList(contextId, a2.references)]);
  attributeEntries(a2).forEach(
    ({ label, value }) => rows.push([label, attributeValue(value)])
  );
  rows.push(...eventRows(a2));
  return fe`<h4>${a2.name}</h4>
    ${a2.description ? fe`<p class="hint">${a2.description}</p>` : null}
    <ul>
      ${rows.map(
    ([label, value]) => fe`<li class="hint"><b>${label}:</b> ${value}</li>`
  )}
    </ul>`;
};
var aggregateSection = (item) => {
  const aggregates = contextById[item.id]?.aggregates;
  return aggregates ? fe`<h3>Aggregates</h3>
        ${aggregates.map((a2) => aggregateBlock(item.id, a2))}` : "";
};

// src/context_mapper/template/dom/query.js
var $2 = (id) => document.getElementById(id);

// src/context_mapper/template/components/panel.js
var { html, render } = standalone_module_exports;
var link = (id) => html`<a data-go="${id}">${nameOf(id)}</a>`;
var list = (ids) => ids.length ? html`<ul>${ids.map((id) => html`<li>${link(id)}</li>`)}</ul>` : html`<p class="hint">None</p>`;
var dependencyList = (edges, end) => edges.length ? html`<ul>${edges.map((e2) => html`<li>${link(e2[end])}${roleText(e2) ? html` <span class="hint roles">${roleText(e2)}</span>` : null}</li>`)}</ul>` : html`<p class="hint">None</p>`;
var chip = (type) => {
  const t2 = MODEL.types[type];
  return html`<span class="chip" style="background:${t2.fill};border-color:${t2.stroke}">${t2.name}</span>`;
};
var Panel = ({ s: s2, visible }) => {
  const legend = html`<div class="legend">${Object.keys(MODEL.types).map(chip)}</div>`;
  if (!s2.focus)
    return html`<h2>Whole system</h2>
      <p class="hint">${visible.size} items shown. Pick a domain, cluster or bounded context to see only what it touches.</p>
      <p><a href="mermaid/index.html">Static diagrams</a></p>${legend}`;
  const id = s2.focus;
  const item = contextById[id] || domainById[id] || clusterById[id];
  const itemWith = (item_id) => {
    const hiddenHere = s2.hide.has(item_id);
    const toggle = hiddenHere ? html`<a data-show="${item_id}" class="toggle">show</a>` : html`<a data-hide="${item_id}" class="toggle">hide</a>`;
    return html`<li>${link(item_id)} ${hiddenHere ? html`<span class="hint">(hidden)</span>` : null}${hiddenHere ? " " : null}${toggle}</li>`;
  };
  if (clusterById[id])
    return html`<h2>${item.name}</h2><span class="hint">Cluster</span>
      <p><a href="mermaid/index.html">All diagrams</a></p>${attributeSection(item)}<h3>Members</h3><ul>${item.members.map(itemWith)}</ul><h3>Legend</h3>${legend}`;
  const r2 = relationEdges(id);
  const parent = owner[id];
  const own = GRAPHS.context.edges;
  const dUps = own.filter((e2) => e2.from === parent);
  const dDowns = own.filter((e2) => e2.to === parent);
  const pname = nameOf(parent);
  const linkLists = (found, heading) => Object.entries(MODEL.symmetric_kinds).filter(([kind]) => found[kind]).map(
    ([kind, info]) => html`<h3>${heading(info)} (${found[kind].length})</h3>${list(found[kind])}`
  );
  const ofParent = {};
  GRAPHS.context.links.filter((l2) => l2.a === parent || l2.b === parent).forEach(
    (l2) => (ofParent[l2.kind] = ofParent[l2.kind] || /* @__PURE__ */ new Set()).add(
      l2.a === parent ? l2.b : l2.a
    )
  );
  Object.keys(ofParent).forEach((kind) => {
    ofParent[kind] = [...ofParent[kind]].sort(
      (x2, y2) => nameOf(x2).localeCompare(nameOf(y2))
    );
  });
  return html`<h2>${item.name}</h2>${chip(item.type)} <span class="hint">${domainById[id] ? "Domain" : "Bounded context"}</span>
      <p><a href="mermaid/${id}.html">Static diagram</a> · <a href="mermaid/index.html">All diagrams</a></p>
      ${item.description ? html`<p class="hint">${item.description}</p>` : null}${attributeSection(item)}${aggregateSection(item)}${eventSections(item)}
      ${isMulti(id) ? html`<h3>Bounded contexts</h3><ul>${domainById[id].contexts.map(itemWith)}</ul>` : null}
      ${!isMulti(id) && isMulti(parent) ? html`<h3>Domain</h3>${list([parent])}` : null}
      <h3>Depends on (${r2.ups.length})</h3>${dependencyList(r2.ups, "to")}
      <h3>Used by (${r2.downs.length})</h3>${dependencyList(r2.downs, "from")}
      ${linkLists(linkRelations(id), (info) => info.heading)}
      ${!isMulti(id) && isMulti(parent) && dUps.length ? html`<h3>${pname} as a whole depends on</h3>${dependencyList(dUps, "to")}` : null}
      ${!isMulti(id) && isMulti(parent) && dDowns.length ? html`<h3>${pname} as a whole is used by</h3>${dependencyList(dDowns, "from")}` : null}
      ${!isMulti(id) && isMulti(parent) ? linkLists(ofParent, (info) => `${pname} as a whole ${info.verb}`) : null}
      <h3>Legend</h3>${legend}`;
};
function renderInfo(s2, visible) {
  render(
    html`<${Panel} key=${s2.focus || "all"} s=${s2} visible=${visible} />`,
    $2("info")
  );
}

// src/context_mapper/template/dom/tips.js
var tip = document.createElement("div");
tip.id = "tip";
document.body.appendChild(tip);
function showTip(note, ev) {
  if (!note.length) return hideTip();
  tip.replaceChildren(
    ...note.map((n2) => {
      const p2 = document.createElement("p");
      if (n2.kind === "attr") {
        p2.className = n2.multiline ? "attr multi" : "attr";
        const label = document.createElement("span");
        label.className = "k";
        label.textContent = n2.title;
        p2.append(label, n2.multiline ? "\n" : " ", n2.text);
        return p2;
      }
      if (n2.kind) p2.className = n2.kind;
      const title = document.createElement("b");
      title.textContent = n2.title;
      p2.append(title);
      if (n2.roles) {
        const roles = document.createElement("span");
        roles.className = "roles";
        roles.textContent = n2.roles;
        p2.append(document.createElement("br"), roles);
      }
      if (n2.text) p2.append(document.createElement("br"), n2.text);
      return p2;
    })
  );
  tip.style.display = "block";
  const x2 = Math.min(ev.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
  const y2 = ev.clientY + 18 + tip.offsetHeight > window.innerHeight ? ev.clientY - tip.offsetHeight - 12 : ev.clientY + 18;
  tip.style.left = Math.max(8, x2) + "px";
  tip.style.top = Math.max(8, y2) + "px";
}
var hideTip = () => {
  tip.style.display = "none";
};

// src/context_mapper/template/dom/svg.js
function boxMapOf(svg) {
  const boxes = {};
  svg.querySelectorAll("g[id]").forEach((g2) => {
    const m2 = /-flowchart-(.+)-\d+$/.exec(g2.id);
    if (m2) boxes[m2[1]] = g2;
    else if (g2.classList.contains("cluster"))
      boxes[g2.id.slice(svg.id.length + 1)] = g2;
  });
  Object.values(boxes).forEach((g2) => g2.classList.add("box"));
  return boxes;
}
function bindEdgeHover(svg, tips) {
  if (!svg) return;
  const paths = [...svg.querySelectorAll("path.flowchart-link")];
  const labels = [...svg.querySelectorAll(".edgeLabel")];
  const boxes = boxMapOf(svg);
  const endsOf = (path) => {
    const rest = path.id.slice(svg.id.length + 3).replace(/_\d+$/, "");
    for (const from of Object.keys(boxes)) {
      if (rest.startsWith(from + "_") && boxes[rest.slice(from.length + 1)])
        return [boxes[from], boxes[rest.slice(from.length + 1)]];
    }
    return [];
  };
  const markers = {};
  const accentMarker = (ref) => {
    const m2 = /url\(["']?#([^"')]+)["']?\)/.exec(ref || "");
    const src = m2 && svg.getElementById(m2[1]);
    if (!src) return null;
    if (!markers[m2[1]]) {
      const copy = src.cloneNode(true);
      copy.id = m2[1] + "-on";
      copy.querySelectorAll("*").forEach((n2) => {
        n2.style.fill = "var(--accent)";
        n2.style.stroke = "var(--accent)";
      });
      src.parentNode.appendChild(copy);
      markers[m2[1]] = copy.id;
    }
    return `url(#${markers[m2[1]]})`;
  };
  paths.forEach((path, i2) => {
    const hit = path.cloneNode(false);
    hit.removeAttribute("id");
    hit.removeAttribute("style");
    hit.removeAttribute("marker-end");
    hit.removeAttribute("marker-start");
    hit.setAttribute("class", "edge-hit");
    path.after(hit);
    const ends = endsOf(path);
    const label = labels[i2];
    const marker = path.getAttribute("marker-end");
    const note = tips[i2] || [];
    hit.addEventListener("mousemove", (ev) => showTip(note, ev));
    hit.addEventListener("mouseenter", (ev) => {
      showTip(note, ev);
      svg.classList.add("hovering");
      path.classList.add("edge-on");
      label?.classList.add("edge-on");
      ends.forEach((n2) => n2.classList.add("node-on"));
      const on = accentMarker(marker);
      if (on) path.setAttribute("marker-end", on);
    });
    hit.addEventListener("mouseleave", () => {
      hideTip();
      svg.classList.remove("hovering");
      path.classList.remove("edge-on");
      label?.classList.remove("edge-on");
      ends.forEach((n2) => n2.classList.remove("node-on"));
      if (marker) path.setAttribute("marker-end", marker);
    });
  });
}
function bindBoxTips(svg) {
  const boxes = Object.entries(boxMapOf(svg)).filter(
    ([id, g2]) => !g2.classList.contains("cluster") || itemOfNode[id] && contextById[itemOfNode[id].id]
  );
  const innermost = (target) => {
    let best = null;
    boxes.forEach(([id, g2]) => {
      if (g2.contains(target) && (!best || best.g.contains(g2))) best = { id, g: g2 };
    });
    return best ? best.id : null;
  };
  svg.addEventListener("mousemove", (ev) => {
    if (ev.target.closest(".edge-hit")) return;
    const id = innermost(ev.target) || "";
    const entries = aggregateOfNode[id] ? aggregateTipEntries(aggregateOfNode[id]) : boxTipEntries(itemOfNode[id]);
    if (entries.length) showTip(entries, ev);
    else hideTip();
  });
  svg.addEventListener("pointerleave", hideTip);
}

// src/context_mapper/template/arrowheads.js
function dropViolationHeads(svg, source) {
  const found = /^\s*%% violations: ([\d,]+)$/m.exec(source);
  if (!svg || !found) return;
  const paths = svg.querySelectorAll("path.flowchart-link");
  found[1].split(",").forEach((i2) => paths[Number(i2)]?.removeAttribute("marker-end"));
}

// src/context_mapper/template/roles.js
function drawRoleLabels(svg, source) {
  const found = /^\s*%% roles: (.+)$/m.exec(source);
  const kernels = /^\s*%% kernels: ([\d,]+)$/m.exec(source);
  if (!svg || !found && !kernels) return;
  const ns = "http://www.w3.org/2000/svg";
  const paths = svg.querySelectorAll("path.flowchart-link");
  const group = document.createElementNS(ns, "g");
  group.setAttribute("class", "role-labels");
  group.setAttribute("style", "pointer-events:none");
  const placed = [];
  let host = null;
  const measure = (path) => {
    if (!path || typeof path.getTotalLength !== "function") return null;
    const total = path.getTotalLength();
    if (!(total > 0)) return null;
    const at = (l2) => path.getPointAtLength(Math.min(Math.max(l2, 0), total));
    const a2 = at(0);
    const b2 = at(total);
    const chord = Math.hypot(b2.x - a2.x, b2.y - a2.y);
    if (!(chord > 0)) return null;
    let samples = null;
    const on = (want) => {
      const count = Math.min(Math.max(Math.round(total), 60), 3e3);
      samples = samples || Array.from({ length: count }, (_2, i2) => at(total * i2 / (count - 1)));
      return samples.reduce(
        (best, p2) => Math.hypot(p2.x - want.x, p2.y - want.y) < Math.hypot(best.x - want.x, best.y - want.y) ? p2 : best
      );
    };
    return {
      a: a2,
      b: b2,
      chord,
      at,
      total,
      on,
      u: { x: (b2.x - a2.x) / chord, y: (b2.y - a2.y) / chord }
    };
  };
  const badge = (x2, y2, width, height, text) => {
    placed.push({ x: x2, y: y2, width, height });
    const box = document.createElementNS(ns, "rect");
    box.setAttribute("x", x2 - width / 2);
    box.setAttribute("y", y2 - height / 2);
    box.setAttribute("width", width);
    box.setAttribute("height", height);
    box.setAttribute("rx", 3);
    box.setAttribute(
      "style",
      "fill:#fff;fill-opacity:0.92;stroke:#8a8a8a;stroke-width:0.75px"
    );
    const label = document.createElementNS(ns, "text");
    label.setAttribute("x", x2);
    label.setAttribute("y", y2);
    label.setAttribute("text-anchor", "middle");
    label.setAttribute("dominant-baseline", "central");
    label.setAttribute(
      "style",
      "fill:#1a1a1a;font-size:11px;font-weight:600;stroke:none"
    );
    label.textContent = text;
    group.append(box, label);
  };
  const sizeOf = (text) => ({ width: text.length * 7 + 8, height: 15 });
  const reachOf = (size, d2) => (Math.abs(d2.x) * size.width + Math.abs(d2.y) * size.height) / 2;
  const place = (line, end, text) => {
    const size = sizeOf(text);
    const start = end === "start";
    const tip2 = start ? line.a : line.b;
    const next = line.at(start ? 3 : line.total - 3);
    const span = Math.hypot(next.x - tip2.x, next.y - tip2.y) || 1;
    const inward = { x: (next.x - tip2.x) / span, y: (next.y - tip2.y) / span };
    const reach = (d2) => reachOf(size, d2);
    const travel = start ? inward : { x: -inward.x, y: -inward.y };
    const normal = { x: -travel.y, y: travel.x };
    const gap = start ? 2 : 9;
    const along = Math.min(reach(inward) + gap, line.chord / 2);
    const wanted = { x: tip2.x + inward.x * along, y: tip2.y + inward.y * along };
    const center = line.on(wanted);
    const away = reach(normal) + 2;
    let x2 = center.x + normal.x * away;
    let y2 = center.y + normal.y * away;
    const hits = () => placed.some(
      (r2) => Math.abs(r2.x - x2) < (r2.width + size.width) / 2 && Math.abs(r2.y - y2) < (r2.height + size.height) / 2
    );
    for (let tries = 0; hits() && tries < 20; tries++) {
      x2 += normal.x * 3;
      y2 += normal.y * 3;
    }
    badge(x2, y2, size.width, size.height, text);
  };
  (found ? found[1].split(";") : []).forEach((mark) => {
    const [index, roles] = mark.split("=");
    const path = paths[Number(index)];
    const line = roles ? measure(path) : null;
    if (!line) return;
    const [upstream, downstream] = roles.split(">").map((side) => side.split(",").filter(Boolean).join(", "));
    host = host || path.parentNode.parentNode;
    if (downstream) place(line, "start", downstream);
    if (upstream) place(line, "end", upstream);
  });
  const labelBox = (index) => {
    const label = svg.querySelectorAll(".edgeLabel")[index];
    if (!label || !(label.textContent || "").trim()) return null;
    if (typeof label.getBoundingClientRect !== "function") return null;
    const r2 = label.getBoundingClientRect();
    if (!(r2.width > 0)) return null;
    const m2 = host?.getScreenCTM?.()?.inverse?.();
    const to = (x2, y2) => m2 ? { x: m2.a * x2 + m2.c * y2 + m2.e, y: m2.b * x2 + m2.d * y2 + m2.f } : { x: x2, y: y2 };
    const a2 = to(r2.left, r2.top);
    const b2 = to(r2.right, r2.bottom);
    return {
      x: (a2.x + b2.x) / 2,
      y: (a2.y + b2.y) / 2,
      width: Math.abs(b2.x - a2.x),
      height: Math.abs(b2.y - a2.y)
    };
  };
  (kernels ? kernels[1].split(",") : []).forEach((index) => {
    const path = paths[Number(index)];
    const line = measure(path);
    if (!line) return;
    host = host || path.parentNode.parentNode;
    const text = "SK";
    const size = sizeOf(text);
    const avoid = [...placed];
    const label = labelBox(Number(index));
    if (label) avoid.push(label);
    const clear = (p2) => !avoid.some(
      (r2) => Math.abs(r2.x - p2.x) < (r2.width + size.width) / 2 + 1 && Math.abs(r2.y - p2.y) < (r2.height + size.height) / 2 + 1
    );
    const { a: a2, b: b2, chord, u: u2 } = line;
    const reach = (d2) => reachOf(size, d2);
    const head = path.getAttribute("marker-end") ? 12 : 4;
    const tail = 4;
    const lo = tail + reach(u2);
    const hi = chord - head - reach(u2);
    if (hi >= lo) {
      const middle2 = Math.min(Math.max(chord / 2, lo), hi);
      for (let step = 0; step <= 20; step++) {
        const along = middle2 + (step % 2 ? 1 : -1) * Math.ceil(step / 2) * 8;
        if (along < lo || along > hi) continue;
        const at2 = line.on({ x: a2.x + u2.x * along, y: a2.y + u2.y * along });
        if (clear(at2)) {
          badge(at2.x, at2.y, size.width, size.height, text);
          return;
        }
      }
    }
    const normal = { x: -u2.y, y: u2.x };
    const away = reach(normal) + 2;
    const middle = { x: (a2.x + b2.x) / 2, y: (a2.y + b2.y) / 2 };
    let at = { x: middle.x + normal.x * away, y: middle.y + normal.y * away };
    for (let step = 1; !clear(at) && step <= 6; step++)
      at = {
        x: at.x + normal.x * (reach(normal) * 2 + 2),
        y: at.y + normal.y * (reach(normal) * 2 + 2)
      };
    badge(at.x, at.y, size.width, size.height, text);
  });
  if (group.childNodes.length) (host || svg).appendChild(group);
}

// src/context_mapper/template/dom/controls.js
var levelSel = $2("level");
var focusSel = $2("focus");
var depthIn = $2("depth");
var dirSel = $2("dir");
(function fillFocus() {
  const byName = (a2, b2) => a2.name.localeCompare(b2.name);
  const group = (label, items) => {
    if (!items.length) return;
    const og = document.createElement("optgroup");
    og.label = label;
    items.sort(byName).forEach((i2) => og.appendChild(new Option(i2.name, i2.id)));
    focusSel.appendChild(og);
  };
  group("Domains", [...MODEL.domains]);
  group("Clusters", [...MODEL.clusters]);
  [...MODEL.domains].sort(byName).forEach(
    (d2) => group(
      `Bounded contexts: ${d2.name}`,
      MODEL.contexts.filter((c2) => c2.domain === d2.id && !domainById[c2.id])
    )
  );
})();
(function fillLinks() {
  const nav = $2("links");
  Object.entries(MODEL.links || {}).forEach(([label, url]) => {
    const a2 = document.createElement("a");
    a2.href = url;
    a2.textContent = label;
    nav.appendChild(a2);
  });
  if (!nav.childElementCount) nav.remove();
})();
var displaySels = {};
var toggles = {};
function buildControls() {
  const nameSpan = (name) => {
    const span = document.createElement("span");
    span.className = "name";
    span.textContent = name;
    return span;
  };
  const addSelect = (id, name, cluster) => {
    const label = document.createElement("label");
    label.className = "row";
    const span = nameSpan(name);
    if (cluster) span.classList.add("cluster");
    label.appendChild(span);
    const sel = document.createElement("select");
    MODES.forEach(([value, text]) => sel.appendChild(new Option(text, value)));
    label.appendChild(sel);
    $2("display").appendChild(label);
    displaySels[id] = sel;
  };
  const addToggle = (id, name) => {
    const label = document.createElement("label");
    label.className = "row";
    label.appendChild(nameSpan(name));
    const hint = document.createElement("span");
    hint.className = "hint";
    const link2 = document.createElement("a");
    link2.className = "toggle";
    label.append(hint, link2);
    $2("display").appendChild(label);
    toggles[id] = { row: label, hint, link: link2 };
  };
  const sub = (text) => {
    const heading = document.createElement("h4");
    heading.textContent = text;
    $2("display").appendChild(heading);
  };
  sub("Domains");
  MODEL.domains.forEach(
    (d2) => (d2.single ? addToggle : addSelect)(d2.id, d2.name)
  );
  sub("Clusters");
  MODEL.clusters.forEach((c2) => addSelect(c2.id, c2.name, true));
}
buildControls();
var displayModes = () => Object.fromEntries(
  Object.entries(displaySels).map(([id, sel]) => [id, sel.value])
);
var hiddenContexts = new Set(DEFAULT_HIDE);
var refreshToggles = () => Object.entries(toggles).forEach(([id, t2]) => {
  const hidden = hiddenContexts.has(id);
  t2.link.removeAttribute("data-hide");
  t2.link.removeAttribute("data-show");
  t2.link.setAttribute(hidden ? "data-show" : "data-hide", id);
  t2.link.textContent = hidden ? "show" : "hide";
  t2.hint.textContent = hidden ? "(hidden)" : "";
  t2.row.classList.toggle("off", hidden);
});
function state() {
  depthIn.value = clampDepth(depthIn.value);
  return {
    level: levelSel.value,
    focus: focusSel.value,
    depth: Number(depthIn.value),
    dir: dirSel.value,
    display: displayModes(),
    hide: new Set(hiddenContexts)
  };
}
function readHash() {
  const s2 = parseHash(location.hash.slice(1));
  levelSel.value = s2.level;
  focusSel.value = s2.focus;
  depthIn.value = s2.depth;
  dirSel.value = s2.dir;
  Object.entries(displaySels).forEach(([id, sel]) => {
    sel.value = s2.display[id];
  });
  hiddenContexts.clear();
  s2.hide.forEach((id) => hiddenContexts.add(id));
}
var setHidden = (id, hide) => {
  hiddenContexts[hide ? "add" : "delete"](id);
  if (displaySels[id])
    displaySels[id].value = hide ? "hidden" : defaultMode(id);
};

// src/context_mapper/template/download.js
function standaloneSvg(svg) {
  const clone = svg.cloneNode(true);
  clone.classList.remove("hovering");
  clone.querySelectorAll(".edge-hit").forEach((n2) => n2.remove());
  clone.querySelectorAll("[id$='-on']").forEach((copy) => {
    const original = copy.id.slice(0, -3);
    clone.querySelectorAll("[marker-end]").forEach((el) => {
      if (el.getAttribute("marker-end").includes(copy.id))
        el.setAttribute("marker-end", `url(#${original})`);
    });
    copy.remove();
  });
  clone.querySelectorAll("a").forEach((a2) => {
    a2.removeAttribute("href");
    a2.removeAttributeNS("http://www.w3.org/1999/xlink", "href");
  });
  const parts = (clone.getAttribute("viewBox") || "").trim().split(/\s+/).map(Number);
  const width = parts.length === 4 ? parts[2] : svg.getBoundingClientRect().width;
  const height = parts.length === 4 ? parts[3] : svg.getBoundingClientRect().height;
  clone.setAttribute("width", Math.round(width));
  clone.setAttribute("height", Math.round(height));
  clone.removeAttribute("style");
  clone.style.fontFamily = getComputedStyle(svg).fontFamily;
  const background = document.createElementNS(
    "http://www.w3.org/2000/svg",
    "rect"
  );
  if (parts.length === 4) {
    background.setAttribute("x", parts[0]);
    background.setAttribute("y", parts[1]);
  }
  background.setAttribute("width", "100%");
  background.setAttribute("height", "100%");
  const pageBg = getComputedStyle(document.body).backgroundColor;
  background.setAttribute(
    "fill",
    pageBg === "rgba(0, 0, 0, 0)" ? "#ffffff" : pageBg
  );
  clone.insertBefore(background, clone.firstChild);
  return {
    text: '<?xml version="1.0" encoding="UTF-8"?>\n' + new XMLSerializer().serializeToString(clone),
    width: Math.round(width),
    height: Math.round(height)
  };
}
function saveBlob(blob, filename) {
  const a2 = document.createElement("a");
  a2.href = URL.createObjectURL(blob);
  a2.download = filename;
  a2.click();
  setTimeout(() => URL.revokeObjectURL(a2.href), 1e3);
}
function downloadDiagram(svg, format, name) {
  const { text, width, height } = standaloneSvg(svg);
  if (format === "svg") {
    saveBlob(
      new Blob([text], { type: "image/svg+xml;charset=utf-8" }),
      name + ".svg"
    );
    return;
  }
  const scale = Math.min(2, 16384 / Math.max(width, height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  const img = new Image();
  img.onload = () => {
    const ctx = canvas.getContext("2d");
    const bg = getComputedStyle(document.body).backgroundColor;
    ctx.fillStyle = bg === "rgba(0, 0, 0, 0)" ? "#ffffff" : bg;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((blob) => blob && saveBlob(blob, name + ".png"), "image/png");
  };
  img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(text);
}

// src/context_mapper/template/app.js
if (DIAGRAM.elk) mermaid.registerLayoutLoaders(elkLayouts);
mermaid.initialize({ startOnLoad: false, securityLevel: "loose" });
var renderCount = 0;
async function render2() {
  const s2 = state();
  history.replaceState(null, "", hashFor(s2) || location.pathname);
  const { source, visible, tips } = mermaidSource(s2);
  renderInfo(s2, visible);
  refreshToggles();
  const run = ++renderCount;
  try {
    const { svg, bindFunctions } = await mermaid.render(
      "diagram-" + run,
      source
    );
    if (run !== renderCount) return;
    $2("graph").innerHTML = svg;
    bindFunctions?.($2("graph"));
    const svgEl = $2("graph").querySelector("svg");
    dropViolationHeads(svgEl, source);
    drawRoleLabels(svgEl, source);
    bindEdgeHover(svgEl, tips);
    bindBoxTips(svgEl);
  } catch (err) {
    if (run === renderCount)
      $2("graph").textContent = "Could not render this diagram: " + err.message;
  }
}
$2("panel").addEventListener("click", (ev) => {
  const hideToggle = ev.target.closest("[data-hide]");
  if (hideToggle) {
    setHidden(hideToggle.dataset.hide, true);
    render2();
    return;
  }
  const showToggle = ev.target.closest("[data-show]");
  if (showToggle) {
    setHidden(showToggle.dataset.show, false);
    render2();
    return;
  }
  const go = ev.target.closest("[data-go]");
  if (go) {
    focusSel.value = go.dataset.go;
    render2();
  }
});
[levelSel, focusSel, depthIn, dirSel].forEach(
  (el) => el.addEventListener("change", render2)
);
Object.entries(displaySels).forEach(
  ([id, sel]) => sel.addEventListener("change", () => {
    hiddenContexts.delete(id);
    render2();
  })
);
$2("reset").addEventListener("click", () => {
  history.replaceState(null, "", location.pathname);
  readHash();
  render2();
});
window.addEventListener("hashchange", () => {
  readHash();
  render2();
});
$2("download").addEventListener("click", () => {
  const svg = $2("graph").querySelector("svg");
  if (!svg) return;
  const s2 = state();
  const name = ["context-map", s2.focus, s2.level === "context" ? null : s2.level].filter(Boolean).join("-");
  downloadDiagram(svg, $2("image").value, name);
});
readHash();
render2();
