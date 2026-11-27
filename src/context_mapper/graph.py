"""Normalized domain model and graph walks shared by the build and the Mermaid renderer.

Two levels:
- context: nodes are bounded contexts, plus multi-context domains (for dependencies
  that point at a domain as a whole). Edges are as written in context-map.yml.
- domain: nodes are domains. Edges are lifted from contexts to their domains,
  merged, and edges inside a domain are dropped.

Three kinds of thing, in three sections: `types` is the role vocabulary of the
model (a domain or bounded context has one, and it colors the box), `clusters`
names a set of domains or contexts treated together (members point at one with
`cluster:`), and `context-map` maps each id to what it is. An optional
`attributes` section declares the attributes any entry can set, typed and
checked by the build. A cluster holds members; a domain holds bounded
contexts; neither can be depended on or hold the other's children. How anything
first renders comes from `defaultDisplay` in the style file: a domain or a
cluster can be expanded, collapsed, contents or hidden; a bounded context — a
domain no context points at is one too — is one box with nothing inside, so it
can only be expanded or hidden. No type name is special.

A bounded context can also list its `aggregates`: names only, with a root, the
entities and value objects it holds, and the aggregates it references. They are
checked here and carried on the context; a third level of the page, `aggregate`,
draws them inside their contexts, over the walk of the context level.
"""
import datetime

# Mermaid classDef attributes a box style may set, in `types`, `clusters` and
# `context-map` alike. The build checks them, so a typo fails the build instead
# of drawing nothing.
BOX_STYLE_KEYS = {"color", "fill", "fill-opacity", "font-family", "font-size",
                  "font-weight", "opacity", "stroke", "stroke-dasharray",
                  "stroke-opacity", "stroke-width"}

# The types an attribute can take. `text` is one value, `list` a list of
# them, `map` label-to-value pairs, and `any` whatever shape the model wants:
# the escape hatch, for an attribute a model declares for itself.
ATTRIBUTE_TYPES = ("any", "list", "map", "text")

# How a container first renders. expanded: the box and the boxes inside it.
# collapsed: the box alone, the inside hidden. contents: the inside alone, the
# box hidden. hidden: neither.
DISPLAY_STATES = ("expanded", "collapsed", "contents", "hidden")

# How a bounded context first renders — a domain no context points at is one
# too. It is a single box with nothing inside, so there is nothing to collapse
# and no contents to show: expanded draws the box, hidden doesn't.
BOX_DISPLAY_STATES = ("expanded", "hidden")

# What a style fills in when the entry doesn't say: readable text on a light box.
TEXT_DEFAULTS = {"color": "#1a1a1a"}

# The roles a dependency can carry, from the DDD context-map patterns: what the upstream is, and what
# the downstream is. Each has a short code for drawing and a display name for tooltips and lists. The
# order here is the canonical one: roles are always drawn and listed in it, never in the YAML's order.
UPSTREAM_ROLES = {
    "OpenHostService": {"code": "OHS", "name": "Open Host Service"},
    "PublishedLanguage": {"code": "PL", "name": "Published Language"},
    "Supplier": {"code": "S", "name": "Supplier"},
}
DOWNSTREAM_ROLES = {
    "AnticorruptionLayer": {"code": "ACL", "name": "Anticorruption Layer"},
    "Conformist": {"code": "CF", "name": "Conformist"},
    "Customer": {"code": "C", "name": "Customer"},
}
# Every role with the side it belongs to, as the interactive page gets them.
ROLES = {**{role: {**info, "side": "upstream"} for role, info in UPSTREAM_ROLES.items()},
         **{role: {**info, "side": "downstream"} for role, info in DOWNSTREAM_ROLES.items()}}


# The relationships that have no direction: two entries that plan together (a partnership) or share part
# of the model itself (a shared kernel). Each is a key an entry can carry, a map like `violations`. They
# are not dependencies, so they never make a cycle, but a focus reaches across them both ways. `link` is
# the line Mermaid draws when nothing else carries the pair: no heads, for both.
SYMMETRIC_KINDS = {
    "partnership": {"key": "partnerships", "name": "Partnership", "heading": "Partners", "verb": "partners with",
                    "link": "---"},
    "sharedKernel": {"key": "sharedKernels", "name": "Shared Kernel", "heading": "Shares a kernel with",
                     "verb": "shares a kernel with", "link": "---"},
}


def role_text(upstream, downstream):
    """A dependency's roles as a sentence for tooltips and lists: the upstream roles, an arrow, the downstream
    roles, with the display names. One side alone says which side it is. No roles, no text."""
    up = ", ".join(ROLES[role]["name"] for role in upstream)
    down = ", ".join(ROLES[role]["name"] for role in downstream)
    if up and down:
        return f"{up} \u2192 {down}"
    if up:
        return f"{up} (upstream)"
    if down:
        return f"{down} (downstream)"
    return ""


def role_codes(upstream, downstream):
    """The short codes of a dependency's roles, as (upstream, downstream) lists of strings."""
    return [ROLES[role]["code"] for role in upstream], [ROLES[role]["code"] for role in downstream]


def shared_roles(deps):
    """The roles a merged edge keeps: those every dependency it stands for carries, exactly. A dependency
    with no roles is different from one with roles, so one of each drops them all."""
    seen = {(tuple(dep.get("upstream") or ()), tuple(dep.get("downstream") or ())) for dep in deps}
    upstream, downstream = seen.pop() if len(seen) == 1 else ((), ())
    return list(upstream), list(downstream)


def check_roles(where, spec, errors):
    """Check the `upstream` and `downstream` of one dependency and return them as two lists, in the canonical
    order. A bad side is an error and comes back empty, so one mistake doesn't hide the other side's."""
    sides = {"upstream": UPSTREAM_ROLES, "downstream": DOWNSTREAM_ROLES}
    checked, clean = {"upstream": [], "downstream": []}, True
    for side, known in sides.items():
        if side not in spec:
            continue
        here, value = f"{where}.{side}", spec[side]
        listing = f"Known: {', '.join(known)}"
        problems = []
        if not isinstance(value, list):
            problems.append(f"{here}: must be a list of roles. {listing}")
        else:
            for role in value:
                if not isinstance(role, str):
                    problems.append(f"{here}: a role is a string, not {role!r}. {listing}")
                elif role in sides["downstream" if side == "upstream" else "upstream"]:
                    elsewhere = "downstream" if side == "upstream" else "upstream"
                    article = "a" if elsewhere == "downstream" else "an"
                    problems.append(f"{here}: '{role}' is {article} {elsewhere} role, it goes under `{elsewhere}`")
                elif role not in known:
                    problems.append(f"{here}: unknown role '{role}'. {listing}")
            problems += [f"{here}: '{role}' is listed more than once"
                         for role in known if value.count(role) > 1]
        errors += problems
        if problems:
            clean = False
        else:
            checked[side] = [role for role in known if role in value]
    if not clean:
        return [], []

    upstream, downstream = checked["upstream"], checked["downstream"]
    if "AnticorruptionLayer" in downstream and "Conformist" in downstream:
        errors.append(f"{where}.downstream: AnticorruptionLayer and Conformist exclude each other, "
                      "a downstream either translates or conforms")
    elif "Conformist" in downstream and ("Customer" in downstream or "Supplier" in upstream):
        errors.append(f"{where}: Conformist can't go with Customer or Supplier, "
                      "a conformist takes what it is given and has no say")
    elif ("Supplier" in upstream) != ("Customer" in downstream):
        missing = "Customer under `downstream`" if "Supplier" in upstream else "Supplier under `upstream`"
        errors.append(f"{where}: Supplier and Customer come as a pair, it needs {missing}")
    return upstream, downstream


def classdef(attrs, defaults=TEXT_DEFAULTS):
    """A Mermaid classDef string: the attributes as written, then the defaults not set."""
    items = list((attrs or {}).items())
    have = {key for key, _ in items}
    items += [(key, value) for key, value in defaults.items() if key not in have]
    return ",".join(f"{key}:{value}" for key, value in items)


def is_scalar(value):
    """A single value, not a list or a map: what a text attribute takes and
    what a list or a map holds. A date counts, and a datetime is a date."""
    return isinstance(value, (str, int, float, bool, datetime.date))


def display_text(value):
    """One value as the text to show: a bool reads as true or false, a date as
    its ISO form, anything else as its own text."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime.date):
        return value.isoformat()
    return str(value)


def any_value(value):
    """An `any` value as the plain text, list and map the pages can show:
    strings all the way down, and the parts with no value left out."""
    if isinstance(value, dict):
        return {str(key): any_value(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [any_value(item) for item in value if item is not None]
    return display_text(value)


def check_attributes(where, values, definitions, errors):
    """Check the attributes one entry sets and return them, coerced for
    display. A bad attribute is an error and is left out; the others are kept,
    so one typo does not hide the rest of the entry."""
    if values is None:
        return None
    if not isinstance(values, dict):
        errors.append(f"{where}.attributes: must be a map from attribute to value")
        return None
    if not values:
        errors.append(f"{where}.attributes is empty")
        return None
    attributes = {}
    for attribute_id, value in values.items():
        definition = definitions.get(attribute_id)
        if definition is None:
            errors.append(f"{where}.attributes.{attribute_id}: unknown attribute, it is not in `attributes`")
            continue
        if value is None:
            errors.append(f"{where}.attributes.{attribute_id}: must have a value")
            continue
        kind = definition["type"]
        if kind == "text":
            if isinstance(value, (dict, list)):
                errors.append(f"{where}.attributes.{attribute_id}: a text attribute takes a single value")
                continue
            attributes[attribute_id] = display_text(value)
        elif kind == "list":
            if not isinstance(value, list):
                errors.append(f"{where}.attributes.{attribute_id}: a list attribute takes a list of values")
                continue
            if not value:
                errors.append(f"{where}.attributes.{attribute_id}: needs at least one value")
                continue
            if not all(is_scalar(item) for item in value):
                errors.append(f"{where}.attributes.{attribute_id}: list values must be single values")
                continue
            attributes[attribute_id] = [display_text(item) for item in value]
        elif kind == "map":
            if not isinstance(value, dict):
                errors.append(f"{where}.attributes.{attribute_id}: a map attribute takes a map from label to value")
                continue
            if not value:
                errors.append(f"{where}.attributes.{attribute_id}: needs at least one value")
                continue
            if not all(is_scalar(item) for item in value.values()):
                errors.append(f"{where}.attributes.{attribute_id} values must be single values")
                continue
            attributes[attribute_id] = {str(key): display_text(item) for key, item in value.items()}
        else:  # any: whatever shape, as long as it can be shown
            if isinstance(value, (dict, list)) and not value:
                errors.append(f"{where}.attributes.{attribute_id}: needs at least one value")
                continue
            attributes[attribute_id] = any_value(value)
    return attributes


# The keys an aggregate takes. An aggregate is a name, a root, the entities and value objects it holds, and
# the aggregates it points at: names only, nothing about fields or behavior.
AGGREGATE_KEYS = ("description", "root", "entities", "valueObjects", "references", "publishes", "consumes",
                  "attributes")

# The keys an entry takes for events. `publishes` names the events it publishes, `consumes` the addresses of the
# events it consumes. An aggregate, a bounded context and a domain take both; a cluster takes neither.
EVENT_KEYS = ("publishes", "consumes")


def check_members(where, key, value, errors):
    """The `entities` or the `valueObjects` of an aggregate: a list of names, or a map from name to description
    (a string, or nothing). Returns [{name, description}], in the order written; a bad value is an error and
    comes back empty."""
    here = f"{where}.{key}"
    if isinstance(value, list):
        pairs = [(item, None) for item in value]
    elif isinstance(value, dict):
        pairs = list(value.items())
    else:
        errors.append(f"{here}: must be a list of names, or a map from name to description")
        return []
    if not pairs:
        errors.append(f"{here}: needs at least one name")
        return []
    members, clean = [], True
    for name, description in pairs:
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{here}: a name is a non-empty string, not {name!r}")
            clean = False
        elif description is not None and not isinstance(description, str):
            errors.append(f"{here}.{name}: the description must be a string, or nothing")
            clean = False
        else:
            members.append({"name": name, "description": description})
    return members if clean else []


def parse_events(where, spec, errors):
    """The `publishes` and the `consumes` of one entry, as (publishes, consumes). `publishes` is [{name,
    description}], names with no `/` and none twice; `consumes` is [{address, description}] as written, which
    check_events resolves once the whole model is known. Each key is a list of names or a map from name to
    description. A bad value is an error and comes back empty. The description of a consume is why the consumer
    reacts to the event: its `reason`."""
    publishes, consumes = [], []
    if "publishes" in spec:
        seen = set()
        for member in check_members(where, "publishes", spec["publishes"], errors):
            if "/" in member["name"]:
                errors.append(f"{where}.publishes: '{member['name']}' can't hold a '/', which an event's address "
                              "uses to say where it is published")
            elif member["name"] in seen:
                errors.append(f"{where}.publishes: '{member['name']}' is published twice here")
            else:
                seen.add(member["name"])
                publishes.append(member)
    if "consumes" in spec:
        consumes = [{"address": member["name"], "reason": member["description"]}
                    for member in check_members(where, "consumes", spec["consumes"], errors)]
    return publishes, consumes


def check_aggregates(where, raw, definitions, errors):
    """Check the `aggregates` of one bounded context and return them, in the order written. Each is {name,
    description, root, entities, valueObjects, references, attributes?}: the root is named once, apart from the
    entities, and `references` still holds the strings as written — check_references resolves them once the
    model is known. A bad part is an error and is left out, so one typo doesn't hide the rest."""
    if not isinstance(raw, dict):
        errors.append(f"{where}.aggregates: must be a map from aggregate name to what it holds")
        return []
    if not raw:
        errors.append(f"{where}.aggregates is empty")
        return []
    aggregates = []
    for name, spec in raw.items():
        here = f"{where}.aggregates.{name}"
        if not isinstance(name, str) or not name.strip():
            errors.append(f"{where}.aggregates: the name of an aggregate is a non-empty string, not {name!r}")
            continue
        if "/" in name:
            errors.append(f"{here}: an aggregate's name can't hold a '/', which a reference uses to say "
                          "which context it is in")
            continue
        if spec is not None and not isinstance(spec, dict):
            errors.append(f"{here}: must be a map, or nothing at all for an aggregate with only a name")
            continue
        spec = spec or {}
        for key in spec:
            if key not in AGGREGATE_KEYS:
                errors.append(f"{here}.{key}: unknown option. Known: {', '.join(sorted(AGGREGATE_KEYS))}")
        description = spec.get("description")
        if description is not None and not isinstance(description, str):
            errors.append(f"{here}.description: must be a string")
            description = None
        root = spec.get("root", name)
        if not isinstance(root, str) or not root.strip():
            errors.append(f"{here}.root: must be the name of the root entity")
            root = name
        entities = check_members(here, "entities", spec["entities"], errors) if "entities" in spec else []
        value_objects = check_members(here, "valueObjects", spec["valueObjects"], errors) if "valueObjects" in spec else []
        # A name is used once in an aggregate, whatever it is: the root counts as an entity.
        used = {root: "the root"}
        for kind, members in (("an entity", entities), ("a value object", value_objects)):
            for member in members:
                if member["name"] in used:
                    before = used[member["name"]]
                    hint = ", and the root is an entity already, so it is not listed with them" if before == "the root" else ""
                    errors.append(f"{here}: '{member['name']}' is named more than once, as {before} and as {kind}{hint}")
                else:
                    used[member["name"]] = kind
        references = []
        if "references" in spec:
            value = spec["references"]
            if not isinstance(value, list):
                errors.append(f"{here}.references: must be a list of aggregates, `Name` in this context "
                              "or `context-id/Name` in another")
            elif not value:
                errors.append(f"{here}.references: needs at least one aggregate")
            else:
                for reference in value:
                    if isinstance(reference, str) and reference.strip():
                        references.append(reference)
                    else:
                        errors.append(f"{here}.references: a reference is a string, `Name` or `context-id/Name`, "
                                      f"not {reference!r}")
        publishes, consumes = parse_events(here, spec, errors)
        aggregate = {"name": name, "description": description, "root": root, "entities": entities,
                     "valueObjects": value_objects, "references": references, "publishes": publishes,
                     "consumes": consumes}
        attributes = check_attributes(here, spec.get("attributes"), definitions, errors)
        if attributes:
            aggregate["attributes"] = attributes
        aggregates.append(aggregate)
    return aggregates


def event_entries(where, spec, errors):
    """The `publishes` and `consumes` of a bounded context or a domain, as the keys its entry carries: only the
    ones it sets, and not empty."""
    publishes, consumes = parse_events(where, spec, errors)
    return {key: value for key, value in (("publishes", publishes), ("consumes", consumes)) if value}


def event_where(info):
    """Where an event is published, in words: the aggregate, the bounded context or the domain."""
    if info["level"] == "aggregate":
        return f"the aggregate '{info['aggregate']}' of '{info['owner']}'"
    return f"the {'domain' if info['level'] == 'domain' else 'bounded context'} '{info['owner']}'"


def check_events(data, errors):
    """Resolve what each aggregate, bounded context and domain consumes, in place, and tie the model's events
    together. An event has one address, which mirrors where it is published: `context-id/Aggregate/Event` on an
    aggregate, `context-id/Event` on a bounded context (a domain with no contexts is one), `domain-id/Event` on
    a domain that holds contexts. The address of what is consumed is that, in full, always.

    A consumer is the context an entry belongs to, an aggregate's too, or the domain for a key of a domain that
    holds contexts. Consuming across them takes a dependency from the consumer to the publisher, the way an
    aggregate reference does (written between them, or against either one's whole domain), or a partnership
    between them. A violation and a shared kernel don't count. Inside one domain, a context and the domain
    itself are the same side. Each publish gets its `address` and its `consumers`, each consume is resolved to
    {address, reason, publisher, level, aggregate, name}, and the dependencies and partnerships an event
    crosses carry it in `events`, which is where the interactive page gets the tooltip of an arrow. A bad
    consume is an error and is left out."""
    contexts = {context["id"]: context for context in data["contexts"]}
    domains = {domain["id"]: domain for domain in data["domains"]}
    multi = {domain_id for domain_id, domain in domains.items() if not domain["single"]}
    owner = {context_id: context["domain"] for context_id, context in contexts.items()}
    owner.update({domain_id: domain_id for domain_id in multi})

    # Everything that publishes or consumes: (owner id, aggregate name or None, the entry, where it is written).
    holders = []
    for context_id, context in contexts.items():
        holders.append((context_id, None, context, f"context-map.{context_id}"))
        holders += [(context_id, aggregate["name"], aggregate,
                     f"context-map.{context_id}.aggregates.{aggregate['name']}")
                    for aggregate in context.get("aggregates", [])]
    holders += [(domain_id, None, domains[domain_id], f"context-map.{domain_id}") for domain_id in multi]

    published = {}
    for holder_id, aggregate, holder, _ in holders:
        for event in holder.get("publishes", []):
            address = "/".join(part for part in (holder_id, aggregate, event["name"]) if part)
            level = "aggregate" if aggregate else "domain" if holder_id in multi else "context"
            event["address"], event["consumers"] = address, []
            published[address] = {"event": event, "owner": holder_id, "aggregate": aggregate, "level": level,
                                  "name": event["name"]}

    def elsewhere(name, owners):
        return [(address, info) for address, info in published.items() if info["owner"] in owners and info["name"] == name]

    def lookup(address, here):
        parts = address.split("/")
        if len(parts) not in (2, 3) or not all(part.strip() for part in parts):
            errors.append(f"{here}: '{address}' is not an event address: `context-id/Aggregate/Event` for an event "
                          "of an aggregate, `context-id/Event` for one of a bounded context, `domain-id/Event` "
                          "for one of a domain")
            return None
        place, name = parts[0], parts[-1]
        if place not in contexts and not (len(parts) == 2 and place in multi):
            known = " It is a domain, and a domain has no aggregates." if place in multi else ""
            what = "bounded context" if len(parts) == 3 else "bounded context or domain"
            errors.append(f"{here}: unknown {what} '{place}' in '{address}'.{known}")
            return None
        if len(parts) == 3:
            names = [aggregate["name"] for aggregate in contexts[place].get("aggregates", [])]
            if parts[1] not in names:
                errors.append(f"{here}: unknown aggregate '{parts[1]}' in '{place}', in '{address}'. "
                              f"Known: {', '.join(names) or 'none'}")
                return None
        if address in published:
            return published[address]
        # Which part is unknown, and where the event is published, when it is somewhere else in the same place.
        if len(parts) == 3:
            holder = next(aggregate for aggregate in contexts[place]["aggregates"] if aggregate["name"] == parts[1])
            in_place, where = [e["name"] for e in holder.get("publishes", [])], f"on the aggregate '{parts[1]}'"
        else:
            holder = contexts.get(place) or domains[place]
            in_place, where = [e["name"] for e in holder.get("publishes", [])], f"on '{place}'"
        scope = ({place, *domains[place]["contexts"]} if place in multi
                 else {place, *({owner[place]} & multi)})
        found = elsewhere(name, scope)
        hint = ""
        if found:
            hint = " " + " and ".join(f"It is published on {event_where(info)}, its address is '{found_address}'."
                                       for found_address, info in found)
        errors.append(f"{here}: unknown event '{name}' {where} in '{address}'. "
                      f"Known: {', '.join(in_place) or 'none'}.{hint}")
        return None

    def crossing(consumer, publisher):
        """(allowed, the dependencies or partnerships the events go through, why not)."""
        target = publisher["owner"]
        if consumer == target or (owner[consumer] == owner[target] and (consumer in multi or target in multi)):
            return True, [], ""
        if consumer in multi:
            starts = {member: 0 for member in (consumer, *domains[consumer]["contexts"])}
            domain_id = owner[target]
            ends = {member: 0 for member in ((domain_id, *domains[domain_id]["contexts"]) if domain_id in multi
                                             else (domain_id,))}
        elif owner[consumer] == owner[target]:
            starts, ends = {consumer: 0}, {target: 0}
        else:
            starts = {consumer: 0, **({owner[consumer]: 1} if owner[consumer] in multi else {})}
            ends = ({target: 0, **{member: 1 for member in domains[target]["contexts"]}} if target in multi
                    else {target: 0, **({owner[target]: 1} if owner[target] in multi else {})})

        def hits(rules, one, other, flip=False):
            found = []
            for rule in rules:
                if (rule[one] in starts and rule[other] in ends):
                    found.append((starts[rule[one]] + ends[rule[other]], rule))
                elif flip and rule[other] in starts and rule[one] in ends:
                    found.append((starts[rule[other]] + ends[rule[one]], rule))
            if consumer in multi or not found:
                return [rule for _, rule in found]
            best = min(rank for rank, _ in found)
            return [rule for rank, rule in found if rank == best]

        rules = hits(data["edges"], "from", "to")
        if rules:
            return True, rules, ""
        rules = hits([rule for rule in data["symmetric"] if rule["kind"] == "partnership"], "a", "b", flip=True)
        if rules:
            return True, rules, ""
        side = f"'{consumer}'" if consumer not in multi else f"the '{consumer}' domain"
        against = hits(data["violations"], "from", "to")
        kernel = hits([rule for rule in data["symmetric"] if rule["kind"] == "sharedKernel"], "a", "b", flip=True)
        reverse = [rule for rule in data["edges"] if rule["from"] in ends and rule["to"] in starts]
        if against:
            why = (f"{side} has only a violation against '{target}' (in context-map.{against[0]['from']}"
                   f".violations.{against[0]['to']}), a known mistake and not a permission")
        elif kernel:
            why = (f"{side} shares a kernel with '{target}', and a kernel shares types, it gives no direction")
        elif reverse:
            why = f"'{target}' depends on {side}, not the other way round, so {side} is upstream"
        else:
            why = f"{side} doesn't depend on '{target}'" + (", and neither do its bounded contexts"
                                                          if consumer in multi else "")
        return False, [], why

    seen = {}  # consumer id -> {address: where it was written first}
    for holder_id, aggregate, holder, where in holders:
        resolved = []
        for item in holder.get("consumes", []):
            address, here = item["address"], f"{where}.consumes"
            publisher = lookup(address, here)
            if not publisher:
                continue
            first = seen.setdefault(holder_id, {})
            if address in first:
                errors.append(f"{here}: '{address}' is consumed twice by '{holder_id}' (also in {first[address]}). "
                              "A context and its aggregates count together")
                continue
            first[address] = here
            allowed, rules, why = crossing(holder_id, publisher)
            if not allowed:
                errors.append(f"{here}: '{address}' is not allowed, {why}. A consumer is downstream of what it "
                              f"consumes from, so list '{holder_id}' under context-map.{publisher['owner']}"
                              ".downstreams, declare a partnership between them, or drop the event")
                continue
            # Each consumer's own reason goes with the event, where it crosses: that arrow is its.
            for rule in rules:
                marked = rule.setdefault("events", [])
                marked.append({"address": address, "name": publisher["name"], "aggregate": publisher["aggregate"],
                               "description": publisher["event"]["description"], "consumer": holder_id,
                               "reason": item["reason"]})
            publisher["event"]["consumers"].append({"id": holder_id, "aggregate": aggregate, "reason": item["reason"]})
            resolved.append({"address": address, "reason": item["reason"], "publisher": publisher["owner"],
                             "level": publisher["level"], "aggregate": publisher["aggregate"],
                             "name": publisher["name"]})
        if "consumes" in holder:
            if resolved or aggregate:
                holder["consumes"] = resolved
            else:
                del holder["consumes"]


def check_references(contexts, domains, edges, violations, symmetric, errors):
    """Resolve what each aggregate references, in place: from the strings as written to {context, name}, the
    context always spelled out. A bare name is in the aggregate's own context, and `context/Name` may say so too.
    A reference to another context's aggregate is allowed when that context is upstream of this one: this
    context depends on it, directly or through a dependency written against either one's domain as a whole, or
    the two share a kernel or a partnership. A violation is a known mistake, not a permission. A bad reference
    is an error and is left out."""
    aggregate_names = {context["id"]: [aggregate["name"] for aggregate in context.get("aggregates", [])]
                       for context in contexts}
    owned_by = {context["id"]: context["domain"] for context in contexts}
    whole = {domain["id"] for domain in domains if not domain["single"]}

    def sides(context_id):
        """The ids a dependency can name for a context: itself, and its domain when that holds several."""
        domain_id = owned_by[context_id]
        return {context_id, domain_id} if domain_id in whole else {context_id}

    def between(one, other, rules, keys):
        """Whether a rule runs from `one` to `other`, either side given as a whole domain. Two contexts of
        one domain count only for a rule that names them."""
        if owned_by[one] == owned_by[other]:
            starts, ends = {one}, {other}
        else:
            starts, ends = sides(one), sides(other)
        return next((rule for rule in rules if rule[keys[0]] in starts and rule[keys[1]] in ends), None)

    for context in contexts:
        for aggregate in context.get("aggregates", []):
            here = f"context-map.{context['id']}.aggregates.{aggregate['name']}.references"
            resolved = []
            for reference in aggregate["references"]:
                target, _, name = reference.rpartition("/") if "/" in reference else (context["id"], "", reference)
                if not target.strip() or not name.strip():
                    errors.append(f"{here}: '{reference}' is not `Name` or `context-id/Name`")
                    continue
                if target not in aggregate_names:
                    kind = " It is a domain: name one of its bounded contexts." if target in owned_by.values() else ""
                    errors.append(f"{here}: unknown bounded context '{target}' in '{reference}'.{kind}")
                    continue
                if name not in aggregate_names[target]:
                    known = ", ".join(aggregate_names[target]) or "none"
                    errors.append(f"{here}: unknown aggregate '{name}' in '{target}'. Known: {known}")
                    continue
                if target == context["id"] and name == aggregate["name"]:
                    errors.append(f"{here}: '{aggregate['name']}' references itself")
                    continue
                if target != context["id"]:
                    mine = context["id"]
                    reaches = (between(mine, target, edges, ("from", "to"))
                               or between(mine, target, symmetric, ("a", "b"))
                               or between(target, mine, symmetric, ("a", "b")))
                    if not reaches:
                        against = between(mine, target, violations, ("from", "to"))
                        reverse = between(target, mine, edges, ("from", "to"))
                        if against:
                            why = (f"'{mine}' has only a violation against '{target}' (in "
                                   f"context-map.{against['from']}.violations.{against['to']}), a known mistake and not a permission")
                        elif reverse:
                            why = (f"'{target}' depends on '{mine}', not the other way round, so '{mine}' is "
                                   f"upstream and can't know what is downstream of it")
                        else:
                            why = f"'{mine}' doesn't depend on '{target}'"
                        errors.append(f"{here}: '{reference}' is not allowed, {why}. A context references the "
                                      f"aggregates of what it depends on, so list '{mine}' under "
                                      f"context-map.{target}.downstreams, share a kernel or a partnership with it, "
                                      "or drop the reference")
                        continue
                if any(item == {"context": target, "name": name} for item in resolved):
                    errors.append(f"{here}: '{reference}' is listed more than once")
                    continue
                resolved.append({"context": target, "name": name})
            aggregate["references"] = resolved


def box_style(section, item_id, style, defaults, required, errors, allowed=None,
              display_states=DISPLAY_STATES):
    """Check one box style map and return its classDef string, or None when there is nothing to draw."""
    if not style:
        return None
    allowed = allowed or BOX_STYLE_KEYS
    if "defaultDisplay" in style and "defaultDisplay" in allowed and style["defaultDisplay"] not in display_states:
        hint = "" if display_states is DISPLAY_STATES else " — a bounded context is one box, with nothing inside it"
        errors.append(f"context-map.style.yml: {section}.{item_id}.defaultDisplay must be one of "
                      f"{', '.join(display_states)}{hint}")
    for key in style:
        if key not in allowed:
            errors.append(f"context-map.style.yml: {section}.{item_id}.{key}: unknown option. "
                          f"Known: {', '.join(sorted(allowed))}")
    if required and not set(required) <= style.keys():
        errors.append(f"context-map.style.yml: {section}.{item_id} needs `{required[0]}` and `{required[1]}`")
    attrs = {key: value for key, value in style.items() if key in BOX_STYLE_KEYS}
    return classdef(attrs, defaults) if attrs else None


def normalize(model, styles=None):
    """Turn context-map.yml and context-map.style.yml into {types, clusters, domains, contexts, edges,
    violations, attributes} plus a list of errors.

    `styles` is the parsed context-map.style.yml. Its sections mirror the model's —
    `types`, `clusters`, `context-map` — keyed by the same ids.
    """
    styles = styles or {}
    type_styles = styles.get("types") or {}
    cluster_styles = styles.get("clusters") or {}
    entry_styles = styles.get("context-map") or {}
    errors = []
    domains, contexts, pending, pending_violations, pending_symmetric = [], [], [], [], []
    model = model or {}

    for section in ("types", "context-map"):
        if not model.get(section):
            errors.append(f"context-map.yml: `{section}` is missing or empty")
    if errors:
        return ({"types": {}, "clusters": [], "domains": [], "contexts": [], "edges": [], "violations": [],
                 "symmetric": [], "attributes": {}}, errors)

    types = {}
    for type_id, type_entry in model["types"].items():
        if not isinstance(type_entry, dict):
            errors.append(f"context-map.yml: types.{type_id}: needs a map with `name`")
            continue
        for key in type_entry:
            if key != "name":
                errors.append(f"context-map.yml: types.{type_id}.{key}: unknown option. Known: name")
        style = type_styles.get(type_id) or {}
        mermaid_style = box_style("types", type_id, style, TEXT_DEFAULTS, ("fill", "stroke"), errors)
        if mermaid_style is None:
            errors.append(f"context-map.style.yml: types.{type_id} needs `fill` and `stroke`")
        types[type_id] = {**type_entry, **style, "mermaid_style": mermaid_style}
    for type_id in type_styles:
        if type_id not in model["types"]:
            errors.append(f"context-map.style.yml: types.{type_id}: unknown type, it is not in context-map.yml")

    # Attributes: what an entry may set, declared once for the whole model.
    # The build checks every value against these, so an attribute nobody
    # declared, or a value of the wrong shape, fails the build instead of hiding.
    attributes = {}
    raw_attributes = model.get("attributes") or {}
    if not isinstance(raw_attributes, dict):
        errors.append("context-map.yml: `attributes` must be a map from attribute id to its definition")
        raw_attributes = {}
    for attribute_id, definition in raw_attributes.items():
        if not isinstance(definition, dict):
            errors.append(f"context-map.yml: attributes.{attribute_id}: needs a map with `type`")
            continue
        for key in definition:
            if key not in ("name", "type"):
                errors.append(f"context-map.yml: attributes.{attribute_id}.{key}: unknown option. Known: name, type")
        kind = definition.get("type")
        if kind is None:
            errors.append(f"context-map.yml: attributes.{attribute_id}: needs a type")
            continue
        if kind not in ATTRIBUTE_TYPES:
            errors.append(f"context-map.yml: attributes.{attribute_id}.type: must be one of "
                          f"{', '.join(ATTRIBUTE_TYPES)}")
            continue
        attributes[attribute_id] = {"name": definition.get("name") or attribute_id[:1].upper() + attribute_id[1:],
                                    "type": kind}

    # A cluster names a set of domains or contexts treated together. It holds
    # members, never bounded contexts, and nothing can depend on it.
    raw_entries = model.get("context-map") or {}
    if isinstance(raw_entries, list):
        errors.append("context-map.yml: `context-map` must be a map keyed by id")
        raw_entries = {}

    raw_clusters = model.get("clusters") or {}
    if isinstance(raw_clusters, list):
        errors.append("context-map.yml: `clusters` must be a map keyed by cluster id")
        raw_clusters = {}
    cluster_ids = set(raw_clusters)
    for cluster_id, cluster in raw_clusters.items():
        if not isinstance(cluster, dict):
            errors.append(f"context-map.yml: clusters.{cluster_id}: needs a map with `name`")
            continue
        for key in cluster:
            if key in {info["key"] for info in SYMMETRIC_KINDS.values()}:
                errors.append(f"context-map.yml: clusters.{cluster_id}.{key}: a cluster can't be paired, "
                              "nothing can depend on a cluster, and nothing can be partnered with one either")
            elif key == "aggregates":
                errors.append(f"context-map.yml: clusters.{cluster_id}.aggregates: a cluster has no aggregates, "
                              "only a bounded context does")
            elif key in EVENT_KEYS:
                errors.append(f"context-map.yml: clusters.{cluster_id}.{key}: a cluster has no events, "
                              "an aggregate, a bounded context or a domain does")
            elif key not in ("name", "attributes"):
                errors.append(f"context-map.yml: clusters.{cluster_id}.{key}: unknown option. "
                              f"Known: {', '.join(sorted(('name', 'attributes')))}")
        if not cluster.get("name"):
            errors.append(f"context-map.yml: clusters.{cluster_id}: needs a name")
        if cluster_id in raw_entries:
            errors.append(f"context-map.yml: clusters.{cluster_id}: '{cluster_id}' is also an entry in context-map")

    for entry_id in entry_styles:
        entry = raw_entries.get(entry_id)
        if not isinstance(entry, dict):
            errors.append(f"context-map.style.yml: context-map.{entry_id}: unknown entry, it is not in context-map.yml")
    for cluster_id in cluster_styles:
        if cluster_id not in cluster_ids:
            errors.append(f"context-map.style.yml: clusters.{cluster_id}: unknown cluster, it is not in context-map.yml")

    def check_keys(entry_id, entry, allowed):
        for key in entry:
            if key not in allowed:
                errors.append(f"context-map.{entry_id}.{key}: unknown option. Known: {', '.join(sorted(allowed))}")
        if not entry.get("name"):
            errors.append(f"context-map.{entry_id}: needs a name")

    def check_cluster(entry_id, cluster):
        if cluster is None:
            return
        if not isinstance(cluster, str):
            errors.append(f"context-map.{entry_id}: `cluster` must be an id")
        elif cluster not in cluster_ids:
            errors.append(f"context-map.{entry_id}: unknown cluster '{cluster}', it is not in `clusters`")

    # An entry with a `domain:` key is a bounded context of that domain; any
    # other entry is a domain, and one no context points at is a single bounded
    # context. Every id, domain or context, is a key of this one map, so
    # nothing can be described twice.
    raw_domains, raw_contexts = [], []
    member_of = {}
    for entry_id, entry in raw_entries.items():
        if not isinstance(entry, dict):
            errors.append(f"context-map.{entry_id}: needs a map with `name` and `type`")
            continue
        if "domain" in entry:
            check_keys(entry_id, entry, ("name", "domain", "type", "cluster", "downstreams", "violations",
                                         "partnerships", "sharedKernels", "description", "attributes",
                                         "aggregates", *EVENT_KEYS))
            if entry.get("cluster") is not None:
                errors.append(f"context-map.{entry_id}: a bounded context is inside its domain "
                              "already, it can't also be in a cluster")
            parent = raw_entries.get(entry.get("domain"))
            if not isinstance(parent, dict) or "domain" in parent:
                errors.append(f"context-map.{entry_id}: unknown domain '{entry.get('domain')}'")
            raw_contexts.append((entry_id, entry))
        else:
            check_keys(entry_id, entry, ("name", "type", "cluster", "downstreams", "violations", "partnerships",
                                         "sharedKernels", "description", "attributes", "aggregates",
                                         *EVENT_KEYS))
            check_cluster(entry_id, entry.get("cluster"))
            if entry.get("cluster") is not None:
                member_of[entry_id] = entry["cluster"]
            if entry.get("type") is None:
                errors.append(f"context-map.{entry_id}: needs a type")
            elif entry.get("type") not in types:
                errors.append(f"context-map.{entry_id}: unknown type '{entry.get('type')}'")
            raw_domains.append((entry_id, entry))

    for domain_id, domain in raw_domains:
        domain_type, cluster = domain.get("type"), domain.get("cluster")
        domain_style = entry_styles.get(domain_id) or {}
        if "downstreams" in domain:
            pending.append((domain_id, f"context-map.{domain_id}", domain["downstreams"]))
        if "violations" in domain:
            pending_violations.append((domain_id, f"context-map.{domain_id}", domain["violations"]))
        for kind, info in SYMMETRIC_KINDS.items():
            if info["key"] in domain:
                pending_symmetric.append((domain_id, f"context-map.{domain_id}", kind, domain[info["key"]]))
        context_ids = []
        for context_id, context in raw_contexts:
            if context.get("domain") != domain_id:
                continue
            context_name, context_type = context.get("name"), context.get("type", domain_type)
            if context_type not in types:
                errors.append(f"context '{context_id}': unknown type '{context_type}'")
            context_style = entry_styles.get(context_id) or {}
            context_mermaid_style = box_style("context-map", context_id, context_style, TEXT_DEFAULTS, (), errors,
                                              allowed=BOX_STYLE_KEYS | {"defaultDisplay"},
                                              display_states=BOX_DISPLAY_STATES)
            context_entry = {"id": context_id, "name": context_name, "type": context_type, "domain": domain_id,
                             "description": context.get("description"),
                             "mermaid_style": context_mermaid_style,
                             "defaultDisplay": context_style.get("defaultDisplay")}
            context_attributes = check_attributes(f"context-map.{context_id}", context.get("attributes"),
                                                 attributes, errors)
            if context_attributes:
                context_entry["attributes"] = context_attributes
            if "aggregates" in context:
                context_aggregates = check_aggregates(f"context-map.{context_id}", context["aggregates"],
                                                      attributes, errors)
                if context_aggregates:
                    context_entry["aggregates"] = context_aggregates
            context_entry.update(event_entries(f"context-map.{context_id}", context, errors))
            contexts.append(context_entry)
            context_ids.append(context_id)
            if "downstreams" in context:
                pending.append((context_id, f"context-map.{context_id}", context["downstreams"]))
            if "violations" in context:
                pending_violations.append((context_id, f"context-map.{context_id}", context["violations"]))
            for kind, info in SYMMETRIC_KINDS.items():
                if info["key"] in context:
                    pending_symmetric.append((context_id, f"context-map.{context_id}", kind, context[info["key"]]))
        # A domain with no bounded contexts is one itself: one box, with nothing
        # inside, so its defaultDisplay is a bounded context's.
        mermaid_style = box_style("context-map", domain_id, domain_style, TEXT_DEFAULTS, (), errors,
                                  allowed=BOX_STYLE_KEYS | {"defaultDisplay"},
                                  display_states=DISPLAY_STATES if context_ids else BOX_DISPLAY_STATES)
        domain_entry = {"id": domain_id, "name": domain.get("name"), "type": domain_type, "cluster": cluster,
                        "contexts": context_ids, "single": not context_ids,
                        "mermaid_style": mermaid_style, "defaultDisplay": domain_style.get("defaultDisplay"),
                        "description": domain.get("description")}
        domain_attributes = check_attributes(f"context-map.{domain_id}", domain.get("attributes"),
                                             attributes, errors)
        if domain_attributes:
            domain_entry["attributes"] = domain_attributes
        if context_ids:
            # A domain with no contexts is a single bounded context: its events are the context's.
            domain_entry.update(event_entries(f"context-map.{domain_id}", domain, errors))
        domains.append(domain_entry)
        if context_ids and "aggregates" in domain:
            errors.append(f"context-map.{domain_id}.aggregates: a domain that holds bounded contexts has no "
                          "aggregates of its own, put them on the bounded context that has them")
        if not context_ids:
            # The domain is its own bounded context, and it takes the attributes
            # the domain sets, as it takes its description.
            single_context = {"id": domain_id, "name": domain.get("name"), "type": domain_type, "domain": domain_id,
                              "description": domain.get("description"),
                              "defaultDisplay": domain_style.get("defaultDisplay")}
            if domain_attributes:
                single_context["attributes"] = domain_attributes
            if "aggregates" in domain:
                domain_aggregates = check_aggregates(f"context-map.{domain_id}", domain["aggregates"],
                                                     attributes, errors)
                if domain_aggregates:
                    single_context["aggregates"] = domain_aggregates
            single_context.update(event_entries(f"context-map.{domain_id}", domain, errors))
            contexts.append(single_context)

    clusters = []
    for cluster_id, cluster in raw_clusters.items():
        style = cluster_styles.get(cluster_id) or {}
        mermaid_style = box_style("clusters", cluster_id, style, TEXT_DEFAULTS, (), errors,
                                  allowed=BOX_STYLE_KEYS | {"defaultDisplay"})
        members = [member for member, member_cluster in member_of.items() if member_cluster == cluster_id]
        if isinstance(cluster, dict) and not members and not errors:
            errors.append(f"context-map.yml: clusters.{cluster_id}: no entry points at it with `cluster:`")
        cluster_entry = {"id": cluster_id, "name": cluster.get("name") if isinstance(cluster, dict) else None,
                         "members": members, "mermaid_style": mermaid_style,
                         "defaultDisplay": style.get("defaultDisplay")}
        cluster_attributes = check_attributes(f"context-map.yml: clusters.{cluster_id}",
                                              cluster.get("attributes") if isinstance(cluster, dict) else None,
                                              attributes, errors)
        if cluster_attributes:
            cluster_entry["attributes"] = cluster_attributes
        clusters.append(cluster_entry)

    seen = set(raw_entries)

    edges = []
    for owner, where, downstreams_map in pending:
        # An edge points from the downstream (the one that depends) to the upstream.
        # A downstream maps to why it depends on the upstream (the tooltip), or to
        # {comment, style, upstream, downstream} when the edge also carries a style or relationship roles,
        # or to nothing at all.
        if not isinstance(downstreams_map, dict):
            errors.append(f"{where}: `downstreams` must be a map from downstream to comment")
            continue
        if not downstreams_map:
            errors.append(f"{where}: `downstreams` is empty")
            continue
        for downstream, spec in downstreams_map.items():
            comment, edge_style, upstream_roles, downstream_roles = spec, "solid", [], []
            if isinstance(spec, dict):
                for key in spec:
                    if key not in ("comment", "style", "upstream", "downstream"):
                        errors.append(f"{where}.downstreams.{downstream}.{key}: "
                                      "unknown option. Known: comment, style, upstream, downstream")
                comment, edge_style = spec.get("comment"), spec.get("style") or "solid"
                upstream_roles, downstream_roles = check_roles(f"{where}.downstreams.{downstream}", spec, errors)
            elif spec is not None and not isinstance(spec, str):
                errors.append(f"{where}.downstreams.{downstream}: must be a comment "
                              "string, or a map with `comment` and `style` (and `upstream`, `downstream` for roles)")
            for endpoint in (owner, downstream):
                if endpoint not in seen:
                    errors.append(f"unknown domain or context '{endpoint}' in {where}.downstreams")
            edges.append({"from": downstream, "to": owner, "style": edge_style, "comment": comment,
                          "upstream": upstream_roles, "downstream": downstream_roles})

    # A violation is a dependency that goes against the direction the model draws: `violations` under an
    # entry names what it depends on although it is upstream of it. It is a real dependency, known to be
    # wrong, so it has to be writable — and it never joins `edges`, or the cycle it makes with the
    # downstream it breaks would fail the build. It takes no part in cycles, walks or relations.
    real = {(edge["from"], edge["to"]) for edge in edges}
    violations = []
    for owner, where, violations_map in pending_violations:
        if not isinstance(violations_map, dict):
            errors.append(f"{where}: `violations` must be a map from what it depends on, against the direction, to a comment")
            continue
        if not violations_map:
            errors.append(f"{where}: `violations` is empty")
            continue
        for target, comment in violations_map.items():
            if isinstance(comment, dict) and {"upstream", "downstream"} & comment.keys():
                errors.append(f"{where}.violations.{target}: a violation takes no roles, only a comment string. "
                              "Roles (`upstream`, `downstream`) go on a dependency, under `downstreams`")
                comment = None
            elif comment is not None and not isinstance(comment, str):
                errors.append(f"{where}.violations.{target}: must be a comment string, or nothing")
            if target not in seen:
                errors.append(f"unknown domain or context '{target}' in {where}.violations")
            elif target == owner:
                errors.append(f"{where}.violations.{target}: an entry can't violate its direction toward itself")
            elif (owner, target) in real:
                errors.append(f"{where}.violations.{target}: '{owner}' depends on '{target}' already "
                              f"(in context-map.{target}.downstreams), so it is not against the direction")
            violations.append({"from": owner, "to": target, "comment": comment})

    # A partnership has no direction: both ends plan together, so it replaces a dependency between the two,
    # and a pair that has one — or a violation — already is an error. A shared kernel says the two share part
    # of the model, which takes no direction away: one can still depend on the other, and is drawn on that
    # arrow. A pair is declared once, on either end, as one or the other, and the one that declares it is
    # drawn first. An entry paired with its own domain or one of its contexts is the same thing said twice.
    owned_by = {context["id"]: context["domain"] for context in contexts}
    owned_by.update({domain["id"]: domain["id"] for domain in domains})
    declared = {}
    symmetric = []
    for owner, where, kind, links_map in pending_symmetric:
        info = SYMMETRIC_KINDS[kind]
        key = info["key"]
        if not isinstance(links_map, dict):
            errors.append(f"{where}: `{key}` must be a map from the {info['name'].lower()}'s other end to a comment")
            continue
        if not links_map:
            errors.append(f"{where}: `{key}` is empty")
            continue
        for target, comment in links_map.items():
            here = f"{where}.{key}.{target}"
            if comment is not None and not isinstance(comment, str):
                errors.append(f"{here}: must be a comment string, or nothing")
            if target in cluster_ids:
                errors.append(f"{here}: a cluster can't be paired, nothing can depend on a cluster")
                continue
            if target not in seen:
                errors.append(f"unknown domain or context '{target}' in {where}.{key}")
                continue
            if target == owner:
                errors.append(f"{here}: an entry can't be paired with itself")
                continue
            if owned_by.get(owner) == target or owned_by.get(target) == owner:
                whole, part = (owner, target) if owned_by.get(target) == owner else (target, owner)
                errors.append(f"{here}: '{part}' is in the '{whole}' domain already, so they are not two ends")
                continue
            pair = frozenset((owner, target))
            if pair in declared:
                before, earlier = declared[pair]
                said = ("declare the pair once" if earlier == kind else
                        "a pair is a partnership or a shared kernel, not both")
                errors.append(f"{here}: '{owner}' and '{target}' are paired already (in {before}), {said}")
                continue
            declared[pair] = (f"{where}.{key}.{target}", kind)
            name = info["name"].lower()
            if kind == "sharedKernel":
                symmetric.append({"kind": kind, "a": owner, "b": target, "comment": comment})
                continue
            if (owner, target) in real or (target, owner) in real:
                upstream, downstream = (owner, target) if (target, owner) in real else (target, owner)
                errors.append(f"{here}: '{owner}' and '{target}' have a dependency already (in "
                              f"context-map.{upstream}.downstreams), a {name} replaces the direction between "
                              "them, so keep one of the two")
                continue
            if any({rule["from"], rule["to"]} == set(pair) for rule in violations):
                violating = next(rule["from"] for rule in violations if {rule["from"], rule["to"]} == set(pair))
                errors.append(f"{here}: '{owner}' and '{target}' have a violation already (in "
                              f"context-map.{violating}.violations), a {name} replaces the direction between "
                              "them, so keep one of the two")
                continue
            symmetric.append({"kind": kind, "a": owner, "b": target, "comment": comment})

    check_references(contexts, domains, edges, violations, symmetric, errors)

    data = {"types": types, "clusters": clusters, "domains": domains, "contexts": contexts, "edges": edges,
            "violations": violations, "symmetric": symmetric, "attributes": attributes, "roles": ROLES,
            "symmetric_kinds": SYMMETRIC_KINDS}
    check_events(data, errors)
    if not errors:
        cycle = find_cycle(level_graph(data, "context"))
        if cycle:
            errors.append("dependency cycle: " + " -> ".join(cycle))
    return data, errors


def index(data):
    """Lookups used everywhere: id -> item, and id -> owning domain id."""
    domains = {domain["id"]: domain for domain in data["domains"]}
    contexts = {context["id"]: context for context in data["contexts"]}
    owner = {context["id"]: context["domain"] for context in data["contexts"]}
    owner.update({domain["id"]: domain["id"] for domain in data["domains"]})
    names = {**{domain["id"]: domain["name"] for domain in data["domains"]}, **{context["id"]: context["name"] for context in data["contexts"]}}
    return domains, contexts, owner, names


def level_graph(data, level):
    """Return {nodes: set, edges: [...], child_of: {node: container id}} for a level.

    `child_of` says which container a node renders inside: a bounded context
    inside its domain, a member inside its cluster."""
    domains, contexts, owner, _ = index(data)
    child_of = {domain["id"]: domain["cluster"] for domain in data["domains"] if domain["cluster"]}
    if level == "context":
        nodes = set(contexts) | {domain_id for domain_id, domain in domains.items() if not domain["single"]}
        child_of.update({context_id: context["domain"] for context_id, context in contexts.items()
                         if not domains[context["domain"]]["single"]})
        edges = [{"from": edge["from"], "to": edge["to"], "styles": {edge["style"]}, "via": [edge],
                  "upstream": edge["upstream"], "downstream": edge["downstream"]} for edge in data["edges"]]
        violations = [{"from": rule["from"], "to": rule["to"], "via": [rule]} for rule in data["violations"]]
        links = [{"kind": rule["kind"], "a": rule["a"], "b": rule["b"], "via": [rule]} for rule in data["symmetric"]]
        return {"nodes": nodes, "edges": edges, "violations": violations, "links": links, "child_of": child_of}

    merged = {}
    for edge in data["edges"]:
        downstream_owner, upstream_owner = owner[edge["from"]], owner[edge["to"]]
        if downstream_owner == upstream_owner:
            continue
        entry = merged.setdefault((downstream_owner, upstream_owner),
                                  {"from": downstream_owner, "to": upstream_owner, "styles": set(), "via": []})
        entry["styles"].add(edge["style"])
        entry["via"].append(edge)
    # A merged edge keeps the roles its dependencies all carry, exactly, and none otherwise.
    for entry in merged.values():
        entry["upstream"], entry["downstream"] = shared_roles(entry["via"])
    # A violation between two domains stands for the ones between what they hold, and goes when the
    # domains depend that way anyway — the dependency's own arrow says it, and drawn twice it would only repeat.
    violations = {}
    for rule in data["violations"]:
        downstream_owner, upstream_owner = owner[rule["from"]], owner[rule["to"]]
        key = (downstream_owner, upstream_owner)
        if downstream_owner == upstream_owner or key in merged:
            continue
        violations.setdefault(key, {"from": downstream_owner, "to": upstream_owner, "via": []})["via"].append(rule)
    # A partnership or a shared kernel is lifted the same way: the ones of one kind between the same two
    # domains become one, drawn from the end that declared the first of them; inside a domain they go.
    links = {}
    for rule in data["symmetric"]:
        a_owner, b_owner = owner[rule["a"]], owner[rule["b"]]
        if a_owner == b_owner:
            continue
        key = (rule["kind"], frozenset((a_owner, b_owner)))
        links.setdefault(key, {"kind": rule["kind"], "a": a_owner, "b": b_owner, "via": []})["via"].append(rule)
    return {
        "nodes": set(domains),
        "edges": list(merged.values()),
        "violations": list(violations.values()),
        "links": list(links.values()),
        "child_of": child_of,
    }


def descendants(level_graph, ids):
    """Each id and everything rendered inside it, at this level."""
    kids = {}
    for child, parent in level_graph["child_of"].items():
        kids.setdefault(parent, []).append(child)
    result, stack = set(), list(ids)
    while stack:
        node = stack.pop()
        if node in result:
            continue
        result.add(node)
        stack += kids.get(node, [])
    return result


def find_cycle(level_graph):
    adjacency = {node: [] for node in level_graph["nodes"]}
    for edge in level_graph["edges"]:
        adjacency[edge["from"]].append(edge["to"])
    state, stack = {}, []

    def visit(node):
        state[node] = "open"
        stack.append(node)
        for next_node in adjacency[node]:
            if state.get(next_node) == "open":
                return stack[stack.index(next_node):] + [next_node]
            if next_node not in state:
                found = visit(next_node)
                if found:
                    return found
        stack.pop()
        state[node] = "done"
        return None

    for node in sorted(level_graph["nodes"]):
        if node not in state:
            found = visit(node)
            if found:
                return found
    return None


def focus_set(data, level, focus):
    """The node ids a focus starts from at a level. A domain focus opens it: its
    bounded contexts are starts too. A cluster focus opens it: its members —
    and their bounded contexts there — are starts too."""
    if not focus:
        return set()
    domains, _, owner, _ = index(data)
    clusters = {cluster["id"]: cluster for cluster in data["clusters"]}
    if focus in clusters:
        starts = {focus, *clusters[focus]["members"]}
        if level == "context":
            for member in clusters[focus]["members"]:
                starts.update(domains[member]["contexts"])
        return starts
    if level == "domain":
        return {owner[focus]}
    if focus in domains and not domains[focus]["single"]:
        return {focus, *domains[focus]["contexts"]}
    return {focus}


def walk(level_graph, starts, depth, direction, hidden):
    """Nodes reachable from `starts` within `depth` hops. Without starts, every node.
    `hidden` holds what isn't shown: a hidden container and everything inside it.
    A start is always shown; one that isn't a node, like a cluster, only marks
    itself. Reaching a container reaches what it holds, at the same hop: an edge
    to a domain is an edge to the whole of it, so the walk goes on from its
    bounded contexts too."""

    def is_shown(node):
        return node in starts or node not in hidden

    if not starts:
        return {node for node in level_graph["nodes"] if is_shown(node)}
    upstreams_of = {node: [] for node in level_graph["nodes"]}
    downstreams_of = {node: [] for node in level_graph["nodes"]}
    for edge in level_graph["edges"]:
        upstreams_of[edge["from"]].append(edge["to"])
        downstreams_of[edge["to"]].append(edge["from"])
    # A partnership or a shared kernel has no direction: it is a dependency both ways, whatever `dir` says.
    for link in level_graph["links"]:
        for one, other in ((link["a"], link["b"]), (link["b"], link["a"])):
            upstreams_of[one].append(other)
            downstreams_of[one].append(other)
    seen = set(starts)

    def expand(adjacency):
        # Each direction keeps its own account of where it has been: a link has no direction, so a box the
        # other direction reached through one is still a box this one goes on from.
        been = set(starts)
        frontier = list(starts)
        for _ in range(depth):
            next_frontier = []
            for node in frontier:
                for neighbor in adjacency.get(node, []):
                    for reached in descendants(level_graph, [neighbor]):
                        if reached not in been and is_shown(reached):
                            been.add(reached)
                            seen.add(reached)
                            next_frontier.append(reached)
            frontier = next_frontier

    if direction != "down":
        expand(upstreams_of)
    if direction != "up":
        expand(downstreams_of)
    return seen


def link_relations(data, item_id):
    """The partnerships and shared kernels of a context, or of a domain (lifted to domain level), as
    {kind: [the other ends, sorted by name]}. A kind with none is left out."""
    domains, _, _, names = index(data)
    multi = item_id in domains and not domains[item_id]["single"]
    links = level_graph(data, "domain" if multi else "context")["links"]
    found = {}
    for link in links:
        if item_id in (link["a"], link["b"]):
            found.setdefault(link["kind"], []).append(link["b"] if link["a"] == item_id else link["a"])
    return {kind: sorted(others, key=names.get) for kind, others in found.items()}


def relation_edges(data, item_id):
    """Direct dependencies of a context, or of a domain (lifted to domain level), as the edges themselves:
    (upstreams, downstreams), each sorted by the name of the one at the other end, with the roles the edge
    carries. In an upstream edge the other end is `to`, in a downstream edge it is `from`."""
    domains, _, _, names = index(data)
    if item_id in domains and not domains[item_id]["single"]:
        graph_at_level = level_graph(data, "domain")
    else:
        graph_at_level = level_graph(data, "context")
    upstreams = [edge for edge in graph_at_level["edges"] if edge["from"] == item_id]
    downstreams = [edge for edge in graph_at_level["edges"] if edge["to"] == item_id]
    return (sorted(upstreams, key=lambda edge: names[edge["to"]]),
            sorted(downstreams, key=lambda edge: names[edge["from"]]))


def relations(data, item_id):
    """Direct dependencies of a context, or of a domain (lifted to domain level)."""
    upstreams, downstreams = relation_edges(data, item_id)
    return [edge["to"] for edge in upstreams], [edge["from"] for edge in downstreams]
