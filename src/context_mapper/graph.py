"""Normalized domain model and graph walks shared by the build and the Mermaid renderer.

Two levels:
- context: nodes are bounded contexts, plus multi-context domains (for dependencies
  that point at a domain as a whole). Edges are as written in context-map.yml.
- domain: nodes are domains. Edges are lifted from contexts to their domains,
  merged, and edges inside a domain are dropped.

Three kinds of thing, in three sections: `types` is the role vocabulary of the
model (a domain or bounded context has one, and it colors the box), `clusters`
names a set of domains or contexts treated together (members point at one with
`cluster:`), and `context-map` maps each id to what it is. A cluster holds
members; a domain holds bounded contexts; neither can be depended on or hold the
other's children. How either first renders comes from `defaultDisplay` in the
style file: expanded, collapsed, contents or hidden. No type name is special.
"""


# Mermaid classDef attributes a box style may set, in `types`, `clusters` and
# `context-map` alike. The build checks them, so a typo fails the build instead
# of drawing nothing.
BOX_STYLE_KEYS = {"color", "fill", "fill-opacity", "font-family", "font-size",
                  "font-weight", "opacity", "stroke", "stroke-dasharray",
                  "stroke-opacity", "stroke-width"}

# How a container first renders. expanded: the box and the boxes inside it.
# collapsed: the box alone, the inside hidden. contents: the inside alone, the
# box hidden. hidden: neither.
DISPLAY_STATES = ("expanded", "collapsed", "contents", "hidden")

# What a style fills in when the entry doesn't say: readable text on a light box.
TEXT_DEFAULTS = {"color": "#1a1a1a"}


def classdef(attrs, defaults=TEXT_DEFAULTS):
    """A Mermaid classDef string: the attributes as written, then the defaults not set."""
    items = list((attrs or {}).items())
    have = {key for key, _ in items}
    items += [(key, value) for key, value in defaults.items() if key not in have]
    return ",".join(f"{key}:{value}" for key, value in items)


def box_style(section, item_id, style, defaults, required, errors, allowed=None):
    """Check one box style map and return its classDef string, or None when there is nothing to draw."""
    if not style:
        return None
    allowed = allowed or BOX_STYLE_KEYS
    if "collapsible" in style:
        errors.append(f"context-map.style.yml: {section}.{item_id}.collapsible: "
                      "`collapsible` is now `defaultDisplay: collapsed`, on the entry")
    if section == "types" and "defaultDisplay" in style:
        errors.append(f"context-map.style.yml: {section}.{item_id}.defaultDisplay: "
                      "`defaultDisplay` is now set per entry, under `context-map:` or `clusters:`")
    if "color" in style and "border" in style:
        errors.append(f"context-map.style.yml: {section}.{item_id}: `color`+`border` are now `fill`+`stroke`")
    elif "border" in style:
        errors.append(f"context-map.style.yml: {section}.{item_id}.border: `border` is now `stroke`")
    if "mermaid_style" in style:
        errors.append(f"context-map.style.yml: {section}.{item_id}.mermaid_style: `mermaid_style` is now "
                      "written as the attributes themselves, e.g. fill: \"#fff\", stroke: \"#000\"")
    if "defaultDisplay" in style and style["defaultDisplay"] not in DISPLAY_STATES:
        errors.append(f"context-map.style.yml: {section}.{item_id}.defaultDisplay must be one of "
                      f"{', '.join(DISPLAY_STATES)}")
    for key in style:
        if key not in allowed:
            errors.append(f"context-map.style.yml: {section}.{item_id}.{key}: unknown option. "
                          f"Known: {', '.join(sorted(allowed))}")
    if required and not {"border", "mermaid_style"} & style.keys() and not set(required) <= style.keys():
        errors.append(f"context-map.style.yml: {section}.{item_id} needs `{required[0]}` and `{required[1]}`")
    attrs = {key: value for key, value in style.items() if key in BOX_STYLE_KEYS}
    return classdef(attrs, defaults) if attrs else None


def normalize(model, styles=None):
    """Turn context-map.yml and context-map.style.yml into {types, clusters, domains, contexts, edges}
    plus a list of errors.

    `styles` is the parsed context-map.style.yml. Its sections mirror the model's —
    `types`, `clusters`, `context-map` — keyed by the same ids.
    """
    styles = styles or {}
    type_styles = styles.get("types") or {}
    cluster_styles = styles.get("clusters") or {}
    entry_styles = styles.get("context-map") or {}
    errors = []
    domains, contexts, pending = [], [], []
    model = model or {}

    if model.get("groups"):
        return ({"types": {}, "clusters": [], "domains": [], "contexts": [], "edges": []},
                ["context-map.yml: `groups` is now `clusters`, with just a `name`, "
                 "pointed at by members' `cluster`"])
    for section in ("types", "context-map"):
        if not model.get(section):
            if section == "context-map" and "domains" in model:
                errors.append("context-map.yml: `domains` is now `context-map`")
            else:
                errors.append(f"context-map.yml: `{section}` is missing or empty")
    if errors:
        return {"types": {}, "clusters": [], "domains": [], "contexts": [], "edges": []}, errors

    types = {}
    for type_id, t in model["types"].items():
        if not isinstance(t, dict):
            errors.append(f"context-map.yml: types.{type_id}: needs a map with `name`")
            continue
        for key in t:
            if key == "label":
                errors.append(f"context-map.yml: types.{type_id}.label: `label` is now `name`")
            elif key != "name":
                errors.append(f"context-map.yml: types.{type_id}.{key}: unknown option. Known: name")
        style = type_styles.get(type_id) or {}
        mermaid_style = box_style("types", type_id, style, TEXT_DEFAULTS, ("fill", "stroke"), errors)
        if mermaid_style is None:
            errors.append(f"context-map.style.yml: types.{type_id} needs `fill` and `stroke`")
        types[type_id] = {**t, **style, "mermaid_style": mermaid_style}
    for type_id in type_styles:
        if type_id not in model["types"]:
            errors.append(f"context-map.style.yml: types.{type_id}: unknown type, it is not in context-map.yml")

    # A cluster names a set of domains or contexts treated together. It holds
    # members, never bounded contexts, and nothing can depend on it.
    raw_entries = model.get("context-map") or {}
    if isinstance(raw_entries, list):
        errors.append("context-map.yml: `context-map` is now a map keyed by id")
        raw_entries = {}
    if any(isinstance(e, dict) and "contexts" in e for e in raw_entries.values()):
        errors.append("context-map.yml: contexts now live next to their domains, each with a `domain:` key")

    raw_clusters = model.get("clusters") or {}
    if isinstance(raw_clusters, list):
        errors.append("context-map.yml: `clusters` is now a map keyed by cluster id")
        raw_clusters = {}
    cluster_ids = set(raw_clusters)
    for cluster_id, c in raw_clusters.items():
        if not isinstance(c, dict):
            errors.append(f"context-map.yml: clusters.{cluster_id}: needs a map with `name`")
            continue
        for key in c:
            if key != "name":
                errors.append(f"context-map.yml: clusters.{cluster_id}.{key}: unknown option. Known: name")
        if not c.get("name"):
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

    def check_keys(entry_id, d, allowed):
        for key in d:
            if key not in allowed:
                errors.append(f"context-map.{entry_id}.{key}: unknown option. Known: {', '.join(sorted(allowed))}")
        if not d.get("name"):
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
    for entry_id, d in raw_entries.items():
        if not isinstance(d, dict):
            errors.append(f"context-map.{entry_id}: needs a map with `name` and `type`")
            continue
        if "group" in d:
            errors.append(f"context-map.{entry_id}.group: `group` is now `cluster`")
        if "domain" in d:
            check_keys(entry_id, d, ("name", "domain", "type", "cluster", "downstreams", "description"))
            if d.get("cluster") is not None:
                errors.append(f"context-map.{entry_id}: a bounded context is inside its domain "
                              "already, it can't also be in a cluster")
            parent = raw_entries.get(d.get("domain"))
            if not isinstance(parent, dict) or "domain" in parent:
                errors.append(f"context-map.{entry_id}: unknown domain '{d.get('domain')}'")
            raw_contexts.append((entry_id, d))
        else:
            check_keys(entry_id, d, ("name", "type", "cluster", "downstreams", "description"))
            check_cluster(entry_id, d.get("cluster"))
            if d.get("cluster") is not None:
                member_of[entry_id] = d["cluster"]
            if d.get("type") is None:
                errors.append(f"context-map.{entry_id}: needs a type")
            elif d.get("type") not in types:
                errors.append(f"context-map.{entry_id}: unknown type '{d.get('type')}'")
            raw_domains.append((entry_id, d))

    for domain_id, d in raw_domains:
        dtype, cluster = d.get("type"), d.get("cluster")
        dstyle = entry_styles.get(domain_id) or {}
        mermaid_style = box_style("context-map", domain_id, dstyle, TEXT_DEFAULTS, (), errors,
                                  allowed=BOX_STYLE_KEYS | {"defaultDisplay"})
        if "downstreams" in d:
            pending.append((domain_id, f"context-map.{domain_id}", d["downstreams"]))
        ids = []
        for context_id, c in raw_contexts:
            if c.get("domain") != domain_id:
                continue
            cname, ctype = c.get("name"), c.get("type", dtype)
            if ctype not in types:
                errors.append(f"context '{context_id}': unknown type '{ctype}'")
            contexts.append({"id": context_id, "name": cname, "type": ctype, "domain": domain_id,
                             "description": c.get("description")})
            ids.append(context_id)
            if "downstreams" in c:
                pending.append((context_id, f"context-map.{context_id}", c["downstreams"]))
        domains.append({"id": domain_id, "name": d.get("name"), "type": dtype, "cluster": cluster,
                        "contexts": ids, "single": not ids,
                        "mermaid_style": mermaid_style, "defaultDisplay": dstyle.get("defaultDisplay"),
                        "description": d.get("description")})
        if not ids:
            contexts.append({"id": domain_id, "name": d.get("name"), "type": dtype, "domain": domain_id,
                             "description": d.get("description")})

    clusters = []
    for cluster_id, c in raw_clusters.items():
        style = cluster_styles.get(cluster_id) or {}
        mermaid_style = box_style("clusters", cluster_id, style, TEXT_DEFAULTS, (), errors,
                                  allowed=BOX_STYLE_KEYS | {"defaultDisplay"})
        members = [m for m, cl in member_of.items() if cl == cluster_id]
        if isinstance(c, dict) and not members and not errors:
            errors.append(f"context-map.yml: clusters.{cluster_id}: no entry points at it with `cluster:`")
        clusters.append({"id": cluster_id, "name": c.get("name") if isinstance(c, dict) else None,
                         "members": members, "mermaid_style": mermaid_style,
                         "defaultDisplay": style.get("defaultDisplay")})

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
                if end not in seen:
                    errors.append(f"unknown domain or context '{end}' in {where}.downstreams")
            if (downstream, owner) in pairs:
                errors.append(f"duplicate dependency {downstream} -> {owner}")
            pairs.add((downstream, owner))
            edges.append({"from": downstream, "to": owner, "style": style, "comment": comment})

    data = {"types": types, "clusters": clusters, "domains": domains, "contexts": contexts, "edges": edges}
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
    """Return {nodes: set, edges: [...], child_of: {node: container id}} for a level.

    `child_of` says which container a node renders inside: a bounded context
    inside its domain, a member inside its cluster."""
    domains, contexts, owner, _ = index(data)
    child_of = {d["id"]: d["cluster"] for d in data["domains"] if d["cluster"]}
    if level == "context":
        nodes = set(contexts) | {d for d, v in domains.items() if not v["single"]}
        child_of.update({c: v["domain"] for c, v in contexts.items()
                         if not domains[v["domain"]]["single"]})
        edges = [{"from": e["from"], "to": e["to"], "styles": {e["style"]}, "via": [e]} for e in data["edges"]]
        return {"nodes": nodes, "edges": edges, "child_of": child_of}

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
        "child_of": child_of,
    }


def descendants(graph, ids):
    """Each id and everything rendered inside it, at this level."""
    kids = {}
    for child, parent in graph["child_of"].items():
        kids.setdefault(parent, []).append(child)
    out, stack = set(), list(ids)
    while stack:
        node = stack.pop()
        if node in out:
            continue
        out.add(node)
        stack += kids.get(node, [])
    return out


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
    """The node ids a focus starts from at a level. A domain focus opens it: its
    bounded contexts are starts too. A cluster focus opens it: its members —
    and their bounded contexts there — are starts too."""
    if not focus:
        return set()
    domains, _, owner, _ = index(data)
    clusters = {c["id"]: c for c in data["clusters"]}
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


def walk(graph, starts, depth, direction, hidden):
    """Nodes reachable from `starts` within `depth` hops. Without starts, every node.
    `hidden` holds what isn't shown: a hidden container and everything inside it.
    A start is always shown; one that isn't a node, like a cluster, only marks
    itself."""
    allowed = lambda n: n in starts or n not in hidden
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
                for m in nxt.get(n, []):
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
