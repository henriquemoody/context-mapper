"""The Mermaid layer: settings, checks, rendering and the static pages."""
import copy
import re

import pytest

from context_mapper import graph, mermaid

# --- settings ---------------------------------------------------------------


def test_settings_fills_in_the_defaults():
    cfg, errors = mermaid.settings({})
    assert errors == []
    assert cfg["direction"] == "BT"
    assert cfg["theme"] == "base"
    assert cfg["layout"] == "dagre"
    assert cfg["look"] == "classic"
    assert cfg["curve"] == "basis"
    assert cfg["pages"] == "all"
    assert cfg["attribute_tooltips"] is True
    assert cfg["relationship_labels"] is True
    assert cfg["defaults"]["level"] == "context"
    assert cfg["defaults"]["depth"] == 1
    assert cfg["defaults"]["dir"] == "both"
    assert cfg["defaults"]["hide"] == []
    assert cfg["defaults"]["child_labels"] is True
    assert cfg["defaults"]["group_by_type"] is False


def test_settings_keeps_what_the_style_file_says():
    cfg, errors = mermaid.settings({"direction": "LR", "layout": "elk", "curve": "step"})
    assert errors == []
    assert cfg["direction"] == "LR"
    assert cfg["layout"] == "elk"
    assert cfg["curve"] == "step"


def test_settings_accepts_attribute_tooltips_off():
    cfg, errors = mermaid.settings({"attribute_tooltips": False})
    assert errors == []
    assert cfg["attribute_tooltips"] is False
    assert mermaid.client_settings(cfg)["attribute_tooltips"] is False


def test_settings_rejects_an_attribute_tooltips_that_is_not_a_boolean():
    _, errors = mermaid.settings({"attribute_tooltips": "show"})
    assert any("mermaid.attribute_tooltips must be true or false" in err for err in errors), errors


def test_settings_accepts_relationship_labels_off():
    cfg, errors = mermaid.settings({"relationship_labels": False})
    assert errors == []
    assert cfg["relationship_labels"] is False
    assert mermaid.client_settings(cfg)["relationship_labels"] is False


def test_settings_hands_the_page_the_relationship_labels_on_by_default():
    cfg, _ = mermaid.settings({})
    assert mermaid.client_settings(cfg)["relationship_labels"] is True


@pytest.mark.parametrize("value", ["yes", 1, None, {}])
def test_settings_rejects_a_relationship_labels_that_is_not_a_boolean(value):
    _, errors = mermaid.settings({"relationship_labels": value})
    assert any("mermaid.relationship_labels must be true or false" in err for err in errors), errors


def test_settings_turns_style_maps_into_classdef_strings():
    cfg, errors = mermaid.settings({
        "focus_style": {"stroke-width": "4px", "font-weight": "bold"},
        "domain_style": {"fill": "#ffffff", "stroke": "#b0b0b0"},
        "edge_styles": {"dotted": {"stroke": "#313131", "stroke-dasharray": "3 3"}},
    })
    assert errors == []
    assert cfg["focus_style"] == "stroke-width:4px,font-weight:bold"
    assert cfg["domain_style"] == "fill:#ffffff,stroke:#b0b0b0"
    assert cfg["edge_styles"]["dotted"] == "stroke:#313131,stroke-dasharray:3 3"


def test_settings_default_styles_are_maps_too():
    cfg, errors = mermaid.settings({})
    assert errors == []
    assert cfg["focus_style"] == "stroke-width:4px,font-weight:bold"
    assert cfg["domain_style"] == "fill:#ffffff,stroke:#b0b0b0"
    assert cfg["edge_styles"] == {"violation": "stroke:#d32f2f,stroke-width:2px", "partnership": "",
                                  "sharedKernel": ""}


def test_settings_lets_the_style_file_restyle_the_violation_arrow():
    cfg, errors = mermaid.settings({"edge_styles": {"violation": {"stroke": "#ff0000", "stroke-dasharray": "6 2"}}})
    assert errors == []
    assert cfg["edge_styles"]["violation"] == "stroke:#ff0000,stroke-dasharray:6 2"


@pytest.mark.parametrize("key, value", [
    ("focus_style", "stroke-width:4px"),
    ("domain_style", "fill:#ffffff"),
    ("edge_styles", "stroke:#313131"),
    ("edge_styles", {"dotted": "stroke:#313131"}),
])
def test_settings_rejects_a_style_that_is_not_a_map(key, value):
    _, errors = mermaid.settings({key: value})
    assert any("must be a map" in err for err in errors), errors


def test_settings_rejects_an_unknown_style_attribute():
    _, errors = mermaid.settings({"focus_style": {"stroke-widht": "4px"}})
    assert any("mermaid.focus_style.stroke-widht: unknown option" in err for err in errors), errors


def test_settings_rejects_an_unknown_edge_style():
    _, errors = mermaid.settings({"edge_styles": {"wavy": {"stroke": "#000"}}})
    assert any("mermaid.edge_styles.wavy: unknown option" in err for err in errors), errors


def test_settings_does_not_change_the_config_it_is_given():
    config = {"focus_style": {"stroke-width": "4px"}}
    mermaid.settings(config)
    assert config == {"focus_style": {"stroke-width": "4px"}}


def test_settings_rejects_an_unknown_top_level_key():
    _, errors = mermaid.settings({"bogus": 1})
    assert any("mermaid.bogus: unknown option" in err for err in errors), errors


def test_settings_rejects_an_unknown_defaults_key():
    _, errors = mermaid.settings({"defaults": {"bogus": 1}})
    assert any("mermaid.defaults.bogus: unknown option" in err for err in errors), errors


def test_settings_rejects_an_unknown_view_key():
    _, errors = mermaid.settings({"views": [{"id": "one", "bogus": 1}]})
    assert any("mermaid.views.one.bogus: unknown option" in err for err in errors), errors


@pytest.mark.parametrize("option, value", [
    ("level", "nope"),
    ("dir", "nope"),
    ("direction", "nope"),
])
def test_settings_rejects_an_invalid_value(option, value):
    _, errors = mermaid.settings({"defaults": {option: value}})
    assert any("must be one of" in err for err in errors), errors


def test_settings_rejects_a_view_without_an_id():
    _, errors = mermaid.settings({"views": [{"title": "No id"}]})
    assert any("every view needs an id" in err for err in errors), errors


def test_settings_rejects_an_invalid_display_value():
    """`show` was the old name for a display state; it is not one now."""
    _, errors = mermaid.settings({"defaults": {"display": "show"}})
    assert any("must be one of" in err for err in errors), errors


def test_settings_accepts_a_display_map():
    cfg, errors = mermaid.settings({"defaults": {"display": {"catalog": "contents"}}})
    assert errors == []
    assert cfg["defaults"]["display"] == {"catalog": "contents"}


def test_settings_rejects_the_old_view_option_name():
    """`group_labels` was the old name for `child_labels`."""
    _, errors = mermaid.settings({"views": [{"id": "one", "group_labels": True}]})
    assert any("unknown option" in err for err in errors), errors


def test_settings_accepts_a_hide_list():
    cfg, errors = mermaid.settings({"defaults": {"hide": ["crm"]}, "views": [{"id": "one", "hide": ["orders"]}]})
    assert errors == []
    assert cfg["defaults"]["hide"] == ["crm"]
    assert cfg["views"][0]["hide"] == ["orders"]


@pytest.mark.parametrize("where, config", [
    ("defaults", {"defaults": {"hide": "crm"}}),
    ("views.one", {"views": [{"id": "one", "hide": "crm"}]}),
])
def test_settings_rejects_a_hide_that_is_not_a_list(where, config):
    _, errors = mermaid.settings(config)
    assert any(f"mermaid.{where}.hide must be a list" in err for err in errors), errors


# --- check ------------------------------------------------------------------


def test_check_accepts_the_example(example_data, example_cfg):
    assert mermaid.check(example_data, example_cfg) == []


def test_check_rejects_an_invalid_pages_value(example_data):
    cfg, _ = mermaid.settings({"pages": "everything"})
    errors = mermaid.check(example_data, cfg)
    assert any("mermaid.pages must be all, domains, contexts, or a list of ids" in err
               for err in errors), errors


def test_check_rejects_a_page_for_an_unknown_id(example_data):
    cfg, _ = mermaid.settings({"pages": ["nowhere"]})
    errors = mermaid.check(example_data, cfg)
    assert any("mermaid.pages: unknown id 'nowhere'" in err for err in errors), errors


def test_check_rejects_a_view_id_used_twice(example_data):
    cfg, _ = mermaid.settings({"views": [{"id": "catalog", "title": "Catalog again"}]})
    errors = mermaid.check(example_data, cfg)
    assert any("mermaid view id 'catalog' is used twice" in err for err in errors), errors


def test_check_rejects_an_unknown_focus(example_data):
    cfg, _ = mermaid.settings({"views": [{"id": "one", "focus": "nowhere"}]})
    errors = mermaid.check(example_data, cfg)
    assert any("unknown focus 'nowhere'" in err for err in errors), errors


def test_check_rejects_a_display_for_an_unknown_container(example_data):
    cfg, _ = mermaid.settings({"defaults": {"display": {"nowhere": "contents"}}})
    errors = mermaid.check(example_data, cfg)
    assert any("unknown container 'nowhere'" in err for err in errors), errors


@pytest.mark.parametrize("where, config", [
    ("defaults", {"defaults": {"hide": ["nowhere"]}}),
    ("views.one", {"views": [{"id": "one", "hide": ["nowhere"]}]}),
])
def test_check_rejects_a_hide_for_an_unknown_id(example_data, where, config):
    cfg, _ = mermaid.settings(config)
    errors = mermaid.check(example_data, cfg)
    assert any(f"mermaid.{where}.hide: unknown id 'nowhere'" in err for err in errors), errors


def test_check_accepts_a_hide_of_any_kind(example_data):
    """Domains, bounded contexts and clusters can all be hidden."""
    cfg, _ = mermaid.settings({"defaults": {"hide": ["catalog", "orders", "checkout", "foundations"]}})
    assert mermaid.check(example_data, cfg) == []


# --- page_items and views ---------------------------------------------------


def test_page_items_with_pages_all(example_data, example_cfg):
    assert mermaid.page_items(example_data, example_cfg) == [
        "catalog", "orders", "identity", "payments", "browsing", "search",
        "checkout", "fulfillment", "crm",
    ]


def test_page_items_with_an_explicit_list(example_data):
    cfg, _ = mermaid.settings({"pages": ["checkout", "catalog"]})
    assert mermaid.page_items(example_data, cfg) == ["checkout", "catalog"]


def test_page_items_with_domains_and_contexts(example_data):
    cfg, _ = mermaid.settings({"pages": "domains"})
    assert mermaid.page_items(example_data, cfg) == [
        "identity", "payments", "catalog", "orders", "crm"]
    cfg, _ = mermaid.settings({"pages": "contexts"})
    assert mermaid.page_items(example_data, cfg) == [
        "identity", "payments", "browsing", "search", "checkout", "fulfillment", "crm"]


def test_views_put_the_named_views_first(example_data, example_cfg):
    views = mermaid.views(example_data, example_cfg)
    assert [view["id"] for view in views[:4]] == [
        "overview", "foundations-detail", "checkout-upstreams", "orders-detail"]
    assert len(views) == 13


def test_views_add_one_page_per_item(example_data, example_cfg):
    views = mermaid.views(example_data, example_cfg)
    pages = [view for view in views if view.get("page")]
    assert len(pages) == 9
    assert [view["id"] for view in pages][:2] == ["catalog", "orders"]
    assert all(view["focus"] == view["id"] for view in pages)


def test_views_let_a_named_view_override_the_defaults(example_data, example_cfg, find_view):
    views = mermaid.views(example_data, example_cfg)
    overview = find_view(views, "overview")
    assert overview["level"] == "domain"
    assert overview["depth"] == 99
    upstreams = find_view(views, "checkout-upstreams")
    assert upstreams["dir"] == "up"


# --- render -----------------------------------------------------------------


def test_render_writes_a_mermaid_diagram(example_data, example_cfg, find_view):
    views = mermaid.views(example_data, example_cfg)
    source = mermaid.render(example_data, example_cfg, find_view(views, "overview"))
    assert source.startswith("---\n")
    assert "flowchart BT" in source


def test_render_writes_a_class_def_for_every_type(example_data, example_cfg, find_view):
    views = mermaid.views(example_data, example_cfg)
    source = mermaid.render(example_data, example_cfg, find_view(views, "overview"))
    assert "classDef core fill:#dedaff,stroke:#6631d7" in source
    assert "classDef supporting fill:#c6dcff,stroke:#305bab" in source
    assert "classDef generic fill:#adf0c7,stroke:#067429" in source
    assert "classDef focus " in source


def test_render_draws_a_subgraph_for_a_domain_with_contexts(example_data, example_cfg, find_view):
    views = mermaid.views(example_data, example_cfg)
    source = mermaid.render(example_data, example_cfg, find_view(views, "orders"))
    assert 'subgraph orders["Orders"]' in source
    assert 'checkout["Checkout"]' in source
    assert 'fulfillment["Fulfillment"]' in source


def test_render_draws_the_styled_edge_as_a_dotted_arrow(example_data, example_cfg, find_view):
    views = mermaid.views(example_data, example_cfg)
    source = mermaid.render(example_data, example_cfg, find_view(views, "orders"))
    assert "checkout -.-> catalog" in source


def test_render_draws_a_violation_as_a_red_arrow(example_data, example_cfg, find_view):
    views = mermaid.views(example_data, example_cfg)
    lines = mermaid.render(example_data, example_cfg, find_view(views, "orders")).splitlines()
    arrows = [line for line in lines if re.match(r"  \w+ (-->|-\.->|<-->)", line)]  # a label may follow the arrow
    position = arrows.index("  checkout <--> catalog")
    assert position == len(arrows) - 1  # after the dependencies
    assert f"  linkStyle {position} interpolate step stroke:#d32f2f,stroke-width:2px" in lines


def test_render_lays_a_violation_out_the_way_the_dependency_runs(example_data, example_cfg, find_view):
    """Catalog calls Checkout against the direction, but the arrow is written from Checkout to Catalog, like the
    dependency, so the layout keeps Catalog above Checkout; the page's script drops the head at Catalog."""
    views = mermaid.views(example_data, example_cfg)
    lines = mermaid.render(example_data, example_cfg, find_view(views, "orders")).splitlines()
    assert "  catalog --> checkout" not in lines
    arrows = [line for line in lines if re.match(r"  \w+ (-->|-\.->|<-->)", line)]
    assert f"  %% violations: {len(arrows) - 1}" in lines


def test_render_draws_a_violation_between_the_domains(example_data, example_cfg, find_view):
    views = mermaid.views(example_data, example_cfg)
    source = mermaid.render(example_data, example_cfg, find_view(views, "overview"))
    assert "  orders <--> catalog" in source
    assert "stroke:#d32f2f" in source


def test_render_leaves_a_violation_out_when_an_end_is_not_drawn(example_data, example_cfg, find_view):
    views = mermaid.views(example_data, example_cfg)
    view = {**find_view(views, "orders"), "hide": ["checkout"]}
    source = mermaid.render(example_data, example_cfg, view)
    assert "<-->" not in source
    assert "%% violations" not in source


def test_render_does_not_reach_anything_through_a_violation(tiny_model, tiny_style):
    tiny_model["context-map"]["solo"]["violations"] = {"core_lib": "Solo calls the core."}
    data, errors = graph.normalize(tiny_model, tiny_style)
    assert errors == []
    cfg, errors = mermaid.settings({})
    assert errors == []
    whole = mermaid.render(data, cfg, {**cfg["defaults"], "id": "all"})
    assert "  core_lib <--> solo" in whole
    focused = mermaid.render(data, cfg, {**cfg["defaults"], "id": "solo", "focus": "solo", "depth": 99})
    assert "core_lib" not in focused


def test_render_draws_a_violation_into_a_collapsed_box(tiny_model, tiny_style):
    tiny_model["context-map"]["solo"]["violations"] = {"core_lib": "x", "core_db": "y"}
    data, errors = graph.normalize(tiny_model, tiny_style)
    assert errors == []
    cfg, _ = mermaid.settings({})
    source = mermaid.render(data, cfg, {**cfg["defaults"], "id": "all", "display": "collapsed"})
    assert source.count("  base <--> solo") == 1  # the cluster holds both, and the two violations become one arrow


def test_build_gives_every_static_page_the_script_that_drops_the_extra_head(tmp_path, example_data, example_style):
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    page = (tmp_path / "mermaid" / "orders.html").read_text()
    assert "function dropViolationHeads(svg, source)" in page
    assert 'dropViolationHeads(el.querySelector("svg"), src);' in page
    assert "export function" not in page


def test_render_writes_click_handlers_for_the_links(example_data, example_cfg, find_view):
    views = mermaid.views(example_data, example_cfg)
    links = {"checkout": "checkout.html", "crm": "crm.html"}
    source = mermaid.render(example_data, example_cfg, find_view(views, "orders"), links)
    assert 'click checkout href "checkout.html"' in source
    assert 'click crm href "crm.html"' in source


def test_render_marks_the_focused_node(example_data, example_cfg, find_view):
    views = mermaid.views(example_data, example_cfg)
    source = mermaid.render(example_data, example_cfg, find_view(views, "crm"))
    assert "class crm focus" in source


def test_render_uses_the_markdown_layout_only_for_markdown(example_data, example_cfg, find_view):
    views = mermaid.views(example_data, example_cfg)
    view = find_view(views, "overview")
    html_source = mermaid.render(example_data, example_cfg, view)
    markdown_source = mermaid.render(example_data, example_cfg, view, None, True)
    assert '"layout": "elk"' in html_source
    assert '"layout": "dagre"' in markdown_source


# --- relationship roles -----------------------------------------------------


def arrows_of(source):
    """The dependency arrows of a source, in the order `linkStyle` counts them, a label and all."""
    return [line.strip() for line in source.splitlines() if re.match(r"  \w+ (-->|-\.->)", line)]


def roles_line(source):
    found = [line.strip() for line in source.splitlines() if line.strip().startswith("%% roles:")]
    assert len(found) <= 1
    return found[0] if found else None


def checkout_view(cfg, **extra):
    """Checkout and its neighbors, with the foundations cluster open so Identity and Payments are arrows of
    their own."""
    return {**cfg["defaults"], "id": "checkout", "focus": "checkout", "display": {"foundations": "expanded"}, **extra}


def test_render_says_which_arrows_carry_roles_and_what_they_are(example_data, example_cfg):
    source = mermaid.render(example_data, example_cfg, checkout_view(example_cfg))
    arrows = arrows_of(source)
    identity, payments = arrows.index("checkout --> identity"), arrows.index("checkout --> payments")
    assert roles_line(source) == f"%% roles: {identity}=OHS,PL>ACL;{payments}=S>C"


def test_render_writes_the_roles_in_the_canonical_order_not_the_one_in_the_yaml(example_model, example_style):
    """The fixture lists PublishedLanguage before OpenHostService."""
    spec = example_model["context-map"]["identity"]["downstreams"]["checkout"]
    assert spec["upstream"] == ["PublishedLanguage", "OpenHostService"]
    data, errors = graph.normalize(example_model, example_style)
    assert errors == []
    cfg, _ = mermaid.settings(example_style["mermaid"])
    assert "=OHS,PL>ACL" in mermaid.render(data, cfg, checkout_view(cfg))


def test_render_leaves_the_roles_out_of_the_arrow_label(example_data, example_cfg):
    source = mermaid.render(example_data, example_cfg, checkout_view(example_cfg))
    assert "OHS" not in "\n".join(arrows_of(source))
    assert "<br/>" not in "\n".join(arrows_of(source))


def test_render_says_nothing_about_roles_when_no_arrow_has_any(example_data, example_cfg, find_view):
    source = mermaid.render(example_data, example_cfg, find_view(mermaid.views(example_data, example_cfg), "catalog"))
    assert "%% roles" not in source


def test_render_leaves_a_side_with_no_roles_empty(example_data, example_cfg):
    view = {**example_cfg["defaults"], "id": "orders", "focus": "orders"}
    source = mermaid.render(example_data, example_cfg, view)
    assert roles_line(source) == f"%% roles: {arrows_of(source).index('crm --> orders')}=>CF"


def test_render_drops_the_roles_of_an_arrow_whose_dependencies_differ(example_data, example_cfg):
    """With the foundations cluster collapsed, one arrow stands for Checkout's dependency on Identity and on
    Payments, which carry different roles."""
    source = mermaid.render(example_data, example_cfg, checkout_view(example_cfg, display={}))
    assert "checkout -->|\"Identity, Payments\"| foundations" in source
    assert "%% roles" not in source


def collapsed_data(tiny_model, tiny_style, first, second):
    """Web's contexts depend on `core_lib` and `core_db`, with the given roles on each."""
    for owner, downstream, roles in (("web_ui", "core_lib", first), ("web_api", "core_db", second)):
        tiny_model["context-map"][owner]["downstreams"] = {downstream: {"comment": "x", **(roles or {})}}
    data, errors = graph.normalize(tiny_model, tiny_style)
    assert errors == []
    return data


def collapsed_source(data, markdown=False, **extra):
    cfg, _ = mermaid.settings({})
    return mermaid.render(data, cfg, {**cfg["defaults"], "id": "all", "display": {"web": "collapsed", "core": "collapsed"},
                         **extra}, markdown=markdown)


def test_render_keeps_the_roles_of_a_collapsed_box_when_what_it_holds_agrees(tiny_model, tiny_style):
    roles = {"upstream": ["OpenHostService"], "downstream": ["AnticorruptionLayer"]}
    source = collapsed_source(collapsed_data(tiny_model, tiny_style, roles, dict(roles)))
    assert arrows_of(source)[0].startswith("core -")  # one arrow for Web's two contexts
    assert roles_line(source) == "%% roles: 0=OHS>ACL"


def test_render_drops_the_roles_of_a_collapsed_box_when_what_it_holds_differs(tiny_model, tiny_style):
    first = {"upstream": ["OpenHostService"], "downstream": ["AnticorruptionLayer"]}
    second = {"upstream": ["PublishedLanguage"], "downstream": ["AnticorruptionLayer"]}
    assert roles_line(collapsed_source(collapsed_data(tiny_model, tiny_style, first, second))) is None


def test_render_drops_the_roles_of_a_collapsed_box_when_one_dependency_has_none(tiny_model, tiny_style):
    first = {"upstream": ["OpenHostService"], "downstream": ["AnticorruptionLayer"]}
    assert roles_line(collapsed_source(collapsed_data(tiny_model, tiny_style, first, None))) is None


def test_render_lifts_the_roles_to_the_domains_when_they_agree(tiny_model, tiny_style):
    roles = {"upstream": ["Supplier"], "downstream": ["Customer"]}
    cfg, _ = mermaid.settings({})
    data = collapsed_data(tiny_model, tiny_style, roles, dict(roles))
    source = mermaid.render(data, cfg, {**cfg["defaults"], "id": "all", "level": "domain"})
    assert roles_line(source) == "%% roles: 0=S>C"
    data = collapsed_data(tiny_model, tiny_style, roles, None)
    assert roles_line(mermaid.render(data, cfg, {**cfg["defaults"], "id": "all", "level": "domain"})) is None


def test_render_counts_the_arrows_the_way_linkstyle_does(example_data, example_cfg, find_view):
    source = mermaid.render(example_data, example_cfg, find_view(mermaid.views(example_data, example_cfg), "orders"))
    arrows = arrows_of(source)
    index = int(re.search(r"%% roles: (\d+)=", source).group(1))
    assert arrows[index].startswith("crm -->")  # the Conformist's
    styled = [int(i) for line in source.splitlines() if "linkStyle" in line
              for i in line.split()[1].split(",")]
    assert index in styled  # the same number linkStyle uses for that arrow


def test_render_turns_the_role_labels_off(example_model, example_style):
    example_style["mermaid"]["relationship_labels"] = False
    data, errors = graph.normalize(example_model, example_style)
    assert errors == []
    cfg, errors = mermaid.settings(example_style["mermaid"])
    assert errors == []
    view = checkout_view(cfg)
    assert roles_line(mermaid.render(data, cfg, view)) is None
    markdown = mermaid.render(data, cfg, view, markdown=True)
    assert "U:" not in markdown and "D:" not in markdown
    assert "%% roles" not in markdown


def test_render_puts_the_roles_of_a_markdown_diagram_on_the_middle_of_the_arrow(example_data, example_cfg):
    source = mermaid.render(example_data, example_cfg, checkout_view(example_cfg), markdown=True)
    arrows = arrows_of(source)
    assert 'checkout -->|"U: OHS, PL<br/>D: ACL"| identity' in arrows
    assert 'checkout -->|"U: S<br/>D: C"| payments' in arrows
    assert "%% roles" not in source  # there is no script to read it


def test_render_leaves_a_side_with_no_roles_off_the_markdown_label(example_data, example_cfg):
    view = {**example_cfg["defaults"], "id": "crm", "focus": "crm"}
    source = mermaid.render(example_data, example_cfg, view, markdown=True)
    assert 'crm -->|"D: CF"| orders' in arrows_of(source)


def test_render_leaves_an_arrow_without_roles_unlabeled_in_markdown(example_data, example_cfg):
    source = mermaid.render(example_data, example_cfg, checkout_view(example_cfg), markdown=True)
    assert "checkout -.-> catalog" in arrows_of(source)


def test_render_puts_the_names_of_a_collapsed_box_above_the_roles_in_markdown(tiny_model, tiny_style):
    roles = {"upstream": ["OpenHostService"], "downstream": ["AnticorruptionLayer"]}
    data = collapsed_data(tiny_model, tiny_style, roles, dict(roles))
    markdown = collapsed_source(data, markdown=True)
    assert 'core -->|"Web API, Web UI<br/>U: OHS<br/>D: ACL"| web' in arrows_of(markdown)


def test_render_leaves_the_names_alone_when_child_labels_are_off_in_markdown(tiny_model, tiny_style):
    roles = {"upstream": ["OpenHostService"], "downstream": []}
    data = collapsed_data(tiny_model, tiny_style, roles, dict(roles))
    markdown = collapsed_source(data, markdown=True, child_labels=False)
    assert '|"U: OHS"|' in markdown
    assert "Web UI" not in "\n".join(arrows_of(markdown))


# --- relationship roles, in the lists and the pages --------------------------


def test_fact_sections_say_which_roles_a_dependency_carries(example_data):
    sections = {heading: notes for heading, _, notes in
                mermaid.fact_sections(example_data, {"focus": "checkout", "depth": 1, "dir": "both"})}
    notes = sections["Depends on (3)"]
    assert notes == {"identity": "Open Host Service, Published Language \u2192 Anticorruption Layer",
                     "payments": "Supplier \u2192 Customer"}
    assert sections["Used by (0)"] == {}


def test_fact_sections_say_it_about_the_dependencies_of_the_whole_domain(example_data):
    sections = {heading: notes for heading, _, notes in
                mermaid.fact_sections(example_data, {"focus": "checkout", "depth": 1, "dir": "both"})}
    assert sections["Orders as a whole is used by (1)"] == {"crm": "Conformist (downstream)"}


def test_fact_sections_lift_the_roles_of_a_domain(example_data):
    sections = {heading: notes for heading, _, notes in
                mermaid.fact_sections(example_data, {"focus": "orders", "depth": 1, "dir": "both"})}
    # Payments is reached by two dependencies of the domain, one with roles and one without: none are kept.
    assert sections["Depends on (3)"] == {"identity": "Open Host Service, Published Language \u2192 Anticorruption Layer"}


def test_facts_stay_pairs_of_a_heading_and_ids(example_data):
    for entry in mermaid.facts(example_data, {"focus": "checkout", "depth": 1, "dir": "both"}):
        assert len(entry) == 2


def test_build_shows_the_roles_in_the_lists_of_a_static_page(tmp_path, example_data, example_style):
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    page = (tmp_path / "mermaid" / "checkout.html").read_text()
    assert "<span class='hint'>\u00b7 Open Host Service, Published Language \u2192 Anticorruption Layer</span>" in page
    assert "<span class='hint'>\u00b7 Supplier \u2192 Customer</span>" in page


def test_build_shows_the_roles_in_the_lists_of_a_markdown_page(tmp_path, example_data, example_style):
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    markdown = (tmp_path / "markdown" / "checkout.md").read_text()
    assert "[Identity](identity.md) \u00b7 Open Host Service, Published Language \u2192 Anticorruption Layer" in markdown
    assert "[Payments](payments.md) \u00b7 Supplier \u2192 Customer" in markdown
    assert "(Supplier" not in markdown


def test_build_shows_the_roles_in_the_lists_even_with_the_labels_off(tmp_path, example_data, example_style):
    example_style["mermaid"]["relationship_labels"] = False
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    markdown = (tmp_path / "markdown" / "checkout.md").read_text()
    assert "\u00b7 Supplier \u2192 Customer" in markdown
    assert "U: S" not in markdown


def test_build_writes_the_role_labels_into_the_markdown_diagram(tmp_path, example_data, example_style):
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    markdown = (tmp_path / "markdown" / "identity.md").read_text()
    assert "U: OHS, PL<br/>D: ACL" in markdown
    assert "%% roles" not in markdown


def test_build_gives_every_static_page_the_script_that_draws_the_roles(tmp_path, example_data, example_style):
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    page = (tmp_path / "mermaid" / "checkout.html").read_text()
    assert "function drawRoleLabels(svg, source)" in page
    assert 'drawRoleLabels(el.querySelector("svg"), src);' in page
    assert "%% roles:" in page  # in the source the script reads
    assert "__ROLES__" not in page
    assert "export " not in page.split('<script type="module">')[1]  # spliced as plain functions


# --- partnerships and shared kernels ---------------------------------------


STATEMENT = re.compile(r"  \w+ (-->|-\.->|<-->|---)")


def statements_of(source):
    """Every arrow or line of a source, in the order `linkStyle` counts them."""
    return [line.strip() for line in source.splitlines() if STATEMENT.match(line)]


def link_view(cfg, **extra):
    return {**cfg["defaults"], "id": "links", "focus": "search", **extra}


def test_settings_gives_the_links_a_line_style_that_follows_solid():
    cfg, errors = mermaid.settings({"edge_styles": {"solid": {"stroke": "#313131", "stroke-width": "1.5px"}}})
    assert errors == []
    assert cfg["edge_styles"]["partnership"] == "stroke:#313131,stroke-width:1.5px"
    assert cfg["edge_styles"]["sharedKernel"] == "stroke:#313131,stroke-width:1.5px"


def test_settings_lets_the_style_file_restyle_the_links():
    cfg, errors = mermaid.settings({"edge_styles": {"partnership": {"stroke": "#00f"},
                                                   "sharedKernel": {"stroke": "#0f0", "stroke-width": "5px"}}})
    assert errors == []
    assert cfg["edge_styles"]["partnership"] == "stroke:#00f"
    assert cfg["edge_styles"]["sharedKernel"] == "stroke:#0f0,stroke-width:5px"


def test_settings_rejects_an_unknown_attribute_in_a_link_style():
    _, errors = mermaid.settings({"edge_styles": {"partnership": {"colour": "red"}}})
    assert any("mermaid.edge_styles.partnership.colour: unknown option" in err for err in errors), errors


def test_settings_lists_the_link_styles_among_the_known_edge_styles():
    _, errors = mermaid.settings({"edge_styles": {"friendship": {}}})
    assert any("Known: solid, dotted, violation, partnership, sharedKernel" in err for err in errors), errors


def test_render_draws_a_partnership_as_a_line_with_no_heads(example_data, example_cfg):
    source = mermaid.render(example_data, example_cfg, link_view(example_cfg))
    assert 'checkout --- search' in statements_of(source)


def test_render_draws_a_shared_kernel_as_a_plain_line_with_a_badge_mark(example_data, example_cfg):
    """No middle label and no thick line: the page's script draws an SK badge on the arrow the line names."""
    view = {**example_cfg["defaults"], "id": "crm", "focus": "crm", "display": {"foundations": "expanded"}}
    source = mermaid.render(example_data, example_cfg, view)
    statements = statements_of(source)
    assert statements[-1] == "payments --- crm"
    kernels = re.search(r"  %% kernels: ([\d,]+)", source).group(1).split(",")
    assert str(len(statements) - 1) in kernels
    assert statements[int(kernels[0])] == "fulfillment --> payments"  # the kernel beside a dependency, on its arrow
    assert "Shared Kernel" not in source
    assert "stroke-width:3px" not in source


def test_render_makes_the_declaring_entry_the_target_of_the_line(example_data, example_cfg):
    """Search declares the partnership, so it takes the upstream's place: the target, on top by default."""
    source = mermaid.render(example_data, example_cfg, link_view(example_cfg))
    assert statements_of(source)[-1].endswith(" search")
    flipped = mermaid.render(example_data, example_cfg, link_view(example_cfg, focus="checkout"))
    assert 'checkout --- search' in statements_of(flipped)


def test_render_moving_the_declaration_flips_the_line(example_model, example_style):
    example_model["context-map"]["search"].pop("partnerships")
    example_model["context-map"]["checkout"]["partnerships"] = {"search": "Search and Checkout plan the cart together."}
    data, errors = graph.normalize(example_model, example_style)
    assert errors == []
    cfg, _ = mermaid.settings(example_style["mermaid"])
    assert 'search --- checkout' in statements_of(mermaid.render(data, cfg, link_view(cfg)))


def test_render_counts_the_links_after_the_dependencies_and_the_violations(example_data, example_cfg):
    view = {**example_cfg["defaults"], "id": "orders", "focus": "orders", "depth": 99}
    source = mermaid.render(example_data, example_cfg, view)
    statements = statements_of(source)
    kinds = ["violation" if "<-->" in line else "link" if "---" in line else "dependency"
             for line in statements]
    assert kinds == sorted(kinds, key={"dependency": 0, "violation": 1, "link": 2}.get)
    assert "link" in kinds and "violation" in kinds
    violation = int(re.search(r"%% violations: (\d+)", source).group(1))
    assert kinds[violation] == "violation"
    styled = {}
    for line in source.splitlines():
        found = re.match(r"  linkStyle ([\d,]+) interpolate \w+ ?(.*)", line)
        if found:
            for index in found.group(1).split(","):
                styled[int(index)] = found.group(2)
    assert sorted(styled) == list(range(len(statements)))  # every line is styled, none twice
    assert styled[kinds.index("link")] == "stroke:#313131,stroke-width:1.5px"


def test_render_keeps_the_roles_and_the_violations_on_the_arrows_they_name(example_data, example_cfg):
    """The page's scripts count `path.flowchart-link` the way linkStyle does: the links come after both."""
    source = mermaid.render(example_data, example_cfg, {**example_cfg["defaults"], "id": "orders", "focus": "orders",
                                                         "depth": 99})
    statements = statements_of(source)
    for index in re.search(r"%% violations: ([\d,]+)", source).group(1).split(","):
        assert "<-->" in statements[int(index)]
    for mark in re.search(r"%% roles: (.+)", source).group(1).split(";"):
        assert re.search(r"-->|-\.->", statements[int(mark.split("=")[0])])


def test_render_styles_the_links_by_kind(example_data, example_cfg):
    view = {**example_cfg["defaults"], "id": "all", "level": "domain", "display": {"foundations": "expanded"}}
    source = mermaid.render(example_data, example_cfg, view)
    statements = statements_of(source)
    partnership = statements.index("orders --- catalog")
    kernel = statements.index("payments --- crm")
    for index in (partnership, kernel):
        assert re.search(rf"linkStyle [\d,]*\b{index}\b[\d,]* interpolate step stroke:#313131,stroke-width:1.5px",
                         source), index
    assert "%% kernels: " in source and str(kernel) in re.search(r"%% kernels: ([\d,]+)", source).group(1).split(",")


def test_render_draws_a_shared_kernel_beside_a_dependency_on_the_arrow_itself(example_data, example_cfg):
    """Fulfillment depends on Payments and shares a kernel with it: one arrow, no line, a badge mark."""
    view = {**example_cfg["defaults"], "id": "fulfillment", "focus": "fulfillment",
            "display": {"foundations": "expanded"}}
    source = mermaid.render(example_data, example_cfg, view)
    statements = statements_of(source)
    assert "fulfillment --> payments" in statements
    assert not any("---" in line and "payments" in line for line in statements)
    assert str(statements.index("fulfillment --> payments")) in re.search(
        r"%% kernels: ([\d,]+)", source).group(1).split(",")
    assert "Shared Kernel" not in source


def test_render_keeps_the_direction_and_the_roles_of_a_dependency_that_shares_a_kernel(example_model, example_style):
    example_model["context-map"]["payments"]["sharedKernels"] = {"checkout": "Same payment types."}
    data, errors = graph.normalize(example_model, example_style)
    assert errors == []
    cfg, _ = mermaid.settings(example_style["mermaid"])
    source = mermaid.render(data, cfg, checkout_view(cfg))
    statements = statements_of(source)
    index = statements.index("checkout --> payments")  # the dependency's direction, whoever declares the kernel
    assert not any("---" in line and "payments" in line for line in statements)
    assert f"{index}=S>C" in source  # its roles, at its ends
    assert str(index) in re.search(r"%% kernels: ([\d,]+)", source).group(1).split(",")


def test_render_styles_a_kernel_arrow_in_the_kernel_style_laid_over_its_own(example_model, example_style):
    example_style["mermaid"]["edge_styles"]["sharedKernel"] = {"stroke": "#00f"}
    example_model["context-map"]["payments"]["sharedKernels"] = {"checkout": "x"}
    example_model["context-map"]["checkout"]["downstreams"] = {}
    data, errors = graph.normalize(example_model, example_style)
    cfg, _ = mermaid.settings(example_style["mermaid"])
    assert cfg["edge_styles"]["sharedKernel"] == "stroke:#00f"
    assert mermaid.merge_styles("stroke:#313131,stroke-width:1.5px,stroke-dasharray:3 3", "stroke:#00f") == \
        "stroke:#00f,stroke-width:1.5px,stroke-dasharray:3 3"


def test_render_draws_a_violation_beside_a_kernel_as_its_own_arrow(tiny_model, tiny_style):
    """Only a dependency takes the kernel onto its arrow: a violation is a separate fact."""
    tiny_model["context-map"]["solo"]["sharedKernels"] = {"core_lib": "x"}
    tiny_model["context-map"]["core_lib"]["violations"] = {"solo": "calls solo"}
    data, errors = graph.normalize(tiny_model, tiny_style)
    assert errors == []
    cfg, _ = mermaid.settings({})
    source = mermaid.render(data, cfg, {**cfg["defaults"], "id": "all"})
    statements = statements_of(source)
    assert "solo <--> core_lib" in statements and "core_lib --- solo" in statements
    kernels = re.search(r"%% kernels: ([\d,]+)", source).group(1).split(",")
    assert kernels == [str(statements.index("core_lib --- solo"))]


def test_render_draws_the_lifted_partnership_once_between_the_domains(example_data, example_cfg):
    view = {**example_cfg["defaults"], "id": "all", "level": "domain"}
    statements = statements_of(mermaid.render(example_data, example_cfg, view))
    assert len([line for line in statements if "---" in line]) == 1
    assert "orders --- catalog" in statements
    assert "orders -.-> catalog" in statements  # the dependency is still there: two facts, two lines


def test_render_leaves_out_a_link_inside_a_domain(tiny_model, tiny_style):
    tiny_model["context-map"]["web_ui"]["partnerships"] = {"web_api": "x"}
    data, errors = graph.normalize(tiny_model, tiny_style)
    assert errors == []
    cfg, _ = mermaid.settings({})
    assert "web_api --- web_ui" in statements_of(mermaid.render(data, cfg, {**cfg["defaults"], "id": "all"}))
    domain = mermaid.render(data, cfg, {**cfg["defaults"], "id": "all", "level": "domain"})
    assert "---" not in "\n".join(statements_of(domain))


def collapsed_links(tiny_model, tiny_style, **extra):
    tiny_model["context-map"]["solo"]["partnerships"] = {"web_ui": "x", "web_api": "y"}
    data, errors = graph.normalize(tiny_model, tiny_style)
    assert errors == []
    cfg, _ = mermaid.settings({})
    markdown = extra.pop("markdown", False)
    return mermaid.render(data, cfg, {**cfg["defaults"], "id": "all", "display": {"web": "collapsed"}, **extra},
                          markdown=markdown)


def test_render_merges_the_links_of_a_collapsed_box_and_names_what_it_holds(tiny_model, tiny_style):
    source = collapsed_links(tiny_model, tiny_style)
    lines = [line for line in statements_of(source) if "---" in line]
    assert lines == ['web ---|"Web API, Web UI"| solo']


def test_render_leaves_the_names_out_of_a_collapsed_links_label_without_child_labels(tiny_model, tiny_style):
    source = collapsed_links(tiny_model, tiny_style, child_labels=False)
    assert "web --- solo" in statements_of(source)


def test_render_puts_the_link_label_in_the_markdown_too(example_data, example_cfg):
    source = mermaid.render(example_data, example_cfg, link_view(example_cfg), markdown=True)
    assert 'checkout --- search' in statements_of(source)
    assert "%% roles" not in source


def test_render_turns_the_link_labels_off(example_model, example_style):
    example_style["mermaid"]["relationship_labels"] = False
    data, errors = graph.normalize(example_model, example_style)
    assert errors == []
    cfg, _ = mermaid.settings(example_style["mermaid"])
    for markdown in (False, True):
        statements = statements_of(mermaid.render(data, cfg, link_view(cfg), markdown=markdown))
        assert statements[-1] == "checkout --- search"
    view = {**cfg["defaults"], "id": "crm", "focus": "crm", "display": {"foundations": "expanded"}}
    for markdown in (False, True):
        source = mermaid.render(data, cfg, view, markdown=markdown)
        assert statements_of(source)[-1] == "payments --- crm"
        assert "%% kernels" not in source and "Shared Kernel" not in source


def test_render_reaches_across_a_link_in_every_direction(example_data, example_cfg):
    for direction in ("both", "up", "down"):
        source = mermaid.render(example_data, example_cfg, link_view(example_cfg, dir=direction))
        assert 'checkout --- search' in statements_of(source), direction


def test_render_hides_a_link_whose_end_is_hidden(example_data, example_cfg):
    source = mermaid.render(example_data, example_cfg, link_view(example_cfg, hide=["checkout"]))
    assert "Partnership" not in source


def test_render_gives_a_model_without_links_the_sources_it_always_did(tiny_data):
    cfg, _ = mermaid.settings({})
    source = mermaid.render(tiny_data, cfg, {**cfg["defaults"], "id": "all"})
    assert "---|" not in source and "%% kernels" not in source


# --- links in the lists and the pages ----------------------------------------


def test_fact_sections_list_the_partners_and_the_shared_kernels(example_data):
    sections = {heading: ids for heading, ids, _ in
                mermaid.fact_sections(example_data, {"focus": "search", "depth": 1, "dir": "both"})}
    assert sections["Partners (1)"] == ["checkout"]
    sections = {heading: ids for heading, ids, _ in
                mermaid.fact_sections(example_data, {"focus": "crm", "depth": 1, "dir": "both"})}
    assert sections["Shares a kernel with (1)"] == ["payments"]


def test_fact_sections_leave_out_a_list_with_nobody_in_it(example_data):
    headings = [heading for heading, _, _ in
                mermaid.fact_sections(example_data, {"focus": "identity", "depth": 1, "dir": "both"})]
    assert not any(heading.startswith(("Partners", "Shares a kernel")) for heading in headings)


def test_fact_sections_list_what_the_whole_domain_is_paired_with(tiny_model, tiny_style):
    tiny_model["context-map"]["web"]["partnerships"] = {"solo": "x"}
    data, errors = graph.normalize(tiny_model, tiny_style)
    assert errors == []
    sections = {heading: ids for heading, ids, _ in
                mermaid.fact_sections(data, {"focus": "web_ui", "depth": 1, "dir": "both"})}
    assert sections["Web as a whole partners with (1)"] == ["solo"]


def test_build_writes_the_partners_into_the_page_and_the_markdown(tmp_path, example_data, example_style):
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    page = (tmp_path / "mermaid" / "search.html").read_text()
    assert "<h3>Partners (1)</h3>" in page
    assert "<li><a href='checkout.html'>Checkout</a></li>" in page
    assert "<h3>Shares a kernel with" not in page
    markdown = (tmp_path / "markdown" / "crm.md").read_text()
    assert "**Shares a kernel with (1):** [Payments](payments.md)" in markdown
    assert "**Partners" not in markdown
    assert 'crm -->|"Identity, Payments<br/>Shared Kernel"| foundations' in markdown
    assert 'checkout --- search' in (tmp_path / "markdown" / "search.md").read_text()


# --- reaching a domain ------------------------------------------------------


def _hub_data():
    """`hub` is used by the whole of `web`; `web_ui` has a user in `ops`, which holds two contexts."""
    data, errors = graph.normalize({
        "types": {"core": {"name": "Core"}},
        "context-map": {
            "hub": {"name": "Hub", "type": "core", "downstreams": {"web": "All of Web uses it."}},
            "web": {"name": "Web", "type": "core"},
            "web_ui": {"name": "Web UI", "domain": "web", "downstreams": {"ops_a": "Ops A embeds the UI."}},
            "web_api": {"name": "Web API", "domain": "web"},
            "ops": {"name": "Ops", "type": "core"},
            "ops_a": {"name": "Ops A", "domain": "ops"},
            "ops_b": {"name": "Ops B", "domain": "ops"},
        },
    }, {"types": {"core": {"fill": "#dedaff", "stroke": "#6631d7"}}})
    assert errors == []
    cfg, errors = mermaid.settings({})
    assert errors == []
    return data, cfg


def test_render_draws_a_domain_holding_only_the_contexts_that_were_reached():
    data, cfg = _hub_data()
    view = {**cfg["defaults"], "id": "v", "focus": "web_ui", "dir": "down", "depth": 99}
    source = mermaid.render(data, cfg, view)
    assert 'subgraph ops["Ops"]' in source
    assert 'ops_a["Ops A"]' in source
    assert "Ops B" not in source
    assert "ops_a --> web_ui" in source


def test_render_follows_a_domain_level_edge_into_the_contexts_of_the_domain():
    data, cfg = _hub_data()
    view = {**cfg["defaults"], "id": "v", "focus": "hub", "dir": "down", "depth": 99}
    source = mermaid.render(data, cfg, view)
    assert "web --> hub" in source
    assert 'ops_a["Ops A"]' in source and "ops_a --> web_ui" in source
    assert "Ops B" not in source


# --- hide --------------------------------------------------------------------


def test_render_hides_a_domain_in_the_whole_system(example_data, example_cfg):
    view = {**example_cfg["defaults"], "id": "whole", "hide": ["crm"]}
    source = mermaid.render(example_data, example_cfg, view)
    assert "crm" not in source
    assert "CRM" not in source
    assert "--> orders" not in source      # the CRM -> orders dependency goes too
    assert 'subgraph orders["Orders"]' in source


def test_render_hides_a_cluster_and_its_members(example_data, example_cfg):
    view = {**example_cfg["defaults"], "id": "whole", "hide": ["foundations"]}
    source = mermaid.render(example_data, example_cfg, view)
    assert "foundations" not in source
    assert "Identity" not in source and "Payments" not in source


def test_render_hides_a_bounded_context_in_a_domain_view(example_data, example_cfg):
    """The point of `hide`: a domain page without one of its bounded contexts."""
    view = {**example_cfg["defaults"], "id": "orders-detail", "focus": "orders", "hide": ["fulfillment"]}
    source = mermaid.render(example_data, example_cfg, view)
    assert "fulfillment" not in source
    assert "Fulfillment" not in source
    assert 'checkout["Checkout"]' in source
    assert 'subgraph orders["Orders"]' in source


def test_render_does_not_reach_through_a_hidden_context(tiny_data):
    cfg, _ = mermaid.settings({})
    view = {**cfg["defaults"], "id": "web-view", "focus": "web", "depth": 1, "hide": ["web_ui"]}
    source = mermaid.render(tiny_data, cfg, view)
    assert "web_ui" not in source
    assert "core_lib" not in source       # it was only reachable through Web UI
    assert 'web_api["Web API"]' in source


def test_render_never_hides_the_focus_itself(example_data, example_cfg):
    view = {**example_cfg["defaults"], "id": "crm-page", "focus": "crm", "hide": ["crm"]}
    source = mermaid.render(example_data, example_cfg, view)
    assert 'crm["CRM"]' in source
    assert "class crm focus" in source


def test_render_draws_a_focused_context_inside_its_domain(example_data, example_cfg):
    """A bounded-context focus appears in its domain box, with only what was reached."""
    view = {**example_cfg["defaults"], "id": "checkout-page", "focus": "checkout"}
    source = mermaid.render(example_data, example_cfg, view)
    assert 'subgraph orders["Orders"]' in source
    assert 'checkout["Checkout"]' in source
    assert "Fulfillment" not in source            # a sibling nobody reached stays out
    assert "class checkout focus" in source
    assert "checkout -.-> catalog" in source      # its own dependency draws too
    assert "crm" not in source                    # but the domain's own relations stay out


def test_render_hides_a_member_of_a_focused_cluster(example_data, example_cfg):
    view = {**example_cfg["defaults"], "id": "foundations-view", "focus": "foundations", "hide": ["identity"]}
    source = mermaid.render(example_data, example_cfg, view)
    assert 'subgraph foundations["Shared Foundations"]' in source
    assert 'payments["Payments"]' in source
    assert "Identity" not in source


def test_render_keeps_a_focused_cluster_whose_members_are_all_hidden(example_data, example_cfg):
    view = {**example_cfg["defaults"], "id": "foundations-view", "focus": "foundations",
            "hide": ["identity", "payments"]}
    source = mermaid.render(example_data, example_cfg, view)
    assert 'foundations["Shared Foundations"]' in source
    assert "class foundations focus" in source
    assert "Identity" not in source and "Payments" not in source


def test_render_leaves_a_hidden_context_out_of_a_collapsed_label(example_data, example_cfg):
    view = {**example_cfg["defaults"], "id": "whole", "display": {"orders": "collapsed"}, "hide": ["fulfillment"]}
    source = mermaid.render(example_data, example_cfg, view)
    assert "Fulfillment" not in source
    assert "<b>Orders</b><br/>Checkout" in source


# --- defaultDisplay ---------------------------------------------------------


HIDDEN_MODEL = {
    "types": {"core": {"name": "Core"}},
    "context-map": {
        "dom": {"name": "Dom", "type": "core"},
        "shy": {"name": "Shy", "domain": "dom", "type": "core"},
        "out": {"name": "Out", "domain": "dom", "type": "core",
                "downstreams": {"solo": "Out stands on Solo."}},
        "solo": {"name": "Solo", "type": "core"},
    },
}
HIDDEN_STYLE = {
    "types": {"core": {"fill": "#dedaff", "stroke": "#6631d7"}},
    "context-map": {
        "shy": {"defaultDisplay": "hidden"},
        "out": {"fill": "#f7f7ff", "stroke": "#6631d7"},
        "solo": {"defaultDisplay": "hidden"},
    },
}


@pytest.fixture
def hidden_data():
    """A domain holding one bounded context that starts hidden and one that
    doesn't, plus a single domain that starts hidden, depended on by Out."""
    data, errors = graph.normalize(HIDDEN_MODEL, HIDDEN_STYLE)
    assert errors == []
    return data


def test_render_leaves_out_what_starts_hidden(hidden_data):
    """`defaultDisplay: hidden` on a bounded context — or on a single domain,
    which is one — hides it like `hide` hides it."""
    cfg, _ = mermaid.settings({})
    source = mermaid.render(hidden_data, cfg, {**cfg["defaults"], "id": "whole"})
    assert "shy" not in source and "Shy" not in source
    assert "solo" not in source and "Solo" not in source
    assert 'out["Out"]' in source
    assert "out --> solo" not in source      # an arrow needs both its boxes


def test_render_still_shows_what_starts_hidden_where_it_is_the_focus(hidden_data):
    cfg, _ = mermaid.settings({})
    view = {**cfg["defaults"], "id": "shy", "focus": "shy"}
    source = mermaid.render(hidden_data, cfg, view)
    assert 'shy["Shy"]' in source
    assert "class shy focus" in source


def test_render_keeps_what_starts_hidden_out_of_its_domains_page(hidden_data):
    """Like `hide`, a default-hidden bounded context stays out even of the page
    of the domain holding it; only its own page shows it."""
    cfg, _ = mermaid.settings({})
    view = {**cfg["defaults"], "id": "dom", "focus": "dom", "depth": 99}
    source = mermaid.render(hidden_data, cfg, view)
    assert "Shy" not in source
    assert 'subgraph dom["Dom"]' in source
    assert 'out["Out"]' in source


def test_render_styles_a_bounded_context_of_its_own(hidden_data):
    cfg, _ = mermaid.settings({})
    source = mermaid.render(hidden_data, cfg, {**cfg["defaults"], "id": "whole"})
    assert 'out["Out"]:::core' in source
    assert "style out fill:#f7f7ff,stroke:#6631d7,color:#1a1a1a" in source


# --- build ------------------------------------------------------------------


def test_build_writes_a_page_for_every_view(tmp_path, example_data, example_style, example_cfg):
    count = mermaid.build(example_data, example_style["mermaid"], tmp_path)
    assert count == 13
    for view in mermaid.views(example_data, example_cfg):
        assert (tmp_path / "mermaid" / f"{view['id']}.html").exists()
        assert (tmp_path / "markdown" / f"{view['id']}.md").exists()


def test_build_writes_the_indexes(tmp_path, example_data, example_style):
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    assert (tmp_path / "mermaid" / "index.html").exists()
    assert (tmp_path / "markdown" / "README.md").exists()


def test_build_removes_the_pages_of_a_previous_build(tmp_path, example_data, example_style):
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    stale_html = tmp_path / "mermaid" / "stale.html"
    stale_md = tmp_path / "markdown" / "stale.md"
    stale_html.write_text("old")
    stale_md.write_text("old")
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    assert not stale_html.exists()
    assert not stale_md.exists()


def test_build_writes_the_diagram_into_the_page(tmp_path, example_data, example_style):
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    page = (tmp_path / "mermaid" / "overview.html").read_text()
    assert "flowchart BT" in page
    markdown = (tmp_path / "markdown" / "overview.md").read_text()
    assert markdown.startswith("# ")
    assert "```mermaid" in markdown


def test_build_writes_the_download_links_into_the_page(tmp_path, example_data, example_style):
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    page = (tmp_path / "mermaid" / "overview.html").read_text()
    assert 'data-download="png"' in page
    assert 'data-download="svg"' in page
    assert "function downloadDiagram" in page    # the shared export script, spliced in
    assert "getComputedStyle(svg).fontFamily" in page    # the page's font travels with the file
    assert "__DOWNLOAD__" not in page            # never left behind
    assert 'downloadDiagram(svg, a.dataset.download, "overview")' in page
    assert 'from "../mermaid.js"' in page         # the renderer is vendored, not fetched
    assert "jsdelivr" not in page                 # no CDN left anywhere on the page


# --- attributes --------------------------------------------------------------


def test_build_writes_the_attributes_into_the_page(tmp_path, example_data, example_style):
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    page = (tmp_path / "mermaid" / "checkout.html").read_text()
    assert '<p class="hint"><b>Service:</b> checkout-service</p>' in page
    assert "<b>Aggregates:</b> Order, Cart" in page


def test_build_writes_the_attributes_into_the_markdown(tmp_path, example_data, example_style):
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    markdown = (tmp_path / "markdown" / "checkout.md").read_text()
    assert "**Service:** checkout-service" in markdown
    assert "**Aggregates:** Order, Cart" in markdown


def test_build_leaves_out_the_attributes_of_an_item_that_sets_none(tmp_path, example_data, example_style):
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    page = (tmp_path / "mermaid" / "search.html").read_text()
    assert "<b>Service:</b>" not in page


def test_attribute_text_shows_a_list_and_a_map_inline():
    assert mermaid.attribute_text("one") == "one"
    assert mermaid.attribute_text(["one", "two"]) == "one, two"
    assert mermaid.attribute_text({"owner": "team", "on-call": "#team"}) == "owner: team · on-call: #team"


# --- describe and item_description -------------------------------------------


def test_describe_says_what_the_view_shows(example_data):
    description = mermaid.describe(example_data, {
        "focus": "checkout", "depth": 2, "dir": "up", "direction": "BT"})
    assert "Checkout" in description
    assert "2 hops" in description
    assert "what it depends on" in description


def test_describe_of_a_cluster_says_what_it_holds(example_data):
    description = mermaid.describe(example_data, {
        "focus": "foundations", "depth": 1, "dir": "both"})
    assert "Shared Foundations" in description
    assert "1 hop" in description


def test_describe_without_a_focus_is_about_the_arrows(example_data):
    description = mermaid.describe(example_data, {"depth": 1, "dir": "both"})
    assert "Arrows point to what something depends on." in description


def test_describe_says_when_items_are_hidden(example_data):
    description = mermaid.describe(example_data, {"focus": "orders", "depth": 1, "dir": "both", "hide": ["fulfillment"]})
    assert "Some items are hidden in this view." in description


def test_item_description_is_the_description_of_the_focused_item(example_data):
    assert mermaid.item_description(example_data, {"focus": "checkout"}) == (
        "Takes a cart and turns it into a paid order.")
    assert mermaid.item_description(example_data, {"focus": "catalog"}) == (
        "Everything that can be bought, with its prices and availability.")


def test_item_description_is_nothing_for_an_item_without_one(example_data):
    assert mermaid.item_description(example_data, {"focus": "orders"}) is None
    assert mermaid.item_description(example_data, {}) is None


# --- facts ------------------------------------------------------------------


def test_facts_of_a_cluster_list_its_members(example_data):
    facts = mermaid.facts(example_data, {"focus": "foundations", "depth": 1, "dir": "both"})
    headings = [heading for heading, _ in facts]
    assert "Members" in headings
    members = dict(facts)["Members"]
    assert members == ["identity", "payments"]


def test_facts_of_a_context_say_where_it_lives_and_who_it_talks_to(example_data):
    facts = mermaid.facts(example_data, {"focus": "checkout", "depth": 1, "dir": "both"})
    headings = [heading for heading, _ in facts]
    assert "Domain" in headings
    assert any(heading.startswith("Depends on") for heading in headings)
    assert any(heading.startswith("Used by") for heading in headings)
    assert dict(facts)["Domain"] == ["orders"]


def test_facts_of_a_domain_list_its_bounded_contexts(example_data):
    facts = mermaid.facts(example_data, {"focus": "orders", "depth": 1, "dir": "both"})
    assert dict(facts)["Bounded contexts"] == ["checkout", "fulfillment"]


def test_facts_without_a_focus_are_empty(example_data):
    assert mermaid.facts(example_data, {"depth": 1, "dir": "both"}) == []


def test_render_spells_the_shared_kernel_out_in_the_markdown_where_no_script_runs(example_model, example_style):
    example_model["context-map"]["payments"]["sharedKernels"] = {"checkout": "Same payment types."}
    data, errors = graph.normalize(example_model, example_style)
    assert errors == []
    cfg, _ = mermaid.settings(example_style["mermaid"])
    source = mermaid.render(data, cfg, checkout_view(cfg), markdown=True)
    assert 'checkout -->|"Shared Kernel<br/>U: S<br/>D: C"| payments' in statements_of(source)
    assert "%% kernels" not in source
    lone = mermaid.render(data, cfg, {**cfg["defaults"], "id": "crm", "focus": "crm",
                                      "display": {"foundations": "expanded"}}, markdown=True)
    assert 'payments ---|"Shared Kernel"| crm' in statements_of(lone)


def test_render_names_what_a_collapsed_box_holds_beside_the_kernel_in_the_markdown(tiny_model, tiny_style):
    tiny_model["context-map"]["solo"]["sharedKernels"] = {"web_ui": "x"}
    data, errors = graph.normalize(tiny_model, tiny_style)
    assert errors == []
    cfg, _ = mermaid.settings({})
    view = {**cfg["defaults"], "id": "all", "display": {"web": "collapsed"}}
    assert 'web ---|"Web UI<br/>Shared Kernel"| solo' in statements_of(mermaid.render(data, cfg, view, markdown=True))
    source = mermaid.render(data, cfg, view)
    assert 'web ---|"Web UI"| solo' in statements_of(source)  # the badge goes beside this label, in the script
    assert "%% kernels: " in source


def test_render_gives_a_merged_arrow_the_kernel_when_any_pair_in_it_shares_one(tiny_model, tiny_style):
    """Unlike roles, the kernel isn't an agreement: one of the two dependencies sharing it is enough."""
    tiny_model["context-map"]["web_ui"]["sharedKernels"] = {"core_lib": "x"}
    data, errors = graph.normalize(tiny_model, tiny_style)
    assert errors == []
    cfg, _ = mermaid.settings({})
    source = mermaid.render(data, cfg, {**cfg["defaults"], "id": "all", "level": "domain"})
    statements = statements_of(source)
    assert statements == ["core --> web"] or statements[0].startswith("core -")
    assert re.search(r"%% kernels: 0", source)
    assert not any("---" in line for line in statements)


def test_render_lays_the_kernel_style_over_a_dotted_arrow(tiny_model, tiny_style):
    tiny_model["context-map"]["web_api"]["sharedKernels"] = {"core_db": "x"}
    data, errors = graph.normalize(tiny_model, tiny_style)
    assert errors == []
    cfg, _ = mermaid.settings({"edge_styles": {"dotted": {"stroke": "#313131", "stroke-dasharray": "3 3"},
                                               "sharedKernel": {"stroke": "#00f"}}})
    source = mermaid.render(data, cfg, {**cfg["defaults"], "id": "all"})
    statements = statements_of(source)
    index = statements.index("core_db -.-> web_api")  # still dotted, still that direction
    assert not any("---" in line for line in statements)
    assert "interpolate basis stroke:#00f,stroke-dasharray:3 3" in "\n".join(
        line for line in source.splitlines() if re.search(rf"linkStyle [\d,]*\b{index}\b", line))


# --- aggregates -------------------------------------------------------------


def aggregate_view(cfg, **extra):
    return {**cfg["defaults"], "id": "aggregates", "level": "aggregate", **extra}


def arrow_lines(source):
    return [line.strip() for line in source.splitlines() if re.match(r"^\s{2}\w+ (-->|-\.->|<-->|---)", line)]


def test_settings_accepts_the_aggregate_level_in_the_defaults_and_in_a_view():
    cfg, errors = mermaid.settings({"defaults": {"level": "aggregate"}, "views": [{"id": "a", "level": "aggregate"}]})
    assert errors == []
    assert cfg["defaults"]["level"] == "aggregate"


def test_settings_lists_the_aggregate_level_among_the_levels_it_rejects_a_wrong_one_for():
    _, errors = mermaid.settings({"views": [{"id": "a", "level": "aggregates"}]})
    assert any("mermaid.views.a.level must be one of aggregate, context, domain" in err for err in errors), errors
    _, errors = mermaid.settings({"defaults": {"level": "tactical"}})
    assert any("mermaid.defaults.level must be one of aggregate, context, domain" in err for err in errors), errors


def test_render_draws_a_context_with_aggregates_as_a_container_around_a_box_for_each(example_data, example_cfg):
    source = mermaid.render(example_data, example_cfg, aggregate_view(example_cfg, focus="checkout"))
    assert '    subgraph checkout["Checkout"]' in source
    assert '      checkout__Order["Order"]:::aggregate' in source
    assert '      checkout__Cart["Cart"]:::aggregate' in source
    assert "classDef aggregate fill:#ffffff,stroke:#6b6b6b,color:#1a1a1a" in source
    # The container is in the colors of its type, with the focus style when it is the focus.
    assert ("    style checkout fill:#dedaff,stroke:#6631d7,color:#1a1a1a,stroke-width:4px,font-weight:bold"
            in source)
    # A domain still wraps its contexts.
    assert '  subgraph orders["Orders"]' in source


def test_render_draws_a_domain_no_context_points_at_as_a_container_around_its_aggregates(example_data, example_cfg):
    source = mermaid.render(example_data, example_cfg,
                            aggregate_view(example_cfg, focus="payments", display={"foundations": "expanded"}))
    assert '    subgraph payments["Payments"]' in source
    assert '      payments__Payment["Payment"]:::aggregate' in source
    assert "payments__Payment" not in source.split("classDef focus")[0]


def test_render_draws_a_context_with_no_aggregates_as_a_plain_box(example_data, example_cfg):
    source = mermaid.render(example_data, example_cfg, aggregate_view(example_cfg, focus="search"))
    assert '    search["Search"]:::core' in source
    assert "subgraph search" not in source


def test_render_draws_no_aggregates_in_a_collapsed_domain(example_data, example_cfg):
    source = mermaid.render(example_data, example_cfg,
                            aggregate_view(example_cfg, display={"foundations": "expanded", "orders": "collapsed"}))
    assert 'orders["<b>Orders</b><br/>Checkout, Fulfillment"]' in source
    assert "checkout__Order" not in source


def test_render_draws_no_arrow_between_containers_that_a_reference_covers(example_data, example_cfg):
    kwargs = {"focus": "orders", "depth": 99, "display": {"foundations": "expanded"}}
    contexts = arrow_lines(mermaid.render(example_data, example_cfg, {**example_cfg["defaults"], "id": "c", **kwargs}))
    aggregates = arrow_lines(mermaid.render(example_data, example_cfg, aggregate_view(example_cfg, **kwargs)))
    between_containers = [line for line in aggregates if not re.fullmatch(r"\w+__\w+ -.?-> \w+__\w+", line)]
    # Checkout, Fulfillment and CRM depend on Identity and Payments, and their aggregates reference
    # theirs: those dependencies are drawn on the references.
    covered = ["checkout --> identity", "crm --> identity", "checkout --> payments", "fulfillment --> payments"]
    assert all(line in contexts for line in covered)
    assert not any(line in aggregates for line in covered)
    # What no reference explains keeps its arrow, in the order it had: a dependency on a whole domain, the
    # violation, the partnership and the shared kernel.
    assert between_containers == [line for line in contexts if line not in covered]
    assert "crm --> orders" in between_containers
    assert "payments --- crm" in between_containers


def test_render_draws_a_dependency_on_the_reference_that_covers_it(example_data, example_cfg):
    source = mermaid.render(example_data, example_cfg, aggregate_view(
        example_cfg, focus="orders", depth=99, display={"foundations": "expanded"}))
    arrows = arrow_lines(source)
    roles = dict(mark.split("=") for mark in re.search(r"%% roles: (.+)", source).group(1).split(";"))
    # The roles of the dependencies are marked at the references that carry them.
    assert arrows[int(next(i for i, role in roles.items() if role == "OHS,PL>ACL"))] == \
        "checkout__Order --> identity__Account"
    assert arrows[int(next(i for i, role in roles.items() if role == "S>C"))] == \
        "checkout__Order --> payments__Payment"
    # The one that stays between containers is marked there.
    assert arrows[int(next(i for i, role in roles.items() if role == ">CF"))] == "crm --> orders"
    # A shared kernel beside a dependency rides on the reference too. A kernel with no dependency stays a line.
    kernels = [arrows[int(i)] for i in re.search(r"%% kernels: (.+)", source).group(1).split(",")]
    assert kernels == ["payments --- crm", "fulfillment__Shipment --> payments__Payment"]
    # Neither a partnership nor a kernel alone moves anything onto a reference.
    assert "crm__Ticket --> payments__Payment" in arrows
    assert "fulfillment__Return --> browsing__Session" in arrows


def covering_model(references, **dependency):
    """Alpha's aggregate `One` references what `references` says in Beta, which Alpha depends on."""
    return {
        "types": {"core": {"name": "Core"}},
        "context-map": {
            "alpha": {"name": "Alpha", "type": "core", "aggregates": {
                "One": {"references": references[0]}, "Two": {"references": references[1]}}},
            "beta": {"name": "Beta", "type": "core", "aggregates": {"Thing": None, "Other": None},
                     "downstreams": {"alpha": dependency or None}},
        },
    }


def render_aggregates(model, **view):
    data, errors = graph.normalize(model, {"types": {"core": {"fill": "#dedaff", "stroke": "#6631d7"}}})
    assert errors == []
    cfg, _ = mermaid.settings({})
    return mermaid.render(data, cfg, aggregate_view(cfg, **view))


def test_render_draws_the_style_of_the_dependency_on_the_reference():
    source = render_aggregates(covering_model([["beta/Thing"], ["beta/Other"]], style="dotted"))
    arrows = arrow_lines(source)
    assert arrows[0] == "alpha__One -.-> beta__Thing"
    assert arrows[1] == "alpha__Two --> beta__Other"
    assert "alpha -.-> beta" not in arrows
    # Styled as a dotted dependency, apart from the plain reference.
    assert "  linkStyle 0 interpolate basis" in source and "  linkStyle 1 interpolate basis" in source


def test_render_lets_the_first_reference_carry_a_dependency_several_cover():
    source = render_aggregates(covering_model([["beta/Other", "beta/Thing"], ["beta/Thing"]],
                                              upstream=["Supplier"], downstream=["Customer"]))
    arrows = arrow_lines(source)
    assert arrows == ["alpha__One --> beta__Other", "alpha__One --> beta__Thing", "alpha__Two --> beta__Thing"]
    assert "%% roles: 0=S>C" in source


def test_render_keeps_the_arrow_between_containers_of_a_dependency_no_reference_explains():
    # Nothing references Beta: Alpha's aggregates point at each other only.
    uncovered = render_aggregates(covering_model([["Two"], ["One"]]))
    assert arrow_lines(uncovered)[0] == "alpha --> beta"


def test_render_keeps_the_arrow_of_a_dependency_whose_referenced_aggregate_is_not_drawn(example_data, example_cfg):
    # Foundations is collapsed: Identity and Payments fold into it, and the aggregates in them aren't drawn.
    arrows = arrow_lines(mermaid.render(example_data, example_cfg, aggregate_view(example_cfg, focus="checkout")))
    assert 'checkout -->|"Identity, Payments"| foundations' in arrows
    assert not any("identity__Account" in line for line in arrows)


def test_render_puts_the_dependency_on_the_reference_in_the_markdown_too(example_data, example_cfg):
    view = aggregate_view(example_cfg, focus="checkout", display={"foundations": "expanded"})
    markdown = mermaid.render(example_data, example_cfg, view, markdown=True)
    assert 'checkout__Order -->|"U: OHS, PL<br/>D: ACL"| identity__Account' in markdown
    assert "checkout --> identity" not in markdown


def test_render_draws_a_reference_from_the_aggregate_that_holds_it_to_the_one_it_points_at(example_data, example_cfg):
    arrows = arrow_lines(mermaid.render(example_data, example_cfg, aggregate_view(
        example_cfg, focus="orders", depth=99, display={"foundations": "expanded"})))
    assert "checkout__Order --> identity__Account" in arrows
    assert "checkout__Cart --> checkout__Order" in arrows
    assert "checkout__Cart --> browsing__Session" in arrows  # a dependency on the Catalog domain as a whole
    assert "fulfillment__Return --> browsing__Session" in arrows  # a partnership
    assert "crm__Ticket --> payments__Payment" in arrows  # a shared kernel
    assert "crm__Ticket --> checkout__Order" in arrows


def test_render_draws_a_reference_only_when_both_aggregates_are_drawn(example_data, example_cfg):
    # Foundations is collapsed by default, so the aggregates inside it aren't drawn.
    arrows = arrow_lines(mermaid.render(example_data, example_cfg, aggregate_view(example_cfg, focus="checkout")))
    assert not any("identity__Account" in line for line in arrows)
    assert "checkout__Cart --> checkout__Order" in arrows


def test_render_counts_every_arrow_once_in_the_link_styles(example_data, example_cfg):
    source = mermaid.render(example_data, example_cfg, aggregate_view(
        example_cfg, focus="orders", depth=99, display={"foundations": "expanded"}))
    styled = [int(i) for line in source.splitlines() if re.match(r"^\s*linkStyle ", line)
              for i in line.split()[1].split(",")]
    assert sorted(styled) == list(range(len(arrow_lines(source))))


def test_render_links_an_aggregate_to_the_page_of_its_context(example_data, example_cfg):
    view = aggregate_view(example_cfg, focus="checkout")
    source = mermaid.render(example_data, example_cfg, view, links={"checkout": "checkout.html"})
    assert '  click checkout__Order href "checkout.html"' in source
    assert "click checkout__Order" not in mermaid.render(example_data, example_cfg, view)


def test_render_keeps_the_roles_in_the_middle_of_the_arrow_in_the_markdown(example_data, example_cfg):
    view = aggregate_view(example_cfg, focus="checkout", display={"foundations": "expanded"})
    markdown = mermaid.render(example_data, example_cfg, view, markdown=True)
    assert "U: OHS, PL<br/>D: ACL" in markdown
    assert "%% roles" not in markdown
    assert "%% kernels" not in markdown


def test_render_without_the_aggregate_level_draws_no_aggregates(example_data, example_cfg):
    source = mermaid.render(example_data, example_cfg, {**example_cfg["defaults"], "id": "c", "focus": "checkout"})
    assert "checkout__Order" not in source
    assert "classDef aggregate" not in source


def test_describe_says_what_the_aggregate_level_shows(example_data, example_cfg):
    description = mermaid.describe(example_data, aggregate_view(example_cfg, focus="checkout"))
    assert "an arrow between two is a reference" in description


def test_aggregate_diagram_is_a_class_diagram_with_a_namespace_for_each_aggregate(example_data, example_cfg):
    source = mermaid.aggregate_diagram(example_data, example_cfg, "checkout")
    lines = [line.strip() for line in source.splitlines()]
    assert "classDiagram" in lines
    assert "direction BT" in lines
    assert "namespace Order {" in lines
    assert "namespace Cart {" in lines
    assert 'class checkout__Order_Order["Order"]:::inside {' in lines
    assert 'class checkout__Order_OrderLine["OrderLine"]:::inside {' in lines
    assert 'class checkout__Order_Money["Money"]:::inside {' in lines
    for annotation in ("<<root>>", "<<entity>>", "<<value object>>"):
        assert annotation in lines
    # The configuration of the other diagrams, so the theme and the look carry over.
    assert source.startswith("---\n")
    assert '"look": "handDrawn"' in source


def test_aggregate_diagram_draws_a_reference_between_the_root_classes(example_data, example_cfg):
    lines = mermaid.aggregate_diagram(example_data, example_cfg, "checkout").splitlines()
    assert "  checkout__Cart_Cart --> checkout__Order_Order" in lines
    assert "  checkout__Order_Order --> ext_identity__Account" in lines


def test_aggregate_diagram_draws_the_aggregates_of_other_contexts_outside_the_namespaces_and_muted(example_data, example_cfg):
    source = mermaid.aggregate_diagram(example_data, example_cfg, "checkout")
    lines = [line.strip() for line in source.splitlines()]
    # Named for their context, and muted.
    assert 'class ext_identity__Account["Account"]:::muted {' in lines
    assert "<<Identity>>" in lines
    assert 'class ext_browsing__Session["Session"]:::muted {' in lines
    assert any(line.startswith("classDef muted fill:#f4f4f4") for line in lines)
    namespaced = source[source.index("namespace Order"):source.index("class ext_identity__Account")]
    assert "ext_" not in namespaced.replace("class ext_", "")


def test_aggregate_diagram_takes_the_colors_of_the_type_of_the_context(example_data, example_cfg):
    source = mermaid.aggregate_diagram(example_data, example_cfg, "checkout")
    assert "classDef inside fill:#dedaff,stroke:#6631d7,color:#1a1a1a" in source
    # A single domain's own entry carries the style of its box.
    assert "classDef inside fill:#adf0c7,stroke:#067429,color:#1a1a1a" in mermaid.aggregate_diagram(
        example_data, example_cfg, "payments")


def test_aggregate_diagram_names_the_root_when_it_is_not_the_aggregate(example_data, example_cfg):
    source = mermaid.aggregate_diagram(example_data, example_cfg, "browsing")
    assert 'class browsing__Session_Visit["Visit"]:::inside {' in source
    assert "browsing__Session_Visit --> " not in source  # no references


def test_aggregate_diagram_has_nothing_for_a_context_without_aggregates_or_events(example_data, example_cfg):
    bare = copy.deepcopy(example_data)
    for context in bare["contexts"]:
        if context["id"] == "search":
            context.pop("publishes"), context.pop("consumes")
    assert mermaid.aggregate_diagram(bare, example_cfg, "search") is None
    # A domain that holds contexts has no diagram of its own, whatever it publishes.
    assert mermaid.aggregate_diagram(example_data, example_cfg, "orders") is None
    assert mermaid.aggregate_diagram(example_data, example_cfg, None) is None


def test_aggregate_diagram_follows_the_direction_of_the_view(example_data, example_cfg):
    assert "direction LR" in mermaid.aggregate_diagram(example_data, example_cfg, "checkout", direction="LR")


def test_aggregate_diagram_uses_the_markdown_config_for_the_markdown(example_data, example_cfg):
    source = mermaid.aggregate_diagram(example_data, example_cfg, "checkout", markdown=True)
    assert '"layout": "dagre"' in source


def test_build_writes_the_aggregates_and_their_class_diagram_into_the_page(tmp_path, example_data, example_style):
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    page = (tmp_path / "mermaid" / "checkout.html").read_text()
    assert "<h2>Aggregates</h2>" in page
    assert "<h3>Order</h3>" in page
    assert '<p class="hint">A cart that was paid for.</p>' in page
    assert "<li><b>Root:</b> Order</li>" in page
    assert "<li><b>Entities:</b> OrderLine</li>" in page
    assert "<li><b>Value objects:</b> Money, Address</li>" in page
    assert "<li><b>Entities:</b> CartLine (One product, and how many of it.), Coupon</li>" in page
    # A reference to another context's aggregate links to its page.
    assert "<a href='identity.html'>Identity</a> / Account" in page
    # A reference to an aggregate of the context itself is its bare name.
    assert "<li><b>References:</b> Order, <a href='browsing.html'>Browsing</a> / Session</li>" in page
    assert '<div id="aggregates-diagram">' in page
    assert '<script type="text/plain" id="aggregates-source">---' in page
    assert "classDiagram" in page
    assert 'mermaid.render("aggregates-svg"' in page


def test_build_writes_no_aggregates_into_a_page_of_something_without_them(tmp_path, example_data, example_style):
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    for name in ("search", "orders", "overview"):
        page = (tmp_path / "mermaid" / f"{name}.html").read_text()
        assert "<h2>Aggregates</h2>" not in page
        assert "## Aggregates" not in (tmp_path / "markdown" / f"{name}.md").read_text()
    for name in ("orders", "overview"):
        page = (tmp_path / "mermaid" / f"{name}.html").read_text()
        assert 'id="aggregates-diagram"' not in page
        assert 'mermaid.render("aggregates-svg"' not in page


def test_build_writes_the_aggregates_into_the_markdown(tmp_path, example_data, example_style):
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    markdown = (tmp_path / "markdown" / "checkout.md").read_text()
    assert "## Aggregates" in markdown
    assert "### Order" in markdown
    assert "A cart that was paid for." in markdown
    assert "- **Root:** Order" in markdown
    assert "- **Value objects:** Money, Address" in markdown
    # A context that has the aggregate's own name says it once.
    assert ("- **References:** [Identity](identity.md) / Account, [Identity](identity.md), "
            "[Payments](payments.md) / Payment") in markdown
    assert "```mermaid\n---\n" in markdown
    assert "classDiagram" in markdown
    assert markdown.count("```mermaid") == 2
    assert '"layout": "dagre"' in markdown.split("classDiagram")[0].split("```mermaid")[-1]


def test_build_writes_the_aggregate_attributes_into_the_page(tmp_path, example_model, example_style):
    example_model["attributes"]["owner"] = {"name": "Owner", "type": "text"}
    example_model["context-map"]["checkout"]["aggregates"]["Order"]["attributes"] = {"owner": "team-a"}
    data, errors = graph.normalize(example_model, example_style)
    assert errors == []
    mermaid.build(data, example_style["mermaid"], tmp_path)
    assert "<li><b>Owner:</b> team-a</li>" in (tmp_path / "mermaid" / "checkout.html").read_text()
    assert "- **Owner:** team-a" in (tmp_path / "markdown" / "checkout.md").read_text()


def test_build_links_the_interactive_view_at_the_level_of_the_view(tmp_path, example_data, example_style):
    example_style["mermaid"]["views"] = [{"id": "agg", "level": "aggregate", "focus": "checkout"},
                                         {"id": "agg-all", "level": "aggregate"}]
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    assert 'href="../index.html#focus=checkout&level=aggregate"' in (tmp_path / "mermaid" / "agg.html").read_text()
    assert 'href="../index.html#level=aggregate"' in (tmp_path / "mermaid" / "agg-all.html").read_text()
    assert "level=" not in (tmp_path / "mermaid" / "checkout.html").read_text().split("Interactive view")[0].split("href=")[-1]


def test_build_writes_a_static_page_and_markdown_for_a_view_at_the_aggregate_level(tmp_path, example_data, example_style):
    example_style["mermaid"]["views"] = [{"id": "agg", "level": "aggregate", "focus": "checkout", "depth": 99}]
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    page = (tmp_path / "mermaid" / "agg.html").read_text()
    assert "checkout__Order[" in page
    assert 'click checkout__Order href "checkout.html"' in page
    markdown = (tmp_path / "markdown" / "agg.md").read_text()
    assert "checkout__Order[" in markdown
    assert "click" not in markdown
    assert "%% violations" in page and "%% violations" in markdown


def test_build_says_a_name_once_when_the_context_and_the_aggregate_share_it(tmp_path, example_data, example_style):
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    page = (tmp_path / "mermaid" / "checkout.html").read_text()
    assert "<a href='identity.html'>Identity</a> / Account, <a href='identity.html'>Identity</a>, " in page
    assert "Identity</a> / Identity" not in page


def test_aggregate_diagram_leaves_out_the_annotation_that_would_repeat_the_name(example_data, example_cfg):
    lines = [line.strip() for line in mermaid.aggregate_diagram(example_data, example_cfg, "checkout").splitlines()]
    # Muted, and named for its context only where the context's name is another one.
    assert 'class ext_identity__Identity["Identity"]:::muted' in lines
    assert 'class ext_identity__Account["Account"]:::muted {' in lines
    index = lines.index('class ext_identity__Identity["Identity"]:::muted')
    assert lines[index + 1] != "<<Identity>>"
    assert "<<Identity>>" in lines  # still on Account


# --- events -----------------------------------------------------------------


def test_build_writes_what_an_aggregate_publishes_and_consumes_into_its_block(tmp_path, example_data, example_style):
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    page = (tmp_path / "mermaid" / "checkout.html").read_text()
    # Each event with its description and its consumers, linked and with their aggregate after a slash.
    # Each consumer gets a line of its own when one of them says why it consumes the event.
    assert ("<li><b>Publishes:</b><ul><li>OrderPlaced — Checkout turned a cart into an order. Consumed by:"
            "<ul><li><a href='search.html'>Search</a> — Opens the search history of the cart.</li>"
            "<li><a href='crm.html'>CRM</a></li></ul></li></ul></li>") in page
    # Each address as written, with its first part a link to the publisher, and why after a dash.
    assert ("<li><b>Consumes:</b><ul><li><a href='identity.html'>identity</a>/Account/AccountOpened — "
            "Links the order to the account a guest just got.</li>"
            "<li><a href='payments.html'>payments</a>/Payment/PaymentCaptured</li></ul></li>") in page


def test_build_writes_what_a_context_publishes_and_consumes_as_a_section_of_its_own(tmp_path, example_data, example_style):
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    page = (tmp_path / "mermaid" / "checkout.html").read_text()
    assert "<h2>Events</h2>" in page
    assert "<h3>Publishes (1)</h3><ul><li>CartAbandoned</li></ul>" in page
    assert ("<h3>Consumes (2)</h3><ul><li><a href='identity.html'>identity</a>/KeysRotated</li>"
            "<li><a href='search.html'>search</a>/QueryRun</li></ul>") in page
    # A domain's page has them too, and no class diagram.
    orders = (tmp_path / "mermaid" / "orders.html").read_text()
    assert "<h3>Publishes (1)</h3><ul><li>OrderSettled — An order was paid and shipped. Consumed by:<ul>" in orders
    assert ("<li><a href='checkout.html'>Checkout</a> / Cart</li>"
            "<li><a href='crm.html'>CRM</a> — Syncs the order into the ticket system.</li>") in orders
    assert 'id="aggregates-diagram"' not in orders


def test_build_writes_only_the_event_sections_that_have_something(tmp_path, example_data, example_style):
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    search = (tmp_path / "mermaid" / "search.html").read_text()
    assert "<h3>Publishes (1)</h3>" in search and "<h3>Consumes (1)</h3>" in search
    assert "<h2>Aggregates</h2>" not in search  # events but no aggregates: no aggregates section
    assert "classDiagram" in search  # and still a diagram of the events
    payments = (tmp_path / "mermaid" / "payments.html").read_text()
    assert "<h2>Events</h2>" not in payments  # its events are on the aggregate


def test_build_writes_the_events_into_the_markdown(tmp_path, example_data, example_style):
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    markdown = (tmp_path / "markdown" / "checkout.md").read_text()
    assert ("- **Publishes:**\n  - OrderPlaced — Checkout turned a cart into an order. Consumed by:\n"
            "    - [Search](search.md) — Opens the search history of the cart.\n    - [CRM](crm.md)\n") in markdown
    assert ("- **Consumes:**\n  - [identity](identity.md)/Account/AccountOpened — "
            "Links the order to the account a guest just got.\n") in markdown
    assert "## Events\n\n**Publishes (1):**\n\n- CartAbandoned\n" in markdown
    assert "**Consumes (2):**\n\n- [identity](identity.md)/KeysRotated\n- [search](search.md)/QueryRun" in markdown
    assert markdown.index("## Events") < markdown.index("classDiagram")


def test_build_leaves_the_events_out_of_a_page_without_them(tmp_path, example_data, example_style):
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    for name in ("overview", "billing") if (tmp_path / "mermaid" / "billing.html").exists() else ("overview",):
        assert "<h2>Events</h2>" not in (tmp_path / "mermaid" / f"{name}.html").read_text()
        assert "## Events" not in (tmp_path / "markdown" / f"{name}.md").read_text()


def test_aggregate_diagram_draws_what_an_aggregate_publishes_inside_its_namespace(example_data, example_cfg):
    lines = [line.strip() for line in mermaid.aggregate_diagram(example_data, example_cfg, "checkout").splitlines()]
    namespace = lines[lines.index("namespace Order {"):lines.index("namespace Cart {")]
    assert 'class checkout__ev_Order_OrderPlaced["OrderPlaced"]:::inside {' in namespace
    assert "<<event>>" in namespace
    # Linked from the root with a dashed dependency.
    assert "checkout__Order_Order ..> checkout__ev_Order_OrderPlaced" in lines


def test_aggregate_diagram_draws_what_the_context_publishes_outside_the_namespaces(example_data, example_cfg):
    source = mermaid.aggregate_diagram(example_data, example_cfg, "checkout")
    lines = [line.strip() for line in source.splitlines()]
    assert 'class checkout__ev_CartAbandoned["CartAbandoned"]:::inside {' in lines
    assert lines.index('class checkout__ev_CartAbandoned["CartAbandoned"]:::inside {') > lines.index("}")
    namespaced = source[source.index("namespace Order"):source.index("class checkout__ev_CartAbandoned")]
    assert "CartAbandoned" not in namespaced
    # Nothing links it: it belongs to the context.
    assert not any(line.endswith("checkout__ev_CartAbandoned") for line in lines if "..>" in line)


def test_aggregate_diagram_draws_what_is_consumed_muted_and_named_for_its_publisher(example_data, example_cfg):
    lines = [line.strip() for line in mermaid.aggregate_diagram(example_data, example_cfg, "checkout").splitlines()]
    assert 'class ext_identity__ev_Account_AccountOpened["AccountOpened"]:::muted {' in lines
    assert "<<event from Identity / Account>>" in lines
    # By an aggregate: linked from its root. By the context: left alone.
    assert "checkout__Order_Order ..> ext_identity__ev_Account_AccountOpened" in lines
    assert 'class ext_identity__ev_KeysRotated["KeysRotated"]:::muted {' in lines
    assert "<<event from Identity>>" in lines
    assert not any(line.endswith("ext_identity__ev_KeysRotated") for line in lines if "..>" in line)
    # A domain's event is muted too, and named for the domain, even the one this context is in.
    assert 'class ext_orders__ev_OrderSettled["OrderSettled"]:::muted {' in lines
    assert "<<event from Orders>>" in lines
    assert "checkout__Cart_Cart ..> ext_orders__ev_OrderSettled" in lines


def test_aggregate_diagram_links_an_event_consumed_from_its_own_context_to_the_class_that_is_there(example_data, example_cfg):
    data = copy.deepcopy(example_data)
    context = next(c for c in data["contexts"] if c["id"] == "checkout")
    context["aggregates"][1]["consumes"] = [{"address": "checkout/Order/OrderPlaced", "description": None,
                                             "publisher": "checkout", "level": "aggregate", "aggregate": "Order",
                                             "name": "OrderPlaced"}]
    lines = [line.strip() for line in mermaid.aggregate_diagram(data, example_cfg, "checkout").splitlines()]
    assert "checkout__Cart_Cart ..> checkout__ev_Order_OrderPlaced" in lines
    assert not any("ext_checkout" in line for line in lines)


def test_aggregate_diagram_keeps_one_muted_class_for_an_event_several_consume(example_data, example_cfg):
    source = mermaid.aggregate_diagram(example_data, example_cfg, "fulfillment")
    assert source.count('class ext_payments__ev_Payment_PaymentCaptured["PaymentCaptured"]') == 1
    assert "fulfillment__Shipment_Shipment ..> ext_payments__ev_Payment_PaymentCaptured" in source


def test_aggregate_diagram_is_made_for_a_context_with_only_events(example_data, example_cfg):
    source = mermaid.aggregate_diagram(example_data, example_cfg, "search")
    assert "namespace" not in source
    assert 'class search__ev_QueryRun["QueryRun"]:::inside {' in source
    assert "<<event from Checkout / Order>>" in source


def test_render_puts_the_events_nowhere_in_the_flowchart_of_the_aggregate_level(example_data, example_cfg):
    view = aggregate_view(example_cfg, focus="checkout", display={"foundations": "expanded"})
    source = mermaid.render(example_data, example_cfg, view)
    assert "OrderPlaced" not in source and "AccountOpened" not in source


def test_build_reads_the_consumers_of_an_event_inline_when_none_says_why(tmp_path, example_data, example_style):
    mermaid.build(example_data, example_style["mermaid"], tmp_path)
    page = (tmp_path / "mermaid" / "browsing.html").read_text()
    assert "SessionEnded — A visitor left, with or without a cart. Consumed by:<ul>" in page  # Fulfillment says why
    fulfillment = (tmp_path / "markdown" / "fulfillment.md").read_text()
    assert "  - ShipmentDispatched. Consumed by [Browsing](browsing.md)\n" in fulfillment
    assert "- [payments](payments.md)/Payment/PaymentCaptured — Releases the shipment once it is paid.\n" in \
        fulfillment.replace("  - ", "- ")
