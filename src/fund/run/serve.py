"""The dashboard, served locally, with the little backend its buttons need.

    PYTHONPATH=src python3 -m fund.run.serve [--port 8000] [--no-browser]

A static file cannot start a cycle, so this serves `front-end/` and four endpoints:

| route | what it does |
|---|---|
| `GET /api/manifest` | which cycle, book and swaps the page is reading, by path |
| `GET /api/data` | the eight payloads, rebuilt from the artifacts on each request |
| `POST /api/cycle/run` | starts **one** live cycle. It spends; the page confirms first |
| `GET /api/cycle/progress?since=N` | the stages that have happened, as the page's own events |

**It starts one cycle at a time and never retries.** A second POST while one runs is
refused. The subprocess is `python -m fund.run.cycle --live`, the same command a
person would type; this reads its output and turns the stages it prints into the
progress events `Openfund.applyProgressEvent` defines.

**The flow ends at `treasurer.done`.** A paper cycle submits nothing, so no
`chain.*` event is ever emitted from a cycle: stock fills are paper because
tokenized-stock execution is location-gated, and the real swaps in the Chain section
were authorized by their own signed instructions, not by this cycle. Saying otherwise
with an animation would be a lie the page cannot take back.

Bound to localhost. Nothing here authenticates, so it is a local tool, not a
deployment.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import parse_qs, urlparse

from fund import config
from fund.run import dashboard

ROOT = config.REPO_ROOT
FRONT_END = ROOT / "front-end"
#: The page's four analyst node ids, keyed by the seat whose result file appears.
SEATS = dashboard.SEATS


class Run:
    """One live cycle, and the events the page can animate it with."""

    def __init__(self) -> None:
        self.process: subprocess.Popen | None = None
        self.events: list[dict[str, Any]] = []
        self.started = 0.0
        self.lock = threading.Lock()

    @property
    def running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def emit(self, **event: Any) -> None:
        with self.lock:
            event["seq"] = len(self.events) + 1
            event.setdefault("at", int((time.monotonic() - self.started) * 1000))
            self.events.append(event)

    def since(self, seq: int) -> list[dict[str, Any]]:
        with self.lock:
            return [e for e in self.events if e["seq"] > seq]

    def start(self, db: Path, out: Path) -> None:
        if self.running:
            raise RuntimeError("a cycle is already running")
        with self.lock:
            self.events = []
        self.started = time.monotonic()
        self.process = subprocess.Popen(
            [sys.executable, "-m", "fund.run.cycle", "--live", "--db", str(db), "--out", str(out)],
            cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            env={**_environment(), "PYTHONUNBUFFERED": "1"})
        threading.Thread(target=self._watch, args=(out,), daemon=True).start()

    def _watch(self, out: Path) -> None:
        """Turn what the cycle prints into the page's own progress events.

        The cycle's stages are printed by `run/cycle.py:live`; each analyst seat's
        result file appearing is the one event the printout does not carry."""
        seen_seats: set[str] = set()
        stage = None
        for line in self.process.stdout:  # type: ignore[union-attr]
            sys.stdout.write("cycle | " + line)
            sys.stdout.flush()
            if "1/3" in line:
                self.emit(type="snapshot.start")
                stage = "snapshot"
            elif stage == "snapshot" and re.search(r"snapshot-([0-9a-f]{64})\.json", line):
                self.emit(type="snapshot.done",
                          hash=re.search(r"snapshot-([0-9a-f]{64})\.json", line).group(1))
                stage = None
            elif "2/3" in line:
                self.emit(type="analysts.start")
                cycle_dir = re.search(r"into (\S+)", line)
                if cycle_dir:
                    threading.Thread(target=self._seats, args=(Path(cycle_dir.group(1)),
                                                               seen_seats), daemon=True).start()
            elif "3/3" in line:
                for seat, node in SEATS.items():  # any seat still open ends with the stage
                    if node not in seen_seats:
                        self.emit(type="analyst.done", agent=node)
                        seen_seats.add(node)
                self.emit(type="aggregate.start")
                self.emit(type="aggregate.done")
                self.emit(type="risk.start")
            elif line.startswith("record") or "decision " in line:
                if not any(e["type"] == "risk.done" for e in self.events):
                    self.emit(type="risk.done")
                    self.emit(type="treasurer.start")
            elif "the paper book at block" in line or "no rebalance" in line:
                self.emit(type="treasurer.done")
        code = self.process.wait()  # type: ignore[union-attr]
        if not any(e["type"] == "treasurer.done" for e in self.events):
            self.emit(type="treasurer.done")
        self.emit(type="cycle.finished", ok=code == 0, code=code)

    def _seats(self, cycle_dir: Path, seen: set[str]) -> None:
        """Each seat's result file appearing is that analyst finishing."""
        while self.running:
            for seat, node in SEATS.items():
                path = cycle_dir / "results" / f"{seat}.json"
                if node in seen or not path.exists():
                    continue
                try:
                    result = json.loads(path.read_text())
                except ValueError:
                    continue
                if result.get("status") in ("ok", "no_call", "failed"):
                    seen.add(node)
                    self.emit(type="analyst.done", agent=node,
                              seat=seat, status=result.get("status"))
            time.sleep(1.0)


def _environment() -> dict[str, str]:
    import os
    return {**os.environ, "PYTHONPATH": str(ROOT / "src")}


RUN = Run()
LIVE_DB = ROOT / "fixtures" / "live" / "live.sqlite"
LIVE_OUT = ROOT / "fixtures" / "live" / "decisions"


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FRONT_END), **kwargs)

    def log_message(self, fmt, *args):  # one line each, not the default noise
        if "/api/" in (args[0] if args else ""):
            sys.stderr.write("  %s\n" % (fmt % args))

    def _json(self, payload: Any, status: int = 200) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 — the base class's name
        route = urlparse(self.path)
        if route.path == "/api/manifest":
            found = dashboard.latest_cycle()
            return self._json({
                "decision": str(found["decision"].relative_to(ROOT)) if found["decision"] else None,
                "cycle": str(found["cycle"].relative_to(ROOT)) if found["cycle"] else None,
                "snapshot": str(found["snapshot"].relative_to(ROOT)) if found["snapshot"] else None,
                "swaps": [s["_dir"] for s in dashboard.live_swaps()],
                "running": RUN.running})
        if route.path == "/api/data":
            try:
                return self._json(dashboard.build())
            except SystemExit as empty:
                return self._json({"error": str(empty)}, 503)
        if route.path == "/api/cycle/progress":
            since = int((parse_qs(route.query).get("since") or ["0"])[0])
            return self._json({"running": RUN.running, "events": RUN.since(since)})
        if route.path == "/":
            self.path = "/Openfund.html"
        return super().do_GET()

    def _confirmed(self) -> bool:
        """A POST spends, so it carries a word saying so. A request that reaches this
        endpoint by accident — a stray click, a test, a reload — cannot spend by
        accident: it is refused, and the refusal is logged."""
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            body = {}
        return body.get("confirm") == "spend"

    def do_POST(self):  # noqa: N802
        if urlparse(self.path).path != "/api/cycle/run":
            return self._json({"error": "no such endpoint"}, 404)
        if not self._confirmed():
            sys.stderr.write("  REFUSED a run with no confirmation: nothing was spent\n")
            return self._json({"error": "this endpoint spends; POST {\"confirm\": \"spend\"}"},
                              400)
        if RUN.running:
            return self._json({"error": "a cycle is already running"}, 409)
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        try:
            RUN.start(LIVE_DB, LIVE_OUT / f"live-{stamp}")
        except RuntimeError as refused:
            return self._json({"error": str(refused)}, 409)
        sys.stderr.write(f"\n== a live cycle started: {stamp}. It spends.\n")
        return self._json({"started": stamp})


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="fund.run.serve")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-export", action="store_true",
                        help="do not refresh front-end/data before serving")
    args = parser.parse_args(argv)

    if not args.no_export:
        try:
            dashboard.write(dashboard.build())
        except SystemExit as empty:
            print(f"note: {empty}")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"openfund dashboard  http://127.0.0.1:{args.port}/")
    print(f"   serving {FRONT_END.relative_to(ROOT)}")
    print("   the run button spends about $1.20 and takes about four minutes; it confirms first")
    print("   ctrl-c to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
