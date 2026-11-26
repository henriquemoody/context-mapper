// The attribute data: the text of a value, the entries an item sets, and
// the tooltip rows of a box — pure data, no DOM, shared by the panel's
// rendering and the page's tooltips.
import { MODEL, DIAGRAM, contextById } from "./model.js";

// An attribute's value as the text to show: a list as its items, a map as
// label-to-value pairs, anything else as it is.
export const attributeText = (v) =>
  Array.isArray(v)
    ? v.map(attributeText).join(", ")
    : v && typeof v === "object"
      ? Object.entries(v)
          .map(([k, item]) => `${k}: ${attributeText(item)}`)
          .join(" · ")
      : String(v);

// The attributes the item sets, in the order the model declared them: the id,
// the label to show and the value. An item that sets none has none.
export const attributeEntries = (item) =>
  Object.entries(MODEL.attributes || {})
    .filter(([id]) => item.attributes && id in item.attributes)
    .map(([id, def]) => ({ id, label: def.name, value: item.attributes[id] }));

// The tooltip entries of a box: its description first, then one entry per
// attribute it sets, in the order the model declared them. The attribute
// entries carry `kind: "attr"` so the tooltip can dress them as data rather
// than as names — under a hairline, in the panel's small-label style. A model
// can leave the attributes out of the tooltips with `attribute_tooltips: false`.
export const boxTipEntries = (item) => {
  if (!item) return [];
  const entries = item.description
    ? [{ kind: "desc", title: item.name, text: item.description }]
    : [];
  if (!DIAGRAM.attribute_tooltips) return entries;
  const aggregates = contextById[item.id]?.aggregates || [];
  return entries
    .concat(
      attributeEntries(item).map(({ label, value }) => ({
        kind: "attr",
        title: label,
        text: attributeText(value),
      })),
    )
    .concat(
      aggregates.length
        ? [
            {
              kind: "attr",
              title: "Aggregates",
              text: aggregates.map((a) => a.name).join(", "),
            },
          ]
        : [],
    );
};

// The tooltip entries of an aggregate's box: its description, then what it
// holds by name — the root, the entities, the value objects — and the
// attributes it sets, as data rows. Like a context's, the rows follow
// `attribute_tooltips`, and the description stays.
export const aggregateTipEntries = (aggregate) => {
  const entries = aggregate.description
    ? [{ kind: "desc", title: aggregate.name, text: aggregate.description }]
    : [];
  if (!DIAGRAM.attribute_tooltips) return entries;
  const names = (items) => items.map((m) => m.name).join(", ");
  return entries.concat(
    [
      ["Root", aggregate.root],
      ["Entities", names(aggregate.entities)],
      ["Value objects", names(aggregate.valueObjects)],
    ]
      .filter(([, text]) => text)
      .map(([title, text]) => ({ kind: "attr", title, text })),
    attributeEntries(aggregate).map(({ label, value }) => ({
      kind: "attr",
      title: label,
      text: attributeText(value),
    })),
  );
};
