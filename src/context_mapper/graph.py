"""Normalized domain model and graph walks shared by the build and the Mermaid renderer.

Two levels:
- context: nodes are bounded contexts, plus multi-context domains (for dependencies
  that point at a domain as a whole). Edges are as written in context-map.yml.
- domain: nodes are domains. Edges are lifted from contexts to their domains,
  merged, and edges inside a domain are dropped.
"""


# Mermaid classDef attributes a box style may set, in `types`, `groups` and
# `domains` alike. The build checks them, so a typo fails the build instead of
# drawing nothing.
BOX_STYLE_KEYS = {"color", "fill", "fill-opacity", "font-family", "font-size",
                  "font-weight", "opacity", "stroke", "stroke-dasharray",
                  "stroke-opacity", "stroke-width"}

# What a style fills in when the entry doesn't say: readable text on a light
# box, and for a group the dashed stroke that marks it as a set, not a thing.
TEXT_DEFAULTS = {"color": "#1a1a1a"}
GROUP_DEFAULTS = {"stroke-dasharray": "4 3", "color": "#1a1a1a"}


def classdef(attrs, defaults=TEXT_DEFAULTS):
    """A Mermaid classDef string: the attributes as written, then the defaults not set."""
    items = list((attrs or {}).items())
    have = {key for key, _ in items}
    items += [(key, value) for key, value in defaults.items() if key not in have]
    return ",".join(f"{key}:{value}" for key, value in items)


def box_style(section, item_id, style, defaults, required, errors):
    """Check one box style map and return its classDef string, or None when there is nothing to draw."""
    if not style:
        return None
    if "color" in style and "border" in style:
        errors.append(f"context-map.style.yml: {section}.{item_id}: `color`+`border` are now `fill`+`stroke`")
    elif "border" in style:
        errors.append(f"context-map.style.yml: {section}.{item_id}.border: `border` is now `stroke`")
    if "mermaid_style" in style:
        errors.append(f"context-map.style.yml: {section}.{item_id}.mermaid_style: `mermaid_style` is now "
                      "written as the attributes themselves, e.g. fill: \"#fff\", stroke: \"#000\"")
    for key in style:
        if key not in BOX_STYLE_KEYS:
            errors.append(f"context-map.style.yml: {section}.{item_id}.{key}: unknown option. "
                          f"Known: {', '.join(sorted(BOX_STYLE_KEYS))}")
    if required and not {"border", "mermaid_style"} & style.keys() and not set(required) <= style.keys():
        errors.append(f"context-map.style.yml: {section}.{item_id} needs `{required[0]}` and `{required[1]}`")
    return classdef(style, defaults)


def normalize(model, styles=None):
    """Turn context-map.yml and context-map.style.yml into {types, groups, domains, contexts, edges} plus a list of errors.

    `styles` is the parsed context-map.style.yml. Its box styles (types, groups,
    domains) are keyed by the ids in context-map.yml.
    """
    styles = styles or {}
    type_styles = styles.get("types") or {}
    group_styles = styles.get("groups") or {}
    domain_styles = styles.get("domains") or {}
    errors = []
    domains, contexts, pending = [], [], []
    model = model or {}

    if model.get("groups"):
        return ({"types": {}, "groups": [], "domains": [], "contexts": [], "edges": []},
                ["context-map.yml: `groups` is now entries in `context-map`, with just a `name`, "
                 "pointed at by members' `group`"])
    for section in ("types", "context-map"):
        if not model.get(section):
            if section == "context-map" and "domains" in model:
                errors.append("context-map.yml: `domains` is now `context-map`")
            else:
                errors.append(f"context-map.yml: `{section}` is missing or empty")
    if errors:
        return {"types": {}, "groups": [], "domains": [], "contexts": [], "edges": []}, errors

    types = {}
    for type_id, t in model["types"].items():
        style = type_styles.get(type_id) or {}
        mermaid_style = box_style("types", type_id, style, TEXT_DEFAULTS, ("fill", "stroke"), errors)
        if mermaid_style is None:
            errors.append(f"context-map.style.yml: types.{type_id} needs `fill` and `stroke`")
        types[type_id] = {**t, **style, "mermaid_style": mermaid_style}
    for type_id in type_styles:
        if type_id not in model["types"]:
            errors.append(f"context-map.style.yml: types.{type_id}: unknown type, it is not in context-map.yml")

    raw_entries = model.get("context-map") or {}
    if isinstance(raw_entries, list):
        errors.append("context-map.yml: `context-map` is now a map keyed by id")
        raw_entries = {}
    if any(isinstance(e, dict) and "contexts" in e for e in raw_entries.values()):
        errors.append("context-map.yml: contexts now live next to their domains, each with a `domain:` key")

    # An entry with a `domain:` key is a bounded context of that domain; an
    # entry others' `group:` points at is a group; any other entry is a domain.
    # Every id, domain, context or group, is a key of this one map, so nothing
    # can be described twice.
    group_refs = {d.get("group") for d in raw_entries.values()
                  if isinstance(d, dict) and isinstance(d.get("group"), str)}

    def is_group(entry_id, d):
        return "domain" not in d and entry_id in group_refs and d.get("type") is None

    for entry_id in domain_styles:
        entry = raw_entries.get(entry_id)
        if not isinstance(entry, dict) or "domain" in entry:
            errors.append(f"context-map.style.yml: domains.{entry_id}: unknown domain, it is not in context-map.yml")
        elif is_group(entry_id, entry):
            errors.append(f"context-map.style.yml: domains.{entry_id}: unknown domain, it is a group")

    def check_keys(entry_id, d, allowed):
        for key in d:
            if key not in allowed:
                errors.append(f"context-map.{entry_id}.{key}: unknown option. Known: {', '.join(sorted(allowed))}")
        if not d.get("name"):
            errors.append(f"context-map.{entry_id}: needs a name")

    def check_group(kind, item_id, group):
        if group is None:
            return
        if not isinstance(group, str):
            errors.append(f"{kind} '{item_id}': `group` must be an id")
            return
        target = raw_entries.get(group)
        if not isinstance(target, dict):
            errors.append(f"{kind} '{item_id}': unknown group '{group}'")
        elif "domain" in target:
            errors.append(f"{kind} '{item_id}': unknown group '{group}', it is a bounded context")
        elif not is_group(group, target):
            errors.append(f"{kind} '{item_id}': unknown group '{group}', it is a domain")

    raw_domains, raw_contexts, raw_groups = [], [], []
    for entry_id, d in raw_entries.items():
        if not isinstance(d, dict):
            errors.append(f"context-map.{entry_id}: needs a map with `name` and `type`")
            continue
        if "domain" in d:
            check_keys(entry_id, d, ("name", "domain", "type", "group", "downstreams", "description"))
            parent = raw_entries.get(d.get("domain"))
            if not isinstance(parent, dict) or "domain" in parent:
                errors.append(f"context-map.{entry_id}: unknown domain '{d.get('domain')}'")
            elif is_group(d.get("domain"), parent):
                errors.append(f"context-map.{entry_id}: unknown domain '{d.get('domain')}', it is a group")
            raw_contexts.append((entry_id, d))
        elif is_group(entry_id, d):
            check_keys(entry_id, d, ("name",))
            raw_groups.append((entry_id, d))
        else:
            check_keys(entry_id, d, ("name", "type", "group", "downstreams", "description"))
            check_group("domain", entry_id, d.get("group"))
            if d.get("type") is None:
                errors.append(f"context-map.{entry_id}: needs a type")
            elif d.get("type") not in types:
                errors.append(f"context-map.{entry_id}: unknown type '{d.get('type')}'")
            raw_domains.append((entry_id, d))

    groups = []
    for group_id, d in raw_groups:
        style = group_styles.get(group_id) or {}
        mermaid_style = box_style("groups", group_id, style, GROUP_DEFAULTS, (), errors)
        groups.append({"id": group_id, "name": d.get("name"), "mermaid_style": mermaid_style})
    group_ids = {g["id"] for g in groups}
    for group_id in group_styles:
        if group_id in group_ids:
            continue
        entry = raw_entries.get(group_id)
        detail = ("it is a bounded context" if isinstance(entry, dict) and "domain" in entry
                  else "it is a domain" if isinstance(entry, dict)
                  else "it is not in context-map.yml")
        errors.append(f"context-map.style.yml: groups.{group_id}: unknown group, {detail}")

    for domain_id, d in raw_domains:
        dtype, group = d.get("type"), d.get("group")
        dstyle = domain_styles.get(domain_id) or {}
        mermaid_style = box_style("domains", domain_id, dstyle, TEXT_DEFAULTS, (), errors)
        if "downstreams" in d:
            pending.append((domain_id, f"context-map.{domain_id}", d["downstreams"]))
        ids = []
        for context_id, c in raw_contexts:
            if c.get("domain") != domain_id:
                continue
            cname, ctype, cgroup = c.get("name"), c.get("type", dtype), c.get("group", group)
            if ctype not in types:
                errors.append(f"context '{context_id}': unknown type '{ctype}'")
            check_group("context", context_id, cgroup)
            contexts.append({
                "id": context_id, "name": cname, "type": ctype, "domain": domain_id, "group": cgroup,
                "description": c.get("description"),
            })
            ids.append(context_id)
            if "downstreams" in c:
                pending.append((context_id, f"context-map.{context_id}", c["downstreams"]))
        if ids:
            domains.append({"id": domain_id, "name": d.get("name"), "type": dtype, "group": group,
                            "contexts": ids, "single": False, "mermaid_style": mermaid_style,
                            "description": d.get("description")})
        else:
            contexts.append({"id": domain_id, "name": d.get("name"), "type": dtype, "domain": domain_id,
                             "group": group, "description": d.get("description")})
            domains.append({"id": domain_id, "name": d.get("name"), "type": dtype, "group": group,
                            "contexts": [domain_id], "single": True, "mermaid_style": mermaid_style,
                            "description": d.get("description")})

    seen = set(raw_entries)

    edges, pairs = [], set()
    for section in ("dependencies", "upstreams"):
        if section in model:
            errors.append(f"context-map.yml: `{section}` is now `downstreams`, under the domain "
                          "or context it belongs to")
    for owner, where, raw in pending:
        # An edge points from the downstream (the one that depends) to the upstream.
        # A downstream maps to why it depends on the upstream (the tooltip), or to
        # {comment, style} when the edge also carries a style, or to nothing at all.
        if not isinstance(raw, dict):
            errors.append(f"{where}: `downstreams` must be a map from downstream to comment")
            continue
        if not raw:
            errors.append(f"{where}: `downstreams` is empty")
            continue
        for downstream, value in raw.items():
            comment, style = value, "solid"
            if isinstance(value, dict):
                for key in value:
                    if key not in ("comment", "style"):
                        errors.append(f"{where}.downstreams.{downstream}.{key}: "
                                      "unknown option. Known: comment, style")
                comment, style = value.get("comment"), value.get("style") or "solid"
            elif value is not None and not isinstance(value, str):
                errors.append(f"{where}.downstreams.{downstream}: must be a comment "
                              "string, or a map with `comment` and `style`")
            for end in (owner, downstream):
                if end in group_ids:
                    errors.append(f"a group can't be a dependency: '{end}' in {where}.downstreams")
                elif end not in seen:
                    errors.append(f"unknown domain or context '{end}' in {where}.downstreams")
            if (downstream, owner) in pairs:
                errors.append(f"duplicate dependency {downstream} -> {owner}")
            pairs.add((downstream, owner))
            edges.append({"from": downstream, "to": owner, "style": style, "comment": comment})

    data = {"types": types, "groups": groups, "domains": domains, "contexts": contexts, "edges": edges}
    if not errors:
        cycle = find_cycle(level_graph(data, "context"))
        if cycle:
            errors.append("dependency cycle: " + " -> ".join(cycle))
    return data, errors


def index(data):
    """Lookups used everywhere: id -> item, and id -> owning domain id."""
    domains = {d["id"]: d for d in data["domains"]}
    contexts = {c["id"]: c for c in data["contexts"]}
    owner = {c["id"]: c["domain"] for c in data["contexts"]}
    owner.update({d["id"]: d["id"] for d in data["domains"]})
    names = {**{d["id"]: d["name"] for d in data["domains"]}, **{c["id"]: c["name"] for c in data["contexts"]}}
    return domains, contexts, owner, names


def level_graph(data, level):
    """Return {nodes: set, edges: [{from, to, styles, via}], groups: {node: group id}} for a level."""
    domains, contexts, owner, _ = index(data)
    if level == "context":
        nodes = set(contexts) | {d for d, v in domains.items() if not v["single"]}
        member = {c: v["group"] for c, v in contexts.items() if v["group"]}
        member.update({d: v["group"] for d, v in domains.items() if not v["single"] and v["group"]})
        edges = [{"from": e["from"], "to": e["to"], "styles": {e["style"]}, "via": [e]} for e in data["edges"]]
        return {"nodes": nodes, "edges": edges, "groups": member}

    merged = {}
    for e in data["edges"]:
        a, b = owner[e["from"]], owner[e["to"]]
        if a == b:
            continue
        entry = merged.setdefault((a, b), {"from": a, "to": b, "styles": set(), "via": []})
        entry["styles"].add(e["style"])
        entry["via"].append(e)
    return {
        "nodes": set(domains),
        "edges": list(merged.values()),
        "groups": {d: v["group"] for d, v in domains.items() if v["group"]},
    }


def find_cycle(graph):
    out = {n: [] for n in graph["nodes"]}
    for e in graph["edges"]:
        out[e["from"]].append(e["to"])
    state, stack = {}, []

    def visit(node):
        state[node] = "open"
        stack.append(node)
        for nxt in out[node]:
            if state.get(nxt) == "open":
                return stack[stack.index(nxt):] + [nxt]
            if nxt not in state:
                found = visit(nxt)
                if found:
                    return found
        stack.pop()
        state[node] = "done"
        return None

    for node in sorted(graph["nodes"]):
        if node not in state:
            found = visit(node)
            if found:
                return found
    return None


def focus_set(data, level, focus):
    """The node ids a focus starts from at a level. A domain focus at context level includes its contexts."""
    if not focus:
        return set()
    domains, _, owner, _ = index(data)
    if level == "domain":
        return {owner[focus]}
    if focus in domains and not domains[focus]["single"]:
        return {focus, *domains[focus]["contexts"]}
    return {focus}


def walk(graph, starts, depth, direction, hidden_groups):
    """Nodes reachable from `starts` within `depth` hops. Without starts, every node.
    Members of `hidden_groups` are skipped, unless they are a start."""
    allowed = lambda n: n in starts or graph["groups"].get(n) not in hidden_groups
    if not starts:
        return {n for n in graph["nodes"] if allowed(n)}
    up = {n: [] for n in graph["nodes"]}
    down = {n: [] for n in graph["nodes"]}
    for e in graph["edges"]:
        up[e["from"]].append(e["to"])
        down[e["to"]].append(e["from"])
    seen = set(starts)

    def go(nxt):
        frontier = list(starts)
        for _ in range(depth):
            new = []
            for n in frontier:
                for m in nxt[n]:
                    if m not in seen and allowed(m):
                        seen.add(m)
                        new.append(m)
            frontier = new

    if direction != "down":
        go(up)
    if direction != "up":
        go(down)
    return seen


def relations(data, item_id):
    """Direct dependencies of a context, or of a domain (lifted to domain level)."""
    domains, _, _, names = index(data)
    if item_id in domains and not domains[item_id]["single"]:
        g = level_graph(data, "domain")
    else:
        g = level_graph(data, "context")
    ups = [e["to"] for e in g["edges"] if e["from"] == item_id]
    downs = [e["from"] for e in g["edges"] if e["to"] == item_id]
    key = lambda i: names[i]
    return sorted(ups, key=key), sorted(downs, key=key)
