"""The structural rules CODEBASE §3 names, read from the source, and the recorded
rules the 2026-09-18 audit found no test for. Each test was shown to fail with
its rule broken on purpose (tracker/LOGS.md, the test audit).

The credential-in-logs rule lives in tests/test_redaction.py. The deployed
isolation test is unit 4.12's, and needs a deployed process to run against.
"""

from __future__ import annotations

import ast
import dataclasses
import json
import pathlib

from fund.adapters import bankr_quote
from fund.core import valuation

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


# --- one gate definition, and its three named exceptions ------------------------------------

#: The three threshold comparisons that stay where the plan put them until unit
#: 3.4 sweeps them into core/gates.py (DECISION 2026-09-18; CODEBASE §1
#: principle 3). The decision says this test must name all three.
NAMED_EXCEPTIONS = {
    ("fund.adapters.chain_4663", "freshness"): "feed staleness (1.3)",
    ("fund.core.valuation", "cross_check"): "the divergence tier's line and veto (1.4)",
    ("fund.adapters.bankr_quote", "tradeability"): "quote age and signed impact (1.5)",
}

THRESHOLDS = json.loads((REPO / "config" / "thresholds.json").read_text())

#: The names a threshold travels under once read from config/thresholds.json:
#: the fields of the two objects that carry the gates' limits, and the chain
#: adapter's staleness margin. The trade size is not a limit.
THRESHOLD_NAMES = ({f.name for f in dataclasses.fields(valuation.DivergenceRule)}
                   | {f.name for f in dataclasses.fields(bankr_quote.Limits)} - {"nominal"}
                   | {"margin_s", "staleness_margin_s"})
THRESHOLD_KEYS = {k for k in THRESHOLDS if not k.startswith("_")}
ORDERING = (ast.Lt, ast.LtE, ast.Gt, ast.GtE)


def _mentions(node: ast.AST, tainted: set[str]) -> bool:
    for sub in ast.walk(node):
        if isinstance(sub, ast.Name) and (sub.id in tainted or sub.id in THRESHOLD_NAMES):
            return True
        if isinstance(sub, ast.Attribute) and sub.attr in THRESHOLD_NAMES:
            return True
        if isinstance(sub, ast.Constant) and sub.value in THRESHOLD_KEYS:
            return True
    return False


def _own_nodes(func: ast.AST):
    """A function's own nodes, lambdas included, not those of the functions and
    classes defined inside it."""
    todo = list(ast.iter_child_nodes(func))
    while todo:
        node = todo.pop()
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            todo.extend(ast.iter_child_nodes(node))


def _assigned(node: ast.AST) -> list[tuple[ast.AST, ast.AST]]:
    """(target, value) pairs, a tuple assignment split element by element."""
    if isinstance(node, ast.Assign):
        pairs = [(t, node.value) for t in node.targets]
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)) and node.value is not None:
        pairs = [(node.target, node.value)]
    else:
        return []
    out = []
    for target, value in pairs:
        if (isinstance(target, ast.Tuple) and isinstance(value, ast.Tuple)
                and len(target.elts) == len(value.elts)):
            out += list(zip(target.elts, value.elts))
        else:
            out.append((target, value))
    return out


def _threshold_comparisons() -> dict[tuple[str, str], list[int]]:
    """Every ordering comparison of a measured value against a threshold, by the
    function it sits in. A threshold is a name in THRESHOLD_NAMES, a key of
    thresholds.json, or a local assigned from either; a comparison with a bare
    number (a sign check such as `x > 0`) is not one."""
    found: dict[tuple[str, str], list[int]] = {}

    def visit(node: ast.AST, module: str, path: tuple[str, ...], outer: set[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, module, path + (child.name,), outer)
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                own = list(_own_nodes(child))
                tainted = set(outer) | {a.arg for a in child.args.args + child.args.kwonlyargs
                                        if a.arg in THRESHOLD_NAMES}
                grew = True
                while grew:
                    grew = False
                    for target, value in (p for n in own for p in _assigned(n)):
                        if _mentions(value, tainted):
                            for name in (s.id for s in ast.walk(target) if isinstance(s, ast.Name)):
                                if name not in tainted:
                                    tainted.add(name)
                                    grew = True
                for n in own:
                    if (isinstance(n, ast.Compare) and any(isinstance(op, ORDERING) for op in n.ops)
                            and _mentions(n, tainted)
                            and not any(isinstance(o, ast.Constant) for o in [n.left, *n.comparators])):
                        found.setdefault((module, child.name), []).append(n.lineno)
                visit(child, module, path + (child.name,), tainted)

    for module, path in MODULES.items():
        visit(ast.parse(path.read_text()), module, (), set())
    return found


def test_one_gate_definition_names_its_three_exceptions():
    """gates.py is the only module that compares against a threshold, apart from the
    three named exceptions (CODEBASE §3; PLAN §2 invariant 4). When 3.4 sweeps one
    in, it leaves this list, or this test fails."""
    found = _threshold_comparisons()
    elsewhere = {site: lines for site, lines in found.items()
                 if site[0] != "fund.core.gates" and site not in NAMED_EXCEPTIONS}
    assert elsewhere == {}
    assert {site for site in NAMED_EXCEPTIONS if site not in found} == set(), \
        "a named exception no longer compares: take it off the list"
