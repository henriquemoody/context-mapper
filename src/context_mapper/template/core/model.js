// The model the Python build splices into the bundled script, over the
// expression below; tests set globalThis.contextMapperModel before import.
export const MODEL = globalThis.contextMapperModel ?? null;

// Lookups. A "single" domain is one bounded context with the same id.
export const domainById = Object.fromEntries(MODEL.domains.map(d => [d.id, d]));
export const contextById = Object.fromEntries(MODEL.contexts.map(c => [c.id, c]));
export const clusterById = Object.fromEntries(MODEL.clusters.map(c => [c.id, c]));
export const owner = {};
MODEL.contexts.forEach(c => owner[c.id] = c.domain);
MODEL.domains.forEach(d => owner[d.id] = d.id);
export const nameOf = id => (contextById[id] || domainById[id]).name;
export const isMulti = id => domainById[id] && !domainById[id].single;

export const DIAGRAM = MODEL.mermaid;

// A container first renders as the view says, else as its own `defaultDisplay` says, else expanded.
export const defaultDisplayOf = id => (clusterById[id] || domainById[id]).defaultDisplay || "expanded";
export const STYLE_HIDE = DIAGRAM.hide || [];
export const defaultMode = id => {
  const d = DIAGRAM.display;
  if (d === null || d === undefined) return defaultDisplayOf(id);
  return typeof d === "object" ? (d[id] || defaultDisplayOf(id)) : d;
};
export const MODES = [["expanded", "Expanded"], ["collapsed", "Collapsed"], ["contents", "Contents"], ["hidden", "Hidden"]];

// What `hide` in the style file keeps out, of any kind: a bounded context, a
// domain, a cluster member — and what `defaultDisplay: hidden` starts with,
// which only a bounded context or a single domain can be: one box with nothing
export const DEFAULT_HIDE = new Set([...STYLE_HIDE,
  ...MODEL.contexts.filter(c => c.defaultDisplay === "hidden").map(c => c.id)]);
