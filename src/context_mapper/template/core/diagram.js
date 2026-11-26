import {
  MODEL,
  domainById,
  contextById,
  clusterById,
  owner,
  nameOf,
  DIAGRAM,
  defaultMode,
} from "./model.js";
import { GRAPHS, focusSet, descendants, walk } from "./graph.js";
import { hashFor } from "./state.js";
import { roleCodes, roleText } from "./roles.js";

// Same diagram as mermaid.py's render(): keep the two in step.
export const nodeId = (id) => id.replace(/\W/g, "_");
export const quote = (value) => value.replaceAll('"', "#quot;");
// A node id in the page is an id with every non-word character turned into an
// underscore, so `audit-log` reaches the DOM as `audit_log`. This maps back to the
// item, for the places that read ids out of the SVG.
export const itemOfNode = {};
[...MODEL.contexts, ...MODEL.domains, ...MODEL.clusters].forEach(
  (item) => (itemOfNode[nodeId(item.id)] = item),
);

// Mermaid style strings (`key:value,key:value`) laid over each other: a later
// one wins a key it sets, and the keys keep the order they first appeared in.
const mergeStyles = (...styles) => {
  const merged = new Map();
  styles.forEach((style) =>
    (style || "")
      .split(",")
      .filter(Boolean)
      .forEach((part) => {
        const at = part.indexOf(":");
        merged.set(part.slice(0, at), part.slice(at + 1));
      }),
  );
  return [...merged].map(([k, v]) => `${k}:${v}`).join(",");
};
// The style of an edge kind, or of two laid over each other, `dotted+sharedKernel`.
const styleOf = (kind) =>
  mergeStyles(...kind.split("+").map((k) => DIAGRAM.edge_styles[k] || ""));

export function mermaidSource(s) {
  const g = GRAPHS[s.level];
  let starts = focusSet(s.level, s.focus);
  const containers = [
    ...MODEL.domains.filter((d) => !d.single),
    ...MODEL.clusters,
  ];
  const state = {};
  containers.forEach(
    (d) =>
      (state[d.id] = starts.has(d.id)
        ? "expanded"
        : s.display[d.id] || defaultMode(d.id)),
  );
  // What isn't shown: containers set to hidden, with everything inside them,
  // plus the bounded contexts hidden here. The focus itself is never hidden.
  const hidden = descendants(g, [
    ...containers.filter((d) => state[d.id] === "hidden").map((d) => d.id),
    ...s.hide,
  ]);
  if (s.focus) {
    starts = new Set([...starts].filter((id) => !hidden.has(id)));
    starts.add(s.focus);
    if (s.level === "domain" && owner[s.focus]) starts.add(owner[s.focus]);
  }
  const visible = walk(g, starts, s.depth, s.dir, hidden);

  const kidsOf = {};
  Object.entries(g.childOf).forEach(([c, p]) =>
    (kidsOf[p] = kidsOf[p] || []).push(c),
  );
  const held = (d) =>
    (s.level === "context"
      ? (d.contexts || []).filter((c) => c !== d.id)
      : []
    ).concat((d.members || []).filter((m) => m !== d.id));
  const folded = {}; // node -> the collapsed container it folded into
  const fold = (cid, into) =>
    (kidsOf[cid] || []).forEach((child) => {
      if (starts.has(child)) return;
      if (visible.has(child)) folded[child] = into;
      fold(child, into);
    });
  const collapsedAncestor = (cid) => {
    let p = g.childOf[cid];
    while (p) {
      if (state[p] === "collapsed") return true;
      p = g.childOf[p];
    }
    return false;
  };
  containers
    .filter((d) => state[d.id] === "collapsed" && !collapsedAncestor(d.id))
    .forEach((d) => fold(d.id, d.id));

  const lines = [
    "---",
    JSON.stringify({ config: DIAGRAM.config }),
    "---",
    `flowchart ${DIAGRAM.direction}`,
  ];
  Object.entries(MODEL.types).forEach(([id, t]) =>
    lines.push(`  classDef ${id} ${t.mermaid_style}`),
  );
  lines.push(`  classDef focus ${DIAGRAM.focus_style}`);

  const plainNodes = [];
  const drawn = new Set();
  const box = (id, label, type, indent) => {
    plainNodes.push(id);
    drawn.add(id);
    return `${indent}${nodeId(id)}["${label}"]${type ? ":::" + type : ""}`;
  };

  const drawChild = (c, indent) => {
    if (contextById[c] && !domainById[c]) {
      const out = [
        box(c, quote(contextById[c].name), contextById[c].type, indent),
      ];
      if (contextById[c].mermaid_style)
        out.push(`${indent}style ${nodeId(c)} ${contextById[c].mermaid_style}`);
      return out;
    }
    return drawEntry(domainById[c], indent);
  };

  function drawEntry(d, indent) {
    if (folded[d.id] || (hidden.has(d.id) && d.id !== s.focus)) return [];
    const st = state[d.id] || "expanded";
    if (st === "hidden") return [];
    const isCluster = !domainById[d.id];
    const kids = held(d);
    const foldedKids = kids.filter((c) => folded[c] === d.id);
    const inside = kids.filter((c) => visible.has(c) && !folded[c]);
    if (isCluster) {
      // A cluster isn't a node in the walk: it draws only through what it holds.
      // The focus is the exception: with everything it holds hidden, it is
      // still one box of its own.
      if (st === "collapsed" && !foldedKids.length) return [];
      if (st === "expanded" && !inside.length && d.id !== s.focus) return [];
    } else if (
      !visible.has(d.id) &&
      !foldedKids.length &&
      !inside.length &&
      !kids.some((c) => starts.has(c))
    ) {
      // Not reached itself, holds nothing that was reached, and no start
      // either. A domain that holds one of those — the focus of a
      // bounded-context view, or a context reached on its own — still draws,
      // so it has a box to appear in.
      return [];
    }
    if (st === "contents") return inside.flatMap((c) => drawChild(c, indent));
    if (st === "expanded" && kids.length) {
      let show = inside;
      if (!show.length) {
        // Nothing inside was reached: show what is there that isn't hidden.
        // A start is never hidden, not even by `hide`.
        show = kids.filter(
          (c) => !folded[c] && (!hidden.has(c) || starts.has(c)),
        );
      }
      if (show.length) {
        drawn.add(d.id);
        const out = [`${indent}subgraph ${nodeId(d.id)}["${quote(d.name)}"]`];
        show.forEach((c) => out.push(...drawChild(c, indent + "  ")));
        out.push(`${indent}end`);
        let style = d.mermaid_style || DIAGRAM.domain_style;
        if (d.id === s.focus) style += "," + DIAGRAM.focus_style;
        out.push(`${indent}style ${nodeId(d.id)} ${style}`);
        return out;
      }
    }
    let label = quote(d.name);
    if (DIAGRAM.child_labels && !d.single) {
      const named = (d.contexts || [])
        .filter((c) => c !== d.id && !hidden.has(c))
        .map(nameOf)
        .concat((d.members || []).filter((m) => folded[m] === d.id).map(nameOf))
        .sort();
      if (named.length)
        label = `<b>${label}</b><br/>${quote(named.join(", "))}`;
    }
    const out = [box(d.id, label, d.type, indent)];
    if (d.mermaid_style)
      out.push(`${indent}style ${nodeId(d.id)} ${d.mermaid_style}`);
    return out;
  }

  // A domain drawn inside another container comes from that container's own drawing.
  const opens = new Set(
    Object.entries(state)
      .filter(([, st]) => st === "expanded" || st === "contents")
      .map(([id]) => id)
      .filter(
        (id) =>
          (domainById[id] ? visible.has(id) : true) &&
          !folded[id] &&
          !hidden.has(id),
      ),
  );
  const atTop = (d) => !opens.has(g.childOf[d.id]);

  if (DIAGRAM.group_by_type) {
    Object.entries(MODEL.types).forEach(([typeId, t]) => {
      const block = MODEL.domains
        .filter((d) => d.type === typeId && atTop(d))
        .flatMap((d) => drawEntry(d, "    "));
      if (block.length)
        lines.push(
          `  subgraph type_${typeId}["${quote(t.name)}"]`,
          ...block,
          "  end",
        );
    });
  } else {
    MODEL.domains
      .filter(atTop)
      .forEach((d) => lines.push(...drawEntry(d, "  ")));
    MODEL.clusters.forEach((c) => lines.push(...drawEntry(c, "  ")));
  }

  // Merge edges that land on the same pair once containers are collapsed.
  const target = (n) => folded[n] || n;
  const foldedBoxes = new Set(Object.values(folded));
  const merged = new Map();
  g.edges.forEach((e) => {
    if (!visible.has(e.from) || !visible.has(e.to)) return;
    const a = target(e.from),
      b = target(e.to);
    if (a === b || !drawn.has(a) || !drawn.has(b)) return;
    const key = a + "|" + b;
    if (!merged.has(key))
      merged.set(key, {
        a,
        b,
        styles: new Set(),
        names: new Set(),
        roles: new Set(),
        via: [],
      });
    const entry = merged.get(key);
    e.styles.forEach((x) => entry.styles.add(x));
    entry.roles.add(JSON.stringify([e.upstream || [], e.downstream || []]));
    entry.via.push(...e.via);
    if (foldedBoxes.has(b)) entry.names.add(nameOf(e.to));
    else if (foldedBoxes.has(a)) entry.names.add(nameOf(e.from));
  });
  // A partnership or a shared kernel is a line with no heads. The ones of a
  // kind between the same two boxes become one once containers are collapsed.
  // A shared kernel does not take the direction away, so where a dependency is
  // drawn between its two boxes the kernel rides on that arrow, in the
  // kernel's style and with its label, and gets no line of its own: one edge
  // per pair. Every other one is a line, drawn after the violations, and the
  // entry that declared it takes the upstream's place, as the target of the
  // line does: on top with the default direction. Moving the declaration to
  // the other entry flips the line.
  const symmetric = new Map();
  g.links.forEach((l) => {
    if (!visible.has(l.a) || !visible.has(l.b)) return;
    const a = target(l.a),
      b = target(l.b);
    if (a === b || !drawn.has(a) || !drawn.has(b)) return;
    const key = l.kind + "|" + [a, b].sort().join("|");
    if (!symmetric.has(key))
      symmetric.set(key, { kind: l.kind, a, b, names: new Set(), via: [] });
    const entry = symmetric.get(key);
    entry.via.push(...l.via);
    if (foldedBoxes.has(b)) entry.names.add(nameOf(l.b));
    else if (foldedBoxes.has(a)) entry.names.add(nameOf(l.a));
  });
  const loneLinks = [];
  symmetric.forEach((entry) => {
    const carrier =
      entry.kind === "sharedKernel"
        ? [entry.a + "|" + entry.b, entry.b + "|" + entry.a].find((k) =>
            merged.has(k),
          )
        : undefined;
    if (carrier) merged.get(carrier).kernel = entry;
    else loneLinks.push(entry);
  });
  const byStyle = {};
  // What the tooltip of each arrow says, in the order the arrows are drawn:
  // its dependencies, and the shared kernel it carries.
  const tips = [...merged.values()].map((entry) =>
    entry.via
      .filter((e) => e.comment || roleText(e))
      .map(tipEntry)
      .concat(entry.kernel ? entry.kernel.via.map(linkTipEntry) : []),
  );
  const roleMarks = []; // `index=upstream>downstream`, for the page's script
  const kernelMarks = []; // the index of each edge that shares a kernel
  [...merged.values()].forEach((entry, i) => {
    const style = entry.styles.has("solid")
      ? "solid"
      : [...entry.styles].sort()[0];
    // Roles are kept only when every dependency the arrow stands for carries
    // the very same ones.
    let up = [],
      down = [];
    if (entry.roles.size === 1) {
      const [upstream, downstream] = JSON.parse([...entry.roles][0]);
      [up, down] = roleCodes({ upstream, downstream });
    }
    const labelLines = [];
    const names = new Set([...entry.names, ...(entry.kernel?.names || [])]);
    if (names.size && DIAGRAM.child_labels)
      labelLines.push([...names].sort().join(", "));
    if (entry.kernel && DIAGRAM.relationship_labels) kernelMarks.push(i);
    if ((up.length || down.length) && DIAGRAM.relationship_labels)
      roleMarks.push(`${i}=${up.join(",")}>${down.join(",")}`);
    const label = labelLines.length
      ? `|"${quote(labelLines.join("<br/>"))}"|`
      : "";
    lines.push(
      `  ${nodeId(entry.a)} ${style === "dotted" ? "-.->" : "-->"}${label} ${nodeId(entry.b)}`,
    );
    const key = entry.kernel ? `${style}+sharedKernel` : style;
    (byStyle[key] = byStyle[key] || []).push(i);
  });
  // A violation is drawn after the real dependencies, when both ends are
  // drawn. Folded into a collapsed box it can land on a pair that depends
  // that way anyway, and then the dependency says it all.
  const violations = new Map();
  g.violations.forEach((r) => {
    if (!visible.has(r.from) || !visible.has(r.to)) return;
    const a = target(r.from),
      b = target(r.to);
    const key = a + "|" + b;
    if (a === b || !drawn.has(a) || !drawn.has(b) || merged.has(key)) return;
    if (!violations.has(key)) violations.set(key, { a, b, via: [] });
    violations.get(key).via.push(...r.via);
  });
  [...violations.values()].forEach((entry) => {
    // Drawn the way the dependency runs, not the way the violation points: see arrowheads.js.
    lines.push(`  ${nodeId(entry.b)} <--> ${nodeId(entry.a)}`);
    (byStyle.violation = byStyle.violation || []).push(tips.length);
    tips.push(entry.via.map(violationTipEntry));
  });
  loneLinks.forEach((entry) => {
    const info = MODEL.symmetric_kinds[entry.kind];
    const labelLines = [];
    if (entry.names.size && DIAGRAM.child_labels)
      labelLines.push([...entry.names].sort().join(", "));
    // A line with no heads says it is a partnership on its own, but a plain
    // one doesn't say it is a kernel: the page's script draws a badge.
    if (entry.kind === "sharedKernel" && DIAGRAM.relationship_labels)
      kernelMarks.push(tips.length);
    const label = labelLines.length
      ? `|"${quote(labelLines.join("<br/>"))}"|`
      : "";
    lines.push(`  ${nodeId(entry.b)} ${info.link}${label} ${nodeId(entry.a)}`);
    (byStyle[entry.kind] = byStyle[entry.kind] || []).push(tips.length);
    tips.push(entry.via.map(linkTipEntry));
  });
  Object.entries(byStyle).forEach(([style, indexes]) =>
    lines.push(
      `  linkStyle ${indexes.join(",")} interpolate ${DIAGRAM.curve} ${styleOf(style)}`.trimEnd(),
    ),
  );

  if (byStyle.violation)
    lines.push(`  %% violations: ${byStyle.violation.join(",")}`);

  // The roles are drawn by the page's script, next to each end of the arrow:
  // see roles.js.
  if (roleMarks.length) lines.push(`  %% roles: ${roleMarks.join(";")}`);
  // So are the shared kernels, as a badge at the middle of the arrow.
  if (kernelMarks.length) lines.push(`  %% kernels: ${kernelMarks.join(",")}`);

  const highlight =
    s.level === "domain" && owner[s.focus] ? owner[s.focus] : s.focus;
  plainNodes.forEach((n) => {
    if (n === highlight) lines.push(`  class ${nodeId(n)} focus`);
  });
  // Clicking a box focuses on it, a cluster included. A plain link keeps back and forward working.
  plainNodes.forEach((n) => {
    if (owner[n] || clusterById[n])
      lines.push(`  click ${nodeId(n)} href "${hashFor({ ...s, focus: n })}"`);
  });
  return { source: lines.join("\n") + "\n", visible, tips };
}

// One entry of a tooltip: always a title (who depends on whom) and a description (the comment).
// An arrow can stand for several dependencies, so every entry names its own.
// A violation always has a tooltip: it is worth saying even without a reason.
export const violationTipEntry = (dep) => ({
  title: `${nameOf(dep.from)} → ${nameOf(dep.to)} (violation)`,
  text: dep.comment || "Against the direction of the dependencies.",
});

// The roles, when it has any, spelled out with their display names.
// A partnership or a shared kernel always has a tooltip: its kind, and the
// comment when there is one. A line can stand for several of them, each naming
// its own two ends.
export const linkTipEntry = (link) => {
  const entry = {
    title: `${nameOf(link.a)} ↔ ${nameOf(link.b)} (${MODEL.symmetric_kinds[link.kind].name})`,
  };
  if (link.comment) entry.text = link.comment;
  return entry;
};

export const tipEntry = (dep) => {
  const entry = { title: `${nameOf(dep.from)} → ${nameOf(dep.to)}` };
  const roles = roleText(dep);
  if (roles) entry.roles = roles;
  if (dep.comment) entry.text = dep.comment;
  return entry;
};
