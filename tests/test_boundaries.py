"""The structural rules CODEBASE §3 names, read from the source, and the recorded
rules the 2026-09-18 audit found no test for. Each test was shown to fail with
its rule broken on purpose (tracker/LOGS.md, the test audit).

The credential-in-logs rule lives in tests/test_redaction.py. The deployed
isolation test is unit 4.12's, and needs a deployed process to run against.
"""

from __future__ import annotations

import ast
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[1]
SRC = REPO / "src"


# --- the import graph, read from the source ------------------------------------------------

def _modules() -> dict[str, pathlib.Path]:
    found = {}
    for path in sorted((SRC / "fund").rglob("*.py")):
        parts = list(path.relative_to(SRC).with_suffix("").parts)
        if parts[-1] == "__init__":
            parts.pop()
        found[".".join(parts)] = path
    return found


MODULES = _modules()


def _imports(name: str) -> set[str]:
    """Every module `name` imports, anywhere in its body, function-level and
    relative imports included. `from a import b` counts as importing `a.b`."""
    path = MODULES[name]
    package = name if path.name == "__init__.py" else name.rpartition(".")[0]
    found = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")[:len(package.split(".")) - node.level + 1]
                module = ".".join(base + ([node.module] if node.module else []))
            else:
                module = node.module
            found.add(module)
            found |= {f"{module}.{alias.name}" for alias in node.names}
        elif isinstance(node, ast.Call) and getattr(node.func, "id", None) == "__import__":
            found.add("__import__")
    return found


def _reach(start: str) -> set[str]:
    """Every module under fund/ that loading `start` loads, directly or through
    another module, parent packages included."""
    seen, todo = set(), [start]
    while todo:
        name = todo.pop()
        if name in seen or name not in MODULES:
            continue
        seen.add(name)
        todo += [m for m in _imports(name) if m.startswith("fund")]
        if "." in name:
            todo.append(name.rpartition(".")[0])
    return seen


def _under(*packages: str) -> list[str]:
    return sorted(m for m in MODULES
                  if any(m == p or m.startswith(p + ".") for p in packages))


def _is(name: str, *prefixes: str) -> bool:
    return any(name == p or name.startswith(p + ".") for p in prefixes)


# --- CODEBASE §3 ----------------------------------------------------------------------------

SPEND_AUTHORITY = ("fund.adapters.bankr_exec", "fund.treasurer.sign")


def test_analysts_cannot_spend():
    """No module under agents/ or core/ loads bankr_exec or the signing key, directly
    or through another module (CODEBASE §2 principle 2, §3)."""
    assert set(SPEND_AUTHORITY) <= set(MODULES), "the spend modules moved: update this test"
    reached = {m: sorted(r for r in _reach(m) if _is(r, *SPEND_AUTHORITY))
               for m in _under("fund.agents", "fund.core")}
    assert {m: r for m, r in reached.items() if r} == {}


#: Modules through which a module can reach the network, and `importlib` and
#: `__import__`, through which it could load one this scan cannot see.
NETWORK = ("socket", "ssl", "http", "urllib.request", "urllib.error", "ftplib", "smtplib",
           "poplib", "imaplib", "nntplib", "telnetlib", "xmlrpc", "socketserver", "asyncio",
           "subprocess", "webbrowser", "importlib", "__import__")


def test_core_is_pure():
    """No module under core/ loads adapters/, agents/ or store/, or a module that can
    reach the network, directly or through another module (CODEBASE §1, §3, §8)."""
    core = _under("fund.core")
    assert {"fund.core.types", "fund.core.universe", "fund.core.valuation",
            "fund.core.snapshot"} <= set(core)
    found = {}
    for m in core:
        for r in sorted(_reach(m)):
            if _is(r, "fund.adapters", "fund.agents", "fund.store"):
                found.setdefault(m, []).append(r)
            found.setdefault(m, []).extend(
                f"{r} imports {i}" for i in sorted(_imports(r))
                if i == "urllib" or _is(i, *NETWORK))
    assert {m: v for m, v in found.items() if v} == {}


def test_one_signer():
    """sign.py is imported only by treasurer/ (CODEBASE §3)."""
    importers = [m for m in MODULES if "fund.treasurer.sign" in _imports(m)]
    assert [m for m in importers if not _is(m, "fund.treasurer")] == []
