// Where the relationship roles of a dependency are drawn. The bundler takes
// this into app.js for the interactive page; mermaid.py splices it into the
// script of every static diagram page, as arrowheads.js is.
//
// Mermaid puts a label in the middle of an arrow, and the roles belong at its
// ends: the upstream's next to the upstream, the downstream's next to the
// downstream. So the diagram's source says which arrows carry roles, in a
// `%% roles: 3=OHS,PL>ACL;5=S>C` line — the arrow's index, counted the way
// `linkStyle` counts, then the upstream codes, `>`, the downstream codes — and
// this draws a small label near each end, inside the SVG, so the image a
// download makes keeps them. An arrow is drawn from its downstream to its
// upstream, so its path starts at the downstream end and finishes at the
// upstream one. Where this doesn't run, as in the Markdown on GitLab, the
// source carries the roles on the arrow's middle label instead.
export function drawRoleLabels(svg, source) {
  const found = /^\s*%% roles: (.+)$/m.exec(source);
  if (!svg || !found) return;
  const ns = "http://www.w3.org/2000/svg";
  const paths = svg.querySelectorAll("path.flowchart-link");
  const group = document.createElementNS(ns, "g");
  group.setAttribute("class", "role-labels");
  group.setAttribute("style", "pointer-events:none");

  // A label near one end of a path, beside it: its box clears the line however
  // the line runs, and sits a few pixels in from the end, so it hides neither
  // the arrowhead nor the box the arrow meets.
  const place = (path, total, end, text) => {
    const at = (l) => path.getPointAtLength(Math.min(Math.max(l, 0), total));
    const start = end === "start";
    const tip = at(start ? 0 : total);
    const next = at(start ? 3 : total - 3);
    const span = Math.hypot(next.x - tip.x, next.y - tip.y) || 1;
    const inward = { x: (next.x - tip.x) / span, y: (next.y - tip.y) / span };
    const width = text.length * 7 + 8;
    const height = 15;
    // Half the box's extent along a direction: how far its center must be
    // from the line, or from the end, for the box to clear it.
    const reach = (d) => (Math.abs(d.x) * width + Math.abs(d.y) * height) / 2;
    const along = Math.min(Math.max(16, reach(inward) + 6), total / 2);
    const center = at(start ? along : total - along);
    // The same side of the line at both ends: to the right of the way the
    // arrow is drawn, from the downstream to the upstream.
    const travel = start ? inward : { x: -inward.x, y: -inward.y };
    const normal = { x: -travel.y, y: travel.x };
    const away = reach(normal) + 2;
    const x = center.x + normal.x * away;
    const y = center.y + normal.y * away;
    const box = document.createElementNS(ns, "rect");
    box.setAttribute("x", x - width / 2);
    box.setAttribute("y", y - height / 2);
    box.setAttribute("width", width);
    box.setAttribute("height", height);
    box.setAttribute("rx", 3);
    box.setAttribute(
      "style",
      "fill:#fff;fill-opacity:0.92;stroke:#8a8a8a;stroke-width:0.75px",
    );
    const label = document.createElementNS(ns, "text");
    label.setAttribute("x", x);
    label.setAttribute("y", y);
    label.setAttribute("text-anchor", "middle");
    label.setAttribute("dominant-baseline", "central");
    label.setAttribute(
      "style",
      "fill:#1a1a1a;font-size:11px;font-weight:600;stroke:none",
    );
    label.textContent = text;
    group.append(box, label);
  };

  let host = null;
  found[1].split(";").forEach((mark) => {
    const [index, roles] = mark.split("=");
    const path = paths[Number(index)];
    // Geometry is the browser's: a path with no length to measure (a DOM
    // without layout) has nowhere to put a label.
    if (!path || !roles || typeof path.getTotalLength !== "function") return;
    const total = path.getTotalLength();
    if (!(total > 0)) return;
    const [upstream, downstream] = roles
      .split(">")
      .map((side) => side.split(",").filter(Boolean).join(", "));
    host = host || path.parentNode.parentNode;
    // The path starts at the downstream and finishes at the upstream.
    if (downstream) place(path, total, "start", downstream);
    if (upstream) place(path, total, "end", upstream);
  });
  if (group.childNodes.length) (host || svg).appendChild(group);
}
