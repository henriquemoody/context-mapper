"""The command line: reading the files, loading the model and building the site."""
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from conftest import EXAMPLE_MODEL, EXAMPLE_STYLE

from context_mapper import build


def example_style_without_links(tmp_path, extra=""):
    """The example style file with its `links` section taken out, plus `extra` YAML."""
    sections = yaml.safe_load(EXAMPLE_STYLE.read_text())
    sections.pop("links", None)
    style = tmp_path / "style.yml"
    style.write_text(yaml.safe_dump(sections, sort_keys=False) + extra)
    return style


def example_style_with_mermaid(tmp_path, **options):
    """The example style file with the given options set in its `mermaid` section."""
    sections = yaml.safe_load(EXAMPLE_STYLE.read_text())
    sections["mermaid"].update(options)
    style = tmp_path / "style.yml"
    style.write_text(yaml.safe_dump(sections, sort_keys=False))
    return style


CYCLE_MODEL = """\
types:
  core: { name: Core }
context-map:
  alpha:
    name: Alpha
    type: core
  beta:
    name: Beta
    type: core
  alpha_one:
    name: Alpha One
    domain: alpha
    type: core
    downstreams:
      beta_one: Alpha One uses Beta One.
  alpha_two:
    name: Alpha Two
    domain: alpha
    type: core
  beta_one:
    name: Beta One
    domain: beta
    type: core
  beta_two:
    name: Beta Two
    domain: beta
    type: core
    downstreams:
      alpha_two: Beta Two uses Alpha Two.
"""

STYLE = """\
types:
  core: { fill: "#dedaff", stroke: "#6631d7" }
"""


# --- read_yaml --------------------------------------------------------------


def test_read_yaml_reads_a_file(tmp_path):
    path = tmp_path / "model.yml"
    path.write_text("types:\n  core:\n    name: Core\n")
    assert build.read_yaml(path) == {"types": {"core": {"name": "Core"}}}


def test_read_yaml_refuses_duplicate_keys(tmp_path, capsys):
    path = tmp_path / "model.yml"
    path.write_text("types:\n  core:\n    name: Core\ntypes:\n  other:\n    name: Other\n")
    with pytest.raises(SystemExit) as excinfo:
        build.read_yaml(path)
    assert "duplicate key" in str(excinfo.value)
    assert "duplicate key" not in capsys.readouterr().out


def test_read_yaml_refuses_broken_yaml(tmp_path):
    path = tmp_path / "model.yml"
    path.write_text("types: [unclosed\n")
    with pytest.raises(SystemExit) as excinfo:
        build.read_yaml(path)
    assert "error" in str(excinfo.value)


# --- parse_args -------------------------------------------------------------


def test_parse_args_defaults():
    args = build.parse_args([])
    assert args.model == Path("context-map.yml")
    assert args.diagrams == Path("context-map.style.yml")
    assert args.out == Path("public")


def test_parse_args_takes_the_flags():
    args = build.parse_args([
        "--model", "m.yml",
        "--diagrams", "s.yml",
        "--out", "out",
    ])
    assert args.model == Path("m.yml")
    assert args.diagrams == Path("s.yml")
    assert args.out == Path("out")


# --- load -------------------------------------------------------------------


def test_load_reads_the_example():
    data, mermaid_config, links = build.load(EXAMPLE_MODEL, EXAMPLE_STYLE)
    assert len(data["domains"]) == 5
    assert len(data["contexts"]) == 7
    assert len(data["edges"]) == 6
    assert mermaid_config["direction"] == "BT"
    assert len(mermaid_config["views"]) == 4
    assert links == {"Repository": "https://github.com/henriquemoody/context-mapper",
                     "Issues": "https://github.com/henriquemoody/context-mapper/issues"}


def test_load_reads_the_links_section(tmp_path):
    style = example_style_without_links(tmp_path, "links:\n  Repository: https://github.com/org/repo\n"
                                               "  Issue tracker: https://github.com/org/repo/issues\n")
    _, _, links = build.load(EXAMPLE_MODEL, style)
    assert list(links) == ["Repository", "Issue tracker"]  # in the order written
    assert links["Repository"] == "https://github.com/org/repo"
    assert links["Issue tracker"] == "https://github.com/org/repo/issues"


def test_load_refuses_links_that_are_not_a_map(tmp_path, capsys):
    style = example_style_without_links(tmp_path, "links:\n  - https://github.com/org/repo\n")
    with pytest.raises(SystemExit):
        build.load(EXAMPLE_MODEL, style)
    assert "links must be a map from label to URL" in capsys.readouterr().err


def test_load_refuses_a_link_without_a_url(tmp_path, capsys):
    style = example_style_without_links(tmp_path, "links:\n  Repository:\n")
    with pytest.raises(SystemExit):
        build.load(EXAMPLE_MODEL, style)
    assert "links.Repository: must be a URL string" in capsys.readouterr().err


def test_load_warns_when_the_domains_depend_on_each_other(tmp_path, capsys):
    model = tmp_path / "model.yml"
    model.write_text(CYCLE_MODEL)
    style = tmp_path / "style.yml"
    style.write_text(STYLE)
    data, _, _ = build.load(model, style)
    assert len(data["domains"]) == 2
    assert "domains depend on each other" in capsys.readouterr().err


def test_load_refuses_an_unknown_section(tmp_path, capsys):
    style = tmp_path / "style.yml"
    style.write_text("groups:\n  one:\n    name: One\n")
    with pytest.raises(SystemExit):
        build.load(EXAMPLE_MODEL, style)
    assert "unknown section" in capsys.readouterr().err


# --- main -------------------------------------------------------------------


def test_main_builds_the_site(tmp_path, capsys):
    out = tmp_path / "public"
    build.main([
        "--model", str(EXAMPLE_MODEL),
        "--diagrams", str(EXAMPLE_STYLE),
        "--out", str(out),
    ])
    captured = capsys.readouterr()
    assert "built" in captured.out
    index = out / "index.html"
    assert index.exists()
    text = index.read_text()
    assert "/*__MODEL__*/null" not in text
    assert "/*__STYLE__*/" not in text
    assert "/*__SCRIPT__*/" not in text
    assert "const MODEL = {" in text
    assert "--accent: #305bab" in text        # style.css is inlined
    assert "function mermaidSource(" in text  # app.js is inlined
    assert (out / "mermaid" / "index.html").exists()
    assert (out / "markdown" / "README.md").exists()
    assert (out / "mermaid" / "overview.html").exists()
    assert (out / "markdown" / "overview.md").exists()


HYPHEN_MODEL = """\
types:
  core: { name: Core }
context-map:
  audit-log:
    name: Audit Log
    type: core
    description: Records every action, who took it, and when.
  payments:
    name: Payments
    type: core
    description: Charges the customer for a purchase.
    downstreams:
      audit-log: Payments records every charge in the log.
"""


def test_box_tooltips_map_node_ids_back_to_items(tmp_path):
    """A hyphen in an id becomes an underscore in the SVG: `audit-log` is a node
    called `audit_log`. Box tooltips must go from that node id back to the item,
    or an id with a hyphen gets no tooltip while one without does."""
    model = tmp_path / "model.yml"
    model.write_text(HYPHEN_MODEL)
    style = tmp_path / "style.yml"
    style.write_text(STYLE)
    out = tmp_path / "public"
    build.main(["--model", str(model), "--diagrams", str(style), "--out", str(out)])
    text = (out / "index.html").read_text()
    assert 'itemOfNode[nodeId(item.id)] = item' in text        # the node id -> item map
    assert 'itemOfNode[innermost(ev.target) || ""]' in text    # box tooltips go through it
    assert "descriptionOf" not in text                         # no lookup by SVG id left


def test_the_interactive_page_can_download_the_diagram(tmp_path):
    out = tmp_path / "public"
    build.main(["--model", str(EXAMPLE_MODEL), "--diagrams", str(EXAMPLE_STYLE), "--out", str(out)])
    text = (out / "index.html").read_text()
    assert '<select id="image">' in text                      # PNG or SVG
    assert '<option value="png">PNG</option>' in text
    assert '<option value="svg">SVG</option>' in text
    assert '<button id="download">Download</button>' in text
    assert "function downloadDiagram" in text                 # the shared export script, spliced in
    assert "getComputedStyle(svg).fontFamily" in text         # the page's font travels with the file
    assert "/*__DOWNLOAD__*/" not in text                     # never left behind


def test_main_puts_the_links_in_the_page(tmp_path):
    style = example_style_without_links(tmp_path, "links:\n  Repository: https://github.com/org/repo\n")
    out = tmp_path / "public"
    build.main(["--model", str(EXAMPLE_MODEL), "--diagrams", str(style), "--out", str(out)])
    text = (out / "index.html").read_text()
    assert '"links": {"Repository": "https://github.com/org/repo"}' in text


def test_main_puts_the_attributes_in_the_page(tmp_path):
    out = tmp_path / "public"
    build.main(["--model", str(EXAMPLE_MODEL), "--diagrams", str(EXAMPLE_STYLE), "--out", str(out)])
    text = (out / "index.html").read_text()
    assert '"attributes": {"service": {"name": "Service", "type": "text"}' in text
    assert '"attributes": {"service": "checkout-service", "aggregates": ["Order", "Cart"]}' in text
    assert '"aggregates": ["Product", "Inventory"]' in text


DATE_MODEL = """\
types:
  core: { name: Core }
attributes:
  metadata: { type: any }
context-map:
  alpha:
    name: Alpha
    type: core
    attributes:
      metadata: { released: 2026-11-18 }
"""


def test_main_builds_a_model_with_a_date_in_an_attribute(tmp_path):
    """A YAML date is a date, not a string: the build shows it as its ISO form."""
    model = tmp_path / "model.yml"
    model.write_text(DATE_MODEL)
    style = tmp_path / "style.yml"
    style.write_text(STYLE)
    out = tmp_path / "public"
    build.main(["--model", str(model), "--diagrams", str(style), "--out", str(out)])
    text = (out / "index.html").read_text()
    assert '"metadata": {"released": "2026-11-18"}' in text


def test_main_puts_the_attribute_tooltips_in_the_page(tmp_path):
    out = tmp_path / "public"
    build.main(["--model", str(EXAMPLE_MODEL), "--diagrams", str(EXAMPLE_STYLE), "--out", str(out)])
    text = (out / "index.html").read_text()
    assert '"attribute_tooltips": true' in text


def test_main_turns_the_attribute_tooltips_off(tmp_path):
    style = example_style_with_mermaid(tmp_path, attribute_tooltips=False)
    out = tmp_path / "public"
    build.main(["--model", str(EXAMPLE_MODEL), "--diagrams", str(style), "--out", str(out)])
    text = (out / "index.html").read_text()
    assert '"attribute_tooltips": false' in text


def test_the_panel_shows_the_attributes_under_a_heading(tmp_path):
    out = tmp_path / "public"
    build.main(["--model", str(EXAMPLE_MODEL), "--diagrams", str(EXAMPLE_STYLE), "--out", str(out)])
    text = (out / "index.html").read_text()
    assert "<h3>Attributes</h3>" in text
    assert "const attributeSection" in text


def test_main_refuses_a_model_file_that_is_not_there(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        build.main([
            "--model", str(tmp_path / "nowhere.yml"),
            "--diagrams", str(EXAMPLE_STYLE),
            "--out", str(tmp_path / "public"),
        ])
    assert "not found" in str(excinfo.value)


def test_main_refuses_a_style_file_with_an_unknown_section(tmp_path, capsys):
    style = tmp_path / "style.yml"
    style.write_text("groups:\n  one:\n    name: One\n")
    with pytest.raises(SystemExit):
        build.main([
            "--model", str(EXAMPLE_MODEL),
            "--diagrams", str(style),
            "--out", str(tmp_path / "public"),
        ])
    assert "unknown section" in capsys.readouterr().err


# --- the command line -------------------------------------------------------


def test_the_command_line_builds_the_site(tmp_path):
    result = subprocess.run(
        [
            sys.executable, "-m", "context_mapper",
            "--model", str(EXAMPLE_MODEL),
            "--diagrams", str(EXAMPLE_STYLE),
            "--out", str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "index.html").exists()
    assert (tmp_path / "mermaid" / "index.html").exists()
    assert "built" in result.stdout
