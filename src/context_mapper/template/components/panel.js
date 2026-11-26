import {
  MODEL,
  domainById,
  contextById,
  clusterById,
  owner,
  nameOf,
  isMulti,
} from "../core/model.js";
import { GRAPHS, relationEdges, linkRelations } from "../core/graph.js";
import { roleText } from "../core/roles.js";
import { attributeSection } from "./attributes.js";
import { aggregateSection } from "./aggregates.js";
import { $ } from "../dom/query.js";
// preact's runtime: the tagged-template html and the render that puts a tree
// on the page. It comes in as a namespace so the bundled script keeps the
// names `html` and `render` — the page shows the panel rendering through
// preact.
import * as preact from "htm/preact/standalone";
const { html, render } = preact;

const link = (id) => html`<a data-go="${id}">${nameOf(id)}</a>`;
const list = (ids) =>
  ids.length
    ? html`<ul>${ids.map((id) => html`<li>${link(id)}</li>`)}</ul>`
    : html`<p class="hint">None</p>`;
// A list of dependencies: each edge's name at `end`, and the roles the
// dependency carries, spelled out beside it.
const dependencyList = (edges, end) =>
  edges.length
    ? html`<ul>${edges.map((e) => html`<li>${link(e[end])}${roleText(e) ? html` <span class="hint roles">${roleText(e)}</span>` : null}</li>`)}</ul>`
    : html`<p class="hint">None</p>`;
const chip = (type) => {
  const t = MODEL.types[type];
  return html`<span class="chip" style="background:${t.fill};border-color:${t.stroke}">${t.name}</span>`;
};

// The side panel: one component over the view state. The templates read
// like the HTML they render; interpolations are values, never markup.
const Panel = ({ s, visible }) => {
  const legend = html`<div class="legend">${Object.keys(MODEL.types).map(chip)}</div>`;
  if (!s.focus)
    return html`<h2>Whole system</h2>
      <p class="hint">${visible.size} items shown. Pick a domain, cluster or bounded context to see only what it touches.</p>
      <p><a href="mermaid/index.html">Static diagrams</a></p>${legend}`;
  const id = s.focus;
  const item = contextById[id] || domainById[id] || clusterById[id];
  const itemWith = (item_id) => {
    const hiddenHere = s.hide.has(item_id);
    const toggle = hiddenHere
      ? html`<a data-show="${item_id}" class="toggle">show</a>`
      : html`<a data-hide="${item_id}" class="toggle">hide</a>`;
    return html`<li>${link(item_id)} ${hiddenHere ? html`<span class="hint">(hidden)</span>` : null}${hiddenHere ? " " : null}${toggle}</li>`;
  };
  if (clusterById[id])
    return html`<h2>${item.name}</h2><span class="hint">Cluster</span>
      <p><a href="mermaid/index.html">All diagrams</a></p>${attributeSection(item)}<h3>Members</h3><ul>${item.members.map(itemWith)}</ul><h3>Legend</h3>${legend}`;
  const r = relationEdges(id);
  const parent = owner[id];
  const own = GRAPHS.context.edges;
  const dUps = own.filter((e) => e.from === parent);
  const dDowns = own.filter((e) => e.to === parent);
  const pname = nameOf(parent);
  // Partnerships and shared kernels have no direction: a list of each, when
  // there is one, for the item and for the domain it is written against.
  const linkLists = (found, heading) =>
    Object.entries(MODEL.symmetric_kinds)
      .filter(([kind]) => found[kind])
      .map(
        ([kind, info]) =>
          html`<h3>${heading(info)} (${found[kind].length})</h3>${list(found[kind])}`,
      );
  const ofParent = {};
  GRAPHS.context.links
    .filter((l) => l.a === parent || l.b === parent)
    .forEach((l) =>
      (ofParent[l.kind] = ofParent[l.kind] || new Set()).add(
        l.a === parent ? l.b : l.a,
      ),
    );
  Object.keys(ofParent).forEach((kind) => {
    ofParent[kind] = [...ofParent[kind]].sort((x, y) =>
      nameOf(x).localeCompare(nameOf(y)),
    );
  });
  return html`<h2>${item.name}</h2>${chip(item.type)} <span class="hint">${domainById[id] ? "Domain" : "Bounded context"}</span>
      <p><a href="mermaid/${id}.html">Static diagram</a> · <a href="mermaid/index.html">All diagrams</a></p>
      ${item.description ? html`<p class="hint">${item.description}</p>` : null}${attributeSection(item)}${aggregateSection(item)}
      ${isMulti(id) ? html`<h3>Bounded contexts</h3><ul>${domainById[id].contexts.map(itemWith)}</ul>` : null}
      ${!isMulti(id) && isMulti(parent) ? html`<h3>Domain</h3>${list([parent])}` : null}
      <h3>Depends on (${r.ups.length})</h3>${dependencyList(r.ups, "to")}
      <h3>Used by (${r.downs.length})</h3>${dependencyList(r.downs, "from")}
      ${linkLists(linkRelations(id), (info) => info.heading)}
      ${!isMulti(id) && isMulti(parent) && dUps.length ? html`<h3>${pname} as a whole depends on</h3>${dependencyList(dUps, "to")}` : null}
      ${!isMulti(id) && isMulti(parent) && dDowns.length ? html`<h3>${pname} as a whole is used by</h3>${dependencyList(dDowns, "from")}` : null}
      ${!isMulti(id) && isMulti(parent) ? linkLists(ofParent, (info) => `${pname} as a whole ${info.verb}`) : null}
      <h3>Legend</h3>${legend}`;
};

// The same contract app.js always called: the panel of this view state,
// rendered into #info. The key is the focus: a panel of another focus is
// another panel, and preact builds it afresh — reusing the elements of the
// last one would keep the attributes they lost, an empty style among them.
export function renderInfo(s, visible) {
  render(
    html`<${Panel} key=${s.focus || "all"} s=${s} visible=${visible} />`,
    $("info"),
  );
}
