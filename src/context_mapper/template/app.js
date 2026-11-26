// Mermaid and its ELK layout loader, as the build vendors them: the pages
// import ./mermaid.js, a file generated from npm — pinned, local, no CDN.
import mermaid, { elkLayouts } from "./mermaid.js";
import { DIAGRAM } from "./core/model.js";
import { hashFor } from "./core/state.js";
import { mermaidSource } from "./core/diagram.js";
import { renderInfo } from "./components/panel.js";
import { bindEdgeHover, bindBoxTips } from "./dom/svg.js";
import { dropViolationHeads } from "./arrowheads.js";
import { $ } from "./dom/query.js";
import {
  levelSel,
  focusSel,
  depthIn,
  dirSel,
  displaySels,
  hiddenContexts,
  state,
  readHash,
  setHidden,
  refreshToggles,
} from "./dom/controls.js";
import { downloadDiagram } from "./download.js";

if (DIAGRAM.elk) mermaid.registerLayoutLoaders(elkLayouts);
mermaid.initialize({ startOnLoad: false, securityLevel: "loose" });

let renderCount = 0;
async function render() {
  const s = state();
  history.replaceState(null, "", hashFor(s) || location.pathname);
  const { source, visible, tips } = mermaidSource(s);
  renderInfo(s, visible);
  refreshToggles();
  const run = ++renderCount;
  try {
    const { svg, bindFunctions } = await mermaid.render(
      "diagram-" + run,
      source,
    );
    if (run !== renderCount) return; // a newer render took over
    // Mermaid hands us its drawing as serialized SVG — a renderer's output,
    // not template building — so it goes in through innerHTML; parsing it
    // into nodes risks the HTML nested inside its foreignObject.
    $("graph").innerHTML = svg;
    bindFunctions?.($("graph"));
    const svgEl = $("graph").querySelector("svg");
    dropViolationHeads(svgEl, source);
    bindEdgeHover(svgEl, tips);
    bindBoxTips(svgEl);
  } catch (err) {
    if (run === renderCount)
      $("graph").textContent = "Could not render this diagram: " + err.message;
  }
}

$("panel").addEventListener("click", (ev) => {
  const hideToggle = ev.target.closest("[data-hide]");
  if (hideToggle) {
    setHidden(hideToggle.dataset.hide, true);
    render();
    return;
  }
  const showToggle = ev.target.closest("[data-show]");
  if (showToggle) {
    setHidden(showToggle.dataset.show, false);
    render();
    return;
  }
  const go = ev.target.closest("[data-go]");
  if (go) {
    focusSel.value = go.dataset.go;
    render();
  }
});
[levelSel, focusSel, depthIn, dirSel].forEach((el) =>
  el.addEventListener("change", render),
);
// A container's select takes over from a hide the moment it is touched.
Object.entries(displaySels).forEach(([id, sel]) =>
  sel.addEventListener("change", () => {
    hiddenContexts.delete(id);
    render();
  }),
);
$("reset").addEventListener("click", () => {
  history.replaceState(null, "", location.pathname);
  readHash();
  render();
});
window.addEventListener("hashchange", () => {
  readHash();
  render();
});

// Downloading the diagram as it stands, named after what it shows.
$("download").addEventListener("click", () => {
  const svg = $("graph").querySelector("svg");
  if (!svg) return; // nothing rendered to download
  const s = state();
  const name = ["context-map", s.focus, s.level === "domain" ? "domain" : null]
    .filter(Boolean)
    .join("-");
  downloadDiagram(svg, $("image").value, name);
});

readHash();
render();
