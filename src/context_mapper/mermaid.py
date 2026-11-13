"""Render the domain model as Mermaid flowcharts.

The `mermaid` section of context-map.style.yml controls how diagrams look. See the comments
there and the README for every option. build.py calls `build(data, config, out)`.
"""
import html
import json
import re
from pathlib import Path

from . import graph

VIEW_DEFAULTS = {
    "level": "context",
    "depth": 1,
    "dir": "both",
    "groups": "collapse",
    "group_labels": True,
    "context_labels": True,
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
    "focus_style": "stroke-width:4px,font-weight:bold",
    "domain_style": "fill:#ffffff,stroke:#b0b0b0",
    "edge_styles": {},
    "pages": "all",
    "views": [],
}

VIEW_ONLY = {"id", "title", "focus", "description", "direction"}

ALLOWED = {
    "direction": {"TB", "BT", "LR", "RL"},
    "layout": {"dagre", "elk"},
    "look": {"classic", "handDrawn"},
    "curve": {"basis", "bumpX", "bumpY", "cardinal", "catmullRom", "linear", "monotoneX",
              "monotoneY", "natural", "step", "stepAfter", "stepBefore"},
    "level": {"context", "domain"},
    "dir": {"both", "up", "down"},
    "groups": {"show", "hide", "collapse"},
}

# What a group box looks like when its group has no `mermaid_style`.
GROUP_STYLE = "fill:#f2f2f2,stroke:#595959,stroke-dasharray:4 3,color:#1a1a1a"


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
        name = "defaults" if view is cfg["defaults"] else f"views.{view.get('id', '?')}"
        if view is not cfg["defaults"]:
            if "id" not in view:
                errors.append("mermaid.views: every view needs an id")
            for key in view:
                if key not in VIEW_DEFAULTS and key not in VIEW_ONLY:
                    errors.append(f"mermaid.{name}.{key}: unknown option. Known: "
                                  f"{', '.join(sorted({*VIEW_DEFAULTS, *VIEW_ONLY}))}")
        for key in ("level", "dir", "direction"):
            if key in view and view[key] not in ALLOWED[key]:
                errors.append(f"mermaid.{name}.{key} must be one of: {', '.join(sorted(ALLOWED[key]))}")
        modes = view["groups"].values() if isinstance(view.get("groups"), dict) else [view.get("groups", "collapse")]
        if any(m not in ALLOWED["groups"] for m in modes):
            errors.append(f"mermaid.{name}.groups must be one of {', '.join(sorted(ALLOWED['groups']))}, "
                          "or a map from group id to one of those")
    return cfg, errors


def group_mode(view, group_id):
    """How a view treats one group: show, hide or collapse. `groups` is one mode for all, or a map by id."""
    value = view["groups"]
    return value.get(group_id, VIEW_DEFAULTS["groups"]) if isinstance(value, dict) else value


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
    config = mermaid_config(cfg)
    d = cfg["defaults"]
    return {
        "config": config,
        "elk": uses_elk(cfg),
        "direction": cfg["direction"],
        "curve": config["flowchart"].get("curve", cfg["curve"]),
        "focus_style": cfg["focus_style"],
        "domain_style": cfg["domain_style"],
        "edge_styles": cfg["edge_styles"],
        "group_style": GROUP_STYLE,
        "groups": d["groups"],
        "group_labels": d["group_labels"],
        "context_labels": d["context_labels"],
        "group_by_type": d["group_by_type"],
    }


def node_id(item_id):
    return re.sub(r"\W", "_", item_id)


def group_node_id(group_id):
    return node_id("group_" + group_id)


def text(value):
    return value.replace('"', "#quot;")


def render(data, cfg, view, links=None, markdown=False):
    """Return Mermaid source for one view. `links` maps an id to a URL for click handlers.
    With `markdown`, `markdown_config` is merged in, for renderers like GitLab's that lack ELK."""
    domains, contexts, owner, names = graph.index(data)
    types = data["types"]
    level = view["level"]
    g = graph.level_graph(data, level)
    starts = graph.focus_set(data, level, view.get("focus"))
    group_names = {gr["id"]: gr["name"] for gr in data["groups"]}
    modes = {gid: group_mode(view, gid) for gid in group_names}
    visible = graph.walk(g, starts, view["depth"], view["dir"], {gid for gid, m in modes.items() if m == "hide"})

    # Nodes folded into a group box, by group.
    collapsed = {n for n in visible if modes.get(g["groups"].get(n)) == "collapse" and n not in starts}
    group_boxes = {group_node_id(gid) for gid in group_names}
    target = lambda n: group_node_id(g["groups"][n]) if n in collapsed else node_id(n)

    config_yaml = json.dumps({"config": mermaid_config(cfg, markdown)})
    lines = ["---", config_yaml, "---", f"flowchart {view.get('direction', cfg['direction'])}"]
    for type_id, t in types.items():
        style = t.get("mermaid_style") or f"fill:{t['color']},stroke:{t['border']},color:#1a1a1a"
        lines.append(f"  classDef {type_id} {style}")
    lines.append(f"  classDef focus {cfg['focus_style']}")
    for gr in data["groups"]:
        lines.append(f"  classDef {group_node_id(gr['id'])} {gr['mermaid_style'] or GROUP_STYLE}")

    plain_nodes = []  # ids drawn as plain boxes, for focus and click lines

    def box(item_id, label, type_id, indent):
        plain_nodes.append(item_id)
        return f'{indent}{node_id(item_id)}["{label}"]:::{type_id}'

    def draw_domain(d, indent):
        """Lines for one domain at the current level."""
        if level == "domain":
            if d["id"] not in visible or d["id"] in collapsed:
                return []
            label = text(d["name"])
            if not d["single"] and view["context_labels"]:
                label = f"<b>{label}</b><br/>" + "<br/>".join(text(contexts[c]["name"]) for c in d["contexts"])
            out = [box(d["id"], label, d["type"], indent)]
            if d.get("mermaid_style"):
                out.append(f"{indent}style {node_id(d['id'])} {d['mermaid_style']}")
            return out

        if d["single"]:
            if d["id"] not in visible or d["id"] in collapsed:
                return []
            out = [box(d["id"], text(d["name"]), d["type"], indent)]
            if d.get("mermaid_style"):
                out.append(f"{indent}style {node_id(d['id'])} {d['mermaid_style']}")
            return out

        shown = [c for c in d["contexts"] if c in visible and c not in collapsed]
        domain_shown = d["id"] in visible and d["id"] not in collapsed
        if domain_shown and not shown:
            # The domain is reached as a whole, so show what is inside it.
            shown = [c for c in d["contexts"] if c not in collapsed]
        if not shown:
            return [box(d["id"], text(d["name"]), d["type"], indent)] if domain_shown else []
        out = [f'{indent}subgraph {node_id(d["id"])}["{text(d["name"])}"]']
        out += [box(c, text(contexts[c]["name"]), contexts[c]["type"], indent + "  ") for c in shown]
        out.append(f"{indent}end")
        style = d.get("mermaid_style") or cfg["domain_style"]
        if d["id"] == view.get("focus"):
            style += "," + cfg["focus_style"]
        out.append(f"{indent}style {node_id(d['id'])} {style}")
        return out

    if view["group_by_type"]:
        for type_id, t in types.items():
            block = [line for d in data["domains"] if d["type"] == type_id for line in draw_domain(d, "    ")]
            if block:
                lines += [f'  subgraph type_{type_id}["{text(t["label"])}"]', *block, "  end"]
    else:
        for d in data["domains"]:
            lines += draw_domain(d, "  ")

    for gr in data["groups"]:
        members = sorted(names[n] for n in collapsed if g["groups"][n] == gr["id"])
        if members:
            box_id = group_node_id(gr["id"])
            lines.append(f'  {box_id}["<b>{text(gr["name"])}</b><br/>{text(", ".join(members))}"]:::{box_id}')

    # Merge edges that land on the same pair once groups are collapsed.
    merged = {}
    for e in g["edges"]:
        if e["from"] not in visible or e["to"] not in visible:
            continue
        a, b = target(e["from"]), target(e["to"])
        if a == b:
            continue
        entry = merged.setdefault((a, b), {"styles": set(), "names": set()})
        entry["styles"] |= e["styles"]
        if b in group_boxes:
            entry["names"].add(names[e["to"]])
        elif a in group_boxes:
            entry["names"].add(names[e["from"]])

    by_style = {}
    for i, ((a, b), entry) in enumerate(merged.items()):
        style = "solid" if "solid" in entry["styles"] else sorted(entry["styles"])[0]
        arrow = "-.->" if style == "dotted" else "-->"
        label = ""
        if entry["names"] and view["group_labels"]:
            label = f'|"{text(", ".join(sorted(entry["names"])))}"|'
        lines.append(f"  {a} {arrow}{label} {b}")
        by_style.setdefault(style, []).append(str(i))

    # `interpolate` sets the curve per edge, which works even where the config is ignored.
    for style, indexes in by_style.items():
        extra = cfg["edge_styles"].get(style, "")
        curve = mermaid_config(cfg, markdown)["flowchart"].get("curve", cfg["curve"])
        lines.append(f"  linkStyle {','.join(indexes)} interpolate {curve} {extra}".rstrip())

    # Highlight only the focused item itself: a domain focus marks the domain box, not each context.
    highlight = owner[view["focus"]] if level == "domain" and view.get("focus") else view.get("focus")
    for n in plain_nodes:
        if n == highlight:
            lines.append(f"  class {node_id(n)} focus")
    if links:
        for n in plain_nodes:
            if n in links:
                lines.append(f'  click {node_id(n)} href "{links[n]}"')

    return "\n".join(lines) + "\n"


def page_items(data, cfg):
    """Ids that get their own page."""
    domains, contexts, _, _ = graph.index(data)
    multi = [d["id"] for d in data["domains"] if not d["single"]]
    pages = cfg["pages"]
    if pages == "all":
        return multi + [c["id"] for c in data["contexts"]]
    if pages == "domains":
        return [d["id"] for d in data["domains"]]
    if pages == "contexts":
        return [c["id"] for c in data["contexts"]]
    return list(pages or [])


def views(data, cfg):
    """All views to generate: named views first, then one page per item."""
    domains, _, _, names = graph.index(data)
    result = [{**cfg["defaults"], **v} for v in cfg["views"]]
    for i in page_items(data, cfg):
        is_domain = i in domains and not domains[i]["single"]
        title = f"{names[i]} (domain)" if is_domain else names[i]
        result.append({**cfg["defaults"], "id": i, "title": title, "focus": i, "page": True})
    return result


def check(data, cfg):
    errors = []
    _, _, _, names = graph.index(data)
    pages = cfg["pages"]
    if not (pages in ("all", "domains", "contexts") or isinstance(pages, list)):
        errors.append("mermaid.pages must be all, domains, contexts, or a list of ids")
    elif isinstance(pages, list):
        errors += [f"mermaid.pages: unknown id '{i}'" for i in pages if i not in names]
    seen = set()
    for v in views(data, cfg) if not errors else []:
        if v["id"] in seen:
            errors.append(f"mermaid view id '{v['id']}' is used twice (pages use the domain or context id)")
        seen.add(v["id"])
        if v.get("focus") and v["focus"] not in names:
            errors.append(f"mermaid view '{v['id']}': unknown focus '{v['focus']}'")
    group_ids = {gr["id"] for gr in data["groups"]}
    for name, v in [("defaults", cfg["defaults"]), *((f"views.{v['id']}", v) for v in cfg["views"])]:
        if isinstance(v.get("groups"), dict):
            errors += [f"mermaid.{name}.groups: unknown group '{i}'" for i in v["groups"] if i not in group_ids]
    return errors


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
<p class="hint">{description}</p>
{body}
</main>
</body>
</html>
"""

DIAGRAM = """<div id="diagram">Loading diagram...</div>
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
</script>"""

ELK = ('const { default: elkLayouts } = await import("https://cdn.jsdelivr.net/npm/@mermaid-js/layout-elk@0/dist/mermaid-layout-elk.esm.min.mjs");\n'
       "  mermaid.registerLayoutLoaders(elkLayouts);")


def describe(data, view):
    domains, contexts, _, names = graph.index(data)
    reading = "Arrows point to what something depends on. "
    reading += "Upstream is at the top." if view.get("direction", "BT") == "BT" else ""
    focus = view.get("focus")
    if not focus:
        return reading
    hops = "all hops" if view["depth"] >= 99 else f"{view['depth']} hop" + ("s" if view["depth"] > 1 else "")
    what = {"both": "what it depends on and what uses it", "up": "what it depends on", "down": "what uses it"}[view["dir"]]
    where = ""
    if focus in contexts and not domains[contexts[focus]["domain"]]["single"]:
        where = f", in the {names[contexts[focus]['domain']]} domain"
    return f"{names[focus]}{where}: {what}, {hops}. {reading}"


def facts(data, view, link):
    """Membership and direct relations for a focused page, as (heading, [ids]) pairs."""
    focus = view.get("focus")
    if not focus:
        return []
    domains, contexts, _, names = graph.index(data)
    out = []
    if focus in domains and not domains[focus]["single"]:
        out.append(("Bounded contexts", domains[focus]["contexts"]))
    elif not domains[contexts[focus]["domain"]]["single"]:
        out.append(("Domain", [contexts[focus]["domain"]]))
    ups, downs = graph.relations(data, focus)
    out += [(f"Depends on ({len(ups)})", ups), (f"Used by ({len(downs)})", downs)]

    # Dependencies written against the whole domain apply to this context too, we just don't know how yet.
    if focus in contexts:
        parent = contexts[focus]["domain"]
        if not domains[parent]["single"]:
            name = domains[parent]["name"]
            d_ups = sorted({e["to"] for e in data["edges"] if e["from"] == parent}, key=names.get)
            d_downs = sorted({e["from"] for e in data["edges"] if e["to"] == parent}, key=names.get)
            if d_ups:
                out.append((f"{name} as a whole depends on ({len(d_ups)})", d_ups))
            if d_downs:
                out.append((f"{name} as a whole is used by ({len(d_downs)})", d_downs))
    return out


def build(data, config, out):
    """Write one HTML page per view under out/mermaid and one Markdown page under out/markdown."""
    cfg, _ = settings(config)
    _, _, _, names = graph.index(data)
    all_views = views(data, cfg)
    pages = {v["id"] for v in all_views if v.get("page")}

    html_dir = Path(out) / "mermaid"
    md_dir = Path(out) / "markdown"
    for d in (html_dir, md_dir):
        d.mkdir(parents=True, exist_ok=True)
        # Drop pages for ids that no longer exist.
        for old in d.glob("*.html" if d == html_dir else "*.md"):
            try:
                old.unlink()
            except OSError:
                pass

    html_links = {i: f"{i}.html" for i in pages}
    index_rows = []

    for v in all_views:
        title = v.get("title", v["id"])
        desc = v.get("description") or describe(data, v)
        interactive = "index.html" + (f"#focus={v['focus']}" if v.get("focus") else "")
        if v["level"] == "domain":
            interactive += ("&" if v.get("focus") else "#") + "level=domain"

        html_link = lambda i: (f"<a href='{i}.html'>{html.escape(names[i])}</a>" if i in pages
                               else html.escape(names[i]))
        cols = "".join(
            f"<div><h3>{html.escape(h)}</h3>" + ("<ul>" + "".join(f"<li>{html_link(i)}</li>" for i in ids) + "</ul>"
                                                if ids else "<p class='hint'>None</p>") + "</div>"
            for h, ids in facts(data, v, html_link))
        source = render(data, cfg, v, links=html_links)
        body = DIAGRAM.format(
            relations=f"<div class='cols'>{cols}</div>" if cols else "",
            escaped=html.escape(source),
            raw=source,
            elk=ELK if uses_elk(cfg) else "",
        )
        (html_dir / f"{v['id']}.html").write_text(PAGE.format(
            title=html.escape(title), description=html.escape(desc), interactive=interactive, body=body))

        md_link = lambda i: f"[{names[i]}]({i}.md)" if i in pages else names[i]
        md = [f"# {title}", "", desc, "", "```mermaid", render(data, cfg, v, markdown=True).rstrip(), "```", ""]
        for h, ids in facts(data, v, md_link):
            md += [f"**{h}:** " + (", ".join(md_link(i) for i in ids) or "None"), ""]
        (md_dir / f"{v['id']}.md").write_text("\n".join(md))

        index_rows.append(("Pages" if v.get("page") else "Views", title, v["id"]))

    sections = []
    md = ["# Domain diagrams", "", "Generated from `context-map.yml` and `context-map.style.yml` by `context-mapper`. Do not edit by hand.", ""]
    for group in ("Views", "Pages"):
        rows = sorted((t, i) for g, t, i in index_rows if g == group)
        if rows:
            sections.append(f"<h2>{group}</h2><ul>" + "".join(
                f"<li><a href='{i}.html'>{html.escape(t)}</a></li>" for t, i in rows) + "</ul>")
            md += [f"## {group}", ""] + [f"- [{t}]({i}.md)" for t, i in rows] + [""]
    (html_dir / "index.html").write_text(PAGE.format(
        title="All diagrams", description="Static Mermaid diagrams generated from the context map.",
        interactive="index.html", body="".join(sections)))
    (md_dir / "README.md").write_text("\n".join(md))
    return len(all_views)
