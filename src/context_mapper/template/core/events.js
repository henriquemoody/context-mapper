// The events of the model as pure data, shared by the panel, the tooltips and
// the diagram: whose they are, how an event reads, and which ones cross a
// dependency. An event has one address, which mirrors where it is published,
// and graph.py resolves every consume to it; the dependencies and partnerships
// an event goes through carry it in `events`.
import { contextById } from "./model.js";

// The entry that holds the events of an item: a domain no context points at is
// a single bounded context, and its events are its context's.
export const holderOf = (item) => contextById[item.id] || item;

// An event as a short label: the aggregate it is published on, when it has
// one, then its name.
export const eventLabel = (event) =>
  event.aggregate ? `${event.aggregate} · ${event.name}` : event.name;

// The events that go through any of these dependencies or partnerships, each
// once, in the order they were first met, each with what is said about it
// here: the reasons the consumers give, one text for each different one, or,
// when none of them gives a reason, the event's own description.
export function crossing(rules) {
  const byAddress = new Map();
  rules.forEach((rule) =>
    (rule.events || []).forEach((event) => {
      if (!byAddress.has(event.address)) {
        const { consumer, reason, description, ...own } = event;
        byAddress.set(event.address, {
          ...own,
          description,
          reasons: [],
        });
      }
      const seen = byAddress.get(event.address);
      if (event.reason && !seen.reasons.includes(event.reason))
        seen.reasons.push(event.reason);
    }),
  );
  return [...byAddress.values()].map(({ description, reasons, ...event }) => ({
    ...event,
    texts: reasons.length ? reasons : description ? [description] : [],
  }));
}

// The tooltip entry of an arrow for the events that cross it: none when no
// event does. One line per event, never inline, since an event can carry a
// description or a reason: `Aggregate · Event`, then ` — ` and what is said
// about it, one line for each when several things are.
export function eventsTipEntries(rules) {
  const events = crossing(rules);
  if (!events.length) return [];
  const lines = events.flatMap((event) =>
    event.texts.length
      ? event.texts.map((text) => `${eventLabel(event)} — ${text}`)
      : [eventLabel(event)],
  );
  return [{ kind: "events", title: "Events", text: lines.join("\n") }];
}
