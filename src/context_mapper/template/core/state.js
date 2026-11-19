import {
  MODEL,
  owner,
  clusterById,
  MODES,
  defaultMode,
  DEFAULT_HIDE,
} from "./model.js";

// The depth field takes any whole number of hops; anything else — empty,
// fractional, negative — falls back to the nearest whole hop, at least 1.
export const clampDepth = (raw) => Math.max(1, Math.trunc(Number(raw) || 1));

export function hashFor(s) {
  const p = new URLSearchParams();
  if (s.level !== "context") p.set("level", s.level);
  if (s.focus) p.set("focus", s.focus);
  if (s.depth !== 1) p.set("depth", s.depth);
  if (s.dir !== "both") p.set("dir", s.dir);
  Object.entries(s.display).forEach(([id, mode]) => {
    if (mode !== defaultMode(id) && !s.hide.has(id))
      p.set("display." + id, mode);
  });
  s.hide.forEach((id) => {
    if (!DEFAULT_HIDE.has(id)) p.set("hide." + id, "1");
  });
  DEFAULT_HIDE.forEach((id) => {
    if (!s.hide.has(id)) p.set("hide." + id, "0");
  });
  const h = p.toString();
  return h ? "#" + h : "";
}

// The view state a URL hash stands for: the rules readHash applied to the
// controls, stated for any caller. Containers are the multi-context domains
// and the clusters — the ones that own a display select.
export function parseHash(hash) {
  const p = new URLSearchParams(hash);
  const containers = [
    ...MODEL.domains.filter((d) => !d.single).map((d) => d.id),
    ...MODEL.clusters.map((c) => c.id),
  ];
  const hide = new Set(DEFAULT_HIDE);
  for (const [key, value] of p) {
    const m = /^hide\.(.+)$/.exec(key);
    if (!m) continue;
    if (value === "1") hide.add(m[1]);
    else if (value === "0") hide.delete(m[1]);
  }
  const display = Object.fromEntries(
    containers.map((id) => {
      const m = p.get("display." + id);
      return [id, MODES.some(([value]) => value === m) ? m : defaultMode(id)];
    }),
  );
  containers.forEach((id) => {
    if (hide.has(id)) display[id] = "hidden";
  });
  return {
    level: p.get("level") === "domain" ? "domain" : "context",
    focus:
      p.has("focus") && (owner[p.get("focus")] || clusterById[p.get("focus")])
        ? p.get("focus")
        : "",
    depth: clampDepth(p.get("depth")),
    dir: p.get("dir") || "both",
    display,
    hide,
  };
}
