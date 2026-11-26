// Where an arrowhead goes on a violation. The bundler takes it into app.js
// for the interactive page; mermaid.py splices it into the script of every
// static diagram page, as download.js is.
//
// A violation runs against the direction of the dependencies, and Mermaid lays
// a diagram out by the direction of its arrows: drawn the way it points, it
// would pull its downstream above its upstream. So the source draws it the way
// the dependency runs, from the downstream to the upstream, with a head at
// both ends so both ends are trimmed to fit one — and the diagram's source
// says which arrows these are, in a `%% violations: 3,4` line, counted the way
// `linkStyle` counts. This drops the head at the upstream end, leaving the one
// that points where the violation does. A renderer that never runs this, such
// as the Markdown on GitLab, shows the head at both ends.
export function dropViolationHeads(svg, source) {
  const found = /^\s*%% violations: ([\d,]+)$/m.exec(source);
  if (!svg || !found) return;
  const paths = svg.querySelectorAll("path.flowchart-link");
  found[1]
    .split(",")
    .forEach((i) => paths[Number(i)]?.removeAttribute("marker-end"));
}
