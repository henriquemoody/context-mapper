"""The command line: reading the files, loading the model and building the site."""
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import EXAMPLE_MODEL, EXAMPLE_STYLE

from context_mapper import build

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
    data, mermaid_config = build.load(EXAMPLE_MODEL, EXAMPLE_STYLE)
    assert len(data["domains"]) == 5
    assert len(data["contexts"]) == 7
    assert len(data["edges"]) == 6
    assert mermaid_config["direction"] == "BT"
    assert len(mermaid_config["views"]) == 3


def test_load_warns_when_the_domains_depend_on_each_other(tmp_path, capsys):
    model = tmp_path / "model.yml"
    model.write_text(CYCLE_MODEL)
    style = tmp_path / "style.yml"
    style.write_text(STYLE)
    data, _ = build.load(model, style)
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
    assert "const MODEL = {" in text
    assert (out / "mermaid" / "index.html").exists()
    assert (out / "markdown" / "README.md").exists()
    assert (out / "mermaid" / "overview.html").exists()
    assert (out / "markdown" / "overview.md").exists()


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
