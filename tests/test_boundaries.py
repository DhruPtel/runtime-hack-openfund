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
import os
import pathlib
from types import MappingProxyType

from fund.adapters import bankr_quote, chain_4663
from fund.core import snapshot, universe, valuation
from fund.core.types import BPS, USD, AssetId, Check, FetchStatus, Fixed, Instant

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


# --- no threshold literal outside config ------------------------------------------------------

def _gate_values() -> set[int]:
    """The values of every threshold the code reads by name."""
    source = "\n".join(p.read_text() for p in MODULES.values())
    return {v for k, v in THRESHOLDS.items()
            if k in THRESHOLD_KEYS and type(v) is int and f'"{k}"' in source}


def test_no_threshold_value_is_written_into_a_comparison():
    """A threshold appears as a literal nowhere outside config/ (CODEBASE §8): no
    ordering comparison under src/ carries a number that a read threshold holds."""
    values = _gate_values()
    assert {25, 50, 60, 100, 3600, 1_000_000} <= values
    literal = []
    for module, path in MODULES.items():
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Compare) and any(isinstance(op, ORDERING) for op in node.ops):
                literal += [f"{module}:{node.lineno}: {ast.unparse(node)}" for sub in ast.walk(node)
                            if isinstance(sub, ast.Constant) and type(sub.value) in (int, float)
                            and sub.value in values]
    assert literal == []


def test_each_named_exception_obeys_the_threshold_it_is_given():
    """The three exceptions take their numbers as arguments (DECISION 2026-09-18),
    so a threshold that is not the configured one changes the verdict."""
    from test_bankr_quote import FETCHED as QUOTED, TWENTY_FIVE, parsed, recorded
    from test_chain_4663 import BLOCK, DAY, addr, feed, reading_aged
    from test_valuation import AMZN, FRESH, gecko, reading

    def divergence(max_bps: int, min_volume: int) -> str | None:
        rule = valuation.DivergenceRule(max_bps=Fixed(max_bps, 0, BPS),
                                        min_volume_usd=Fixed(min_volume, 0, USD))
        mark = valuation.mark(AMZN, reading(AMZN, 25260000000), FRESH)  # 252.60
        return valuation.cross_check(mark, *gecko(AMZN, "253.61"), rule, independent=True).rule

    def quote(max_age: int, max_impact: int) -> str | None:
        limits = bankr_quote.Limits(max_age=Fixed(max_age, 0, "s"),
                                    max_impact=Fixed(max_impact, 0, BPS), nominal=Fixed(25, 0, USD))
        ten_seconds_later = Instant(QUOTED.epoch_ms + 10_000)
        return bankr_quote.tradeability(parsed(recorded(swapImpactBps=18)), TWENTY_FIVE,
                                        ten_seconds_later, limits).rule

    def fresh(margin_s: int) -> bool | None:
        return chain_4663.freshness(reading_aged(DAY + 5_400), feed(addr(1)), BLOCK.timestamp,
                                    margin_s).value

    # A 39.8 bps divergence on $2.19M of volume, a quote 10 s old at 18 bps, and a
    # round 90 minutes past its heartbeat: each verdict follows the number given.
    assert (divergence(1000, 1_000_000), divergence(10, 1_000_000), divergence(1000, 5_000_000)) \
        == (None, valuation.RULE_DIVERGENCE, valuation.RULE_CORROBORATOR_LINE)
    assert (quote(60, 500), quote(5, 500), quote(60, 5)) \
        == (None, bankr_quote.RULE_QUOTE_AGE, bankr_quote.RULE_IMPACT)
    assert (fresh(7_200), fresh(3_600)) == (True, False)


# --- the rest of the record ------------------------------------------------------------------

def test_the_worker_deadline_outlasts_the_transport_timeout():
    """The worker is left time to record a call the transport ends (DECISION after
    1.7). 120 s against 180 s was the inversion bug."""
    models = json.loads((REPO / "config" / "models.json").read_text())
    transport, worker = models["transport_timeout_seconds"], models["worker_deadline_seconds"]
    assert type(transport) is int and type(worker) is int
    assert worker > transport


def test_nothing_calls_the_agent_api():
    """No call to `/agent/prompt` anywhere in the system (0.2's done-condition): the
    code, its config, the probes and the Makefile."""
    needle = "/agent/" + "prompt"  # spelled apart, so this file does not match itself
    places = [REPO / "Makefile", REPO / "pyproject.toml"]
    for top in ("src", "config", "probes"):
        for folder, dirs, files in os.walk(REPO / top):
            dirs[:] = [d for d in dirs if d not in ("node_modules", "__pycache__", "out")]
            places += [pathlib.Path(folder) / f for f in files]
    assert len(places) > 50
    assert [str(p.relative_to(REPO)) for p in places
            if needle in p.read_text(errors="replace")] == []


#: PHASE-0-1 1.6: an asset's status is the first of these rules that does not pass.
RECORDED_ORDER = ("identity", "standing", "beacon", "markability", "mark", "history",
                  "corroboration", "corroborator-line", "divergence", "tradeability")
STATUS_OF = {"identity": "identity_in_doubt", "standing": "listed_not_active",
             "beacon": "identity_in_doubt", "markability": "unmarkable", "mark": "no_mark",
             "history": "short_history", "corroboration": "uncorroborated",
             "corroborator-line": "below_corroborator_line", "divergence": "divergence_veto",
             "tradeability": "not_tradeable"}


def test_the_status_is_the_first_rule_in_the_recorded_order_that_fails():
    """For each pair of neighbouring rules, one asset fails both, and the earlier
    rule names its status. Any change to the order inverts some neighbouring pair."""
    from test_snapshot import BEACON, U, entry, inputs, listed, offchain, stock

    nvda = listed("NVDA")
    record = dataclasses.replace(U.records[nvda], status="ASSET_STATUS_INACTIVE")
    inactive = dataclasses.replace(U, records=MappingProxyType({**U.records, nvda: record}))
    unread = Check(None, "beacon slot not read: unreachable")
    unmarkable = Check(False, "constructed: judged unmarkable")
    stale = Check(False, "a gap this long in an open session is stale")
    absent = offchain(None, status=FetchStatus.ABSENT, detail="GeckoTerminal did not list it")

    def holding(u, asset, **changes):
        return dataclasses.replace(stock("NVDA", **changes), asset=asset), u

    both_fail = {
        ("identity", "standing"): lambda: holding(inactive, dataclasses.replace(
            inactive.stock(nvda, BEACON), identity=Check(False, "constructed: identity in doubt"))),
        ("standing", "beacon"): lambda: holding(inactive, inactive.stock(nvda, unread)),
        ("beacon", "markability"): lambda: holding(
            U, dataclasses.replace(U.stock(nvda, unread), markability=unmarkable)),
        ("markability", "mark"): lambda: holding(
            U, dataclasses.replace(U.stock(nvda, BEACON), markability=unmarkable), fresh=stale),
        ("mark", "history"): lambda: (stock("NVDA", fresh=stale, reach=False), U),
        ("history", "corroboration"): lambda: (stock("NVDA", reach=False, corroboration=absent), U),
        ("corroboration", "corroborator-line"): lambda: (
            stock("NVDA", corroboration=absent, volume="242.1"), U),
        ("corroborator-line", "divergence"): lambda: (
            stock("NVDA", volume="242.1", corroborator="265.87982073", closed=False), U),
        ("divergence", "tradeability"): lambda: (
            stock("NVDA", corroborator="265.87982073", closed=False, impact=60), U),
    }
    assert snapshot.ORDER == RECORDED_ORDER
    assert set(both_fail) == set(zip(RECORDED_ORDER, RECORDED_ORDER[1:]))
    wrong = {}
    for (first, second), build in both_fail.items():
        stock_inputs, u = build()
        status = entry(snapshot.build(inputs(stock_inputs), u), "NVDA")["status"]
        if status["value"] != STATUS_OF[first] or (first in ("identity", "beacon")
                                                   and status["rule"] != first):
            wrong[(first, second)] = (status["value"], status["rule"])
    assert wrong == {}


def test_an_asset_deployed_on_several_chains_is_found_on_ours():
    """Nothing assumes a registry asset has one deployment (F0.8.1; PHASE-0-1 1.1,
    1.2): an asset listed on another chain first is still found on 4663."""
    from test_universe import registry_asset

    address = "0x" + "ab" * 20
    item = registry_asset("AAA", address)
    item["deployments"].insert(0, {"chainId": 1, "contractAddress": "0x" + "cd" * 20,
                                   "networkName": "Ethereum"})
    records = universe.parse_registry(json.dumps({"assets": [item]}).encode())
    ours = records[AssetId(4663, address)]
    assert len(ours.deployments) == 2 and ours.deploys(AssetId(4663, address))
