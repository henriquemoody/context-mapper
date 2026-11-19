// The attribute rendering: the rows and the section the panel shows, as
// templates built through preact.
import { attributeText, attributeEntries } from "../core/attributes.js";
import { html } from "htm/preact/standalone";

// An attribute's value as the panel shows it: a list as a list, one line
// per item, under the attribute's label. Anything else is the inline text.
export const attributeValue = (v) =>
  Array.isArray(v)
    ? html`<ul>
        ${v.map((item) => html`<li>${attributeText(item)}</li>`)}
      </ul>`
    : attributeText(v);

// The attributes the item sets, one line each, in the order the model
// declared them. An item that sets none shows nothing.
export const attributeRows = (item) =>
  html`<ul>
    ${attributeEntries(item).map(
      ({ label, value }) =>
        html`<li class="hint"><b>${label}:</b> ${attributeValue(value)}</li>`,
    )}
  </ul>`;

// The attributes of the item, under a heading like the panel's other sections.
// An item that sets none shows neither the heading nor the rows.
export const attributeSection = (item) => {
  const rows = attributeRows(item);
  return rows
    ? html`<h3>Attributes</h3>
        ${rows}`
    : "";
};
