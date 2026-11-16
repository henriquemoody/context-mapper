"""Serve the built site, and rebuild it while the YAML files change.

`context-mapper serve` builds the site once and serves the output directory
over HTTP. With `--watch` it also polls the model and style files and rebuilds
whenever they change: a rebuild that fails says why on the terminal and leaves
the last good site up, so a broken edit never takes the page down.

The watcher is a plain polling loop over each file's mtime and size, so there
is no dependency beyond the standard library. In watch mode the served HTML
pages carry a small script that reloads the page after each successful rebuild;
it is injected on the wire only — the files on disk stay exactly what the
build wrote, ready to publish as they are.
"""
import argparse
import functools
import http.server
import sys
import threading
from pathlib import Path

from .build import add_input_flags, build_site

POLL_SECONDS = 0.5    # how often the watcher checks the YAML files
SETTLE_SECONDS = 0.2  # grace period for editors that write in place

RELOAD_SNIPPET = """\
<script>
(function () {
  var buildId = null;
  setInterval(function () {
    fetch("/__build_id", {cache: "no-store"})
      .then(function (response) { return response.text(); })
      .then(function (id) {
        if (buildId !== null && id !== buildId) location.reload();
        buildId = id;
      })
      .catch(function () {});
  }, 1000);
})();
</script>"""


class Handler(http.server.SimpleHTTPRequestHandler):
    """Serves the output directory; in watch mode HTML pages reload themselves."""

    def do_GET(self):
        if self.server.watching:
            path = self.path.split("?", 1)[0]
            if path == "/__build_id":
                self._send_text(str(self.server.build_id), "text/plain; charset=utf-8")
                return
            page = Path(self.translate_path(path))
            if page.is_dir():
                page = page / "index.html"
            if page.suffix == ".html" and page.is_file():
                try:
                    html = page.read_text()
                except OSError:
                    self.send_error(404, "File not found")
                    return
                self._send_text(html.replace("</body>", RELOAD_SNIPPET + "</body>"),
                                "text/html; charset=utf-8")
                return
        super().do_GET()

    def _send_text(self, text, content_type):
        body = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_request(self, code="-", size="-"):
        if self.path.split("?", 1)[0] != "/__build_id":  # the page polls it every second
            super().log_request(code, size)


class Server(http.server.ThreadingHTTPServer):
    """A file server for the output directory that also carries the build id."""

    def __init__(self, address, out, watching):
        super().__init__(address, functools.partial(Handler, directory=str(out)))
        self.watching = watching
        self.build_id = 0


def file_stamp(path):
    """What counts as a change: a file's mtime and size, or None if it is gone."""
    try:
        stat = path.stat()
    except OSError:
        return None
    return stat.st_mtime_ns, stat.st_size


def watch(server, paths, rebuild, stop=None, ready=None):
    """Poll the files and rebuild on every change; runs on a daemon thread.

    A rebuild that raises SystemExit has already said why (or carries the
    message itself): report it, keep the last good site up, and keep watching —
    the next save fixes it. A successful rebuild bumps the build id, which is
    what tells the pages to reload.
    """
    stop = stop or threading.Event()
    stamps = {path: file_stamp(path) for path in paths}
    if ready:
        ready.set()
    while not stop.is_set():
        stop.wait(POLL_SECONDS)
        current = {path: file_stamp(path) for path in paths}
        if current == stamps:
            continue
        changed = [str(path) for path in paths if current[path] != stamps[path]]
        stamps = current
        print(f"change detected in {', '.join(changed)}; rebuilding")
        stop.wait(SETTLE_SECONDS)
        try:
            rebuild()
        except SystemExit as err:
            if err.code not in (None, 1):  # 1 has already been reported; a string has not
                print(err.code, file=sys.stderr)
            print("rebuild failed; the page still shows the last good build", file=sys.stderr)
        else:
            server.build_id += 1


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="context-mapper serve",
        description="Build the site and serve it over HTTP. With --watch, rebuild "
                    "it whenever the model or style file changes.")
    add_input_flags(parser)
    parser.add_argument("--host", default="127.0.0.1",
                        help="the interface to listen on (default: %(default)s)")
    parser.add_argument("--port", type=int, default=8000,
                        help="the port to listen on (default: %(default)s)")
    parser.add_argument("--watch", action="store_true",
                        help="rebuild whenever the model or style file changes")
    return parser.parse_args(argv)


def serve(argv=None):
    args = parse_args(argv)
    build_site(args)  # the same fail-fast as a plain build
    try:
        server = Server((args.host, args.port), args.out, args.watch)
    except OSError as err:
        sys.exit(f"error: cannot listen on {args.host}:{args.port}: {err.strerror or err}")
    host = "localhost" if args.host in ("", "0.0.0.0", "::") else args.host
    print(f"serving {args.out} at http://{host}:{server.server_port}/ (Ctrl+C to stop)", flush=True)
    if args.watch:
        print(f"watching {args.model} and {args.diagrams}", flush=True)

        def rebuild():
            build_site(args)

        threading.Thread(target=watch, args=(server, (args.model, args.diagrams), rebuild),
                         daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        server.server_close()
