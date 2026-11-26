"""The model logic: normalization, levels, walks and relations."""
import datetime

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
    """`label` was the old name for a type's name; it is an unknown option now.
    An attribute is declared in the `attributes` section, not on a type."""
    errors = errors_of({
        "types": {"core": {"name": "Core", "label": "Core"}},
        "context-map": {"alpha": {"name": "Alpha", "type": "core"}},
    })
    assert any("types.core.label" in e and "unknown option" in e for e in errors), errors
    errors = errors_of({
        "types": {"core": {"name": "Core", "attributes": {"service": "x"}}},
        "context-map": {"alpha": {"name": "Alpha", "type": "core"}},
    })
    assert any("types.core.attributes" in e and "unknown option" in e for e in errors), errors


# --- normalize, attributes ---------------------------------------------------


def test_normalize_reads_the_attributes_the_example_declares(example_data):
    attributes = example_data["attributes"]
    assert attributes["service"] == {"name": "Service", "type": "text"}
    assert attributes["aggregates"] == {"name": "Aggregates", "type": "list"}
    assert attributes["metadata"] == {"name": "Metadata", "type": "any"}


def test_normalize_has_no_attributes_when_the_model_declares_none(tiny_data):
    assert tiny_data["attributes"] == {}


def test_normalize_carries_the_attributes_of_a_context(example_data):
    contexts = {c["id"]: c for c in example_data["contexts"]}
    assert contexts["checkout"]["attributes"] == {"service": "checkout-service",
                                                  "aggregates": ["Order", "Cart"]}


def test_normalize_carries_the_attributes_of_a_domain(example_data):
    domains = {d["id"]: d for d in example_data["domains"]}
    assert domains["catalog"]["attributes"] == {"aggregates": ["Product", "Inventory"]}


def test_normalize_carries_the_attributes_of_a_single_domain_to_its_context(example_data):
    """A domain with no bounded contexts is one itself, and it keeps its attributes."""
    domains = {d["id"]: d for d in example_data["domains"]}
    contexts = {c["id"]: c for c in example_data["contexts"]}
    assert domains["payments"]["attributes"] == {
        "service": "payments-service",
        "metadata": {"owned by": "Payments platform", "on-call": "#payments-support"},
    }
    assert contexts["payments"]["attributes"] == domains["payments"]["attributes"]


def test_normalize_leaves_out_the_attributes_an_entry_does_not_set(example_data):
    contexts = {c["id"]: c for c in example_data["contexts"]}
    assert "attributes" not in contexts["search"]


def test_normalize_attaches_the_attributes_of_a_cluster(tiny_model, tiny_style):
    tiny_model["attributes"] = {"owner": {"name": "Owner", "type": "text"}}
    tiny_model["clusters"]["base"]["attributes"] = {"owner": "platform"}
    data, errors = graph.normalize(tiny_model, tiny_style)
    assert errors == []
    clusters = {c["id"]: c for c in data["clusters"]}
    assert clusters["base"]["attributes"] == {"owner": "platform"}


def test_normalize_names_an_attribute_after_itself_when_no_name_is_given():
    data, errors = graph.normalize({
        "types": {"core": {"name": "Core"}},
        "attributes": {"service": {"type": "text"}},
        "context-map": {"alpha": {"name": "Alpha", "type": "core"}},
    }, STYLE)
    assert errors == []
    assert data["attributes"]["service"] == {"name": "Service", "type": "text"}


def test_normalize_coerces_the_values_of_an_attribute():
    """Everything an attribute holds is shown as text: a bool reads as true or
    false, a number as its digits, a date as its ISO form."""
    data, errors = graph.normalize({
        "types": {"core": {"name": "Core"}},
        "attributes": {
            "flag": {"type": "text"},
            "count": {"type": "text"},
            "day": {"type": "text"},
            "labels": {"type": "map"},
            "anything": {"type": "any"},
        },
        "context-map": {"alpha": {"name": "Alpha", "type": "core", "attributes": {
            "flag": True,
            "count": 3,
            "day": datetime.date(2026, 11, 18),
            "labels": {1: "one"},
            "anything": {"a": [1, True, {"b": datetime.date(2026, 11, 18)}], "c": None},
        }}},
    }, STYLE)
    assert errors == []
    contexts = {c["id"]: c for c in data["contexts"]}
    attributes = contexts["alpha"]["attributes"]
    assert attributes["flag"] == "true"
    assert attributes["count"] == "3"
    assert attributes["day"] == "2026-11-18"
    assert attributes["labels"] == {"1": "one"}
    assert attributes["anything"] == {"a": ["1", "true", {"b": "2026-11-18"}]}


# --- normalize, the error matrix --------------------------------------------


def attributes_model(attributes, values):
    """A one-type model declaring the given attributes, and one entry that
    sets the given values."""
    return {
        "types": {"core": {"name": "Core"}},
        "attributes": attributes,
        "context-map": {"alpha": {"name": "Alpha", "type": "core", "attributes": values}},
    }


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
    (
        attributes_model({"service": {"type": "text"}}, ["checkout-service"]),
        STYLE,
        "context-map.alpha.attributes: must be a map from attribute to value",
    ),
    (
        attributes_model({"service": {"type": "text"}}, {}),
        STYLE,
        "context-map.alpha.attributes is empty",
    ),
    (
        attributes_model({"service": {"type": "text"}}, {"ghost": "x"}),
        STYLE,
        "context-map.alpha.attributes.ghost: unknown attribute, it is not in `attributes`",
    ),
    (
        attributes_model({"service": {"type": "text"}}, {"service": ["a", "b"]}),
        STYLE,
        "context-map.alpha.attributes.service: a text attribute takes a single value",
    ),
    (
        attributes_model({"service": {"type": "text"}}, {"service": {"a": "b"}}),
        STYLE,
        "context-map.alpha.attributes.service: a text attribute takes a single value",
    ),
    (
        attributes_model({"tags": {"type": "list"}}, {"tags": "one"}),
        STYLE,
        "context-map.alpha.attributes.tags: a list attribute takes a list of values",
    ),
    (
        attributes_model({"tags": {"type": "list"}}, {"tags": {"a": "b"}}),
        STYLE,
        "context-map.alpha.attributes.tags: a list attribute takes a list of values",
    ),
    (
        attributes_model({"tags": {"type": "list"}}, {"tags": ["a", ["b"]]}),
        STYLE,
        "context-map.alpha.attributes.tags: list values must be single values",
    ),
    (
        attributes_model({"tags": {"type": "list"}}, {"tags": []}),
        STYLE,
        "context-map.alpha.attributes.tags: needs at least one value",
    ),
    (
        attributes_model({"labels": {"type": "map"}}, {"labels": "one"}),
        STYLE,
        "context-map.alpha.attributes.labels: a map attribute takes a map from label to value",
    ),
    (
        attributes_model({"labels": {"type": "map"}}, {"labels": ["a"]}),
        STYLE,
        "context-map.alpha.attributes.labels: a map attribute takes a map from label to value",
    ),
    (
        attributes_model({"labels": {"type": "map"}}, {"labels": {"a": ["b"]}}),
        STYLE,
        "context-map.alpha.attributes.labels values must be single values",
    ),
    (
        attributes_model({"labels": {"type": "map"}}, {"labels": {}}),
        STYLE,
        "context-map.alpha.attributes.labels: needs at least one value",
    ),
    (
        attributes_model({"service": {"type": "text"}}, {"service": None}),
        STYLE,
        "context-map.alpha.attributes.service: must have a value",
    ),
    (
        {
            "types": {"core": {"name": "Core"}},
            "attributes": {"service": {"type": "text"}},
            "clusters": {"grp": {"name": "Group", "attributes": {"ghost": "x"}}},
            "context-map": {"alpha": {"name": "Alpha", "type": "core", "cluster": "grp"}},
        },
        {**STYLE, "clusters": {"grp": {"fill": "#fff", "stroke": "#000"}}},
        "context-map.yml: clusters.grp.attributes.ghost: unknown attribute, it is not in `attributes`",
    ),
    (
        {
            "types": {"core": {"name": "Core"}},
            "attributes": {"service": {"type": "text"}},
            "context-map": {"alpha": {"name": "Alpha", "type": "core", "customFields": {"service": "x"}}},
        },
        STYLE,
        "context-map.alpha.customFields: unknown option. "
        "Known: attributes, cluster, description, downstreams, name, type, violations",
    ),
    (
        {
            "types": {"core": {"name": "Core"}},
            "attributes": {"service": {"type": "text"}},
            "context-map": {"alpha": {"name": "Alpha", "type": "core", "properties": {"service": "x"}}},
        },
        STYLE,
        "context-map.alpha.properties: unknown option. "
        "Known: attributes, cluster, description, downstreams, name, type, violations",
    ),
    (
        {
            "types": {"core": {"name": "Core"}},
            "attributes": {"service": {"type": "text"}},
            "context-map": {
                "dom": {"name": "Dom", "type": "core"},
                "ctx": {"name": "Ctx", "domain": "dom", "type": "core", "customFields": {"service": "x"}},
            },
        },
        STYLE,
        "context-map.ctx.customFields: unknown option. "
        "Known: attributes, cluster, description, domain, downstreams, name, type, violations",
    ),
    (
        {
            "types": {"core": {"name": "Core"}},
            "attributes": {"service": {"type": "text"}},
            "clusters": {"grp": {"name": "Group", "customFields": {"service": "x"}}},
            "context-map": {"alpha": {"name": "Alpha", "type": "core", "cluster": "grp"}},
        },
        {**STYLE, "clusters": {"grp": {"fill": "#fff", "stroke": "#000"}}},
        "context-map.yml: clusters.grp.customFields: unknown option. Known: attributes, name",
    ),
    (
        {
            "types": {"core": {"name": "Core"}},
            "attributes": {"service": {"type": "text"}},
            "clusters": {"grp": {"name": "Group", "properties": {"service": "x"}}},
            "context-map": {"alpha": {"name": "Alpha", "type": "core", "cluster": "grp"}},
        },
        {**STYLE, "clusters": {"grp": {"fill": "#fff", "stroke": "#000"}}},
        "context-map.yml: clusters.grp.properties: unknown option. Known: attributes, name",
    ),
    (
        {
            "types": {"core": {"name": "Core"}},
            "attributes": ["service"],
            "context-map": {"alpha": {"name": "Alpha", "type": "core"}},
        },
        STYLE,
        "context-map.yml: `attributes` must be a map from attribute id to its definition",
    ),
    (
        {
            "types": {"core": {"name": "Core"}},
            "attributes": "service",
            "context-map": {"alpha": {"name": "Alpha", "type": "core"}},
        },
        STYLE,
        "context-map.yml: `attributes` must be a map from attribute id to its definition",
    ),
    (
        {
            "types": {"core": {"name": "Core"}},
            "attributes": {"service": "text"},
            "context-map": {"alpha": {"name": "Alpha", "type": "core"}},
        },
        STYLE,
        "context-map.yml: attributes.service: needs a map with `type`",
    ),
    (
        {
            "types": {"core": {"name": "Core"}},
            "attributes": {"service": {"name": "Service"}},
            "context-map": {"alpha": {"name": "Alpha", "type": "core"}},
        },
        STYLE,
        "context-map.yml: attributes.service: needs a type",
    ),
    (
        {
            "types": {"core": {"name": "Core"}},
            "attributes": {"service": {"type": "number"}},
            "context-map": {"alpha": {"name": "Alpha", "type": "core"}},
        },
        STYLE,
        "context-map.yml: attributes.service.type: must be one of any, list, map, text",
    ),
    (
        {
            "types": {"core": {"name": "Core"}},
            "attributes": {"service": {"type": "text", "unit": "x"}},
            "context-map": {"alpha": {"name": "Alpha", "type": "core"}},
        },
        STYLE,
        "context-map.yml: attributes.service.unit: unknown option. Known: name, type",
    ),
])
def test_normalize_rejects_a_broken_model(model, style, expected):
    errors = errors_of(model, style)
    assert any(expected in err for err in errors), errors


# --- normalize, violations --------------------------------------------------


def with_violations(violations, **extra):
    """alpha, beta and gamma, with `violations` set on alpha."""
    entries = {
        "alpha": {"name": "Alpha", "type": "core", "violations": violations},
        "beta": {"name": "Beta", "type": "core"},
        "gamma": {"name": "Gamma", "type": "core"},
    }
    for entry_id, entry in extra.items():
        entries[entry_id] = {**entries[entry_id], **entry}
    return model(**entries)


def test_normalize_keeps_a_violation_apart_from_the_dependencies():
    data, errors = graph.normalize(with_violations({"beta": "Alpha calls Beta anyway.", "gamma": None}), STYLE)
    assert errors == []
    assert data["violations"] == [
        {"from": "alpha", "to": "beta", "comment": "Alpha calls Beta anyway."},
        {"from": "alpha", "to": "gamma", "comment": None},
    ]
    assert data["edges"] == []


def test_normalize_reads_the_violations_of_the_example(example_data):
    assert example_data["violations"] == [
        {"from": "catalog", "to": "checkout",
         "comment": "Reads the open carts to decide what to keep in its cache."}]


def test_normalize_lets_a_violation_close_a_cycle_the_dependencies_would_not():
    """Beta depends on Alpha, and Alpha depends on Beta against the direction: written as a
    dependency it would be a cycle and fail the build, which is why it is written as a violation."""
    data, errors = graph.normalize(with_violations({"beta": "Calls back."}, alpha={"downstreams": {"beta": "x"}}), STYLE)
    assert errors == []
    assert [(edge["from"], edge["to"]) for edge in data["edges"]] == [("beta", "alpha")]
    assert [(rule["from"], rule["to"]) for rule in data["violations"]] == [("alpha", "beta")]
    assert graph.find_cycle(graph.level_graph(data, "context")) is None
    _, errors = graph.normalize(model(
        alpha={"name": "Alpha", "type": "core", "downstreams": {"beta": "x"}},
        beta={"name": "Beta", "type": "core", "downstreams": {"alpha": "x"}}), STYLE)
    assert any("dependency cycle" in err for err in errors), errors


@pytest.mark.parametrize("violations, extra, expected", [
    ({"ghost": "x"}, {}, "unknown domain or context 'ghost' in context-map.alpha.violations"),
    ({"alpha": "x"}, {}, "context-map.alpha.violations.alpha: an entry can't violate its direction toward itself"),
    ({"beta": 42}, {}, "context-map.alpha.violations.beta: must be a comment string, or nothing"),
    ({}, {}, "context-map.alpha: `violations` is empty"),
    (["beta"], {}, "context-map.alpha: `violations` must be a map"),
    ({"beta": "x"}, {"beta": {"downstreams": {"alpha": "y"}}},
     "context-map.alpha.violations.beta: 'alpha' depends on 'beta' already"),
])
def test_normalize_rejects_a_broken_violation(violations, extra, expected):
    errors = errors_of(with_violations(violations, **extra))
    assert any(expected in err for err in errors), errors


def test_level_graph_does_not_walk_through_a_violation():
    data, errors = graph.normalize(with_violations({"beta": "x"}), STYLE)
    assert errors == []
    context = graph.level_graph(data, "context")
    assert context["edges"] == []
    assert [(rule["from"], rule["to"]) for rule in context["violations"]] == [("alpha", "beta")]
    assert graph.walk(context, {"alpha"}, 99, "both", set()) == {"alpha"}


def test_level_graph_lifts_a_violation_to_the_domains(tiny_model, tiny_style):
    tiny_model["context-map"]["web_ui"]["violations"] = {"core_db": "UI reads the db."}
    tiny_model["context-map"]["solo"]["violations"] = {"core_lib": "x", "core_db": "y"}
    data, errors = graph.normalize(tiny_model, tiny_style)
    assert errors == []
    violations = graph.level_graph(data, "domain")["violations"]
    assert [(rule["from"], rule["to"], len(rule["via"])) for rule in violations] == [
        ("web", "core", 1), ("solo", "core", 2)]


def test_level_graph_drops_a_violation_inside_a_domain(tiny_model, tiny_style):
    tiny_model["context-map"]["core_lib"]["violations"] = {"core_db": "The lib calls the db."}
    data, errors = graph.normalize(tiny_model, tiny_style)
    assert errors == []
    assert len(graph.level_graph(data, "context")["violations"]) == 1
    assert graph.level_graph(data, "domain")["violations"] == []


def test_level_graph_drops_a_violation_the_domains_have_anyway(tiny_model, tiny_style):
    """Core depends on Web through Core DB → Web API, so Core DB → Web UI adds no arrow between them."""
    tiny_model["context-map"]["core_db"]["violations"] = {"web_ui": "x"}
    data, errors = graph.normalize(tiny_model, tiny_style)
    assert errors == []
    assert len(graph.level_graph(data, "context")["violations"]) == 1
    assert graph.level_graph(data, "domain")["violations"] == []


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


# --- normalize, relationship roles ------------------------------------------


def with_roles(**roles):
    """alpha, beta and gamma, with beta depending on alpha, carrying `roles`."""
    return model(
        alpha={"name": "Alpha", "type": "core", "downstreams": {"beta": {"comment": "x", **roles}}},
        beta={"name": "Beta", "type": "core"},
        gamma={"name": "Gamma", "type": "core"},
    )


def test_normalize_gives_a_dependency_no_roles_unless_it_names_some():
    data, errors = graph.normalize(with_roles(), STYLE)
    assert errors == []
    assert data["edges"][0]["upstream"] == []
    assert data["edges"][0]["downstream"] == []


def test_normalize_reads_the_roles_of_a_dependency_in_the_canonical_order():
    data, errors = graph.normalize(with_roles(upstream=["PublishedLanguage", "OpenHostService"],
                                              downstream=["AnticorruptionLayer"]), STYLE)
    assert errors == []
    assert data["edges"][0]["upstream"] == ["OpenHostService", "PublishedLanguage"]
    assert data["edges"][0]["downstream"] == ["AnticorruptionLayer"]


def test_normalize_reads_the_roles_of_the_example(example_data):
    edge = next(edge for edge in example_data["edges"] if (edge["from"], edge["to"]) == ("checkout", "identity"))
    assert edge["upstream"] == ["OpenHostService", "PublishedLanguage"]  # written the other way round
    assert edge["downstream"] == ["AnticorruptionLayer"]


def test_normalize_hands_the_page_the_codes_and_names_of_the_roles(example_data):
    assert example_data["roles"]["OpenHostService"] == {"code": "OHS", "name": "Open Host Service", "side": "upstream"}
    assert example_data["roles"]["AnticorruptionLayer"] == {"code": "ACL", "name": "Anticorruption Layer",
                                                            "side": "downstream"}
    assert list(example_data["roles"]) == ["OpenHostService", "PublishedLanguage", "Supplier",
                                           "AnticorruptionLayer", "Conformist", "Customer"]


@pytest.mark.parametrize("side", ["upstream", "downstream"])
def test_normalize_accepts_an_empty_list_of_roles(side):
    data, errors = graph.normalize(with_roles(**{side: []}), STYLE)
    assert errors == []
    assert data["edges"][0][side] == []


@pytest.mark.parametrize("roles, expected", [
    ({"upstream": "OpenHostService"},
     "context-map.alpha.downstreams.beta.upstream: must be a list of roles. "
     "Known: OpenHostService, PublishedLanguage, Supplier"),
    ({"downstream": {"Conformist": True}},
     "context-map.alpha.downstreams.beta.downstream: must be a list of roles. "
     "Known: AnticorruptionLayer, Conformist, Customer"),
    ({"upstream": None}, "context-map.alpha.downstreams.beta.upstream: must be a list of roles"),
    ({"upstream": ["Gateway"]},
     "context-map.alpha.downstreams.beta.upstream: unknown role 'Gateway'. "
     "Known: OpenHostService, PublishedLanguage, Supplier"),
    ({"downstream": ["ACL"]},
     "context-map.alpha.downstreams.beta.downstream: unknown role 'ACL'. "
     "Known: AnticorruptionLayer, Conformist, Customer"),
    ({"upstream": [42]}, "context-map.alpha.downstreams.beta.upstream: a role is a string, not 42"),
    ({"upstream": ["Customer"], "downstream": ["Customer"]},
     "context-map.alpha.downstreams.beta.upstream: 'Customer' is a downstream role, it goes under `downstream`"),
    ({"downstream": ["Supplier"]},
     "context-map.alpha.downstreams.beta.downstream: 'Supplier' is an upstream role, it goes under `upstream`"),
    ({"upstream": ["OpenHostService", "OpenHostService"]},
     "context-map.alpha.downstreams.beta.upstream: 'OpenHostService' is listed more than once"),
    ({"downstream": ["Conformist", "Conformist"]},
     "context-map.alpha.downstreams.beta.downstream: 'Conformist' is listed more than once"),
    ({"downstream": ["AnticorruptionLayer", "Conformist"]},
     "context-map.alpha.downstreams.beta.downstream: AnticorruptionLayer and Conformist exclude each other"),
    ({"upstream": ["Supplier"]},
     "context-map.alpha.downstreams.beta: Supplier and Customer come as a pair, it needs Customer under `downstream`"),
    ({"downstream": ["Customer"]},
     "context-map.alpha.downstreams.beta: Supplier and Customer come as a pair, it needs Supplier under `upstream`"),
    ({"upstream": ["Supplier"], "downstream": ["Customer", "Conformist"]},
     "context-map.alpha.downstreams.beta: Conformist can't go with Customer or Supplier"),
    ({"downstream": ["Conformist", "Customer"]},
     "context-map.alpha.downstreams.beta: Conformist can't go with Customer or Supplier"),
])
def test_normalize_rejects_broken_roles(roles, expected):
    errors = errors_of(with_roles(**roles))
    assert any(expected in err for err in errors), errors


def test_normalize_reports_each_broken_role_once_and_nothing_else():
    errors = errors_of(with_roles(upstream=["Gateway"], downstream=["Customer"]))
    assert errors == ["context-map.alpha.downstreams.beta.upstream: unknown role 'Gateway'. "
                      "Known: OpenHostService, PublishedLanguage, Supplier"]


def test_normalize_accepts_a_supplier_and_a_customer_together_with_the_other_roles():
    data, errors = graph.normalize(with_roles(upstream=["OpenHostService", "PublishedLanguage", "Supplier"],
                                              downstream=["AnticorruptionLayer", "Customer"]), STYLE)
    assert errors == []
    assert data["edges"][0]["downstream"] == ["AnticorruptionLayer", "Customer"]


def test_normalize_names_the_roles_in_the_known_options_of_a_dependency():
    errors = errors_of(with_roles(speed="fast"))
    assert any("context-map.alpha.downstreams.beta.speed: unknown option. "
               "Known: comment, style, upstream, downstream" in err for err in errors), errors


@pytest.mark.parametrize("violation, expected", [
    ({"upstream": ["OpenHostService"]}, "a violation takes no roles, only a comment string"),
    ({"comment": "x", "downstream": ["AnticorruptionLayer"]}, "a violation takes no roles, only a comment string"),
    ({"comment": "x"}, "context-map.alpha.violations.beta: must be a comment string, or nothing"),
])
def test_normalize_gives_a_violation_no_roles(violation, expected):
    errors = errors_of(with_violations({"beta": violation}))
    assert any(f"context-map.alpha.violations.beta: {expected}" in err or expected in err for err in errors), errors


def test_a_violation_never_carries_roles():
    data, errors = graph.normalize(with_violations({"beta": "x"}), STYLE)
    assert errors == []
    assert "upstream" not in data["violations"][0]
    assert "downstream" not in data["violations"][0]


# --- merging roles ----------------------------------------------------------


def lifted(tiny_model, tiny_style, first, second):
    """The domain-level edge from Core to Web, which stands for `core_lib → web_ui` and `core_db → web_api`,
    once those two carry the given roles (None: no roles at all)."""
    for owner, downstream, roles in (("web_ui", "core_lib", first), ("web_api", "core_db", second)):
        tiny_model["context-map"][owner]["downstreams"] = {downstream: {"comment": "x", **(roles or {})}}
    data, errors = graph.normalize(tiny_model, tiny_style)
    assert errors == []
    edges = graph.level_graph(data, "domain")["edges"]
    assert [(edge["from"], edge["to"]) for edge in edges] == [("core", "web")]
    return edges[0]


OPEN_HOST = {"upstream": ["OpenHostService"], "downstream": ["AnticorruptionLayer"]}


def test_a_merged_edge_keeps_the_roles_every_dependency_carries(tiny_model, tiny_style):
    edge = lifted(tiny_model, tiny_style, OPEN_HOST, dict(OPEN_HOST))
    assert (edge["upstream"], edge["downstream"]) == (["OpenHostService"], ["AnticorruptionLayer"])


def test_a_merged_edge_drops_the_roles_when_the_dependencies_differ(tiny_model, tiny_style):
    other = {"upstream": ["PublishedLanguage"], "downstream": ["AnticorruptionLayer"]}
    edge = lifted(tiny_model, tiny_style, OPEN_HOST, other)
    assert (edge["upstream"], edge["downstream"]) == ([], [])


def test_a_merged_edge_drops_the_roles_when_one_dependency_has_none(tiny_model, tiny_style):
    edge = lifted(tiny_model, tiny_style, OPEN_HOST, None)
    assert (edge["upstream"], edge["downstream"]) == ([], [])


def test_a_merged_edge_drops_the_roles_when_only_one_side_agrees(tiny_model, tiny_style):
    edge = lifted(tiny_model, tiny_style, OPEN_HOST, {"downstream": ["AnticorruptionLayer"]})
    assert (edge["upstream"], edge["downstream"]) == ([], [])


def test_a_merged_edge_without_any_roles_has_none(tiny_model, tiny_style):
    edge = lifted(tiny_model, tiny_style, None, None)
    assert (edge["upstream"], edge["downstream"]) == ([], [])


def test_a_dependency_between_domains_keeps_its_roles(tiny_model, tiny_style):
    tiny_model["context-map"]["solo"]["downstreams"] = {"web": {"comment": "x", **OPEN_HOST}}
    data, errors = graph.normalize(tiny_model, tiny_style)
    assert errors == []
    edge = next(edge for edge in graph.level_graph(data, "domain")["edges"] if (edge["from"], edge["to"]) == ("web", "solo"))
    assert (edge["upstream"], edge["downstream"]) == (["OpenHostService"], ["AnticorruptionLayer"])


def test_a_dependency_at_context_level_keeps_its_roles(tiny_model, tiny_style):
    lifted(tiny_model, tiny_style, OPEN_HOST, None)
    data, _ = graph.normalize(tiny_model, tiny_style)
    edges = {(edge["from"], edge["to"]): edge for edge in graph.level_graph(data, "context")["edges"]}
    assert edges[("core_lib", "web_ui")]["upstream"] == ["OpenHostService"]
    assert edges[("core_db", "web_api")]["upstream"] == []


def test_shared_roles_of_nothing_is_nothing():
    assert graph.shared_roles([]) == ([], [])


def test_role_text_spells_the_roles_out_in_the_canonical_order():
    assert graph.role_text(["OpenHostService", "PublishedLanguage"], ["AnticorruptionLayer"]) == \
        "Open Host Service, Published Language \u2192 Anticorruption Layer"
    assert graph.role_text(["Supplier"], []) == "Supplier (upstream)"
    assert graph.role_text([], ["Conformist"]) == "Conformist (downstream)"
    assert graph.role_text([], []) == ""


def test_role_codes_are_the_short_ones():
    assert graph.role_codes(["OpenHostService", "PublishedLanguage", "Supplier"],
                            ["AnticorruptionLayer", "Conformist", "Customer"]) == (
        ["OHS", "PL", "S"], ["ACL", "CF", "C"])


def test_relation_edges_carry_the_roles_of_each_dependency(example_data):
    ups, downs = graph.relation_edges(example_data, "checkout")
    by_target = {edge["to"]: edge for edge in ups}
    assert by_target["identity"]["upstream"] == ["OpenHostService", "PublishedLanguage"]
    assert by_target["payments"]["downstream"] == ["Customer"]
    assert by_target["catalog"]["upstream"] == []
    assert downs == []
