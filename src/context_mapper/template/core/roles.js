// The relationship roles of a dependency — what the upstream is, what the
// downstream is — as pure data: the text of them, and what a merged edge
// keeps. The roles themselves (code, display name, side) come from the model,
// in the canonical order graph.py defines.
import { MODEL } from "./model.js";

const names = (ids) => (ids || []).map((id) => MODEL.roles[id].name).join(", ");
const codes = (ids) => (ids || []).map((id) => MODEL.roles[id].code);

// The short codes of an edge's roles: [upstream codes, downstream codes].
export const roleCodes = (edge) => [
  codes(edge.upstream),
  codes(edge.downstream),
];

// The roles as a sentence for tooltips and lists, with the display names:
// the upstream roles, an arrow, the downstream roles. One side alone says
// which side it is. An edge with no roles has no text.
export function roleText(edge) {
  const up = names(edge.upstream);
  const down = names(edge.downstream);
  if (up && down) return `${up} → ${down}`;
  if (up) return `${up} (upstream)`;
  if (down) return `${down} (downstream)`;
  return "";
}

// What a merged edge keeps: the roles every dependency it stands for carries,
// exactly. A dependency with no roles differs from one with roles, so one of
// each drops them all.
export function sharedRoles(deps) {
  const keys = new Set(
    deps.map((d) => JSON.stringify([d.upstream || [], d.downstream || []])),
  );
  if (keys.size !== 1) return { upstream: [], downstream: [] };
  const [upstream, downstream] = JSON.parse([...keys][0]);
  return { upstream, downstream };
}
