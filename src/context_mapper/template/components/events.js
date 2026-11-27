// The events of an entry, as the panel shows them: what it publishes, each
// event with its description and who consumes it, and what it consumes, each
// address with a link to its publisher. An aggregate's two lists are rows of
// its block; a bounded context's or a domain's are sections of their own.
import { nameOf } from "../core/model.js";
import { holderOf } from "../core/events.js";
import { html } from "htm/preact/standalone";

const commaList = (items) =>
  items.map((item, i) => (i ? html`, ${item}` : item));

// A consumer: the context or domain, a link that focuses on it, and its
// aggregate after a slash when the consumer is one.
const consumer = (c) =>
  html`<a data-go="${c.id}">${nameOf(c.id)}</a>${c.aggregate ? ` / ${c.aggregate}` : ""}${c.reason ? ` — ${c.reason}` : ""}`;

// What a published event reads like: its name and description, then who
// consumes it. Consumers read inline; when any of them says why, each has a
// line of its own with its reason after a dash.
const published = (event) => {
  const line =
    event.name + (event.description ? ` — ${event.description}` : "");
  if (!event.consumers.length) return line;
  const glue = /[.!?]$/.test(line) ? " " : ". ";
  return event.consumers.some((c) => c.reason)
    ? html`${line}${glue}Consumed by:
        <ul>
          ${event.consumers.map((c) => html`<li>${consumer(c)}</li>`)}
        </ul>`
    : html`${line}${glue}Consumed by${" "}${commaList(event.consumers.map(consumer))}`;
};

// An address as written, its first part a link that focuses on the publisher,
// and why it is consumed after a dash, when it says.
const consumed = (item) =>
  html`<a data-go="${item.publisher}">${item.publisher}</a>/${item.address.split("/").slice(1).join("/")}${
    item.reason ? ` — ${item.reason}` : ""
  }`;

// The rows of an aggregate's block for its events: a label, and the items.
export const eventRows = (entry) =>
  [
    ["Publishes", (entry.publishes || []).map(published)],
    ["Consumes", (entry.consumes || []).map(consumed)],
  ]
    .filter(([, items]) => items.length)
    .map(([label, items]) => [
      label,
      html`<ul>
        ${items.map((item) => html`<li>${item}</li>`)}
      </ul>`,
    ]);

// The sections of a bounded context or a domain: Publishes and Consumes, each
// only when it has something in it.
export const eventSections = (item) => {
  const holder = holderOf(item);
  const section = (label, items) =>
    items.length
      ? html`<h3>${label} (${items.length})</h3>
          <ul>
            ${items.map((i) => html`<li>${i}</li>`)}
          </ul>`
      : null;
  return [
    section("Publishes", (holder.publishes || []).map(published)),
    section("Consumes", (holder.consumes || []).map(consumed)),
  ];
};
