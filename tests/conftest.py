"""Shared fixtures for the context-mapper test suite.

The files under `example/` are read as fixtures and never modified. The inline
model below is a deliberately small map used by the unit tests: two domains
holding two bounded contexts each, one single domain, and one cluster.
"""
import copy
from pathlib import Path

import pytest
import yaml

from context_mapper import graph, mermaid

ROOT = Path(__file__).resolve().parent.parent

EXAMPLE_MODEL = ROOT / "example" / "context-map.yml"
EXAMPLE_STYLE = ROOT / "example" / "context-map.style.yml"

# A small map: `core` (clustered, two contexts), `web` (two contexts) and
# `solo` (a domain nobody points at, so a single bounded context).
TINY_MODEL = {
    "types": {
        "core": {"name": "Core"},
        "aux": {"name": "Aux"},
    },
    "clusters": {
        "base": {"name": "Base"},
    },
    "context-map": {
        "core": {"name": "Core", "type": "core", "cluster": "base"},
        "web": {"name": "Web", "type": "aux"},
        "core_lib": {
            "name": "Core Lib",
            "domain": "core",
            "type": "core",
            "downstreams": {"core_db": "Lib reads the db."},
        },
        "core_db": {"name": "Core DB", "domain": "core", "type": "core"},
        "web_ui": {
            "name": "Web UI",
            "domain": "web",
            "type": "aux",
            "downstreams": {"core_lib": "UI reads the lib."},
        },
        "web_api": {
            "name": "Web API",
            "domain": "web",
            "type": "aux",
            "downstreams": {
                "core_db": {"comment": "API reads the db.", "style": "dotted"},
            },
        },
        "solo": {"name": "Solo", "type": "aux"},
    },
}

TINY_STYLE = {
    "types": {
        "core": {"fill": "#dedaff", "stroke": "#6631d7"},
        "aux": {"fill": "#adf0c7", "stroke": "#067429"},
    },
    "clusters": {
        "base": {"fill": "#eaf9ef", "stroke": "#067429"},
    },
}


@pytest.fixture
def find_view():
    """Find a view by id in a list of views."""

    def _find(views, view_id):
        for view in views:
            if view["id"] == view_id:
                return view
        raise AssertionError(f"no view {view_id!r} in {[v['id'] for v in views]}")

    return _find


@pytest.fixture
def example_model():
    return yaml.safe_load(EXAMPLE_MODEL.read_text())


@pytest.fixture
def example_style():
    return yaml.safe_load(EXAMPLE_STYLE.read_text())


@pytest.fixture
def example_data(example_model, example_style):
    """The example model, normalized with the example style."""
    data, errors = graph.normalize(example_model, example_style)
    assert errors == []
    return data


@pytest.fixture
def example_cfg(example_style):
    """The example style's mermaid section, filled in with the defaults."""
    cfg, errors = mermaid.settings(example_style["mermaid"])
    assert errors == []
    return cfg


@pytest.fixture
def tiny_model():
    return copy.deepcopy(TINY_MODEL)


@pytest.fixture
def tiny_style():
    return copy.deepcopy(TINY_STYLE)


@pytest.fixture
def tiny_data(tiny_model, tiny_style):
    data, errors = graph.normalize(tiny_model, tiny_style)
    assert errors == []
    return data
