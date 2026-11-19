"""`context-mapper serve`: the command line, the server and the watcher."""
import argparse
import http.client
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from conftest import EXAMPLE_MODEL, EXAMPLE_STYLE

from context_mapper import build
from context_mapper import serve as serve_module

MODEL = """\
types:
  core: { name: Core }
context-map:
  payments:
    name: Payments
    type: core
    description: Charges the customer.
"""

MODEL_WITH_SHIPPING = MODEL + """\
  shipping:
    name: Shipping
    type: core
"""

STYLE = """\
types:
  core: { fill: "#dedaff", stroke: "#6631d7" }
"""


def eventually(condition, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.05)
    return False


def start_server(out, watching=True):
    server = serve_module.Server(("127.0.0.1", 0), out, watching)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def get(port, path):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        return response.status, response.read().decode()
    finally:
        connection.close()


def build_example(out):
    build.main([
        "--model", str(EXAMPLE_MODEL),
        "--diagrams", str(EXAMPLE_STYLE),
        "--out", str(out),
    ])


class Counter:
    """What `watch` needs from a server: the build id it bumps."""

    def __init__(self):
        self.build_id = 0


def start_watcher(paths, rebuild):
    server = Counter()
    stop, ready = threading.Event(), threading.Event()
    threading.Thread(target=serve_module.watch, args=(server, paths, rebuild),
                     kwargs={"stop": stop, "ready": ready}, daemon=True).start()
    assert ready.wait(timeout=5), "the watcher never took its first snapshot"
    return server, stop


# --- parse_args --------------------------------------------------------------


def test_parse_args_defaults():
    args = serve_module.parse_args([])
    assert args.model == Path("context-map.yml")
    assert args.diagrams == Path("context-map.style.yml")
    assert args.out == Path("public")
    assert args.host == "127.0.0.1"
    assert args.port == 8000
    assert args.watch is False


def test_parse_args_takes_the_flags():
    args = serve_module.parse_args([
        "--model", "m.yml",
        "--diagrams", "s.yml",
        "--out", "site",
        "--host", "0.0.0.0",
        "--port", "9000",
        "--watch",
    ])
    assert args.model == Path("m.yml")
    assert args.diagrams == Path("s.yml")
    assert args.out == Path("site")
    assert args.host == "0.0.0.0"
    assert args.port == 9000
    assert args.watch is True


# --- main --------------------------------------------------------------------


def test_main_dispatches_the_serve_command(monkeypatch):
    seen = []
    monkeypatch.setattr(serve_module, "serve", seen.append)
    build.main(["serve", "--watch"])
    assert seen == [["--watch"]]


def test_serve_refuses_a_model_file_that_is_not_there(tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        serve_module.serve([
            "--model", str(tmp_path / "nowhere.yml"),
            "--diagrams", str(EXAMPLE_STYLE),
            "--out", str(tmp_path / "public"),
        ])
    assert "not found" in str(excinfo.value)


# --- the server --------------------------------------------------------------


def test_serves_the_built_site(tmp_path):
    out = tmp_path / "public"
    build_example(out)
    server = start_server(out, watching=False)
    try:
        status, body = get(server.server_port, "/")
        assert status == 200
        assert "var MODEL" in body
        assert "/__build_id" not in body            # no watch, no injected script
        status, _ = get(server.server_port, "/mermaid/index.html")
        assert status == 200
        status, _ = get(server.server_port, "/markdown/README.md")
        assert status == 200
        status, _ = get(server.server_port, "/nope.html")
        assert status == 404
    finally:
        server.shutdown()
        server.server_close()


def test_watch_mode_serves_the_reload_script_and_the_build_id(tmp_path):
    out = tmp_path / "public"
    build_example(out)
    server = start_server(out, watching=True)
    try:
        status, body = get(server.server_port, "/")
        assert status == 200
        assert 'fetch("/__build_id"' in body         # the page reloads itself
        status, body = get(server.server_port, "/mermaid/index.html")
        assert status == 200
        assert 'fetch("/__build_id"' in body        # the static pages too
        assert "/__build_id" not in (out / "index.html").read_text()  # the files stay clean

        status, body = get(server.server_port, "/__build_id")
        assert (status, body) == (200, "0")
        server.build_id = 7
        status, body = get(server.server_port, "/__build_id")
        assert (status, body) == (200, "7")
    finally:
        server.shutdown()
        server.server_close()


# --- the watcher --------------------------------------------------------------


def test_the_watcher_rebuilds_on_change(tmp_path):
    model = tmp_path / "context-map.yml"
    style = tmp_path / "context-map.style.yml"
    out = tmp_path / "public"
    model.write_text(MODEL)
    style.write_text(STYLE)
    args = argparse.Namespace(model=model, diagrams=style, out=out)

    def rebuild():
        build.build_site(args)

    server, stop = start_watcher((model, style), rebuild)
    try:
        model.write_text(MODEL_WITH_SHIPPING)
        assert eventually(lambda: server.build_id == 1), "the watcher never rebuilt"
        assert "Shipping" in (out / "index.html").read_text()
    finally:
        stop.set()


def test_the_watcher_survives_a_failed_rebuild(tmp_path, capsys):
    model = tmp_path / "context-map.yml"
    style = tmp_path / "context-map.style.yml"
    out = tmp_path / "public"
    model.write_text(MODEL)
    style.write_text(STYLE)
    args = argparse.Namespace(model=model, diagrams=style, out=out)

    def rebuild():
        build.build_site(args)

    server, stop = start_watcher((model, style), rebuild)
    try:
        model.write_text(MODEL_WITH_SHIPPING)
        assert eventually(lambda: server.build_id == 1), "the watcher never rebuilt"
        assert "Shipping" in (out / "index.html").read_text()

        model.write_text("types: [unclosed\n")      # a broken edit
        assert eventually(lambda: "rebuild failed" in capsys.readouterr().err)
        assert server.build_id == 1                 # the build id did not move
        assert "Shipping" in (out / "index.html").read_text()  # the good site stays up

        model.write_text(MODEL)                     # the next save fixes it
        assert eventually(lambda: server.build_id == 2), "the watcher never recovered"
        assert "Shipping" not in (out / "index.html").read_text()
    finally:
        stop.set()


# --- the whole loop ----------------------------------------------------------


def test_serve_watch_rebuilds_the_site(tmp_path):
    """The loop as the user runs it: edit the YAML, the served page changes."""
    model = tmp_path / "context-map.yml"
    style = tmp_path / "context-map.style.yml"
    out = tmp_path / "public"
    model.write_text(MODEL)
    style.write_text(STYLE)
    process = subprocess.Popen(
        [sys.executable, "-u", "-m", "context_mapper", "serve", "--watch",
         "--model", str(model), "--diagrams", str(style), "--out", str(out), "--port", "0"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        port = None
        for _ in range(20):                          # the build lines come first
            line = process.stdout.readline()
            assert line, f"serve exited early: {process.stderr.read()}"
            match = re.search(r"http://[\d.]+:(\d+)/", line)
            if match:
                port = int(match.group(1))
                break
        assert port, "serve never said where it is listening"

        status, body = get(port, "/__build_id")
        assert (status, body) == (200, "0")
        status, body = get(port, "/")
        assert "Payments" in body and "Shipping" not in body

        model.write_text(MODEL_WITH_SHIPPING)        # the edit
        assert eventually(lambda: get(port, "/__build_id")[1] == "1"), "never rebuilt"

        status, body = get(port, "/")
        assert "Shipping" in body                    # the served page changed
        assert 'fetch("/__build_id"' in body         # and still reloads itself
        assert "/__build_id" not in (out / "index.html").read_text()  # the file stays clean
    finally:
        process.terminate()
        process.wait(timeout=5)
