"""Normalized domain model and graph walks shared by the build and the Mermaid renderer.

Two levels:
- context: nodes are bounded contexts, plus multi-context domains (for dependencies
  that point at a domain as a whole). Edges are as written in context-map.yml.
- domain: nodes are domains. Edges are lifted from contexts to their domains,
  merged, and edges inside a domain are dropped.
"""


TYPE_STYLE_KEYS = {"color", "border", "mermaid_style"}
GROUP_STYLE_KEYS = {"mermaid_style"}


def normalize(model, styles=None):
    """Turn context-map.yml and context-map.style.yml into {types, groups, domains, contexts, edges} plus a list of errors.

    `styles` is the parsed context-map.style.yml. Its `types` and `groups` are merged onto the ones in the model.
    """
    styles = styles or {}
    type_styles = styles.get("types") or {}
    group_styles = styles.get("groups") or {}
    errors = []
    domains, contexts = [], []

    for section in ("types", "domains"):
        if not (model or {}).get(section):
            errors.append(f"context-map.yml: `{section}` is missing or empty")
    if errors:
        return {"types": {}, "groups": [], "domains": [], "contexts": [], "edges": []}, errors

    types = {}
    for type_id, t in model["types"].items():
        style = type_styles.get(type_id) or {}
        for key in style:
            if key not in TYPE_STYLE_KEYS:
                errors.append(f"context-map.style.yml: types.{type_id}.{key}: unknown option. Known: {', '.join(sorted(TYPE_STYLE_KEYS))}")
        if "mermaid_style" not in style and not {"color", "border"} <= style.keys():
            errors.append(f"context-map.style.yml: types.{type_id} needs `color` and `border` (or `mermaid_style`)")
        types[type_id] = {**t, **style}
    for type_id in type_styles:
        if type_id not in model["types"]:
            errors.append(f"context-map.style.yml: types.{type_id}: unknown type, it is not in context-map.yml")

    raw_groups = model.get("groups") or {}
    if isinstance(raw_groups, list):
        errors.append("context-map.yml: `groups` is now a map keyed by group id")
        raw_groups = {}
    groups = []
    for group_id, value in raw_groups.items():
        # A group maps to its name, or to a map with `name`.
        if isinstance(value, dict):
            for key in value:
                if key != "name":
                    errors.append(f"groups.{group_id}.{key}: unknown option. Known: name")
            name = value.get("name")
        else:
            name = value
        if not name:
            errors.append(f"groups.{group_id}: needs a name")
        style = group_styles.get(group_id) or {}
        for key in style:
            if key not in GROUP_STYLE_KEYS:
                errors.append(f"context-map.style.yml: groups.{group_id}.{key}: unknown option. Known: {', '.join(sorted(GROUP_STYLE_KEYS))}")
        groups.append({"id": group_id, "name": name, "mermaid_style": style.get("mermaid_style")})
    group_ids = {g["id"] for g in groups}
    for group_id in group_styles:
        if group_id not in group_ids:
            errors.append(f"context-map.style.yml: groups.{group_id}: unknown group, it is not in context-map.yml")

    def check_group(kind, item_id, group):
        if group is not None and group not in group_ids:
            errors.append(f"{kind} '{item_id}': unknown group '{group}'")

    raw_domains = model.get("domains") or {}
    if isinstance(raw_domains, list):
        errors.append("context-map.yml: `domains` is now a map keyed by domain id")
        raw_domains = {}
    for domain_id, d in raw_domains.items():
        # A domain maps to its name and type, the group it belongs to, and its
        # bounded contexts. A context maps to its name, or to a map with
        # `name`, `type` and `group` when it overrides its domain's.
        if not isinstance(d, dict):
            errors.append(f"domains.{domain_id}: needs a map with `name` and `type`")
            continue
        for key in d:
            if key not in ("name", "type", "group", "contexts"):
                errors.append(f"domains.{domain_id}.{key}: unknown option. Known: "
                              f"{', '.join(sorted(('name', 'type', 'group', 'contexts')))}")
        dtype, group = d.get("type"), d.get("group")
        check_group("domain", domain_id, group)
        if dtype is None:
            errors.append(f"domains.{domain_id}: needs a type")
        elif dtype not in types:
            errors.append(f"domains.{domain_id}: unknown type '{dtype}'")
        if not d.get("name"):
            errors.append(f"domains.{domain_id}: needs a name")
        raw_contexts = d.get("contexts")
        if raw_contexts is not None and not isinstance(raw_contexts, dict):
            hint = "is now a map keyed by context id" if isinstance(raw_contexts, list) \
                else "must be a map from context id to name"
            errors.append(f"domains.{domain_id}.contexts: {hint}")
            raw_contexts = None
        if raw_contexts == {}:
            errors.append(f"domains.{domain_id}.contexts: is empty")
        ids = []
        for context_id, c in (raw_contexts or {}).items():
            if isinstance(c, dict):
                for key in c:
                    if key not in ("name", "type", "group"):
                        errors.append(f"domains.{domain_id}.contexts.{context_id}.{key}: unknown option. "
                                      f"Known: {', '.join(sorted(('name', 'type', 'group')))}")
                cname, ctype, cgroup = c.get("name"), c.get("type", dtype), c.get("group", group)
            else:
                cname, ctype, cgroup = c, dtype, group
            if not cname:
                errors.append(f"domains.{domain_id}.contexts.{context_id}: needs a name")
            if ctype not in types:
                errors.append(f"context '{context_id}': unknown type '{ctype}'")
            check_group("context", context_id, cgroup)
            contexts.append({
                "id": context_id, "name": cname, "type": ctype, "domain": domain_id, "group": cgroup,
            })
            ids.append(context_id)
        if ids:
            domains.append({"id": domain_id, "name": d.get("name"), "type": dtype, "group": group,
                            "contexts": ids, "single": False})
        else:
            contexts.append({"id": domain_id, "name": d.get("name"), "type": dtype, "domain": domain_id,
                             "group": group})
            domains.append({"id": domain_id, "name": d.get("name"), "type": dtype, "group": group,
                            "contexts": [domain_id], "single": True})

    seen = set()
    for item in [*contexts, *(d for d in domains if not d["single"])]:
        if item["id"] in seen:
            errors.append(f"id '{item['id']}' is used more than once")
        seen.add(item["id"])

    edges, pairs = [], set()
    if "dependencies" in model:
        errors.append("context-map.yml: `dependencies` is now `upstreams`, keyed by upstream "
                      "with a `downstreams` map")
    for upstream, entry in (model.get("upstreams") or {}).items():
        # An edge points from the downstream (the one that depends) to the upstream.
        # A downstream maps to why it depends on the upstream (the tooltip), or to
        # {comment, style} when the edge also carries a style, or to nothing at all.
        if not isinstance(entry, dict) or "downstreams" not in entry:
            errors.append(f"upstreams.{upstream}: needs a `downstreams` map")
            continue
        for key in entry:
            if key != "downstreams":
                errors.append(f"upstreams.{upstream}.{key}: unknown option. Known: downstreams")
        downstreams = entry["downstreams"]
        if not isinstance(downstreams, dict):
            errors.append(f"upstreams.{upstream}: `downstreams` must be a map from downstream to comment")
            continue
        if not downstreams:
            errors.append(f"upstreams.{upstream}: `downstreams` is empty")
            continue
        for downstream, value in downstreams.items():
            comment, style = value, "solid"
            if isinstance(value, dict):
                for key in value:
                    if key not in ("comment", "style"):
                        errors.append(f"upstreams.{upstream}.downstreams.{downstream}.{key}: "
                                      "unknown option. Known: comment, style")
                comment, style = value.get("comment"), value.get("style") or "solid"
            elif value is not None and not isinstance(value, str):
                errors.append(f"upstreams.{upstream}.downstreams.{downstream}: must be a comment "
                              "string, or a map with `comment` and `style`")
            for end in (upstream, downstream):
                if end not in seen:
                    errors.append(f"unknown domain or context '{end}' in upstreams")
            if (downstream, upstream) in pairs:
                errors.append(f"duplicate dependency {downstream} -> {upstream}")
            pairs.add((downstream, upstream))
            edges.append({"from": downstream, "to": upstream, "style": style, "comment": comment})

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
