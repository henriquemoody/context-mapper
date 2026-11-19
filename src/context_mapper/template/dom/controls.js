import {
  MODEL,
  domainById,
  MODES,
  defaultMode,
  DEFAULT_HIDE,
} from "../core/model.js";
import { clampDepth, parseHash } from "../core/state.js";
import { $ } from "./query.js";

export const levelSel = $("level"),
  focusSel = $("focus"),
  depthIn = $("depth"),
  dirSel = $("dir");

(function fillFocus() {
  const byName = (a, b) => a.name.localeCompare(b.name);
  const group = (label, items) => {
    if (!items.length) return;
    const og = document.createElement("optgroup");
    og.label = label;
    items.sort(byName).forEach((i) => og.appendChild(new Option(i.name, i.id)));
    focusSel.appendChild(og);
  };
  group("Domains", [...MODEL.domains]);
  group("Clusters", [...MODEL.clusters]);
  // One group per domain, so a context sits next to the others of its domain.
  [...MODEL.domains].sort(byName).forEach((d) =>
    group(
      `Bounded contexts: ${d.name}`,
      MODEL.contexts.filter((c) => c.domain === d.id && !domainById[c.id]),
    ),
  );
})();

// Header links from the style file: every label goes in as text, never as
// HTML, in the order the file lists them. With nothing to show, the nav
// leaves the header entirely, so no empty flex child holds a stray gap.
(function fillLinks() {
  const nav = $("links");
  Object.entries(MODEL.links || {}).forEach(([label, url]) => {
    const a = document.createElement("a");
    a.href = url;
    a.textContent = label;
    nav.appendChild(a);
  });
  if (!nav.childElementCount) nav.remove();
})();

export const displaySels = {};
const toggles = {}; // a single domain — one plain box — as a hide/show toggle
// The panel's "Show & hide" form, built once so it survives the re-renders of
// the focus info above it: one row per domain and cluster, grouped by kind.
// A multi-context domain or a cluster gets a display select; a single domain
// gets a hide/show toggle instead, driven by `hiddenContexts` like the list
// toggles below.
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
    if (cluster) span.classList.add("cluster"); // a dashed underline, like the box it controls
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
  const sub = (text) => {
    const heading = document.createElement("h4");
    heading.textContent = text;
    $("display").appendChild(heading);
  };
  sub("Domains");
  MODEL.domains.forEach((d) =>
    (d.single ? addToggle : addSelect)(d.id, d.name),
  );
  sub("Clusters");
  MODEL.clusters.forEach((c) => addSelect(c.id, c.name, true));
}
buildControls();
const displayModes = () =>
  Object.fromEntries(
    Object.entries(displaySels).map(([id, sel]) => [id, sel.value]),
  );

// inside. The toggles below hide the same way, so a hidden item stays hidden
// even where focus would open it. A container's select mirrors the hide while
// it holds, and takes over the moment it is touched.
export const hiddenContexts = new Set(DEFAULT_HIDE);

// The form's toggle links are static DOM: on every render, refresh what each
// one says and does — a hidden item's link shows it, a visible one's hides it.
export const refreshToggles = () =>
  Object.entries(toggles).forEach(([id, t]) => {
    const hidden = hiddenContexts.has(id);
    t.link.removeAttribute("data-hide");
    t.link.removeAttribute("data-show");
    t.link.setAttribute(hidden ? "data-show" : "data-hide", id);
    t.link.textContent = hidden ? "show" : "hide";
    t.hint.textContent = hidden ? "(hidden)" : "";
    t.row.classList.toggle("off", hidden);
  });

export function state() {
  depthIn.value = clampDepth(depthIn.value); // the field snaps to what it stands for
  return {
    level: levelSel.value,
    focus: focusSel.value,
    depth: Number(depthIn.value),
    dir: dirSel.value,
    display: displayModes(),
    hide: new Set(hiddenContexts),
  };
}

export function readHash() {
  const s = parseHash(location.hash.slice(1));
  levelSel.value = s.level;
  focusSel.value = s.focus;
  depthIn.value = s.depth;
  dirSel.value = s.dir;
  Object.entries(displaySels).forEach(([id, sel]) => {
    sel.value = s.display[id];
  });
  hiddenContexts.clear();
  s.hide.forEach((id) => hiddenContexts.add(id));
}

export const setHidden = (id, hide) => {
  hiddenContexts[hide ? "add" : "delete"](id);
  if (displaySels[id])
    displaySels[id].value = hide ? "hidden" : defaultMode(id);
};
