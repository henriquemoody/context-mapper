import { itemOfNode, aggregateOfNode } from "../core/diagram.js";
import { contextById } from "../core/model.js";
import { boxTipEntries, aggregateTipEntries } from "../core/attributes.js";
import { showTip, hideTip } from "./tips.js";

// Boxes are g elements whose id holds our node id: "<svg>-flowchart-<id>-<n>", or "<svg>-<id>" for a domain.
function boxMapOf(svg) {
  const boxes = {};
  svg.querySelectorAll("g[id]").forEach((g) => {
    const m = /-flowchart-(.+)-\d+$/.exec(g.id);
    if (m) boxes[m[1]] = g;
    else if (g.classList.contains("cluster"))
      boxes[g.id.slice(svg.id.length + 1)] = g;
  });
  Object.values(boxes).forEach((g) => g.classList.add("box"));
  return boxes;
}

// Hovering an arrow highlights it, its arrowhead and the two boxes it joins, and shows its comments.
export function bindEdgeHover(svg, tips) {
  if (!svg) return;
  const paths = [...svg.querySelectorAll("path.flowchart-link")];
  const labels = [...svg.querySelectorAll(".edgeLabel")];
  const boxes = boxMapOf(svg);
  // An edge id reads "<svg>-L_<from>_<to>_<n>". Ids may hold underscores, so match against the boxes we know.
  const endsOf = (path) => {
    const rest = path.id.slice(svg.id.length + 3).replace(/_\d+$/, "");
    for (const from of Object.keys(boxes)) {
      if (rest.startsWith(from + "_") && boxes[rest.slice(from.length + 1)])
        return [boxes[from], boxes[rest.slice(from.length + 1)]];
    }
    return [];
  };
  const markers = {}; // an accent copy of each arrowhead, made on demand
  const accentMarker = (ref) => {
    const m = /url\(["']?#([^"')]+)["']?\)/.exec(ref || "");
    const src = m && svg.getElementById(m[1]);
    if (!src) return null;
    if (!markers[m[1]]) {
      const copy = src.cloneNode(true);
      copy.id = m[1] + "-on";
      copy.querySelectorAll("*").forEach((n) => {
        n.style.fill = "var(--accent)";
        n.style.stroke = "var(--accent)";
      });
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
    const label = labels[i]; // mermaid draws labels in edge order
    const marker = path.getAttribute("marker-end");

    const note = tips[i] || [];
    hit.addEventListener("mousemove", (ev) => showTip(note, ev));
    hit.addEventListener("mouseenter", (ev) => {
      showTip(note, ev);
      svg.classList.add("hovering");
      path.classList.add("edge-on");
      label?.classList.add("edge-on");
      ends.forEach((n) => n.classList.add("node-on"));
      const on = accentMarker(marker);
      if (on) path.setAttribute("marker-end", on);
    });
    hit.addEventListener("mouseleave", () => {
      hideTip();
      svg.classList.remove("hovering");
      path.classList.remove("edge-on");
      label?.classList.remove("edge-on");
      ends.forEach((n) => n.classList.remove("node-on"));
      if (marker) path.setAttribute("marker-end", marker);
    });
  });
}

// Hovering a box shows its description, when it has one, and the attributes
// it sets. The domain box that wraps several bounded contexts is left out:
// there it is only background, and its description has its own place on the
// domain view. A bounded context drawn around its aggregates is a box of its
// own, though, and so is each aggregate.
export function bindBoxTips(svg) {
  const boxes = Object.entries(boxMapOf(svg)).filter(
    ([id, g]) =>
      !g.classList.contains("cluster") ||
      (itemOfNode[id] && contextById[itemOfNode[id].id]),
  );
  const innermost = (target) => {
    let best = null;
    boxes.forEach(([id, g]) => {
      if (g.contains(target) && (!best || best.g.contains(g))) best = { id, g };
    });
    return best ? best.id : null;
  };
  svg.addEventListener("mousemove", (ev) => {
    if (ev.target.closest(".edge-hit")) return; // the arrow's own tooltip owns the pointer here
    const id = innermost(ev.target) || "";
    const entries = aggregateOfNode[id]
      ? aggregateTipEntries(aggregateOfNode[id])
      : boxTipEntries(itemOfNode[id]);
    if (entries.length) showTip(entries, ev);
    else hideTip();
  });
  svg.addEventListener("pointerleave", hideTip);
}
