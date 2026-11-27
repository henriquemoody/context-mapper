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
        "Known: aggregates, attributes, cluster, consumes, description, downstreams, name, partnerships, publishes, sharedKernels, type, violations",
    ),
    (
        {
            "types": {"core": {"name": "Core"}},
            "attributes": {"service": {"type": "text"}},
            "context-map": {"alpha": {"name": "Alpha", "type": "core", "properties": {"service": "x"}}},
        },
        STYLE,
        "context-map.alpha.properties: unknown option. "
        "Known: aggregates, attributes, cluster, consumes, description, downstreams, name, partnerships, publishes, sharedKernels, type, violations",
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
        "Known: aggregates, attributes, cluster, consumes, description, domain, downstreams, name, partnerships, publishes, sharedKernels, type, violations",
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


# --- normalize, partnerships and shared kernels ------------------------------


def with_links(key="partnerships", links=None, **extra):
    """alpha, beta and gamma, with `key` set on alpha."""
    entries = {
        "alpha": {"name": "Alpha", "type": "core", key: links if links is not None else {"beta": "Plan together."}},
        "beta": {"name": "Beta", "type": "core"},
        "gamma": {"name": "Gamma", "type": "core"},
    }
    for entry_id, entry in extra.items():
        entries[entry_id] = {**entries[entry_id], **entry}
    return model(**entries)


def test_normalize_reads_a_partnership_and_a_shared_kernel_apart_from_the_dependencies():
    data, errors = graph.normalize(with_links(links={"beta": "Plan together.", "gamma": None}), STYLE)
    assert errors == []
    assert data["symmetric"] == [
        {"kind": "partnership", "a": "alpha", "b": "beta", "comment": "Plan together."},
        {"kind": "partnership", "a": "alpha", "b": "gamma", "comment": None},
    ]
    assert data["edges"] == []
    data, errors = graph.normalize(with_links("sharedKernels", {"beta": "Same types."}), STYLE)
    assert errors == []
    assert data["symmetric"] == [{"kind": "sharedKernel", "a": "alpha", "b": "beta", "comment": "Same types."}]


def test_normalize_reads_the_links_of_the_example(example_data):
    assert {(rule["kind"], rule["a"], rule["b"]) for rule in example_data["symmetric"]} == {
        ("partnership", "browsing", "fulfillment"), ("partnership", "search", "checkout"),
        ("sharedKernel", "crm", "payments"), ("sharedKernel", "fulfillment", "payments")}


def test_normalize_hands_the_page_the_kinds_of_link():
    data, _ = graph.normalize(with_links(), STYLE)
    assert data["symmetric_kinds"]["partnership"]["name"] == "Partnership"
    assert data["symmetric_kinds"]["sharedKernel"]["link"] == "---"


def test_normalize_gives_no_links_to_a_model_without_any(tiny_data):
    assert tiny_data["symmetric"] == []


def test_normalize_never_makes_a_cycle_of_a_link():
    """A partnership declared on both ends of what would be a cycle is not one: there is no direction."""
    data, errors = graph.normalize(model(
        alpha={"name": "Alpha", "type": "core", "partnerships": {"beta": "x"}},
        beta={"name": "Beta", "type": "core", "downstreams": {"gamma": "y"}},
        gamma={"name": "Gamma", "type": "core", "downstreams": {"alpha": "z"}}), STYLE)
    assert errors == []
    assert graph.find_cycle(graph.level_graph(data, "context")) is None


@pytest.mark.parametrize("key, value, expected", [
    ("partnerships", ["beta"], "context-map.alpha: `partnerships` must be a map"),
    ("sharedKernels", "beta", "context-map.alpha: `sharedKernels` must be a map"),
    ("partnerships", {}, "context-map.alpha: `partnerships` is empty"),
    ("sharedKernels", {}, "context-map.alpha: `sharedKernels` is empty"),
    ("partnerships", {"ghost": "x"}, "unknown domain or context 'ghost' in context-map.alpha.partnerships"),
    ("sharedKernels", {"ghost": "x"}, "unknown domain or context 'ghost' in context-map.alpha.sharedKernels"),
    ("partnerships", {"alpha": "x"},
     "context-map.alpha.partnerships.alpha: an entry can't be paired with itself"),
    ("partnerships", {"beta": 42}, "context-map.alpha.partnerships.beta: must be a comment string, or nothing"),
    ("partnerships", {"beta": {"comment": "x"}},
     "context-map.alpha.partnerships.beta: must be a comment string, or nothing"),
])
def test_normalize_rejects_a_broken_link(key, value, expected):
    errors = errors_of(with_links(key, value))
    assert any(expected in err for err in errors), errors


def test_normalize_rejects_a_pair_declared_twice():
    """From both ends, it is one pair said twice."""
    for key in ("partnerships", "sharedKernels"):
        errors = errors_of(with_links(key, beta={key: {"alpha": "again"}}))
        assert any(f"are paired already (in context-map.alpha.{key}.beta), declare the pair once" in err
                   for err in errors), errors


def test_normalize_rejects_a_pair_that_is_a_partnership_and_a_shared_kernel():
    for first, second in (("partnerships", "sharedKernels"), ("sharedKernels", "partnerships")):
        for extra in ({"beta": {second: {"alpha": "again"}}}, {"alpha": {second: {"beta": "again"}}}):
            errors = errors_of(with_links(first, **extra))
            assert any("are paired already (in context-map.alpha." in err
                       and "a pair is a partnership or a shared kernel, not both" in err for err in errors), errors


def test_normalize_rejects_a_pair_with_a_dependency_in_either_direction():
    for extra in ({"alpha": {"downstreams": {"beta": "x"}}}, {"beta": {"downstreams": {"alpha": "x"}}}):
        errors = errors_of(with_links(**extra))
        assert any("'alpha' and 'beta' have a dependency already (in context-map." in err
                   and "a partnership replaces the direction between them" in err for err in errors), errors


def test_normalize_names_where_the_dependency_is_declared():
    errors = errors_of(with_links(beta={"downstreams": {"alpha": "x"}}))
    assert any("(in context-map.beta.downstreams)" in err for err in errors), errors


@pytest.mark.parametrize("extra", [
    {"alpha": {"downstreams": {"beta": "x"}}},
    {"beta": {"downstreams": {"alpha": "x"}}},
    {"alpha": {"violations": {"beta": "x"}}},
    {"beta": {"violations": {"alpha": "x"}}},
    {"alpha": {"downstreams": {"beta": {"comment": "x", "upstream": ["Supplier"], "downstream": ["Customer"]}}}},
])
def test_normalize_lets_a_shared_kernel_sit_beside_a_dependency_or_a_violation(extra):
    data, errors = graph.normalize(with_links("sharedKernels", **extra), STYLE)
    assert errors == []
    assert [(rule["kind"], rule["a"], rule["b"]) for rule in data["symmetric"]] == [("sharedKernel", "alpha", "beta")]


def test_normalize_keeps_the_roles_of_a_dependency_that_shares_a_kernel():
    data, errors = graph.normalize(with_links("sharedKernels", beta={"downstreams": {"alpha": {
        "comment": "x", "upstream": ["OpenHostService"], "downstream": ["AnticorruptionLayer"]}}}), STYLE)
    assert errors == []
    assert data["edges"][0]["upstream"] == ["OpenHostService"]
    assert len(data["symmetric"]) == 1


def test_normalize_rejects_a_pair_with_a_violation_in_either_direction():
    for extra in ({"alpha": {"violations": {"beta": "x"}}}, {"beta": {"violations": {"alpha": "x"}}}):
        errors = errors_of(with_links(**extra))
        assert any("have a violation already (in context-map." in err for err in errors), errors


def test_normalize_rejects_an_entry_paired_with_its_own_domain():
    entries = {
        "core": {"name": "Core", "type": "core"},
        "core_lib": {"name": "Core Lib", "domain": "core", "type": "core"},
    }
    for entry_id, other in (("core_lib", "core"), ("core", "core_lib")):
        errors = errors_of(model(**{**entries, entry_id: {**entries[entry_id], "partnerships": {other: "x"}}}))
        assert any("'core_lib' is in the 'core' domain already, so they are not two ends" in err
                   for err in errors), errors


def test_normalize_accepts_two_contexts_of_one_domain():
    data, errors = graph.normalize(model(
        core={"name": "Core", "type": "core"},
        a={"name": "A", "domain": "core", "partnerships": {"b": "x"}},
        b={"name": "B", "domain": "core"}), STYLE)
    assert errors == []
    assert graph.level_graph(data, "domain")["links"] == []  # inside one domain it disappears


def test_normalize_accepts_a_pair_between_a_domain_and_a_context_of_another():
    data, errors = graph.normalize(model(
        core={"name": "Core", "type": "core", "sharedKernels": {"b": "x"}},
        a={"name": "A", "domain": "core"},
        other={"name": "Other", "type": "core"},
        b={"name": "B", "domain": "other"}), STYLE)
    assert errors == []
    assert [(link["a"], link["b"]) for link in graph.level_graph(data, "context")["links"]] == [("core", "b")]
    assert [(link["a"], link["b"]) for link in graph.level_graph(data, "domain")["links"]] == [("core", "other")]


@pytest.mark.parametrize("key", ["partnerships", "sharedKernels"])
def test_normalize_does_not_let_a_cluster_carry_a_link(key):
    errors = errors_of({**model(alpha={"name": "Alpha", "type": "core", "cluster": "base"}),
                        "clusters": {"base": {"name": "Base", key: {"alpha": "x"}}}})
    assert any(f"clusters.base.{key}: a cluster can't be paired" in err for err in errors), errors


def test_normalize_does_not_let_a_link_point_at_a_cluster():
    errors = errors_of({**with_links(links={"base": "x"}), "clusters": {"base": {"name": "Base"}}})
    assert any("context-map.alpha.partnerships.base: a cluster can't be paired" in err for err in errors), errors


# --- links, levels and reach --------------------------------------------------


def test_level_graph_keeps_a_link_as_written_at_context_level(example_data):
    links = graph.level_graph(example_data, "context")["links"]
    assert [(link["kind"], link["a"], link["b"], len(link["via"])) for link in links] == [
        ("partnership", "browsing", "fulfillment", 1), ("partnership", "search", "checkout", 1),
        ("sharedKernel", "fulfillment", "payments", 1), ("sharedKernel", "crm", "payments", 1)]


def test_level_graph_lifts_the_links_of_one_kind_between_two_domains_into_one(example_data):
    links = graph.level_graph(example_data, "domain")["links"]
    assert [(link["kind"], link["a"], link["b"]) for link in links] == [
        ("partnership", "catalog", "orders"), ("sharedKernel", "orders", "payments"),
        ("sharedKernel", "crm", "payments")]
    assert [rule["comment"] for rule in links[0]["via"]] == [
        "Browsing and Fulfillment ship the delivery promise together.", "Search and Checkout plan the cart together."]


def test_level_graph_keeps_two_kinds_between_the_same_domains_apart(tiny_model, tiny_style):
    tiny_model["context-map"]["solo"]["partnerships"] = {"web_ui": "x"}
    tiny_model["context-map"]["web_api"]["sharedKernels"] = {"solo": "y"}
    data, errors = graph.normalize(tiny_model, tiny_style)
    assert errors == []
    assert [(link["kind"], len(link["via"])) for link in graph.level_graph(data, "domain")["links"]] == [
        ("sharedKernel", 1), ("partnership", 1)] or \
        sorted((link["kind"], len(link["via"])) for link in graph.level_graph(data, "domain")["links"]) == [
        ("partnership", 1), ("sharedKernel", 1)]


def test_level_graph_keeps_a_link_and_a_dependency_between_the_same_domains(example_data):
    """Catalog and Orders have a dependency and a partnership: both are drawn, they are different facts."""
    domain = graph.level_graph(example_data, "domain")
    assert any((edge["from"], edge["to"]) == ("orders", "catalog") for edge in domain["edges"])
    assert any(link["kind"] == "partnership" and {link["a"], link["b"]} == {"orders", "catalog"}
               for link in domain["links"])


def test_level_graph_merges_the_same_pair_declared_from_each_domain(tiny_model, tiny_style):
    tiny_model["context-map"]["web_ui"]["partnerships"] = {"core_lib": "x"}
    tiny_model["context-map"]["web_api"]["partnerships"] = {"core_db": "y"}
    for owner in ("web_ui", "web_api"):
        tiny_model["context-map"][owner].pop("downstreams", None)
    data, errors = graph.normalize(tiny_model, tiny_style)
    assert errors == []
    links = graph.level_graph(data, "domain")["links"]
    assert [(link["a"], link["b"], len(link["via"])) for link in links] == [("web", "core", 2)]


@pytest.mark.parametrize("direction", ["both", "up", "down"])
def test_walk_reaches_across_a_link_whatever_the_direction(direction):
    data, errors = graph.normalize(with_links(), STYLE)
    assert errors == []
    context = graph.level_graph(data, "context")
    assert graph.walk(context, {"alpha"}, 1, direction, set()) == {"alpha", "beta"}
    assert graph.walk(context, {"beta"}, 1, direction, set()) == {"alpha", "beta"}


def test_walk_goes_on_across_a_link_and_a_dependency():
    data, errors = graph.normalize(with_links(beta={"downstreams": {"gamma": "x"}}), STYLE)
    assert errors == []
    context = graph.level_graph(data, "context")
    assert graph.walk(context, {"alpha"}, 1, "both", set()) == {"alpha", "beta"}
    assert graph.walk(context, {"alpha"}, 2, "both", set()) == {"alpha", "beta", "gamma"}
    assert graph.walk(context, {"alpha"}, 2, "up", set()) == {"alpha", "beta"}  # gamma depends on beta
    assert graph.walk(context, {"alpha"}, 2, "down", set()) == {"alpha", "beta", "gamma"}


def test_walk_does_not_reach_across_a_hidden_end():
    data, _ = graph.normalize(with_links(), STYLE)
    assert graph.walk(graph.level_graph(data, "context"), {"alpha"}, 1, "both", {"beta"}) == {"alpha"}


def test_link_relations_list_the_other_ends_by_name(example_data):
    assert graph.link_relations(example_data, "search") == {"partnership": ["checkout"]}
    assert graph.link_relations(example_data, "crm") == {"sharedKernel": ["payments"]}
    assert graph.link_relations(example_data, "catalog") == {"partnership": ["orders"]}  # lifted to the domains
    assert graph.link_relations(example_data, "identity") == {}
    assert graph.link_relations(example_data, "fulfillment") == {"partnership": ["browsing"],
                                                                 "sharedKernel": ["payments"]}


def test_relations_leave_the_links_out(example_data):
    ups, downs = graph.relations(example_data, "search")
    assert (ups, downs) == ([], [])


# --- aggregates -------------------------------------------------------------


def with_aggregates(aggregates, **extra):
    """alpha, beta and gamma, with `aggregates` on alpha. Beta is upstream of alpha, and it has `Thing`."""
    entries = {
        "alpha": {"name": "Alpha", "type": "core", "aggregates": aggregates},
        "beta": {"name": "Beta", "type": "core", "downstreams": {"alpha": None},
                 "aggregates": {"Thing": None, "Other": None}},
        "gamma": {"name": "Gamma", "type": "core", "aggregates": {"Stuff": None}},
    }
    for entry_id, entry in extra.items():
        entries[entry_id] = {**entries[entry_id], **entry}
    return model(**entries)


def aggregates_of(data, context_id):
    return {context["id"]: context for context in data["contexts"]}[context_id].get("aggregates")


def test_normalize_reads_the_aggregates_of_a_context(example_data):
    checkout = aggregates_of(example_data, "checkout")
    assert [aggregate["name"] for aggregate in checkout] == ["Order", "Cart"]
    order = checkout[0]
    assert order["description"] == "A cart that was paid for."
    assert order["root"] == "Order"  # the aggregate's name, unless it says otherwise
    assert order["entities"] == [{"name": "OrderLine", "description": None}]
    assert [item["name"] for item in order["valueObjects"]] == ["Money", "Address"]
    assert order["references"] == [{"context": "identity", "name": "Account"},
                                   {"context": "identity", "name": "Identity"},
                                   {"context": "payments", "name": "Payment"}]


def test_normalize_reads_a_root_that_is_not_the_name_of_the_aggregate(example_data):
    session = aggregates_of(example_data, "browsing")[0]
    assert session["name"] == "Session"
    assert session["root"] == "Visit"
    assert session["entities"] == [{"name": "Page", "description": None}]


def test_normalize_reads_the_entities_as_a_map_of_descriptions(example_data):
    cart = aggregates_of(example_data, "checkout")[1]
    assert cart["entities"] == [{"name": "CartLine", "description": "One product, and how many of it."},
                                {"name": "Coupon", "description": None}]


def test_normalize_takes_an_aggregate_with_a_bare_key_as_a_name_alone(example_data):
    account = aggregates_of(example_data, "identity")[0]
    assert account["entities"] == [] and account["references"] == []
    data, errors = graph.normalize(with_aggregates({"Bare": None, "Empty": {}}), STYLE)
    assert errors == []
    assert [aggregate["name"] for aggregate in aggregates_of(data, "alpha")] == ["Bare", "Empty"]
    assert aggregates_of(data, "alpha")[0] == {"name": "Bare", "description": None, "root": "Bare", "entities": [],
                                               "valueObjects": [], "references": [], "publishes": [],
                                               "consumes": []}


def test_normalize_gives_a_domain_no_context_points_at_its_aggregates_as_a_context(example_data):
    assert [aggregate["name"] for aggregate in aggregates_of(example_data, "payments")] == ["Payment"]
    domains = {domain["id"]: domain for domain in example_data["domains"]}
    assert "aggregates" not in domains["payments"]


def test_normalize_leaves_the_aggregates_out_of_a_context_that_has_none(example_data):
    assert aggregates_of(example_data, "search") is None
    assert all("aggregates" not in domain for domain in example_data["domains"])


def test_normalize_still_accepts_a_declared_attribute_named_aggregates(example_data):
    """The fixture declares one, and sets it on contexts that have built-in aggregates too."""
    assert example_data["attributes"]["aggregates"] == {"name": "Aggregates", "type": "list"}
    contexts = {c["id"]: c for c in example_data["contexts"]}
    assert contexts["checkout"]["attributes"]["aggregates"] == ["Order", "Cart"]
    assert [aggregate["name"] for aggregate in contexts["checkout"]["aggregates"]] == ["Order", "Cart"]


def test_normalize_validates_the_attributes_of_an_aggregate_like_any_entry_s():
    definitions = {"owner": {"type": "text"}}
    entries = {"alpha": {"name": "Alpha", "type": "core",
                         "aggregates": {"Thing": {"attributes": {"owner": "team-a"}}}}}
    data, errors = graph.normalize({**model(**entries), "attributes": definitions}, STYLE)
    assert errors == []
    assert aggregates_of(data, "alpha")[0]["attributes"] == {"owner": "team-a"}
    entries["alpha"]["aggregates"]["Thing"]["attributes"] = {"missing": "x", "owner": ["a"]}
    errors = errors_of({**model(**entries), "attributes": definitions})
    assert any("context-map.alpha.aggregates.Thing.attributes.missing: unknown attribute" in e for e in errors), errors
    assert any("Thing.attributes.owner: a text attribute takes a single value" in e for e in errors), errors


@pytest.mark.parametrize("aggregates, expected", [
    ([], "context-map.alpha.aggregates: must be a map from aggregate name to what it holds"),
    ("Thing", "context-map.alpha.aggregates: must be a map from aggregate name to what it holds"),
    ({}, "context-map.alpha.aggregates is empty"),
    ({"Thing": "text"}, "context-map.alpha.aggregates.Thing: must be a map, or nothing at all"),
    ({"Thing": {"fields": []}}, "context-map.alpha.aggregates.Thing.fields: unknown option. Known: attributes, "
                                 "consumes, description, entities, publishes, references, root, valueObjects"),
    ({"Thing": {"description": 3}}, "context-map.alpha.aggregates.Thing.description: must be a string"),
    ({"Thing": {"root": ""}}, "context-map.alpha.aggregates.Thing.root: must be the name of the root entity"),
    ({"Thing": {"root": ["A"]}}, "context-map.alpha.aggregates.Thing.root: must be the name of the root entity"),
    ({"A/B": None}, "context-map.alpha.aggregates.A/B: an aggregate's name can't hold a '/'"),
    ({"Thing": {"entities": "Leg"}}, "Thing.entities: must be a list of names, or a map from name to description"),
    ({"Thing": {"entities": []}}, "Thing.entities: needs at least one name"),
    ({"Thing": {"entities": {}}}, "Thing.entities: needs at least one name"),
    ({"Thing": {"entities": None}}, "Thing.entities: must be a list of names"),
    ({"Thing": {"entities": [1]}}, "Thing.entities: a name is a non-empty string, not 1"),
    ({"Thing": {"valueObjects": [""]}}, "Thing.valueObjects: a name is a non-empty string"),
    ({"Thing": {"entities": {"Leg": 3}}}, "Thing.entities.Leg: the description must be a string, or nothing"),
    ({"Thing": {"valueObjects": {"Id": ["x"]}}}, "Thing.valueObjects.Id: the description must be a string"),
    ({"Thing": {"entities": ["Leg", "Leg"]}}, "'Leg' is named more than once, as an entity and as an entity"),
    ({"Thing": {"entities": ["Leg"], "valueObjects": ["Leg"]}},
     "'Leg' is named more than once, as an entity and as a value object"),
    ({"Thing": {"entities": ["Thing"]}}, "'Thing' is named more than once, as the root and as an entity, and the root "
                                         "is an entity already"),
    ({"Thing": {"root": "Leg", "valueObjects": ["Leg"]}},
     "'Leg' is named more than once, as the root and as a value object"),
    ({"Thing": {"references": "Other"}}, "Thing.references: must be a list of aggregates"),
    ({"Thing": {"references": []}}, "Thing.references: needs at least one aggregate"),
    ({"Thing": {"references": [3]}}, "Thing.references: a reference is a string"),
])
def test_normalize_rejects_a_broken_aggregate(aggregates, expected):
    errors = errors_of(with_aggregates(aggregates))
    assert any(expected in err for err in errors), errors


def test_normalize_rejects_aggregates_on_a_domain_that_holds_bounded_contexts():
    errors = errors_of(model(
        alpha={"name": "Alpha", "type": "core", "aggregates": {"Thing": None}},
        alpha_one={"name": "Alpha One", "domain": "alpha"},
    ))
    assert any("context-map.alpha.aggregates: a domain that holds bounded contexts has no aggregates of its own"
               in err for err in errors), errors


def test_normalize_rejects_aggregates_on_a_cluster():
    errors = errors_of({
        "types": {"core": {"name": "Core"}},
        "clusters": {"base": {"name": "Base", "aggregates": {"Thing": None}}},
        "context-map": {"alpha": {"name": "Alpha", "type": "core", "cluster": "base"}},
    })
    assert any("clusters.base.aggregates: a cluster has no aggregates, only a bounded context does" in err
               for err in errors), errors


def test_normalize_accepts_aggregates_on_a_bounded_context_of_a_domain():
    data, errors = graph.normalize(model(
        alpha={"name": "Alpha", "type": "core"},
        alpha_one={"name": "Alpha One", "domain": "alpha", "aggregates": {"Thing": None}},
    ), STYLE)
    assert errors == []
    assert aggregates_of(data, "alpha_one")[0]["name"] == "Thing"


# A reference to another context's aggregate is allowed toward what the context depends on: directly, or
# through a dependency written against either one's whole domain, or toward one it shares a kernel or a
# partnership with.


def test_normalize_resolves_a_bare_name_to_the_aggregate_s_own_context():
    data, errors = graph.normalize(with_aggregates({"One": {"references": ["Two"]}, "Two": None}), STYLE)
    assert errors == []
    assert aggregates_of(data, "alpha")[0]["references"] == [{"context": "alpha", "name": "Two"}]


def test_normalize_accepts_the_own_context_written_in_full():
    data, errors = graph.normalize(with_aggregates({"One": {"references": ["alpha/Two"]}, "Two": None}), STYLE)
    assert errors == []
    assert aggregates_of(data, "alpha")[0]["references"] == [{"context": "alpha", "name": "Two"}]


def test_normalize_accepts_aggregates_that_reference_each_other():
    data, errors = graph.normalize(
        with_aggregates({"One": {"references": ["Two"]}, "Two": {"references": ["One"]}}), STYLE)
    assert errors == []


def test_normalize_accepts_a_reference_to_what_the_context_depends_on():
    data, errors = graph.normalize(with_aggregates({"One": {"references": ["beta/Thing", "beta/Other"]}}), STYLE)
    assert errors == []
    assert aggregates_of(data, "alpha")[0]["references"] == [{"context": "beta", "name": "Thing"},
                                                            {"context": "beta", "name": "Other"}]


def test_normalize_accepts_a_reference_through_a_dependency_on_the_other_s_whole_domain():
    """Beta's domain holds `beta_one`, and Alpha depends on the domain as a whole."""
    entries = {
        "alpha": {"name": "Alpha", "type": "core", "aggregates": {"One": {"references": ["beta_one/Thing"]}}},
        "beta": {"name": "Beta", "type": "core", "downstreams": {"alpha": None}},
        "beta_one": {"name": "Beta One", "domain": "beta", "aggregates": {"Thing": None}},
    }
    data, errors = graph.normalize(model(**entries), STYLE)
    assert errors == []


def test_normalize_accepts_a_reference_through_a_dependency_of_the_own_whole_domain():
    entries = {
        "alpha": {"name": "Alpha", "type": "core"},
        "alpha_one": {"name": "Alpha One", "domain": "alpha", "aggregates": {"One": {"references": ["beta/Thing"]}}},
        "beta": {"name": "Beta", "type": "core", "downstreams": {"alpha": None}, "aggregates": {"Thing": None}},
    }
    data, errors = graph.normalize(model(**entries), STYLE)
    assert errors == []


def test_normalize_accepts_a_reference_between_whole_domains():
    entries = {
        "alpha": {"name": "Alpha", "type": "core"},
        "alpha_one": {"name": "Alpha One", "domain": "alpha", "aggregates": {"One": {"references": ["beta_one/Thing"]}}},
        "beta": {"name": "Beta", "type": "core", "downstreams": {"alpha": None}},
        "beta_one": {"name": "Beta One", "domain": "beta", "aggregates": {"Thing": None}},
    }
    data, errors = graph.normalize(model(**entries), STYLE)
    assert errors == []


@pytest.mark.parametrize("kind", ["sharedKernels", "partnerships"])
def test_normalize_accepts_a_reference_toward_a_kernel_or_a_partner_from_either_end(kind):
    for owner, other in (("alpha", "gamma"), ("gamma", "alpha")):
        entries = {"alpha": {"aggregates": {"One": {"references": ["gamma/Stuff"]}}},
                   "gamma": {"aggregates": {"Stuff": {"references": ["alpha/One"]}}}}
        entries = {entry_id: {"name": entry_id.title(), "type": "core", **entry} for entry_id, entry in entries.items()}
        entries[owner][kind] = {other: None}
        data, errors = graph.normalize(model(**entries), STYLE)
        assert errors == [], (owner, errors)


def test_normalize_does_not_take_a_violation_for_a_permission():
    entries = with_aggregates({"One": {"references": ["gamma/Stuff"]}},
                              alpha={"violations": {"gamma": "Calls Gamma anyway."}})
    errors = errors_of(entries)
    assert any("'gamma/Stuff' is not allowed, 'alpha' has only a violation against 'gamma' (in "
               "context-map.alpha.violations.gamma), a known mistake and not a permission" in err
               for err in errors), errors


def test_normalize_does_not_let_an_upstream_reference_its_downstream():
    """Alpha depends on Beta, so Beta is upstream: it can't reference Alpha's aggregates."""
    entries = with_aggregates({"One": None}, beta={"aggregates": {"Thing": {"references": ["alpha/One"]}}})
    errors = errors_of(entries)
    assert any("context-map.beta.aggregates.Thing.references: 'alpha/One' is not allowed, 'alpha' depends on "
               "'beta', not the other way round" in err for err in errors), errors


def test_normalize_rejects_a_reference_to_a_context_it_does_not_depend_on():
    errors = errors_of(with_aggregates({"One": {"references": ["gamma/Stuff"]}}))
    assert any("'gamma/Stuff' is not allowed, 'alpha' doesn't depend on 'gamma'" in err
               and "context-map.gamma.downstreams" in err for err in errors), errors


def test_normalize_rejects_a_reference_between_contexts_of_a_domain_with_no_dependency_between_them():
    entries = {
        "alpha": {"name": "Alpha", "type": "core"},
        "alpha_one": {"name": "Alpha One", "domain": "alpha", "aggregates": {"One": {"references": ["alpha_two/Two"]}}},
        "alpha_two": {"name": "Alpha Two", "domain": "alpha", "aggregates": {"Two": None}},
    }
    errors = errors_of(model(**entries))
    assert any("'alpha_two/Two' is not allowed, 'alpha_one' doesn't depend on 'alpha_two'" in err
               for err in errors), errors


def test_normalize_rejects_a_reference_to_itself():
    errors = errors_of(with_aggregates({"One": {"references": ["One"]}}))
    assert any("references: 'One' references itself" in err for err in errors), errors
    errors = errors_of(with_aggregates({"One": {"references": ["alpha/One"]}}))
    assert any("references: 'One' references itself" in err for err in errors), errors


@pytest.mark.parametrize("reference, expected", [
    ("nowhere/Thing", "unknown bounded context 'nowhere' in 'nowhere/Thing'"),
    ("beta/Nothing", "unknown aggregate 'Nothing' in 'beta'. Known: Thing, Other"),
    ("Nothing", "unknown aggregate 'Nothing' in 'alpha'. Known: One"),
    ("/Thing", "'/Thing' is not `Name` or `context-id/Name`"),
    ("beta/", "'beta/' is not `Name` or `context-id/Name`"),
    ("gamma/Stuff", "'gamma/Stuff' is not allowed"),
])
def test_normalize_rejects_a_reference_that_goes_nowhere(reference, expected):
    errors = errors_of(with_aggregates({"One": {"references": [reference]}}))
    assert any(expected in err for err in errors), errors


def test_normalize_says_when_a_reference_names_a_domain_instead_of_a_context():
    entries = {
        "alpha": {"name": "Alpha", "type": "core", "aggregates": {"One": {"references": ["beta/Thing"]}}},
        "beta": {"name": "Beta", "type": "core", "downstreams": {"alpha": None}},
        "beta_one": {"name": "Beta One", "domain": "beta", "aggregates": {"Thing": None}},
    }
    errors = errors_of(model(**entries))
    assert any("unknown bounded context 'beta'" in err and "It is a domain" in err for err in errors), errors


def test_normalize_rejects_a_reference_listed_twice():
    errors = errors_of(with_aggregates({"One": {"references": ["Two", "alpha/Two"]}, "Two": None}))
    assert any("references: 'alpha/Two' is listed more than once" in err for err in errors), errors
    errors = errors_of(with_aggregates({"One": {"references": ["beta/Thing", "beta/Thing"]}}))
    assert any("'beta/Thing' is listed more than once" in err for err in errors), errors


def test_normalize_says_when_the_context_a_reference_names_has_no_aggregates():
    entries = with_aggregates({"One": {"references": ["beta/Thing"]}})
    del entries["context-map"]["beta"]["aggregates"]
    errors = errors_of(entries)
    assert any("unknown aggregate 'Thing' in 'beta'. Known: none" in err for err in errors), errors


# --- events -----------------------------------------------------------------


def ev_model(**changes):
    """`up` is upstream of `down`, and `lone` has no relationship. `dom` is a domain that holds `dom_a` and
    `dom_b`, and `dom_a` depends on `up`. Every entry of `changes` is laid over the entry of that id."""
    entries = {
        "up": {"name": "Up", "type": "core", "publishes": ["Ping"], "downstreams": {"down": None, "dom_a": None},
               "aggregates": {"Agg": {"publishes": {"Deep": "A deep one.", "Other": None}}, "Plain": None}},
        "down": {"name": "Down", "type": "core"},
        "lone": {"name": "Lone", "type": "core", "publishes": ["Alone"]},
        "dom": {"name": "Dom", "type": "core", "publishes": ["Wide"]},
        "dom_a": {"name": "Dom A", "domain": "dom", "publishes": ["Ctx"],
                  "aggregates": {"Thing": {"publishes": ["Inner"]}}},
        "dom_b": {"name": "Dom B", "domain": "dom"},
    }
    for entry_id, entry in changes.items():
        entries[entry_id] = {**entries[entry_id], **entry}
    return model(**entries)


def event_data(**changes):
    data, errors = graph.normalize(ev_model(**changes), STYLE)
    assert errors == []
    return data


def context_of(data, context_id):
    return {context["id"]: context for context in data["contexts"]}[context_id]


def test_events_read_what_an_aggregate_a_context_and_a_domain_publish():
    data = event_data()
    agg = context_of(data, "up")["aggregates"][0]
    assert [(e["name"], e["description"], e["address"]) for e in agg["publishes"]] == [
        ("Deep", "A deep one.", "up/Agg/Deep"), ("Other", None, "up/Agg/Other")]
    assert [e["address"] for e in context_of(data, "up")["publishes"]] == ["up/Ping"]
    domains = {domain["id"]: domain for domain in data["domains"]}
    assert [e["address"] for e in domains["dom"]["publishes"]] == ["dom/Wide"]
    # A domain with no contexts is a single bounded context: its events are the context's.
    assert "publishes" not in domains["up"]
    assert [e["address"] for e in context_of(data, "dom_a")["aggregates"][0]["publishes"]] == ["dom_a/Thing/Inner"]


def test_events_leave_the_keys_out_of_an_entry_that_has_none():
    data = event_data()
    assert "publishes" not in context_of(data, "down") and "consumes" not in context_of(data, "down")
    assert context_of(data, "up")["aggregates"][1]["publishes"] == []
    assert context_of(data, "up")["aggregates"][1]["consumes"] == []


def test_events_read_the_example(example_data):
    cargo = context_of(example_data, "checkout")["aggregates"][0]
    assert cargo["publishes"] == [{"name": "OrderPlaced", "description": "Checkout turned a cart into an order.",
                                   "address": "checkout/Order/OrderPlaced",
                                   "consumers": [{"id": "search", "aggregate": None,
                                                  "reason": "Opens the search history of the cart."},
                                                 {"id": "crm", "aggregate": None, "reason": None}]}]
    assert cargo["consumes"][0] == {
        "address": "identity/Account/AccountOpened", "reason": "Links the order to the account a guest just got.",
        "publisher": "identity", "level": "aggregate", "aggregate": "Account", "name": "AccountOpened"}
    assert cargo["consumes"][1]["reason"] is None


def test_events_say_who_consumes_an_event_and_how_deep():
    data = event_data(
        down={"consumes": ["up/Ping"], "aggregates": {"Reader": {"consumes": ["up/Agg/Deep", "up/Agg/Other"]}}},
        dom_a={"consumes": ["up/Ping"]})
    deep, other = context_of(data, "up")["aggregates"][0]["publishes"]
    assert deep["consumers"] == [{"id": "down", "aggregate": "Reader", "reason": None}]
    ping = context_of(data, "up")["publishes"][0]
    assert ping["consumers"] == [{"id": "down", "aggregate": None, "reason": None},
                                 {"id": "dom_a", "aggregate": None, "reason": None}]
    assert context_of(data, "down")["consumes"] == [{
        "address": "up/Ping", "reason": None, "publisher": "up", "level": "context", "aggregate": None,
        "name": "Ping"}]


def test_events_take_why_a_consumer_reacts_as_the_value_of_a_map():
    """The value of an address is the consumer's reason: a string, or nothing."""
    data = event_data(down={"consumes": {"up/Ping": "Wakes the cache.", "up/Agg/Deep": None}})
    consumes = context_of(data, "down")["consumes"]
    assert [item["reason"] for item in consumes] == ["Wakes the cache.", None]
    # The reason travels with the event wherever it is listed: on the publisher, and on the dependency it crosses.
    ping = context_of(data, "up")["publishes"][0]
    assert ping["consumers"] == [{"id": "down", "aggregate": None, "reason": "Wakes the cache."}]
    edge = next(edge for edge in data["edges"] if (edge["from"], edge["to"]) == ("down", "up"))
    assert {(e["address"], e["consumer"], e["reason"], e["description"]) for e in edge["events"]} == {
        ("up/Ping", "down", "Wakes the cache.", None), ("up/Agg/Deep", "down", None, "A deep one.")}


def test_events_reject_a_reason_that_is_not_text():
    errors = errors_of(ev_model(down={"consumes": {"up/Ping": 3}}))
    assert any("context-map.down.consumes.up/Ping: the description must be a string, or nothing" in e
               for e in errors), errors


@pytest.mark.parametrize("entry, expected", [
    ({"publishes": "Ping"}, "context-map.lone.publishes: must be a list of names, or a map from name to description"),
    ({"publishes": []}, "context-map.lone.publishes: needs at least one name"),
    ({"publishes": {}}, "context-map.lone.publishes: needs at least one name"),
    ({"publishes": [3]}, "context-map.lone.publishes: a name is a non-empty string, not 3"),
    ({"publishes": {"Ping": 3}}, "context-map.lone.publishes.Ping: the description must be a string"),
    ({"publishes": ["a/b"]}, "context-map.lone.publishes: 'a/b' can't hold a '/'"),
    ({"publishes": ["Ping", "Ping"]}, "context-map.lone.publishes: 'Ping' is published twice here"),
    ({"consumes": "up/Ping"}, "context-map.lone.consumes: must be a list of names, or a map from name to description"),
    ({"consumes": []}, "context-map.lone.consumes: needs at least one name"),
    ({"consumes": [None]}, "context-map.lone.consumes: a name is a non-empty string"),
])
def test_events_reject_a_broken_shape(entry, expected):
    errors = errors_of(ev_model(lone=entry))
    assert any(expected in err for err in errors), errors


def test_events_reject_an_event_published_twice_by_the_same_publisher():
    errors = errors_of(ev_model(up={"aggregates": {"Agg": {"publishes": ["Deep", "Deep"]}}}))
    assert any("context-map.up.aggregates.Agg.publishes: 'Deep' is published twice here" in e for e in errors), errors
    errors = errors_of(ev_model(dom={"publishes": ["Wide", "Wide"]}))
    assert any("context-map.dom.publishes: 'Wide' is published twice here" in e for e in errors), errors


def test_events_let_two_publishers_publish_an_event_of_the_same_name():
    """The address tells them apart."""
    data = event_data(lone={"publishes": ["Ping"]})
    assert context_of(data, "lone")["publishes"][0]["address"] == "lone/Ping"


def test_events_reject_them_on_a_cluster():
    errors = errors_of({
        "types": {"core": {"name": "Core"}},
        "clusters": {"base": {"name": "Base", "publishes": ["X"], "consumes": ["up/Ping"]}},
        "context-map": {"alpha": {"name": "Alpha", "type": "core", "cluster": "base"}},
    })
    assert any("clusters.base.publishes: a cluster has no events" in err for err in errors), errors
    assert any("clusters.base.consumes: a cluster has no events" in err for err in errors), errors


def test_events_are_taken_on_a_bounded_context_of_a_domain_and_on_an_aggregate_with_attributes():
    data = event_data(dom_b={"consumes": ["dom/Wide"]})
    assert context_of(data, "dom_b")["consumes"][0]["level"] == "domain"


@pytest.mark.parametrize("address, expected", [
    ("Ping", "'Ping' is not an event address: `context-id/Aggregate/Event`"),
    ("up/Agg/Deep/More", "'up/Agg/Deep/More' is not an event address"),
    ("up//Ping", "'up//Ping' is not an event address"),
    ("nowhere/Ping", "unknown bounded context or domain 'nowhere' in 'nowhere/Ping'"),
    ("nowhere/Agg/Deep", "unknown bounded context 'nowhere' in 'nowhere/Agg/Deep'"),
    ("dom/Thing/Inner", "unknown bounded context 'dom' in 'dom/Thing/Inner'. It is a domain, and a domain has no "
                        "aggregates."),
    ("up/Nothing/Deep", "unknown aggregate 'Nothing' in 'up', in 'up/Nothing/Deep'. Known: Agg, Plain"),
    ("up/Agg/Nothing", "unknown event 'Nothing' on the aggregate 'Agg' in 'up/Agg/Nothing'. Known: Deep, Other."),
    ("up/Plain/Deep", "unknown event 'Deep' on the aggregate 'Plain' in 'up/Plain/Deep'. Known: none. It is "
                      "published on the aggregate 'Agg' of 'up', its address is 'up/Agg/Deep'."),
    ("up/Nothing", "unknown event 'Nothing' on 'up' in 'up/Nothing'. Known: Ping."),
    ("up/Deep", "It is published on the aggregate 'Agg' of 'up', its address is 'up/Agg/Deep'."),
    ("up/Wide", "unknown event 'Wide' on 'up' in 'up/Wide'"),
    ("dom_a/Wide", "It is published on the domain 'dom', its address is 'dom/Wide'."),
    ("dom_a/Thing/Wide", "its address is 'dom/Wide'."),
    ("dom/Ctx", "It is published on the bounded context 'dom_a', its address is 'dom_a/Ctx'."),
    ("dom/Inner", "It is published on the aggregate 'Thing' of 'dom_a', its address is 'dom_a/Thing/Inner'."),
])
def test_events_reject_an_address_that_does_not_resolve_and_say_where_the_event_is(address, expected):
    errors = errors_of(ev_model(down={"consumes": [address]}))
    assert any(expected in err for err in errors), errors


def test_events_reject_the_same_address_consumed_twice_by_one_consumer():
    errors = errors_of(ev_model(down={"consumes": ["up/Ping", "up/Ping"]}))
    assert any("context-map.down.consumes: 'up/Ping' is consumed twice by 'down'" in e for e in errors), errors


def test_events_count_an_aggregate_and_its_own_context_together():
    errors = errors_of(ev_model(down={"consumes": ["up/Ping"], "aggregates": {"Reader": {"consumes": ["up/Ping"]}}}))
    assert any("context-map.down.aggregates.Reader.consumes: 'up/Ping' is consumed twice by 'down' "
               "(also in context-map.down.consumes). A context and its aggregates count together" in e
               for e in errors), errors


def test_events_count_the_aggregates_of_a_context_together_too():
    """The consumer is the context, so two of its aggregates can't consume the same address either."""
    errors = errors_of(ev_model(down={"aggregates": {"A": {"consumes": ["up/Ping"]}, "B": {"consumes": ["up/Ping"]}}}))
    assert any("consumed twice" in e for e in errors), errors


@pytest.mark.parametrize("consumer, address, expected", [
    ("lone", "up/Ping", "'lone' doesn't depend on 'up'. A consumer is downstream of what it consumes from, so "
                        "list 'lone' under context-map.up.downstreams, declare a partnership between them"),
    ("up", "down/Echo", "'down' depends on 'up', not the other way round, so 'up' is upstream"),
])
def test_events_reject_consuming_from_what_the_consumer_does_not_depend_on(consumer, address, expected):
    errors = errors_of(ev_model(down={"publishes": ["Echo"]}, **{consumer: {"consumes": [address]}}))
    assert any(expected in err for err in errors), errors


def test_events_do_not_take_a_violation_for_a_permission():
    errors = errors_of(ev_model(lone={"violations": {"up": "Calls Up anyway."}, "consumes": ["up/Ping"]}))
    assert any("'lone' has only a violation against 'up' (in context-map.lone.violations.up), a known mistake and "
               "not a permission" in e for e in errors), errors


def test_events_do_not_take_a_shared_kernel_for_a_permission():
    errors = errors_of(ev_model(lone={"sharedKernels": {"up": None}, "consumes": ["up/Ping"]}))
    assert any("'lone' shares a kernel with 'up', and a kernel shares types, it gives no direction" in e
               and "context-map.up.downstreams" in e for e in errors), errors


def test_events_take_a_partnership_either_way():
    data = event_data(lone={"partnerships": {"up": None}, "consumes": ["up/Ping"]})
    assert data["symmetric"][0]["events"][0]["address"] == "up/Ping"
    # Declared on the other end, and consumed the other way.
    data = event_data(up={"partnerships": {"lone": None}, "consumes": ["lone/Alone"]})
    assert data["symmetric"][0]["events"][0]["address"] == "lone/Alone"


def test_events_take_a_dependency_written_against_either_whole_domain():
    # The whole `dom` depends on `up`, which covers each context of it.
    data = event_data(up={"downstreams": {"down": None, "dom": None}}, dom_b={"consumes": ["up/Ping"]})
    assert context_of(data, "dom_b")["consumes"][0]["publisher"] == "up"
    # Without that, a sibling of the context that depends on `up` doesn't inherit the dependency.
    errors = errors_of(ev_model(dom_b={"consumes": ["up/Ping"]}))
    assert any("'dom_b' doesn't depend on 'up'" in e for e in errors), errors
    # A context consumes from a domain that holds contexts when it depends on one of them.
    data = event_data(dom_a={"downstreams": {"lone": None}}, lone={"consumes": ["dom/Wide"]})
    assert data["edges"][-1]["events"][0]["address"] == "dom/Wide"


def test_events_take_consuming_within_the_same_context_and_the_same_domain():
    data = event_data(
        up={"aggregates": {"Agg": {"publishes": ["Deep"], "consumes": ["up/Ping"]}, "Plain": {"consumes": ["up/Agg/Deep"]}}},
        dom={"consumes": ["dom_a/Ctx", "dom_a/Thing/Inner"]},
        dom_a={"consumes": ["dom/Wide"]},
        dom_b={"consumes": ["dom/Wide"]})
    assert all("events" not in edge for edge in data["edges"])
    assert [item["address"] for item in context_of(data, "up")["aggregates"][1]["consumes"]] == ["up/Agg/Deep"]
    # A context consumes from another context of its domain only along a dependency between them.
    errors = errors_of(ev_model(dom_b={"consumes": ["dom_a/Ctx"]}))
    assert any("'dom_b' doesn't depend on 'dom_a'" in e for e in errors), errors


def test_events_let_a_domain_consume_when_one_of_its_contexts_depends_on_the_publisher():
    data = event_data(dom={"consumes": ["up/Agg/Deep"]})
    edge = next(edge for edge in data["edges"] if edge["from"] == "dom_a" and edge["to"] == "up")
    assert edge["events"] == [{"address": "up/Agg/Deep", "name": "Deep", "aggregate": "Agg", "description": "A deep one.",
                               "consumer": "dom", "reason": None}]
    errors = errors_of(ev_model(dom={"consumes": ["lone/Alone"]}))
    assert any("the 'dom' domain doesn't depend on 'lone', and neither do its bounded contexts" in e
               for e in errors), errors


def test_events_mark_the_dependency_an_event_goes_through_once():
    data = event_data(
        down={"consumes": ["up/Ping"], "aggregates": {"Reader": {"consumes": ["up/Agg/Deep"]}}},
        dom_a={"consumes": ["up/Ping", "up/Agg/Deep"]})
    by_pair = {(edge["from"], edge["to"]): edge.get("events") for edge in data["edges"]}
    assert [e["address"] for e in by_pair[("down", "up")]] == ["up/Ping", "up/Agg/Deep"]
    assert [e["address"] for e in by_pair[("dom_a", "up")]] == ["up/Ping", "up/Agg/Deep"]


def test_events_prefer_the_dependency_that_names_the_pair_to_one_on_a_whole_domain():
    data = event_data(
        up={"downstreams": {"down": None, "dom_a": None, "dom": None}},
        dom_a={"consumes": ["up/Ping"]})
    by_pair = {(edge["from"], edge["to"]): edge.get("events") for edge in data["edges"]}
    assert by_pair[("dom_a", "up")] and not by_pair[("dom", "up")]
