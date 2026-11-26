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
//
// A shared kernel is a badge too, `SK`, at the middle of the arrow: a
// `%% kernels: 4,7` line names the arrows, counted the same way. Mermaid's
// own middle label is taken — a collapsed box names what it holds there — so a
// badge that would cover it slides along the arrow until it is clear. In the
// Markdown the source spells it out on the middle label instead.
//
// Where an arrow runs is read from its two end points and from points sampled
// along the path itself, never from the length of the path: the hand-drawn
// look strokes every path twice, so its length is twice its line's, and half
// of it is not the line's middle.
export function drawRoleLabels(svg, source) {
  const found = /^\s*%% roles: (.+)$/m.exec(source);
  const kernels = /^\s*%% kernels: ([\d,]+)$/m.exec(source);
  if (!svg || (!found && !kernels)) return;
  const ns = "http://www.w3.org/2000/svg";
  const paths = svg.querySelectorAll("path.flowchart-link");
  const group = document.createElementNS(ns, "g");
  group.setAttribute("class", "role-labels");
  group.setAttribute("style", "pointer-events:none");
  const placed = [];
  let host = null;

  // What an arrow's path says about the line it follows, or nothing when the
  // DOM cannot measure it: its two ends, the straight way between them, and
  // `on`, the point of the path nearest to a wanted point. A path starts at
  // the downstream end and finishes at the upstream one, where the head is.
  const measure = (path) => {
    if (!path || typeof path.getTotalLength !== "function") return null;
    const total = path.getTotalLength();
    if (!(total > 0)) return null;
    const at = (l) => path.getPointAtLength(Math.min(Math.max(l, 0), total));
    const a = at(0);
    const b = at(total);
    const chord = Math.hypot(b.x - a.x, b.y - a.y);
    if (!(chord > 0)) return null;
    let samples = null;
    const on = (want) => {
      const count = Math.min(Math.max(Math.round(total), 60), 3000);
      samples =
        samples ||
        Array.from({ length: count }, (_, i) => at((total * i) / (count - 1)));
      return samples.reduce((best, p) =>
        Math.hypot(p.x - want.x, p.y - want.y) <
        Math.hypot(best.x - want.x, best.y - want.y)
          ? p
          : best,
      );
    };
    return {
      a,
      b,
      chord,
      at,
      total,
      on,
      u: { x: (b.x - a.x) / chord, y: (b.y - a.y) / chord },
    };
  };

  // One badge, centered at x, y: a box with a light fill and a thin stroke,
  // and its text, all as inline styles so a download keeps them.
  const badge = (x, y, width, height, text) => {
    placed.push({ x, y, width, height });
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

  // A badge's size follows its text.
  const sizeOf = (text) => ({ width: text.length * 7 + 8, height: 15 });
  // Half a box's extent along a direction: how far its center must be from a
  // line, or from an end, for the box to clear it.
  const reachOf = (size, d) =>
    (Math.abs(d.x) * size.width + Math.abs(d.y) * size.height) / 2;

  // A label hugging one end of a path, beside it: right against the box the
  // arrow leaves or meets, so it doesn't float into the gap where a
  // container's title sits. Its box clears the line by a pixel or two, and at
  // the upstream end it starts past the arrowhead.
  const place = (line, end, text) => {
    const size = sizeOf(text);
    const start = end === "start";
    const tip = start ? line.a : line.b;
    // The way the path leaves the end, from the path itself: it need not run
    // along the straight way between the ends.
    const next = line.at(start ? 3 : line.total - 3);
    const span = Math.hypot(next.x - tip.x, next.y - tip.y) || 1;
    const inward = { x: (next.x - tip.x) / span, y: (next.y - tip.y) / span };
    const reach = (d) => reachOf(size, d);
    // The same side of the line at both ends: to the right of the way the
    // arrow is drawn, from the downstream to the upstream.
    const travel = start ? inward : { x: -inward.x, y: -inward.y };
    const normal = { x: -travel.y, y: travel.x };
    const gap = start ? 2 : 9; // the upstream end carries the arrowhead
    const along = Math.min(reach(inward) + gap, line.chord / 2);
    const wanted = { x: tip.x + inward.x * along, y: tip.y + inward.y * along };
    const center = line.on(wanted);
    const away = reach(normal) + 2;
    let x = center.x + normal.x * away;
    let y = center.y + normal.y * away;
    // Several arrows leave a box close together: a label that would cover one
    // already placed slides sideways, away from its line, until it is clear.
    const hits = () =>
      placed.some(
        (r) =>
          Math.abs(r.x - x) < (r.width + size.width) / 2 &&
          Math.abs(r.y - y) < (r.height + size.height) / 2,
      );
    // A few pixels at a time, so it stays as close to its own line as it can.
    for (let tries = 0; hits() && tries < 20; tries++) {
      x += normal.x * 3;
      y += normal.y * 3;
    }
    badge(x, y, size.width, size.height, text);
  };

  (found ? found[1].split(";") : []).forEach((mark) => {
    const [index, roles] = mark.split("=");
    const path = paths[Number(index)];
    const line = roles ? measure(path) : null;
    // Geometry is the browser's: a path with no length to measure (a DOM
    // without layout) has nowhere to put a label.
    if (!line) return;
    const [upstream, downstream] = roles
      .split(">")
      .map((side) => side.split(",").filter(Boolean).join(", "));
    host = host || path.parentNode.parentNode;
    // The path starts at the downstream and finishes at the upstream.
    if (downstream) place(line, "start", downstream);
    if (upstream) place(line, "end", upstream);
  });

  // The box of Mermaid's middle label of an arrow, in the arrows' own
  // coordinates, when it has one and the browser can say where it is.
  const labelBox = (index) => {
    const label = svg.querySelectorAll(".edgeLabel")[index];
    if (!label || !(label.textContent || "").trim()) return null;
    if (typeof label.getBoundingClientRect !== "function") return null;
    const r = label.getBoundingClientRect();
    if (!(r.width > 0)) return null;
    const m = host?.getScreenCTM?.()?.inverse?.();
    const to = (x, y) =>
      m ? { x: m.a * x + m.c * y + m.e, y: m.b * x + m.d * y + m.f } : { x, y };
    const a = to(r.left, r.top);
    const b = to(r.right, r.bottom);
    return {
      x: (a.x + b.x) / 2,
      y: (a.y + b.y) / 2,
      width: Math.abs(b.x - a.x),
      height: Math.abs(b.y - a.y),
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
    const clear = (p) =>
      !avoid.some(
        (r) =>
          Math.abs(r.x - p.x) < (r.width + size.width) / 2 + 1 &&
          Math.abs(r.y - p.y) < (r.height + size.height) / 2 + 1,
      );
    const { a, b, chord, u } = line;
    const reach = (d) => reachOf(size, d);
    // Clear of the head: the marker is about 10px, and the path is trimmed
    // short of the box it meets. A few pixels at the tail.
    const head = path.getAttribute("marker-end") ? 12 : 4;
    const tail = 4;
    const lo = tail + reach(u);
    const hi = chord - head - reach(u);
    if (hi >= lo) {
      // Room to sit on the line: the middle, or as close to it as the head
      // allows, then along it, one way and the other.
      const middle = Math.min(Math.max(chord / 2, lo), hi);
      for (let step = 0; step <= 20; step++) {
        const along = middle + (step % 2 ? 1 : -1) * Math.ceil(step / 2) * 8;
        if (along < lo || along > hi) continue;
        const at = line.on({ x: a.x + u.x * along, y: a.y + u.y * along });
        if (clear(at)) {
          badge(at.x, at.y, size.width, size.height, text);
          return;
        }
      }
    }
    // Too short to hold the badge clear of both ends, or no clear place on
    // it: it goes beside the line, at its middle, on the same side as the role
    // codes, so the line and its head stay in full view.
    const normal = { x: -u.y, y: u.x };
    const away = reach(normal) + 2;
    const middle = { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
    let at = { x: middle.x + normal.x * away, y: middle.y + normal.y * away };
    for (let step = 1; !clear(at) && step <= 6; step++)
      at = {
        x: at.x + normal.x * (reach(normal) * 2 + 2),
        y: at.y + normal.y * (reach(normal) * 2 + 2),
      };
    badge(at.x, at.y, size.width, size.height, text);
  });
  if (group.childNodes.length) (host || svg).appendChild(group);
}
