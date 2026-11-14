"""The Mermaid layer: settings, checks, rendering and the static pages."""
import pytest

from context_mapper import mermaid

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
    assert cfg["defaults"]["level"] == "context"
    assert cfg["defaults"]["depth"] == 1
    assert cfg["defaults"]["dir"] == "both"
    assert cfg["defaults"]["child_labels"] is True
    assert cfg["defaults"]["group_by_type"] is False


def test_settings_keeps_what_the_style_file_says():
    cfg, errors = mermaid.settings({"direction": "LR", "layout": "elk", "curve": "step"})
    assert errors == []
    assert cfg["direction"] == "LR"
    assert cfg["layout"] == "elk"
    assert cfg["curve"] == "step"


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
    assert [view["id"] for view in views[:3]] == [
        "overview", "foundations-detail", "checkout-upstreams"]
    assert len(views) == 12


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


# --- build ------------------------------------------------------------------


def test_build_writes_a_page_for_every_view(tmp_path, example_data, example_style, example_cfg):
    count = mermaid.build(example_data, example_style["mermaid"], tmp_path)
    assert count == 12
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
