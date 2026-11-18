"""Render the domain model as Mermaid flowcharts.

The `mermaid` section of context-map.style.yml controls how diagrams look. See the comments
there and the README for every option. build.py calls `build(data, config, out)`.
"""
import html
import json
import re
import textwrap
from pathlib import Path

from . import graph

VIEW_DEFAULTS = {
    "level": "context",
    "depth": 1,
    "dir": "both",
    "display": None,
    "hide": [],
    "child_labels": True,
    "group_by_type": False,
}

TOP_DEFAULTS = {
    "direction": "BT",
    "theme": "base",
    "layout": "dagre",
    "look": "classic",
    "curve": "basis",
    "theme_variables": {},
    "config": {},
    "markdown_config": {},
    "defaults": {},
    "focus_style": {"stroke-width": "4px", "font-weight": "bold"},
    "domain_style": {"fill": "#ffffff", "stroke": "#b0b0b0"},
    "edge_styles": {},
    "pages": "all",
    "views": [],
}

VIEW_ONLY = {"id", "title", "focus", "description", "direction"}

# The kinds of edge `edge_styles` can style: a plain one, and `style: dotted` on a downstream.
EDGE_KINDS = ("solid", "dotted")

ALLOWED = {
    "direction": {"TB", "BT", "LR", "RL"},
    "layout": {"dagre", "elk"},
    "look": {"classic", "handDrawn"},
    "curve": {"basis", "bumpX", "bumpY", "cardinal", "catmullRom", "linear", "monotoneX",
              "monotoneY", "natural", "step", "stepAfter", "stepBefore"},
    "level": {"context", "domain"},
    "dir": {"both", "up", "down"},
    "display": set(graph.DISPLAY_STATES),
}


def settings(config):
    """Fill in defaults and check every key and value. Returns (settings, errors)."""
    config = config or {}
    errors = []
    for key in config:
        if key not in TOP_DEFAULTS:
            errors.append(f"mermaid.{key}: unknown option. Known: {', '.join(sorted(TOP_DEFAULTS))}")
    cfg = {**TOP_DEFAULTS, **config}
    cfg["defaults"] = {**VIEW_DEFAULTS, **(cfg.get("defaults") or {})}

    for key in ("direction", "layout", "look", "curve"):
        if cfg[key] not in ALLOWED[key]:
            errors.append(f"mermaid.{key} must be one of: {', '.join(sorted(ALLOWED[key]))}")

    for key in cfg["defaults"]:
        if key not in VIEW_DEFAULTS:
            errors.append(f"mermaid.defaults.{key}: unknown option. Known: {', '.join(sorted(VIEW_DEFAULTS))}")
    for view in [cfg["defaults"], *cfg["views"]]:
        where = "defaults" if view is cfg["defaults"] else f"views.{view.get('id', '?')}"
        if view is not cfg["defaults"]:
            if "id" not in view:
                errors.append("mermaid.views: every view needs an id")
            for key in view:
                if key not in VIEW_DEFAULTS and key not in VIEW_ONLY:
                    errors.append(f"mermaid.{where}.{key}: unknown option. Known: "
                                  f"{', '.join(sorted({*VIEW_DEFAULTS, *VIEW_ONLY}))}")
        for key in ("level", "dir", "direction"):
            if key in view and view[key] not in ALLOWED[key]:
                errors.append(f"mermaid.{where}.{key} must be one of {', '.join(sorted(ALLOWED[key]))}")
        display = view.get("display")
        for mode in (display.values() if isinstance(display, dict) else [display]):
            if mode is not None and mode not in ALLOWED["display"]:
                errors.append(f"mermaid.{where}.display must be one of {', '.join(sorted(ALLOWED['display']))}, "
                              "or a map from domain id to one of those")
        hide = view.get("hide")
        if hide is not None and not isinstance(hide, list):
            errors.append(f"mermaid.{where}.hide must be a list of ids, such as `hide: [crm]`")

    # Styles are written like the ones in `types`, `clusters` and `context-map`: a map of
    # Mermaid attributes. Past this point they are classDef strings, which is what the
    # renderers (here and in the page's script) put straight into the diagram.
    for key in ("focus_style", "domain_style"):
        cfg[key] = attribute_string(f"mermaid.{key}", cfg[key], errors)
    edge_styles = cfg["edge_styles"]
    if isinstance(edge_styles, dict):
        for kind in edge_styles:
            if kind not in EDGE_KINDS:
                errors.append(f"mermaid.edge_styles.{kind}: unknown option. Known: {', '.join(EDGE_KINDS)}")
        cfg["edge_styles"] = {kind: attribute_string(f"mermaid.edge_styles.{kind}", attrs, errors)
                              for kind, attrs in edge_styles.items()}
    else:
        errors.append("mermaid.edge_styles must be a map from solid or dotted to Mermaid attributes")
        cfg["edge_styles"] = {}
    return cfg, errors


def attribute_string(where, attrs, errors):
    """Check a map of Mermaid style attributes and return it as a classDef string."""
    if not isinstance(attrs, dict):
        errors.append(f"{where} must be a map of Mermaid attributes, "
                      "such as `stroke: \"#313131\"`")
        return ""
    for key in attrs:
        if key not in graph.BOX_STYLE_KEYS:
            errors.append(f"{where}.{key}: unknown option. Known: {', '.join(sorted(graph.BOX_STYLE_KEYS))}")
    return graph.classdef({key: value for key, value in attrs.items() if key in graph.BOX_STYLE_KEYS}, {})


def display_mode(view, domain):
    """How a container first renders: the view's `display`, else the domain's
    own `defaultDisplay` from the style file, else expanded."""
    display = view["display"]
    mode = display.get(domain["id"]) if isinstance(display, dict) else display
    return mode or domain.get("defaultDisplay") or "expanded"


def deep_merge(base, extra):
    out = dict(base)
    for key, value in (extra or {}).items():
        out[key] = deep_merge(out[key], value) if isinstance(value, dict) and isinstance(out.get(key), dict) else value
    return out


def mermaid_config(cfg, markdown=False):
    base = {
        "theme": cfg["theme"],
        "layout": cfg["layout"],
        "look": cfg["look"],
        "flowchart": {"curve": cfg["curve"], "htmlLabels": True},
        "themeVariables": cfg["theme_variables"],
    }
    merged = deep_merge(base, cfg["config"])
    return deep_merge(merged, cfg["markdown_config"]) if markdown else merged


def uses_elk(cfg):
    return str(mermaid_config(cfg).get("layout", "")).startswith("elk")


def client_settings(cfg):
    """The parts of the Mermaid settings the interactive page needs to draw the same diagrams."""
    client_config = mermaid_config(cfg)
    defaults = cfg["defaults"]
    return {
        "config": client_config,
        "elk": uses_elk(cfg),
        "direction": cfg["direction"],
        "curve": client_config["flowchart"].get("curve", cfg["curve"]),
        "focus_style": cfg["focus_style"],
        "domain_style": cfg["domain_style"],
        "edge_styles": cfg["edge_styles"],
        "display": defaults["display"],
        "hide": defaults["hide"],
        "child_labels": defaults["child_labels"],
        "group_by_type": defaults["group_by_type"],
    }


def node_id(item_id):
    return re.sub(r"\W", "_", item_id)


def text(value):
    return value.replace('"', "#quot;")


def render(data, cfg, view, links=None, markdown=False):
    """Return Mermaid source for one view. `links` maps an id to a URL for click handlers.
    With `markdown`, `markdown_config` is merged in, for renderers like GitLab's that lack ELK."""
    domains, contexts, owner, names = graph.index(data)
    types = data["types"]
    level = view["level"]
    level_graph = graph.level_graph(data, level)
    starts = graph.focus_set(data, level, view.get("focus"))

    # A container is a domain that holds bounded contexts, or a cluster that
    # holds members. Its display comes from the view, its own `defaultDisplay`,
    # or expanded; a focused domain opens up.
    containers = {domain["id"]: domain for domain in data["domains"] if not domain["single"]}
    containers.update({cluster["id"]: cluster for cluster in data["clusters"]})
    display_states = {container_id: ("expanded" if container_id in starts else display_mode(view, containers[container_id]))
                      for container_id in containers}

    # `hide` names what this view never draws: a domain or cluster goes with
    # everything inside it, a bounded context with just its own box. A bounded
    # context — a single domain is one too — with `defaultDisplay: hidden` in
    # the style file hides the same way, everywhere but as the focus. The focus
    # itself is never hidden — a page still shows what it is a page of.
    hidden = graph.descendants(level_graph,
                               {container_id for container_id, mode in display_states.items() if mode == "hidden"}
                               | {context["id"] for context in data["contexts"]
                                  if context.get("defaultDisplay") == "hidden"}
                               | set(view.get("hide") or []))
    if view.get("focus"):
        starts = (starts - hidden) | {view["focus"]}
        if level == "domain" and view["focus"] in owner:
            starts.add(owner[view["focus"]])
    visible = graph.walk(level_graph, starts, view["depth"], view["dir"], hidden)

    # What a container holds at this level, and what folded into a collapsed one.
    kids_of = {}
    for child, parent in level_graph["child_of"].items():
        kids_of.setdefault(parent, []).append(child)

    def held(container):
        """A container's children that are nodes at this level: a domain holds
        bounded contexts there, a cluster holds members anywhere."""
        inside = [child_id for child_id in container.get("contexts", []) if child_id != container["id"]] if level == "context" else []
        return inside + [member for member in container.get("members", []) if member != container["id"]]

    folded = {}  # node -> the collapsed container it folded into

    def fold(container_id, into_id):
        for child in kids_of.get(container_id, []):
            if child in starts:
                continue
            if child in visible:
                folded[child] = into_id
            fold(child, into_id)

    def collapsed_ancestor(container_id):
        parent = level_graph["child_of"].get(container_id)
        while parent:
            if display_states.get(parent) == "collapsed":
                return True
            parent = level_graph["child_of"].get(parent)
        return False

    for container_id, mode in display_states.items():
        if mode == "collapsed" and not collapsed_ancestor(container_id):
            fold(container_id, container_id)

    config_json = json.dumps({"config": mermaid_config(cfg, markdown)})
    lines = ["---", config_json, "---", f"flowchart {view.get('direction', cfg['direction'])}"]
    for type_id, type_entry in types.items():
        lines.append(f"  classDef {type_id} {type_entry['mermaid_style']}")
    lines.append(f"  classDef focus {cfg['focus_style']}")

    plain_nodes = []  # ids drawn as plain boxes, for focus and click lines
    drawn = set()     # ids drawn at all: a box, or a wrapper around others

    def box(item_id, label, type_id, indent):
        plain_nodes.append(item_id)
        drawn.add(item_id)
        cls = f":::{type_id}" if type_id else ""
        return f'{indent}{node_id(item_id)}["{label}"]{cls}'

    def draw_child(child_id, indent):
        """One child of a container. A single bounded context is in both payloads;
        the domain entry carries its style, so it wins."""
        if child_id in contexts and child_id not in domains:
            lines = [box(child_id, text(contexts[child_id]["name"]), contexts[child_id]["type"], indent)]
            if contexts[child_id].get("mermaid_style"):
                lines.append(f"{indent}style {node_id(child_id)} {contexts[child_id]['mermaid_style']}")
            return lines
        return draw_entry(domains[child_id], indent)

    def draw_entry(container, indent):
        """Lines for one container: a plain box, a wrapper with the boxes inside it,
        the boxes inside it without a wrapper of its own, or nothing."""
        container_id = container["id"]
        if container_id in folded or (container_id in hidden and container_id != view.get("focus")):
            return []
        mode = display_states.get(container_id, "expanded")
        if mode == "hidden":
            return []
        is_cluster = container_id not in domains
        kids = held(container)
        folded_kids = [child_id for child_id in kids if folded.get(child_id) == container_id]
        inside = [child_id for child_id in kids if child_id in visible and child_id not in folded]
        if is_cluster:
            # A cluster isn't a node in the walk: it draws only through what it holds.
            # The focus is the exception: with everything it holds hidden, it is
            # still one box of its own.
            if mode == "collapsed" and not folded_kids:
                return []
            if mode == "expanded" and not inside and container_id != view.get("focus"):
                return []
        elif container_id not in visible and not folded_kids and not inside \
                and not any(child_id in starts for child_id in kids):
            # Not reached itself, holds nothing that was reached, and no start
            # either. A domain that holds one of those — the focus of a
            # bounded-context view, or a context reached on its own — still
            # draws, so it has a box to appear in.
            return []
        if mode == "contents":
            return [line for child_id in inside for line in draw_child(child_id, indent)]
        if mode == "expanded" and kids:
            if not inside:
                # Nothing inside was reached: show what is there that isn't
                # hidden. A start is never hidden, not even by `hide`.
                inside = [child_id for child_id in kids
                          if child_id not in folded and (child_id not in hidden or child_id in starts)]
            if inside:
                entry_lines = [f'{indent}subgraph {node_id(container_id)}["{text(container["name"])}"]']
                for child_id in inside:
                    entry_lines += draw_child(child_id, indent + "  ")
                entry_lines.append(f"{indent}end")
                drawn.add(container_id)
                style = container.get("mermaid_style") or cfg["domain_style"]
                if container_id == view.get("focus"):
                    style += "," + cfg["focus_style"]
                entry_lines.append(f"{indent}style {node_id(container_id)} {style}")
                return entry_lines
        # A plain box: the container alone. With `child_labels`, it names what it holds.
        label = text(container["name"])
        if view["child_labels"] and not container.get("single", False):
            named = sorted(names[child_id] for child_id in container.get("contexts", [])
                           if child_id != container_id and child_id not in hidden)
            named += sorted(names[member] for member in container.get("members", []) if folded.get(member) == container_id)
            if named:
                label = f"<b>{label}</b><br/>{text(', '.join(named))}"
        entry_lines = [box(container_id, label, container.get("type"), indent)]
        if container.get("mermaid_style"):
            entry_lines.append(f"{indent}style {node_id(container_id)} {container['mermaid_style']}")
        return entry_lines

    # A domain drawn inside another container comes from that container's own drawing.
    opens = {container_id for container_id, mode in display_states.items()
             if mode in ("expanded", "contents") and container_id not in folded and container_id not in hidden
             and (container_id not in domains or container_id in visible)}

    def at_top(container):
        return level_graph["child_of"].get(container["id"]) not in opens

    if view["group_by_type"]:
        for type_id, type_entry in types.items():
            block = [line for domain in data["domains"] if domain["type"] == type_id and at_top(domain)
                     for line in draw_entry(domain, "    ")]
            if block:
                lines += [f'  subgraph type_{type_id}["{text(type_entry["name"])}"]', *block, "  end"]
    else:
        for domain in data["domains"]:
            if at_top(domain):
                lines += draw_entry(domain, "  ")
        for cluster in data["clusters"]:
            lines += draw_entry(cluster, "  ")

    # Merge edges that land on the same pair once containers are collapsed.
    def folded_target(node):
        return folded.get(node, node)

    folded_boxes = set(folded.values())
    merged = {}
    for edge in level_graph["edges"]:
        if edge["from"] not in visible or edge["to"] not in visible:
            continue
        from_id, to_id = folded_target(edge["from"]), folded_target(edge["to"])
        if from_id == to_id or from_id not in drawn or to_id not in drawn:
            continue
        entry = merged.setdefault((from_id, to_id), {"styles": set(), "names": set()})
        entry["styles"] |= edge["styles"]
        if to_id in folded_boxes:
            entry["names"].add(names[edge["to"]])
        elif from_id in folded_boxes:
            entry["names"].add(names[edge["from"]])

    by_style = {}
    for edge_index, ((from_id, to_id), entry) in enumerate(merged.items()):
        edge_style = "solid" if "solid" in entry["styles"] else sorted(entry["styles"])[0]
        arrow = "-.->" if edge_style == "dotted" else "-->"
        label = ""
        if entry["names"] and view["child_labels"]:
            label = f'|"{text(", ".join(sorted(entry["names"])))}"|'
        lines.append(f"  {node_id(from_id)} {arrow}{label} {node_id(to_id)}")
        by_style.setdefault(edge_style, []).append(str(edge_index))

    # `interpolate` sets the curve per edge, which works even where the config is ignored.
    for edge_style, edge_indexes in by_style.items():
        extra = cfg["edge_styles"].get(edge_style, "")
        curve = mermaid_config(cfg, markdown)["flowchart"].get("curve", cfg["curve"])
        lines.append(f"  linkStyle {','.join(edge_indexes)} interpolate {curve} {extra}".rstrip())

    # Highlight only the focused item itself: a domain focus marks the domain box, not each context.
    highlight = owner[view["focus"]] if level == "domain" and view.get("focus") in owner else view.get("focus")
    for node in plain_nodes:
        if node == highlight:
            lines.append(f"  class {node_id(node)} focus")
    if links:
        for node in plain_nodes:
            if node in links:
                lines.append(f'  click {node_id(node)} href "{links[node]}"')

    return "\n".join(lines) + "\n"


def page_items(data, cfg):
    """Ids that get their own page."""
    domains, contexts, _, _ = graph.index(data)
    multi_context_domain_ids = [domain["id"] for domain in data["domains"] if not domain["single"]]
    pages = cfg["pages"]
    if pages == "all":
        return multi_context_domain_ids + [context["id"] for context in data["contexts"]]
    if pages == "domains":
        return [domain["id"] for domain in data["domains"]]
    if pages == "contexts":
        return [context["id"] for context in data["contexts"]]
    return list(pages or [])


def views(data, cfg):
    """All views to generate: named views first, then one page per item."""
    domains, _, _, names = graph.index(data)
    all_views = [{**cfg["defaults"], **view} for view in cfg["views"]]
    for item_id in page_items(data, cfg):
        is_domain = item_id in domains and not domains[item_id]["single"]
        title = f"{names[item_id]} (domain)" if is_domain else names[item_id]
        all_views.append({**cfg["defaults"], "id": item_id, "title": title, "focus": item_id, "page": True})
    return all_views


def check(data, cfg):
    errors = []
    _, _, _, names = graph.index(data)
    pages = cfg["pages"]
    if not (pages in ("all", "domains", "contexts") or isinstance(pages, list)):
        errors.append("mermaid.pages must be all, domains, contexts, or a list of ids")
    elif isinstance(pages, list):
        errors += [f"mermaid.pages: unknown id '{item_id}'" for item_id in pages if item_id not in names]
    seen = set()
    focusable = set(names) | {cluster["id"] for cluster in data["clusters"]}
    for view in views(data, cfg) if not errors else []:
        if view["id"] in seen:
            errors.append(f"mermaid view id '{view['id']}' is used twice (pages use the domain or context id)")
        seen.add(view["id"])
        if view.get("focus") and view["focus"] not in focusable:
            errors.append(f"mermaid view '{view['id']}': unknown focus '{view['focus']}'")
    container_ids = ({domain["id"] for domain in data["domains"] if not domain["single"]}
                     | {cluster["id"] for cluster in data["clusters"]})
    for where, view in [("defaults", cfg["defaults"]), *((f"views.{view['id']}", view) for view in cfg["views"])]:
        if isinstance(view.get("display"), dict):
            errors += [f"mermaid.{where}.display: unknown container '{item_id}'" for item_id in view["display"] if item_id not in container_ids]
        errors += [f"mermaid.{where}.hide: unknown id '{item_id}'" for item_id in (view.get("hide") or [])
                   if item_id not in names and item_id not in {cluster["id"] for cluster in data["clusters"]}]
    return errors


# The download script is shared with the interactive page: build.py splices it
# into app.js, here it goes into every static diagram page's script.
DOWNLOAD_JS = (Path(__file__).parent / "template" / "download.js").read_text().strip()

PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} - Context Map</title>
<style>
  body {{ margin: 0; padding: 16px 24px; font: 15px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; color: #1a1a1a; background: #fff; }}
  a {{ color: #305bab; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  nav {{ display: flex; gap: 16px; font-size: 14px; }}
  h1 {{ font-size: 24px; margin: 12px 0 4px; }}
  h3 {{ margin-bottom: 4px; }}
  .hint {{ color: #595959; margin: 0 0 16px; }}
  #diagram {{ overflow: auto; border: 1px solid #e7e7e7; border-radius: 8px; padding: 16px; }}
  #diagram svg {{ max-width: 100%; height: auto; }}
  #diagram a, #diagram a *, #diagram .clickable, #diagram .clickable * {{ cursor: pointer; }}
  ul {{ padding-left: 18px; margin-top: 4px; }}
  .cols {{ display: flex; flex-wrap: wrap; gap: 8px 48px; }}
  details {{ margin-top: 16px; }}
  pre {{ background: #f7f7f7; padding: 12px; overflow: auto; }}
</style>
</head>
<body>
<nav><a href="index.html">All diagrams</a><a href="../{interactive}">Interactive view</a></nav>
<main>
<h1>{title}</h1>
{about}<p class="hint">{description}</p>
{body}
</main>
</body>
</html>
"""

DIAGRAM = """<p class="hint">Download: <a href="#" data-download="png">PNG</a> · <a href="#" data-download="svg">SVG</a></p>
<div id="diagram">Loading diagram...</div>
{relations}
<details><summary>Mermaid source</summary><pre>{escaped}</pre></details>
<script type="text/plain" id="source">{raw}</script>
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
  {elk}
  mermaid.initialize({{ startOnLoad: false, securityLevel: "loose" }});
  const src = document.getElementById("source").textContent;
  const el = document.getElementById("diagram");
  try {{
    const {{ svg, bindFunctions }} = await mermaid.render("domain-diagram", src);
    el.innerHTML = svg;
    bindFunctions?.(el);
  }} catch (err) {{
    el.textContent = "Could not render this diagram: " + err.message;
  }}
  document.querySelectorAll("[data-download]").forEach(a => a.addEventListener("click", ev => {{
    ev.preventDefault();
    const svg = el.querySelector("svg");
    if (svg) downloadDiagram(svg, a.dataset.download, {name});
  }}));
__DOWNLOAD__
</script>"""

ELK = ('const { default: elkLayouts } = await import("https://cdn.jsdelivr.net/npm/@mermaid-js/layout-elk@0/dist/mermaid-layout-elk.esm.min.mjs");\n'
       "  mermaid.registerLayoutLoaders(elkLayouts);")


def describe(data, view):
    domains, contexts, _, names = graph.index(data)
    reading = "Arrows point to what something depends on. "
    reading += "Upstream is at the top." if view.get("direction", "BT") == "BT" else ""
    if view.get("hide"):
        reading += " Some items are hidden in this view."
    focus = view.get("focus")
    if not focus:
        return reading
    hops = "all hops" if view["depth"] >= 99 else f"{view['depth']} hop" + ("s" if view["depth"] > 1 else "")
    clusters = {cluster["id"]: cluster for cluster in data["clusters"]}
    if focus in clusters:
        return f"{clusters[focus]['name']}: what it holds, and what those touch, {hops}. {reading}"
    what = {"both": "what it depends on and what uses it", "up": "what it depends on", "down": "what uses it"}[view["dir"]]
    where = ""
    if focus in contexts and not domains[contexts[focus]["domain"]]["single"]:
        where = f", in the {names[contexts[focus]['domain']]} domain"
    return f"{names[focus]}{where}: {what}, {hops}. {reading}"


def item_description(data, view):
    """The description of the view's focus item, when it has one."""
    focus = view.get("focus")
    if not focus:
        return None
    domains, contexts, _, _ = graph.index(data)
    item = domains.get(focus) or contexts.get(focus)
    return (item or {}).get("description")


def facts(data, view):
    """Membership and direct relations for a focused page, as (heading, [ids]) pairs."""
    focus = view.get("focus")
    if not focus:
        return []
    domains, contexts, _, names = graph.index(data)
    clusters = {cluster["id"]: cluster for cluster in data["clusters"]}
    sections = []
    if focus in clusters:
        sections.append(("Members", clusters[focus]["members"]))
    elif focus in domains and not domains[focus]["single"]:
        sections.append(("Bounded contexts", domains[focus]["contexts"]))
    elif focus in contexts and not domains[contexts[focus]["domain"]]["single"]:
        sections.append(("Domain", [contexts[focus]["domain"]]))
    upstreams, downstreams = graph.relations(data, focus)
    sections += [(f"Depends on ({len(upstreams)})", upstreams), (f"Used by ({len(downstreams)})", downstreams)]

    # Dependencies written against the whole domain apply to this context too, we just don't know how yet.
    if focus in contexts:
        parent = contexts[focus]["domain"]
        if not domains[parent]["single"]:
            name = domains[parent]["name"]
            domain_upstreams = sorted({edge["to"] for edge in data["edges"] if edge["from"] == parent}, key=names.get)
            domain_downstreams = sorted({edge["from"] for edge in data["edges"] if edge["to"] == parent}, key=names.get)
            if domain_upstreams:
                sections.append((f"{name} as a whole depends on ({len(domain_upstreams)})", domain_upstreams))
            if domain_downstreams:
                sections.append((f"{name} as a whole is used by ({len(domain_downstreams)})", domain_downstreams))
    return sections


def build(data, config, out):
    """Write one HTML page per view under out/mermaid and one Markdown page under out/markdown."""
    cfg, _ = settings(config)
    _, _, _, names = graph.index(data)
    all_views = views(data, cfg)
    pages = {view["id"] for view in all_views if view.get("page")}

    html_dir = Path(out) / "mermaid"
    md_dir = Path(out) / "markdown"
    for directory in (html_dir, md_dir):
        directory.mkdir(parents=True, exist_ok=True)
        # Drop pages for ids that no longer exist.
        for stale in directory.glob("*.html" if directory == html_dir else "*.md"):
            try:
                stale.unlink()
            except OSError:
                pass

    html_links = {item_id: f"{item_id}.html" for item_id in pages}
    index_rows = []

    for view in all_views:
        title = view.get("title", view["id"])
        desc = view.get("description") or describe(data, view)
        about = item_description(data, view)
        interactive = "index.html" + (f"#focus={view['focus']}" if view.get("focus") else "")
        if view["level"] == "domain":
            interactive += ("&" if view.get("focus") else "#") + "level=domain"

        def html_link(item_id):
            return (f"<a href='{item_id}.html'>{html.escape(names[item_id])}</a>" if item_id in pages
                    else html.escape(names[item_id]))

        cols = "".join(
            f"<div><h3>{html.escape(heading)}</h3>" + ("<ul>" + "".join(f"<li>{html_link(item_id)}</li>" for item_id in item_ids) + "</ul>"
                                                      if item_ids else "<p class='hint'>None</p>") + "</div>"
            for heading, item_ids in facts(data, view))
        source = render(data, cfg, view, links=html_links)
        body = DIAGRAM.format(
            relations=f"<div class='cols'>{cols}</div>" if cols else "",
            escaped=html.escape(source),
            raw=source,
            elk=ELK if uses_elk(cfg) else "",
            name=json.dumps(view["id"]),
        )
        body = body.replace("__DOWNLOAD__", textwrap.indent(DOWNLOAD_JS, "  "))
        (html_dir / f"{view['id']}.html").write_text(PAGE.format(
            title=html.escape(title),
            about=f'<p class="hint">{html.escape(about)}</p>' if about else "",
            description=html.escape(desc), interactive=interactive, body=body))

        def md_link(item_id):
            return f"[{names[item_id]}]({item_id}.md)" if item_id in pages else names[item_id]

        md = [f"# {title}", ""]
        if about:
            md += [about, ""]
        md += [desc, "", "```mermaid", render(data, cfg, view, markdown=True).rstrip(), "```", ""]
        for heading, item_ids in facts(data, view):
            md += [f"**{heading}:** " + (", ".join(md_link(item_id) for item_id in item_ids) or "None"), ""]
        (md_dir / f"{view['id']}.md").write_text("\n".join(md))

        index_rows.append(("Pages" if view.get("page") else "Views", title, view["id"]))

    sections = []
    readme_md = ["# Domain diagrams", "", "Generated from `context-map.yml` and `context-map.style.yml` by `context-mapper`. Do not edit by hand.", ""]
    for group in ("Views", "Pages"):
        rows = sorted((row_title, row_id) for row_group, row_title, row_id in index_rows if row_group == group)
        if rows:
            sections.append(f"<h2>{group}</h2><ul>" + "".join(
                f"<li><a href='{row_id}.html'>{html.escape(row_title)}</a></li>" for row_title, row_id in rows) + "</ul>")
            readme_md += [f"## {group}", ""] + [f"- [{row_title}]({row_id}.md)" for row_title, row_id in rows] + [""]
    (html_dir / "index.html").write_text(PAGE.format(
        title="All diagrams", about="",
        description="Static Mermaid diagrams generated from the context map.",
        interactive="index.html", body="".join(sections)))
    (md_dir / "README.md").write_text("\n".join(readme_md))
    return len(all_views)
