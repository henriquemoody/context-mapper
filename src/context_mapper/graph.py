"""Normalized domain model and graph walks shared by the build and the Mermaid renderer.

Two levels:
- context: nodes are bounded contexts, plus multi-context domains (for dependencies
  that point at a domain as a whole). Edges are as written in model.yml.
- domain: nodes are domains. Edges are lifted from contexts to their domains,
  merged, and edges inside a domain are dropped.
"""


TYPE_STYLE_KEYS = {"color", "border", "mermaid_style"}
GROUP_STYLE_KEYS = {"mermaid_style"}


def normalize(model, styles=None):
    """Turn model.yml and diagrams.yml into {types, groups, domains, contexts, edges} plus a list of errors.

    `styles` is the parsed diagrams.yml. Its `types` and `groups` are merged onto the ones in the model.
    """
    styles = styles or {}
    type_styles = styles.get("types") or {}
    group_styles = styles.get("groups") or {}
    errors = []
    domains, contexts = [], []

    types = {}
    for type_id, t in model["types"].items():
        style = type_styles.get(type_id) or {}
        for key in style:
            if key not in TYPE_STYLE_KEYS:
                errors.append(f"diagrams.yml: types.{type_id}.{key}: unknown option. Known: {', '.join(sorted(TYPE_STYLE_KEYS))}")
        if "mermaid_style" not in style and not {"color", "border"} <= style.keys():
            errors.append(f"diagrams.yml: types.{type_id} needs `color` and `border` (or `mermaid_style`)")
        types[type_id] = {**t, **style}
    for type_id in type_styles:
        if type_id not in model["types"]:
            errors.append(f"diagrams.yml: types.{type_id}: unknown type, it is not in model.yml")

    groups = []
    for g in model.get("groups") or []:
        if any(g["id"] == other["id"] for other in groups):
            errors.append(f"group '{g['id']}' is used more than once")
        style = group_styles.get(g["id"]) or {}
        for key in style:
            if key not in GROUP_STYLE_KEYS:
                errors.append(f"diagrams.yml: groups.{g['id']}.{key}: unknown option. Known: {', '.join(sorted(GROUP_STYLE_KEYS))}")
        groups.append({"id": g["id"], "name": g["name"], "mermaid_style": style.get("mermaid_style")})
    group_ids = {g["id"] for g in groups}
    for group_id in group_styles:
        if group_id not in group_ids:
            errors.append(f"diagrams.yml: groups.{group_id}: unknown group, it is not in model.yml")

    def check_group(kind, item_id, group):
        if group is not None and group not in group_ids:
            errors.append(f"{kind} '{item_id}': unknown group '{group}'")

    for d in model["domains"]:
        dtype = d.get("type")
        group = d.get("group")
        check_group("domain", d["id"], group)
        if dtype not in types:
            errors.append(f"domain '{d['id']}': unknown type '{dtype}'")
        if d.get("contexts"):
            ids = []
            for c in d["contexts"]:
                ctype = c.get("type", dtype)
                if ctype not in types:
                    errors.append(f"context '{c['id']}': unknown type '{ctype}'")
                cgroup = c.get("group", group)
                check_group("context", c["id"], cgroup)
                contexts.append({
                    "id": c["id"], "name": c["name"], "type": ctype, "domain": d["id"], "group": cgroup,
                })
                ids.append(c["id"])
            domains.append({"id": d["id"], "name": d["name"], "type": dtype, "group": group,
                            "contexts": ids, "single": False})
        else:
            contexts.append({"id": d["id"], "name": d["name"], "type": dtype, "domain": d["id"],
                             "group": group})
            domains.append({"id": d["id"], "name": d["name"], "type": dtype, "group": group,
                            "contexts": [d["id"]], "single": True})

    seen = set()
    for item in [*contexts, *(d for d in domains if not d["single"])]:
        if item["id"] in seen:
            errors.append(f"id '{item['id']}' is used more than once")
        seen.add(item["id"])

    edges, pairs = [], set()
    for dep in model["dependencies"]:
        # An edge points from the downstream (the one that depends) to the upstream.
        # A downstream is an id, or {id, comment} when the dependency deserves a note.
        upstream = dep["upstream"]
        downstreams = dep["downstream"] if isinstance(dep["downstream"], list) else [dep["downstream"]]
        for item in downstreams:
            downstream, comment = (item["id"], item.get("comment")) if isinstance(item, dict) else (item, None)
            for end in (upstream, downstream):
                if end not in seen:
                    errors.append(f"unknown domain or context '{end}' in dependencies")
            if (downstream, upstream) in pairs:
                errors.append(f"duplicate dependency {downstream} -> {upstream}")
            pairs.add((downstream, upstream))
            edges.append({"from": downstream, "to": upstream, "style": dep.get("style", "solid"), "comment": comment})

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
