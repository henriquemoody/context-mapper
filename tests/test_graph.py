"""The model logic: normalization, levels, walks and relations."""
import pytest

from context_mapper import graph

STYLE = {"types": {"core": {"fill": "#dedaff", "stroke": "#6631d7"}}}


def model(**context_map):
    """A one-type model with the given context-map entries."""
    return {
        "types": {"core": {"name": "Core"}},
        "context-map": context_map or {"alpha": {"name": "Alpha", "type": "core"}},
    }


def errors_of(model, style=None):
    _, errors = graph.normalize(model, style if style is not None else STYLE)
    return errors


# --- classdef ----------------------------------------------------------------


def test_classdef_appends_the_defaults_when_absent():
    assert graph.classdef({"fill": "#fff"}) == "fill:#fff,color:#1a1a1a"


def test_classdef_keeps_a_default_that_is_set():
    assert graph.classdef({"fill": "#fff", "color": "#000"}) == "fill:#fff,color:#000"


def test_classdef_keeps_the_order_the_attributes_were_written_in():
    assert graph.classdef({"stroke": "#000", "fill": "#fff"}) == "stroke:#000,fill:#fff,color:#1a1a1a"


# --- normalize, the example -------------------------------------------------


def test_normalize_reads_the_example(example_data):
    assert len(example_data["domains"]) == 5
    assert len(example_data["contexts"]) == 7
    assert len(example_data["edges"]) == 6


def test_normalize_finds_the_cluster_members(example_data):
    clusters = {c["id"]: c for c in example_data["clusters"]}
    assert clusters["foundations"]["members"] == ["identity", "payments"]
    assert clusters["foundations"]["name"] == "Shared Foundations"


def test_normalize_marks_a_domain_without_contexts_as_single(example_data):
    domains = {d["id"]: d for d in example_data["domains"]}
    assert domains["identity"]["single"] is True
    assert domains["payments"]["single"] is True
    assert domains["crm"]["single"] is True
    assert domains["catalog"]["single"] is False
    assert domains["orders"]["single"] is False
    assert domains["catalog"]["contexts"] == ["browsing", "search"]
    assert domains["orders"]["contexts"] == ["checkout", "fulfillment"]


def test_normalize_lets_a_context_inherit_the_type_of_its_domain(example_data):
    contexts = {c["id"]: c for c in example_data["contexts"]}
    assert contexts["browsing"]["type"] == "core"
    assert contexts["search"]["type"] == "core"
    assert contexts["checkout"]["type"] == "core"


def test_normalize_lets_a_context_override_the_type_of_its_domain(example_data):
    contexts = {c["id"]: c for c in example_data["contexts"]}
    assert contexts["fulfillment"]["type"] == "supporting"


def test_normalize_keeps_the_comment_and_the_style_of_an_edge(example_data):
    edges = {(e["from"], e["to"]): e for e in example_data["edges"]}
    edge = edges[("checkout", "catalog")]
    assert edge["comment"] == "Reads prices and availability at checkout time."
    assert edge["style"] == "dotted"
    assert edges[("checkout", "identity")]["style"] == "solid"
    assert edges[("crm", "identity")]["comment"] is None


def test_normalize_carries_the_descriptions_through(example_data):
    domains = {d["id"]: d for d in example_data["domains"]}
    contexts = {c["id"]: c for c in example_data["contexts"]}
    assert domains["catalog"]["description"] == (
        "Everything that can be bought, with its prices and availability.")
    assert domains["identity"]["description"] == (
        "Accounts and logins. Everyone signs in here.")
    assert contexts["checkout"]["description"] == (
        "Takes a cart and turns it into a paid order.")
    assert contexts["browsing"]["description"] is None


def test_normalize_accepts_the_current_names_only():
    """`label` was the old name for a type's name; it is an unknown option now."""
    errors = errors_of({
        "types": {"core": {"name": "Core", "label": "Core"}},
        "context-map": {"alpha": {"name": "Alpha", "type": "core"}},
    })
    assert any("types.core.label" in e and "unknown option" in e for e in errors), errors


# --- normalize, the error matrix --------------------------------------------


@pytest.mark.parametrize("model, style, expected", [
    (
        {"context-map": {"alpha": {"name": "Alpha", "type": "core"}}},
        {},
        "`types` is missing or empty",
    ),
    (
        {"types": {"core": {"name": "Core"}}},
        {},
        "`context-map` is missing or empty",
    ),
    (
        model(alpha={"name": "Alpha", "type": "nope"}),
        STYLE,
        "context-map.alpha: unknown type 'nope'",
    ),
    (
        model(
            dom={"name": "Dom", "type": "core"},
            ctx={"name": "Ctx", "domain": "dom", "type": "nope"},
        ),
        STYLE,
        "context 'ctx': unknown type 'nope'",
    ),
    (
        model(alpha={"type": "core"}),
        STYLE,
        "context-map.alpha: needs a name",
    ),
    (
        model(alpha={"name": "Alpha"}),
        STYLE,
        "context-map.alpha: needs a type",
    ),
    (
        model(alpha={"name": "Alpha", "type": "core", "bogus": 1}),
        STYLE,
        "context-map.alpha.bogus: unknown option",
    ),
    (
        {
            "types": {"core": {"name": "Core", "bogus": 1}},
            "context-map": {"alpha": {"name": "Alpha", "type": "core"}},
        },
        STYLE,
        "types.core.bogus: unknown option",
    ),
    (
        {
            "types": {"core": {"name": "Core"}},
            "clusters": {"grp": {"name": "Group", "bogus": 1}},
            "context-map": {"alpha": {"name": "Alpha", "type": "core"}},
        },
        STYLE,
        "clusters.grp.bogus: unknown option",
    ),
    (
        model(
            dom={"name": "Dom", "type": "core"},
            ctx={"name": "Ctx", "domain": "dom", "type": "core", "cluster": "grp"},
        ),
        {**STYLE, "clusters": {"grp": {"fill": "#fff", "stroke": "#000"}}},
        "a bounded context is inside its domain already",
    ),
    (
        model(ctx={"name": "Ctx", "domain": "nowhere", "type": "core"}),
        STYLE,
        "unknown domain 'nowhere'",
    ),
    (
        {
            "types": {"core": {"name": "Core"}},
            "clusters": {"grp": {"name": "Group"}},
            "context-map": {"grp": {"name": "Group", "type": "core"}},
        },
        {**STYLE, "clusters": {"grp": {"fill": "#fff", "stroke": "#000"}}},
        "'grp' is also an entry in context-map",
    ),
    (
        model(),
        {**STYLE, "types": {**STYLE["types"], "ghost": {"fill": "#fff", "stroke": "#000"}}},
        "types.ghost: unknown type",
    ),
    (
        model(),
        {**STYLE, "clusters": {"ghost": {"fill": "#fff", "stroke": "#000"}}},
        "clusters.ghost: unknown cluster",
    ),
    (
        model(),
        {**STYLE, "context-map": {"ghost": {"fill": "#fff", "stroke": "#000"}}},
        "context-map.ghost: unknown entry",
    ),
    (
        {
            "types": {"core": {"name": "Core"}},
            "clusters": {"grp": {"name": "Group"}},
            "context-map": {"alpha": {"name": "Alpha", "type": "core"}},
        },
        {**STYLE, "clusters": {"grp": {"fill": "#fff", "stroke": "#000"}}},
        "clusters.grp: no entry points at it with `cluster:`",
    ),
    (
        model(alpha={"name": "Alpha", "type": "core", "downstreams": {}}),
        STYLE,
        "`downstreams` is empty",
    ),
    (
        model(alpha={"name": "Alpha", "type": "core", "downstreams": ["beta"]}),
        STYLE,
        "`downstreams` must be a map from downstream to comment",
    ),
    (
        model(
            alpha={"name": "Alpha", "type": "core", "downstreams": {"beta": 42}},
            beta={"name": "Beta", "type": "core"},
        ),
        STYLE,
        "must be a comment string, or a map with `comment` and `style`",
    ),
    (
        model(alpha={"name": "Alpha", "type": "core", "downstreams": {"ghost": "x"}}),
        STYLE,
        "unknown domain or context 'ghost'",
    ),
    (
        model(
            alpha={"name": "Alpha", "type": "core", "downstreams": {"beta": "x"}},
            beta={"name": "Beta", "type": "core", "downstreams": {"alpha": "y"}},
        ),
        STYLE,
        "dependency cycle: alpha -> beta -> alpha",
    ),
    (
        model(
            dom={"name": "Dom", "type": "core"},
            ctx={"name": "Ctx", "domain": "dom", "type": "core"},
        ),
        {**STYLE, "context-map": {"ctx": {"defaultDisplay": "collapsed"}}},
        "context-map.ctx.defaultDisplay must be one of expanded, hidden",
    ),
    (
        model(solo={"name": "Solo", "type": "core"}),
        {**STYLE, "context-map": {"solo": {"defaultDisplay": "contents"}}},
        "context-map.solo.defaultDisplay must be one of expanded, hidden",
    ),
    (
        model(
            dom={"name": "Dom", "type": "core"},
            ctx={"name": "Ctx", "domain": "dom", "type": "core"},
        ),
        {**STYLE, "context-map": {"ctx": {"bogus": 1}}},
        "context-map.ctx.bogus: unknown option",
    ),
])
def test_normalize_rejects_a_broken_model(model, style, expected):
    errors = errors_of(model, style)
    assert any(expected in err for err in errors), errors


# --- normalize, defaultDisplay ----------------------------------------------


def test_normalize_keeps_a_bounded_contexts_default_display_and_style():
    data, errors = graph.normalize(
        model(dom={"name": "Dom", "type": "core"}, ctx={"name": "Ctx", "domain": "dom", "type": "core"}),
        {**STYLE, "context-map": {"ctx": {"fill": "#fff", "defaultDisplay": "hidden"}}})
    assert errors == []
    contexts = {context["id"]: context for context in data["contexts"]}
    assert contexts["ctx"]["defaultDisplay"] == "hidden"
    assert contexts["ctx"]["mermaid_style"] == "fill:#fff,color:#1a1a1a"


def test_normalize_accepts_every_display_for_a_domain_that_holds_contexts():
    data, errors = graph.normalize(
        model(dom={"name": "Dom", "type": "core"}, ctx={"name": "Ctx", "domain": "dom", "type": "core"}),
        {**STYLE, "context-map": {"dom": {"defaultDisplay": "collapsed"}}})
    assert errors == []
    assert {d["id"]: d for d in data["domains"]}["dom"]["defaultDisplay"] == "collapsed"


def test_normalize_carries_a_single_domains_default_display_to_its_context():
    """A single domain is a bounded context: its entry's defaultDisplay hides that one box."""
    data, errors = graph.normalize(
        model(solo={"name": "Solo", "type": "core"}),
        {**STYLE, "context-map": {"solo": {"defaultDisplay": "hidden"}}})
    assert errors == []
    domains = {domain["id"]: domain for domain in data["domains"]}
    contexts = {context["id"]: context for context in data["contexts"]}
    assert domains["solo"]["defaultDisplay"] == "hidden"
    assert contexts["solo"]["defaultDisplay"] == "hidden"


# --- find_cycle -------------------------------------------------------------


def test_find_cycle_finds_a_cycle():
    g = {
        "nodes": {"a", "b", "c"},
        "edges": [
            {"from": "a", "to": "b"},
            {"from": "b", "to": "c"},
            {"from": "c", "to": "a"},
        ],
        "child_of": {},
    }
    cycle = graph.find_cycle(g)
    assert cycle is not None
    assert set(cycle) == {"a", "b", "c"}


def test_find_cycle_returns_nothing_for_an_acyclic_graph():
    g = {
        "nodes": {"a", "b", "c"},
        "edges": [
            {"from": "a", "to": "b"},
            {"from": "b", "to": "c"},
        ],
        "child_of": {},
    }
    assert graph.find_cycle(g) is None


# --- level_graph ------------------------------------------------------------


def test_level_graph_at_domain_level_lifts_and_merges(tiny_data):
    g = graph.level_graph(tiny_data, "domain")
    assert set(g["nodes"]) == {"core", "web", "solo"}
    assert len(g["edges"]) == 1
    edge = g["edges"][0]
    assert (edge["from"], edge["to"]) == ("core", "web")
    assert edge["styles"] == {"solid", "dotted"}
    assert len(edge["via"]) == 2


def test_level_graph_at_domain_level_drops_the_edges_inside_a_domain(tiny_data):
    g = graph.level_graph(tiny_data, "domain")
    assert all(edge["from"] != edge["to"] for edge in g["edges"])
    assert ("core_db", "core_lib") not in [
        (edge["from"], edge["to"]) for edge in g["edges"]]


def test_level_graph_at_context_level_keeps_the_edges_as_written(tiny_data):
    g = graph.level_graph(tiny_data, "context")
    pairs = sorted((edge["from"], edge["to"]) for edge in g["edges"])
    assert pairs == [
        ("core_db", "core_lib"),
        ("core_db", "web_api"),
        ("core_lib", "web_ui"),
    ]
    styles = {(edge["from"], edge["to"]): edge["styles"] for edge in g["edges"]}
    assert styles[("core_db", "web_api")] == {"dotted"}


# --- walk -------------------------------------------------------------------


def test_walk_without_starts_returns_every_node(tiny_data):
    g = graph.level_graph(tiny_data, "context")
    assert graph.walk(g, set(), 1, "both", set()) == set(g["nodes"])


def test_walk_without_starts_leaves_out_the_hidden_nodes(tiny_data):
    g = graph.level_graph(tiny_data, "context")
    assert graph.walk(g, set(), 1, "both", {"web_api"}) == set(g["nodes"]) - {"web_api"}


def test_walk_stops_after_the_given_number_of_hops(tiny_data):
    g = graph.level_graph(tiny_data, "context")
    assert graph.walk(g, {"web_ui"}, 1, "both", set()) == {"web_ui", "core_lib"}
    assert graph.walk(g, {"web_ui"}, 2, "both", set()) == {"web_ui", "core_lib", "core_db"}


def test_walk_follows_the_direction_it_is_given(tiny_data):
    g = graph.level_graph(tiny_data, "context")
    assert graph.walk(g, {"core_db"}, 1, "up", set()) == {"core_db", "core_lib", "web_api"}
    assert graph.walk(g, {"core_db"}, 1, "down", set()) == {"core_db"}
    assert graph.walk(g, {"core_db"}, 1, "both", set()) == {"core_db", "core_lib", "web_api"}


def test_walk_always_shows_a_start_even_when_it_is_hidden(tiny_data):
    g = graph.level_graph(tiny_data, "context")
    assert "web_api" in graph.walk(g, {"web_api"}, 1, "both", {"web_api"})


def test_walk_goes_on_from_the_contexts_of_a_domain_it_reaches():
    # `hub` is used by the whole of `web`, a domain, and `web_ui` has a user of its own.
    data, errors = graph.normalize({
        "types": {"core": {"name": "Core"}},
        "context-map": {
            "hub": {"name": "Hub", "type": "core", "downstreams": {"web": "Everything in Web uses it."}},
            "web": {"name": "Web", "type": "core"},
            "web_ui": {"name": "Web UI", "domain": "web", "downstreams": {"app": "App embeds the UI."}},
            "web_api": {"name": "Web API", "domain": "web"},
            "app": {"name": "App", "type": "core"},
        },
    }, STYLE)
    assert not errors
    g = graph.level_graph(data, "context")
    assert graph.walk(g, {"hub"}, 1, "down", set()) == {"hub", "web", "web_ui", "web_api"}
    assert graph.walk(g, {"hub"}, 2, "down", set()) == {"hub", "web", "web_ui", "web_api", "app"}
    assert graph.walk(g, {"hub"}, 2, "down", {"web_api"}) == {"hub", "web", "web_ui", "app"}


# --- focus_set --------------------------------------------------------------


def test_focus_set_of_a_domain_opens_its_contexts(tiny_data):
    assert graph.focus_set(tiny_data, "context", "web") == {"web", "web_ui", "web_api"}


def test_focus_set_of_a_domain_at_domain_level_is_the_domain(tiny_data):
    assert graph.focus_set(tiny_data, "domain", "web") == {"web"}


def test_focus_set_of_a_cluster_opens_its_members(tiny_data):
    assert graph.focus_set(tiny_data, "domain", "base") == {"base", "core"}


def test_focus_set_of_a_cluster_at_context_level_opens_the_member_contexts(tiny_data):
    assert graph.focus_set(tiny_data, "context", "base") == {
        "base", "core", "core_lib", "core_db"}


def test_focus_set_of_a_single_domain_is_the_domain(tiny_data):
    assert graph.focus_set(tiny_data, "context", "solo") == {"solo"}
    assert graph.focus_set(tiny_data, "domain", "solo") == {"solo"}


def test_focus_set_of_an_unknown_id_is_that_id(tiny_data):
    assert graph.focus_set(tiny_data, "context", "nowhere") == {"nowhere"}


def test_focus_set_of_an_unknown_id_at_domain_level_has_no_owner(tiny_data):
    """At domain level the focus is looked up in the owner map, so it raises."""
    with pytest.raises(KeyError):
        graph.focus_set(tiny_data, "domain", "nowhere")


def test_focus_set_without_a_focus_is_empty(tiny_data):
    assert graph.focus_set(tiny_data, "context", None) == set()


# --- descendants ------------------------------------------------------------


def test_descendants_resolves_nested_containers(tiny_data):
    context_level = graph.level_graph(tiny_data, "context")
    assert graph.descendants(context_level, {"base"}) == {
        "base", "core", "core_lib", "core_db"}
    domain_level = graph.level_graph(tiny_data, "domain")
    assert graph.descendants(domain_level, {"base"}) == {"base", "core"}


# --- relations --------------------------------------------------------------


def test_relations_of_a_context(example_data):
    ups, downs = graph.relations(example_data, "checkout")
    assert ups == ["catalog", "identity", "payments"]
    assert downs == []


def test_relations_sorts_by_name(example_data):
    ups, downs = graph.relations(example_data, "identity")
    assert ups == []
    # By name, not by id: "CRM" comes before "Checkout".
    assert downs == ["crm", "checkout"]


def test_relations_of_a_domain_are_lifted_to_the_domain_level(example_data):
    ups, downs = graph.relations(example_data, "orders")
    assert ups == ["catalog", "identity", "payments"]
    assert downs == ["crm"]
