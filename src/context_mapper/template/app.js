import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";

const MODEL = /*__MODEL__*/null;

// Lookups. A "single" domain is one bounded context with the same id.
const domainById = Object.fromEntries(MODEL.domains.map(d => [d.id, d]));
const contextById = Object.fromEntries(MODEL.contexts.map(c => [c.id, c]));
const clusterById = Object.fromEntries(MODEL.clusters.map(c => [c.id, c]));
const owner = {};
MODEL.contexts.forEach(c => owner[c.id] = c.domain);
MODEL.domains.forEach(d => owner[d.id] = d.id);
const nameOf = id => (contextById[id] || domainById[id]).name;
const isMulti = id => domainById[id] && !domainById[id].single;

// Same graphs as graph.py: context level as written, domain level lifted and merged.
// childOf says which container a node renders inside: a context inside its domain, a member inside its cluster.
function levelGraph(level) {
  const childOf = {};
  MODEL.domains.filter(d => d.cluster).forEach(d => childOf[d.id] = d.cluster);
  if (level === "context") {
    const nodes = new Set([...MODEL.contexts.map(c => c.id), ...MODEL.domains.filter(d => !d.single).map(d => d.id)]);
    MODEL.contexts.filter(c => !domainById[c.domain].single).forEach(c => childOf[c.id] = c.domain);
    return { nodes, childOf, edges: MODEL.edges.map(e => ({ from: e.from, to: e.to, styles: new Set([e.style]), via: [e] })) };
  }
  const merged = new Map();
  MODEL.edges.forEach(e => {
    const a = owner[e.from], b = owner[e.to];
    if (a === b) return;
    const key = a + "|" + b;
    if (!merged.has(key)) merged.set(key, { from: a, to: b, styles: new Set(), via: [] });
    merged.get(key).styles.add(e.style);
    merged.get(key).via.push(e);
  });
  return { nodes: new Set(MODEL.domains.map(d => d.id)), childOf,
           edges: [...merged.values()] };
}
const GRAPHS = { context: levelGraph("context"), domain: levelGraph("domain") };

// A container and everything rendered inside it.
function descendants(g, ids) {
  const kids = {};
  Object.entries(g.childOf).forEach(([c, p]) => (kids[p] = kids[p] || []).push(c));
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

function focusSet(level, focus) {
  if (!focus) return new Set();
  if (clusterById[focus]) {
    const starts = new Set([focus, ...clusterById[focus].members]);
    if (level === "context") clusterById[focus].members.forEach(m => domainById[m].contexts.forEach(c => starts.add(c)));
    return starts;
  }
  if (level === "domain") return new Set([owner[focus]]);
  if (isMulti(focus)) return new Set([focus, ...domainById[focus].contexts]);
  return new Set([focus]);
}

function walk(g, starts, depth, dir, hidden) {
  const allowed = n => starts.has(n) || !hidden.has(n);
  if (!starts.size) return new Set([...g.nodes].filter(allowed));
  const up = {}, down = {};
  g.nodes.forEach(n => { up[n] = []; down[n] = []; });
  g.edges.forEach(e => { up[e.from].push(e.to); down[e.to].push(e.from); });
  const seen = new Set(starts);
  const go = next => {
    let frontier = [...starts];
    for (let i = 0; i < depth && frontier.length; i++) {
      const nf = [];
      frontier.forEach(n => (next[n] || []).forEach(m => { if (!seen.has(m) && allowed(m)) { seen.add(m); nf.push(m); } }));
      frontier = nf;
    }
  };
  if (dir !== "down") go(up);
  if (dir !== "up") go(down);
  return seen;
}

function relations(id) {
  const g = isMulti(id) ? GRAPHS.domain : GRAPHS.context;
  const byName = (a, b) => nameOf(a).localeCompare(nameOf(b));
  return {
    ups: g.edges.filter(e => e.from === id).map(e => e.to).sort(byName),
    downs: g.edges.filter(e => e.to === id).map(e => e.from).sort(byName),
  };
}

const $ = id => document.getElementById(id);
const levelSel = $("level"), focusSel = $("focus"), depthSel = $("depth"), dirSel = $("dir");

(function fillFocus() {
  const byName = (a, b) => a.name.localeCompare(b.name);
  const group = (label, items) => {
    const og = document.createElement("optgroup");
    og.label = label;
    items.sort(byName).forEach(i => og.appendChild(new Option(i.name, i.id)));
    focusSel.appendChild(og);
  };
  group("Domains", [...MODEL.domains]);
  group("Clusters", [...MODEL.clusters]);
  group("Bounded contexts", MODEL.contexts.filter(c => !domainById[c.id]));
})();

const DIAGRAM = MODEL.mermaid;

// A container first renders as the view says, else as its own `defaultDisplay` says, else expanded.
const defaultDisplayOf = id => (clusterById[id] || domainById[id]).defaultDisplay || "expanded";
const STYLE_HIDE = DIAGRAM.hide || [];
const defaultMode = id => {
  const d = DIAGRAM.display;
  if (d === null || d === undefined) return defaultDisplayOf(id);
  return typeof d === "object" ? (d[id] || defaultDisplayOf(id)) : d;
};
const MODES = [["expanded", "Expanded"], ["collapsed", "Collapsed"], ["contents", "Contents"], ["hidden", "Hidden"]];
const displaySels = {};
const toggles = {};  // a single domain — one plain box — as a hide/show toggle
// The panel's "Show & hide" form, built once so it survives the re-renders of
// the focus info above it: one row per domain and cluster, grouped by kind.
// A multi-context domain or a cluster gets a display select; a single domain
// gets a hide/show toggle instead, driven by `hiddenContexts` like the list
// toggles below.
function buildControls() {
  const nameSpan = name => {
    const span = document.createElement("span");
    span.className = "name";
    span.textContent = name;
    return span;
  };
  const addSelect = (id, name, cluster) => {
    const label = document.createElement("label");
    label.className = "row";
    const span = nameSpan(name);
    if (cluster) span.classList.add("cluster");   // a dashed underline, like the box it controls
    label.appendChild(span);
    const sel = document.createElement("select");
    MODES.forEach(([value, text]) => sel.appendChild(new Option(text, value)));
    label.appendChild(sel);
    $("display").appendChild(label);
    displaySels[id] = sel;
  };
  const addToggle = (id, name) => {
    const label = document.createElement("label");
    label.className = "row";
    label.appendChild(nameSpan(name));
    const hint = document.createElement("span");
    hint.className = "hint";
    const link = document.createElement("a");
    link.className = "toggle";
    label.append(hint, link);
    $("display").appendChild(label);
    toggles[id] = { row: label, hint, link };
  };
  const sub = text => {
    const h = document.createElement("h4");
    h.textContent = text;
    $("display").appendChild(h);
  };
  sub("Domains");
  MODEL.domains.forEach(d => (d.single ? addToggle : addSelect)(d.id, d.name));
  sub("Clusters");
  MODEL.clusters.forEach(c => addSelect(c.id, c.name, true));
}
buildControls();
const displayModes = () => Object.fromEntries(Object.entries(displaySels).map(([id, sel]) => [id, sel.value]));
// What `hide` in the style file keeps out, of any kind: a bounded context, a
// domain, a cluster member. The toggles below hide the same way, so a hidden
// item stays hidden even where focus would open it. A container's select
// mirrors the hide while it holds, and takes over the moment it is touched.
const DEFAULT_HIDE = new Set(STYLE_HIDE);
const hiddenContexts = new Set(DEFAULT_HIDE);

// The form's toggle links are static DOM: on every render, refresh what each
// one says and does — a hidden item's link shows it, a visible one's hides it.
const refreshToggles = () => Object.entries(toggles).forEach(([id, t]) => {
  const hidden = hiddenContexts.has(id);
  t.link.removeAttribute("data-hide");
  t.link.removeAttribute("data-show");
  t.link.setAttribute(hidden ? "data-show" : "data-hide", id);
  t.link.textContent = hidden ? "show" : "hide";
  t.hint.textContent = hidden ? "(hidden)" : "";
  t.row.classList.toggle("off", hidden);
});
if (DIAGRAM.elk) {
  const { default: elkLayouts } = await import("https://cdn.jsdelivr.net/npm/@mermaid-js/layout-elk@0/dist/mermaid-layout-elk.esm.min.mjs");
  mermaid.registerLayoutLoaders(elkLayouts);
}
mermaid.initialize({ startOnLoad: false, securityLevel: "loose" });

function state() {
  return { level: levelSel.value, focus: focusSel.value, depth: Number(depthSel.value), dir: dirSel.value,
           display: displayModes(), hide: new Set(hiddenContexts) };
}

function readHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  levelSel.value = p.get("level") === "domain" ? "domain" : "context";
  focusSel.value = p.has("focus") && (owner[p.get("focus")] || clusterById[p.get("focus")]) ? p.get("focus") : "";
  depthSel.value = p.get("depth") || "1";
  dirSel.value = p.get("dir") || "both";
  Object.entries(displaySels).forEach(([id, sel]) => {
    const m = p.get("display." + id);
    sel.value = MODES.some(([value]) => value === m) ? m : defaultMode(id);
  });
  hiddenContexts.clear();
  DEFAULT_HIDE.forEach(id => hiddenContexts.add(id));
  for (const [key, value] of p) {
    const m = /^hide\.(.+)$/.exec(key);
    if (!m) continue;
    if (value === "1") hiddenContexts.add(m[1]);
    else if (value === "0") hiddenContexts.delete(m[1]);
  }
  Object.entries(displaySels).forEach(([id, sel]) => { if (hiddenContexts.has(id)) sel.value = "hidden"; });
}

function hashFor(s) {
  const p = new URLSearchParams();
  if (s.level !== "context") p.set("level", s.level);
  if (s.focus) p.set("focus", s.focus);
  if (s.depth !== 1) p.set("depth", s.depth);
  if (s.dir !== "both") p.set("dir", s.dir);
  Object.entries(s.display).forEach(([id, mode]) => { if (mode !== defaultMode(id) && !s.hide.has(id)) p.set("display." + id, mode); });
  s.hide.forEach(id => { if (!DEFAULT_HIDE.has(id)) p.set("hide." + id, "1"); });
  DEFAULT_HIDE.forEach(id => { if (!s.hide.has(id)) p.set("hide." + id, "0"); });
  const h = p.toString();
  return h ? "#" + h : "";
}

// Same diagram as mermaid.py's render(): keep the two in step.
const nodeId = id => id.replace(/\W/g, "_");
const quote = value => value.replaceAll('"', "#quot;");
// A node id in the page is an id with every non-word character turned into an
// underscore, so `audit-log` reaches the DOM as `audit_log`. This maps back to the
// item, for the places that read ids out of the SVG.
const itemOfNode = {};
[...MODEL.contexts, ...MODEL.domains, ...MODEL.clusters].forEach(item => itemOfNode[nodeId(item.id)] = item);

function mermaidSource(s) {
  const g = GRAPHS[s.level];
  let starts = focusSet(s.level, s.focus);
  const containers = [...MODEL.domains.filter(d => !d.single), ...MODEL.clusters];
  const state = {};
  containers.forEach(d => state[d.id] = starts.has(d.id) ? "expanded" : (s.display[d.id] || defaultMode(d.id)));
  // What isn't shown: containers set to hidden, with everything inside them,
  // plus the bounded contexts hidden here. The focus itself is never hidden.
  const hidden = descendants(g, [...containers.filter(d => state[d.id] === "hidden").map(d => d.id), ...s.hide]);
  if (s.focus) {
    starts = new Set([...starts].filter(id => !hidden.has(id)));
    starts.add(s.focus);
    if (s.level === "domain" && owner[s.focus]) starts.add(owner[s.focus]);
  }
  const visible = walk(g, starts, s.depth, s.dir, hidden);

  const kidsOf = {};
  Object.entries(g.childOf).forEach(([c, p]) => (kidsOf[p] = kidsOf[p] || []).push(c));
  const held = d => (s.level === "context" ? (d.contexts || []).filter(c => c !== d.id) : [])
    .concat((d.members || []).filter(m => m !== d.id));
  const folded = {};  // node -> the collapsed container it folded into
  const fold = (cid, into) => (kidsOf[cid] || []).forEach(child => {
    if (starts.has(child)) return;
    if (visible.has(child)) folded[child] = into;
    fold(child, into);
  });
  const collapsedAncestor = cid => {
    let p = g.childOf[cid];
    while (p) { if (state[p] === "collapsed") return true; p = g.childOf[p]; }
    return false;
  };
  containers.filter(d => state[d.id] === "collapsed" && !collapsedAncestor(d.id)).forEach(d => fold(d.id, d.id));

  const lines = ["---", JSON.stringify({ config: DIAGRAM.config }), "---", `flowchart ${DIAGRAM.direction}`];
  Object.entries(MODEL.types).forEach(([id, t]) =>
    lines.push(`  classDef ${id} ${t.mermaid_style}`));
  lines.push(`  classDef focus ${DIAGRAM.focus_style}`);

  const plainNodes = [];
  const drawn = new Set();
  const box = (id, label, type, indent) => {
    plainNodes.push(id);
    drawn.add(id);
    return `${indent}${nodeId(id)}["${label}"]${type ? ":::" + type : ""}`;
  };

  const drawChild = (c, indent) =>
    (contextById[c] && !domainById[c]) ? [box(c, quote(contextById[c].name), contextById[c].type, indent)] : drawEntry(domainById[c], indent);

  function drawEntry(d, indent) {
    if (folded[d.id] || (hidden.has(d.id) && d.id !== s.focus)) return [];
    const st = state[d.id] || "expanded";
    if (st === "hidden") return [];
    const isCluster = !domainById[d.id];
    const kids = held(d);
    const foldedKids = kids.filter(c => folded[c] === d.id);
    const inside = kids.filter(c => visible.has(c) && !folded[c]);
    if (isCluster) {
      // A cluster isn't a node in the walk: it draws only through what it holds.
      // The focus is the exception: with everything it holds hidden, it is
      // still one box of its own.
      if (st === "collapsed" && !foldedKids.length) return [];
      if (st === "expanded" && !inside.length && d.id !== s.focus) return [];
    } else if (!visible.has(d.id) && !foldedKids.length && !kids.some(c => starts.has(c))) {
      // Not reached itself, and it holds no start either. A domain that holds
      // one — the focus of a bounded-context view, say — still draws, so the
      // start has a box to appear in.
      return [];
    }
    if (st === "contents") return inside.flatMap(c => drawChild(c, indent));
    if (st === "expanded" && kids.length) {
      let show = inside;
      if (!show.length || !visible.has(d.id)) {
        // Reached as a whole — or through a start it holds — so show what is
        // inside it. A start is never hidden, not even by `hide`.
        show = kids.filter(c => !folded[c] && (!hidden.has(c) || starts.has(c)));
      }
      if (show.length) {
        drawn.add(d.id);
        const out = [`${indent}subgraph ${nodeId(d.id)}["${quote(d.name)}"]`];
        show.forEach(c => out.push(...drawChild(c, indent + "  ")));
        out.push(`${indent}end`);
        let style = d.mermaid_style || DIAGRAM.domain_style;
        if (d.id === s.focus) style += "," + DIAGRAM.focus_style;
        out.push(`${indent}style ${nodeId(d.id)} ${style}`);
        return out;
      }
    }
    let label = quote(d.name);
    if (DIAGRAM.child_labels && !d.single) {
      const named = (d.contexts || []).filter(c => c !== d.id && !hidden.has(c)).map(nameOf)
        .concat((d.members || []).filter(m => folded[m] === d.id).map(nameOf)).sort();
      if (named.length) label = `<b>${label}</b><br/>${quote(named.join(", "))}`;
    }
    const out = [box(d.id, label, d.type, indent)];
    if (d.mermaid_style) out.push(`${indent}style ${nodeId(d.id)} ${d.mermaid_style}`);
    return out;
  }

  // A domain drawn inside another container comes from that container's own drawing.
  const opens = new Set(Object.entries(state).filter(([, st]) => st === "expanded" || st === "contents")
    .map(([id]) => id).filter(id => (domainById[id] ? visible.has(id) : true) && !folded[id] && !hidden.has(id)));
  const atTop = d => !opens.has(g.childOf[d.id]);

  if (DIAGRAM.group_by_type) {
    Object.entries(MODEL.types).forEach(([typeId, t]) => {
      const block = MODEL.domains.filter(d => d.type === typeId && atTop(d)).flatMap(d => drawEntry(d, "    "));
      if (block.length) lines.push(`  subgraph type_${typeId}["${quote(t.name)}"]`, ...block, "  end");
    });
  } else {
    MODEL.domains.filter(atTop).forEach(d => lines.push(...drawEntry(d, "  ")));
    MODEL.clusters.forEach(c => lines.push(...drawEntry(c, "  ")));
  }

  // Merge edges that land on the same pair once containers are collapsed.
  const target = n => folded[n] || n;
  const foldedBoxes = new Set(Object.values(folded));
  const merged = new Map();
  g.edges.forEach(e => {
    if (!visible.has(e.from) || !visible.has(e.to)) return;
    const a = target(e.from), b = target(e.to);
    if (a === b || !drawn.has(a) || !drawn.has(b)) return;
    const key = a + "|" + b;
    if (!merged.has(key)) merged.set(key, { a, b, styles: new Set(), names: new Set(), via: [] });
    const entry = merged.get(key);
    e.styles.forEach(x => entry.styles.add(x));
    entry.via.push(...e.via);
    if (foldedBoxes.has(b)) entry.names.add(nameOf(e.to));
    else if (foldedBoxes.has(a)) entry.names.add(nameOf(e.from));
  });
  const byStyle = {};
  // What the tooltip of each arrow says, in the order the arrows are drawn.
  const tips = [...merged.values()].map(entry => entry.via.filter(e => e.comment).map(tipEntry));
  [...merged.values()].forEach((entry, i) => {
    const style = entry.styles.has("solid") ? "solid" : [...entry.styles].sort()[0];
    const label = entry.names.size && DIAGRAM.child_labels ? `|"${quote([...entry.names].sort().join(", "))}"|` : "";
    lines.push(`  ${nodeId(entry.a)} ${style === "dotted" ? "-.->" : "-->"}${label} ${nodeId(entry.b)}`);
    (byStyle[style] = byStyle[style] || []).push(i);
  });
  Object.entries(byStyle).forEach(([style, indexes]) =>
    lines.push(`  linkStyle ${indexes.join(",")} interpolate ${DIAGRAM.curve} ${DIAGRAM.edge_styles[style] || ""}`.trimEnd()));

  const highlight = s.level === "domain" && owner[s.focus] ? owner[s.focus] : s.focus;
  plainNodes.forEach(n => { if (n === highlight) lines.push(`  class ${nodeId(n)} focus`); });
  // Clicking a box focuses on it, a cluster included. A plain link keeps back and forward working.
  plainNodes.forEach(n => { if (owner[n] || clusterById[n]) lines.push(`  click ${nodeId(n)} href "${hashFor({ ...s, focus: n })}"`); });
  return { source: lines.join("\n") + "\n", visible, tips };
}

let renderCount = 0;
async function render() {
  const s = state();
  history.replaceState(null, "", hashFor(s) || location.pathname);
  const { source, visible, tips } = mermaidSource(s);
  renderInfo(s, visible);
  refreshToggles();
  const run = ++renderCount;
  try {
    const { svg, bindFunctions } = await mermaid.render("diagram-" + run, source);
    if (run !== renderCount) return;  // a newer render took over
    $("graph").innerHTML = svg;
    bindFunctions?.($("graph"));
    const svgEl = $("graph").querySelector("svg");
    bindEdgeHover(svgEl, tips);
    bindBoxTips(svgEl);
  } catch (err) {
    if (run === renderCount) $("graph").textContent = "Could not render this diagram: " + err.message;
  }
}

// Boxes are g elements whose id holds our node id: "<svg>-flowchart-<id>-<n>", or "<svg>-<id>" for a domain.
function boxMapOf(svg) {
  const boxes = {};
  svg.querySelectorAll("g[id]").forEach(g => {
    const m = /-flowchart-(.+)-\d+$/.exec(g.id);
    if (m) boxes[m[1]] = g;
    else if (g.classList.contains("cluster")) boxes[g.id.slice(svg.id.length + 1)] = g;
  });
  Object.values(boxes).forEach(g => g.classList.add("box"));
  return boxes;
}

// Hovering an arrow highlights it, its arrowhead and the two boxes it joins, and shows its comments.
function bindEdgeHover(svg, tips) {
  if (!svg) return;
  const paths = [...svg.querySelectorAll("path.flowchart-link")];
  const labels = [...svg.querySelectorAll(".edgeLabel")];
  const boxes = boxMapOf(svg);
  // An edge id reads "<svg>-L_<from>_<to>_<n>". Ids may hold underscores, so match against the boxes we know.
  const endsOf = path => {
    const rest = path.id.slice(svg.id.length + 3).replace(/_\d+$/, "");
    for (const from of Object.keys(boxes)) {
      if (rest.startsWith(from + "_") && boxes[rest.slice(from.length + 1)]) return [boxes[from], boxes[rest.slice(from.length + 1)]];
    }
    return [];
  };
  const markers = {};  // an accent copy of each arrowhead, made on demand
  const accentMarker = ref => {
    const m = /url\(["']?#([^"')]+)["']?\)/.exec(ref || "");
    const src = m && svg.getElementById(m[1]);
    if (!src) return null;
    if (!markers[m[1]]) {
      const copy = src.cloneNode(true);
      copy.id = m[1] + "-on";
      copy.querySelectorAll("*").forEach(n => { n.style.fill = "var(--accent)"; n.style.stroke = "var(--accent)"; });
      src.parentNode.appendChild(copy);
      markers[m[1]] = copy.id;
    }
    return `url(#${markers[m[1]]})`;
  };

  paths.forEach((path, i) => {
    const hit = path.cloneNode(false);
    hit.removeAttribute("id");
    hit.removeAttribute("style");
    hit.removeAttribute("marker-end");
    hit.removeAttribute("marker-start");
    hit.setAttribute("class", "edge-hit");
    path.after(hit);

    const ends = endsOf(path);
    const label = labels[i];  // mermaid draws labels in edge order
    const marker = path.getAttribute("marker-end");

    const note = tips[i] || [];
    hit.addEventListener("mousemove", ev => showTip(note, ev));
    hit.addEventListener("mouseenter", ev => {
      showTip(note, ev);
      svg.classList.add("hovering");
      path.classList.add("edge-on");
      label?.classList.add("edge-on");
      ends.forEach(n => n.classList.add("node-on"));
      const on = accentMarker(marker);
      if (on) path.setAttribute("marker-end", on);
    });
    hit.addEventListener("mouseleave", () => {
      hideTip();
      svg.classList.remove("hovering");
      path.classList.remove("edge-on");
      label?.classList.remove("edge-on");
      ends.forEach(n => n.classList.remove("node-on"));
      if (marker) path.setAttribute("marker-end", marker);
    });
  });
}

// Hovering a box shows its description, when it has one. The domain box that
// wraps several bounded contexts is left out: there it is only background, and
// its description has its own place on the domain view.
function bindBoxTips(svg) {
  const boxes = Object.entries(boxMapOf(svg)).filter(([, g]) => !g.classList.contains("cluster"));
  const innermost = target => {
    let best = null;
    boxes.forEach(([id, g]) => {
      if (g.contains(target) && (!best || best.g.contains(g))) best = { id, g };
    });
    return best ? best.id : null;
  };
  svg.addEventListener("mousemove", ev => {
    if (ev.target.closest(".edge-hit")) return;  // the arrow's own tooltip owns the pointer here
    const item = itemOfNode[innermost(ev.target) || ""];
    if (item?.description) showTip([{ title: item.name, text: item.description }], ev);
    else hideTip();
  });
  svg.addEventListener("pointerleave", hideTip);
}

// One entry of a tooltip: always a title (who depends on whom) and a description (the comment).
// An arrow can stand for several dependencies, so every entry names its own.
const tipEntry = dep => ({ title: `${nameOf(dep.from)} → ${nameOf(dep.to)}`, text: dep.comment });

// A small box that follows the cursor. Comments come from context-map.yml, so they go in as text, never as HTML.
const tip = document.createElement("div");
tip.id = "tip";
document.body.appendChild(tip);
function showTip(note, ev) {
  if (!note.length) return hideTip();
  tip.replaceChildren(...note.map(n => {
    const p = document.createElement("p");
    const title = document.createElement("b");
    title.textContent = n.title;
    p.append(title, document.createElement("br"), n.text);
    return p;
  }));
  tip.style.display = "block";
  const x = Math.min(ev.clientX + 14, window.innerWidth - tip.offsetWidth - 8);
  const y = ev.clientY + 18 + tip.offsetHeight > window.innerHeight ? ev.clientY - tip.offsetHeight - 12 : ev.clientY + 18;
  tip.style.left = Math.max(8, x) + "px";
  tip.style.top = Math.max(8, y) + "px";
}
const hideTip = () => { tip.style.display = "none"; };

const escapeHtml = t => t.replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const link = id => `<a data-go="${id}">${escapeHtml(nameOf(id))}</a>`;
const list = ids => ids.length ? "<ul>" + ids.map(id => `<li>${link(id)}</li>`).join("") + "</ul>" : '<p class="hint">None</p>';
const chip = type => { const t = MODEL.types[type]; return `<span class="chip" style="background:${t.fill};border-color:${t.stroke}">${t.name}</span>`; };

function renderInfo(s, visible) {
  const legend = '<div class="legend">' + Object.keys(MODEL.types).map(chip).join("") + "</div>";
  const howTo = `<h3>How to read</h3><p class="hint">An arrow from A to B means A depends on B. Upstream is at the top. The outer boxes are domains, the coloured boxes inside them are bounded contexts. The Show &amp; hide form in the right panel has a control for every domain and cluster: a multi-context domain or a cluster can be expanded (the boxes inside it), collapsed (one box), or hidden — a dashed underline marks a cluster's — and a one-box domain hides with a toggle. Focusing on a domain or a cluster lists what it holds, and each item there can be hidden too. Click a box to focus on it.</p>`;
  if (!s.focus) {
    $("info").innerHTML = `<h2>Whole system</h2><p class="hint">${visible.size} items shown. Pick a domain, cluster or bounded context to see only what it touches.</p>
      <p><a href="mermaid/index.html">Static diagrams</a></p>${legend}${howTo}`;
    return;
  }
  const id = s.focus;
  const item = contextById[id] || domainById[id] || clusterById[id];
  const itemWith = item_id => {
    const hiddenHere = s.hide.has(item_id);
    const toggle = `<a data-${hiddenHere ? "show" : "hide"}="${item_id}" class="toggle">${hiddenHere ? "show" : "hide"}</a>`;
    return `<li>${link(item_id)} ${hiddenHere ? `<span class="hint">(hidden)</span> ` : ""}${toggle}</li>`;
  };
  let html;
  if (clusterById[id]) {
    html = `<h2>${escapeHtml(item.name)}</h2><span class="hint">Cluster</span>
      <p><a href="mermaid/index.html">All diagrams</a></p>
      <h3>Members</h3><ul>${item.members.map(itemWith).join("")}</ul>`;
  } else {
    html = `<h2>${escapeHtml(item.name)}</h2>${chip(item.type)} <span class="hint">${domainById[id] ? "Domain" : "Bounded context"}</span>
      <p><a href="mermaid/${id}.html">Static diagram</a> · <a href="mermaid/index.html">All diagrams</a></p>`;
    if (item.description) html += `<p class="hint">${escapeHtml(item.description)}</p>`;
    if (isMulti(id)) {
      html += `<h3>Bounded contexts</h3><ul>${domainById[id].contexts.map(itemWith).join("")}</ul>`;
    } else if (isMulti(owner[id])) {
      html += `<h3>Domain</h3>${list([owner[id]])}`;
    }
    const r = relations(id);
    html += `<h3>Depends on (${r.ups.length})</h3>${list(r.ups)}<h3>Used by (${r.downs.length})</h3>${list(r.downs)}`;
    if (!isMulti(id) && isMulti(owner[id])) {
      const own = GRAPHS.context.edges;
      const dUps = own.filter(e => e.from === owner[id]).map(e => e.to);
      const dDowns = own.filter(e => e.to === owner[id]).map(e => e.from);
      const pname = escapeHtml(nameOf(owner[id]));
      if (dUps.length) html += `<h3>${pname} as a whole depends on</h3>${list(dUps)}`;
      if (dDowns.length) html += `<h3>${pname} as a whole is used by</h3>${list(dDowns)}`;
    }
  }
  $("info").innerHTML = html + `<h3>Legend</h3>${legend}${howTo}`;
}

const setHidden = (id, hide) => {
  hiddenContexts[hide ? "add" : "delete"](id);
  if (displaySels[id]) displaySels[id].value = hide ? "hidden" : defaultMode(id);
};
$("panel").addEventListener("click", ev => {
  const hideToggle = ev.target.closest("[data-hide]");
  if (hideToggle) { setHidden(hideToggle.dataset.hide, true); render(); return; }
  const showToggle = ev.target.closest("[data-show]");
  if (showToggle) { setHidden(showToggle.dataset.show, false); render(); return; }
  const go = ev.target.closest("[data-go]");
  if (go) { focusSel.value = go.dataset.go; render(); }
});
[levelSel, focusSel, depthSel, dirSel].forEach(el => el.addEventListener("change", render));
// A container's select takes over from a hide the moment it is touched.
Object.entries(displaySels).forEach(([id, sel]) => sel.addEventListener("change", () => {
  hiddenContexts.delete(id);
  render();
}));
$("reset").addEventListener("click", () => { history.replaceState(null, "", location.pathname); readHash(); render(); });
window.addEventListener("hashchange", () => { readHash(); render(); });

readHash();
render();
