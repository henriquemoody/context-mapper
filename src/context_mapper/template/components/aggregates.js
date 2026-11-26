// The aggregates of a bounded context, as the panel shows them: a section
// under the attributes, one block per aggregate — its description, its root,
// the entities and value objects it holds, the aggregates it references.
import { contextById, nameOf } from "../core/model.js";
import { attributeEntries } from "../core/attributes.js";
import { attributeValue } from "./attributes.js";
import { html } from "htm/preact/standalone";

// A member by name, and its description in parentheses when it has one.
const members = (items) =>
  items
    .map((m) => (m.description ? `${m.name} (${m.description})` : m.name))
    .join(", ");

// A reference to an aggregate: its name alone in the aggregate's own context,
// else the other context, a link that focuses on it, and the name after a
// slash — the way the model writes it. A context with the aggregate's own
// name says it once: the link.
const reference = (contextId, ref) => {
  if (ref.context === contextId) return ref.name;
  const link = html`<a data-go="${ref.context}">${nameOf(ref.context)}</a>`;
  return nameOf(ref.context) === ref.name ? link : html`${link} / ${ref.name}`;
};

const referenceList = (contextId, refs) =>
  refs.map((ref, i) =>
    i ? html`, ${reference(contextId, ref)}` : reference(contextId, ref),
  );

const aggregateBlock = (contextId, a) => {
  const rows = [["Root", a.root]];
  if (a.entities.length) rows.push(["Entities", members(a.entities)]);
  if (a.valueObjects.length)
    rows.push(["Value objects", members(a.valueObjects)]);
  if (a.references.length)
    rows.push(["References", referenceList(contextId, a.references)]);
  attributeEntries(a).forEach(({ label, value }) =>
    rows.push([label, attributeValue(value)]),
  );
  return html`<h4>${a.name}</h4>
    ${a.description ? html`<p class="hint">${a.description}</p>` : null}
    <ul>
      ${rows.map(
        ([label, value]) =>
          html`<li class="hint"><b>${label}:</b> ${value}</li>`,
      )}
    </ul>`;
};

// The aggregates of the item, under a heading like the panel's other
// sections. An item with none — a domain that holds contexts, a context that
// declares none — shows neither the heading nor the blocks.
export const aggregateSection = (item) => {
  const aggregates = contextById[item.id]?.aggregates;
  return aggregates
    ? html`<h3>Aggregates</h3>
        ${aggregates.map((a) => aggregateBlock(item.id, a))}`
    : "";
};
