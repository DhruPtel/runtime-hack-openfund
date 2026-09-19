"""The analyst report, parsed and checked (unit 2.2).

A report is one plain text, in the format approved at 2.1
(planning/REPORT-FORMAT.md). Code reads two kinds of line and nothing else:

    REPORT <seat> <agent address> <snapshot sha256>
    CALL <SYMBOL> <address> <word> <confidence>

Everything else is prose, for people and for the risk agent. A report with no
CALL line must say `NO CALLS`, so an empty report is a decision rather than a
reply cut short.

Two steps. Both return named refusals rather than raising, so a bad report fails
its own worker and never the cycle:

  - `parse` reads the shape: the first line, each CALL line, NO CALLS, and the
    figure lines (`- ` lines) under each call;
  - `check` holds the report to the snapshot it names:
      - the header: seat, agent and snapshot;
      - the seat's vocabulary and the three confidence words;
      - each called asset: present at its address, under its own symbol, and
        tradeable;
      - at most the configured number of calls, one per asset;
      - every citation naming a field that exists;
      - every figure matching the field it cites.

**The figure check is the one that matters most.** A figure line that cites a
single field (`[mark.price_usd]`, `[timeline 2026-09-03]`) must write that
field's value. Each decimal, each `N bps` and each `$N.NNM` in the line must be
one of the line's cited single fields, to the precision written. That means the
field lies within half a unit of the last digit written, the midpoint included.

Either rounding of an exact midpoint is correct. The capture holds AMZN's close
of 266.085, which the approved report writes 266.08, and USO's of 161.405,
written 161.41. A strict half-up rule refused the first; that was the rule's
error, not the report's.

A percentage is computed, and a line that cites only a whole series
(`[timeline]`) is computed. Computed figures are cited but not checked, as
REPORT-FORMAT.md states.

One leniency: a single code fence wrapped around the whole reply is removed
before parsing. It is transport, not content. Nothing else is forgiven.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from fund import config

NO_CALLS = "NO CALLS"

_HEADER = re.compile(r"^REPORT (\S+) (\S+) ([0-9a-f]{64})$")
_CALL = re.compile(r"^CALL (\S+) (0x[0-9a-fA-F]{40}) (\S+) (\S+)$")
_BRACKET = re.compile(r"\[([^\[\]]+)\]")
_ITEM_ALL = re.compile(r"^all \d+$")
_ITEM_TIMELINE = re.compile(r"^(?:([A-Z][A-Z0-9.]*) )?timeline(?: (\d{4}-\d{2}-\d{2}))?$")
_ITEM_FIELD = re.compile(
    r"^(?:([A-Z][A-Z0-9.]*) )?([a-z][a-z0-9_]*(?:\.[a-z0-9_]+)*)(?: = (-?\d+(?:\.\d+)?))?$")

_MILLIONS = re.compile(r"\$(\d+(?:\.\d+)?)M")
_BPS = re.compile(r"(?<![\d.])(-?\d+(?:\.\d+)?) ?bps\b")
_PERCENT = re.compile(r"[+-]?\d+(?:\.\d+)?%")
_DECIMAL = re.compile(r"(?<![\d.])(-?\d+\.\d+)(?![\d.])")

_MISSING = object()


# --- what the aggregator gets --------------------------------------------------------------------

@dataclass(frozen=True)
class Refusal:
    """One named reason a report is not accepted."""

    rule: str
    detail: str
    line: int | None = None

    def __str__(self) -> str:
        where = f" (line {self.line})" if self.line else ""
        return f"{self.rule}: {self.detail}{where}"


@dataclass(frozen=True)
class Figure:
    """A `- ` line under a call, its continuation lines joined."""

    text: str
    line: int


@dataclass(frozen=True)
class Call:
    symbol: str
    address: str  # lowercased; the asset's identity (tickers are for display only)
    word: str
    confidence: str
    line: int
    figures: tuple[Figure, ...]
    text: str  # the call's block, its CALL line included


@dataclass(frozen=True)
class Report:
    seat: str
    agent: str
    snapshot: str
    calls: tuple[Call, ...]
    no_calls: bool
    opening: str  # the prose that is not under any call
    text: str  # the report as parsed: what the record hashes

    def as_dict(self) -> dict[str, Any]:
        """What the aggregator consumes: per seat, per asset, a word and a confidence."""
        return {"seat": self.seat, "agent": self.agent, "snapshot": self.snapshot,
                "no_calls": self.no_calls,
                "calls": [{"symbol": c.symbol, "address": c.address, "word": c.word,
                           "confidence": c.confidence} for c in self.calls]}


@dataclass(frozen=True)
class Verdict:
    report: Report | None
    refusals: tuple[Refusal, ...]

    @property
    def ok(self) -> bool:
        return self.report is not None and not self.refusals

    @property
    def rule(self) -> str | None:
        return self.refusals[0].rule if self.refusals else None


@dataclass(frozen=True)
class Contract:
    """What one seat's report is held to, read from config/analysts.json."""

    seat: str
    vocabulary: tuple[str, ...]
    confidence: tuple[str, ...]
    max_calls: int

    @classmethod
    def load(cls, seat: str, analysts: Mapping[str, Any] | None = None) -> "Contract":
        analysts = config.load_json("analysts.json") if analysts is None else analysts
        entry = next((a for a in analysts["analysts"] if a["id"] == seat), None)
        if entry is None:
            raise KeyError(f"{seat} is not a seat in config/analysts.json")
        return cls(seat=seat,
                   vocabulary=tuple(analysts["vocabularies"][entry["vocabulary"]]),
                   confidence=tuple(analysts["confidence"]),
                   max_calls=int(analysts["max_calls_per_report"]))


# --- the shape -----------------------------------------------------------------------------------

def _unfence(text: str) -> str:
    lines = text.strip().split("\n")
    if len(lines) >= 2 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1])
    return text.strip()


def _figures(block: Sequence[tuple[int, str]]) -> tuple[Figure, ...]:
    figures: list[list[Any]] = []
    for number, line in block:
        if line.startswith("- "):
            figures.append([number, line[2:].strip()])
        elif line.startswith("  ") and figures and figures[-1] is not None and line.strip():
            figures[-1][1] += " " + line.strip()
        elif figures:
            figures.append(None)  # anything else ends the figure it follows
    return tuple(Figure(text=f[1], line=f[0]) for f in figures if f is not None)


def parse(text: str) -> tuple[Report | None, tuple[Refusal, ...]]:
    """Read the report's shape. Returns the report (None only when there is no
    header to read) and the refusals the shape alone earns."""
    body = _unfence(text)
    lines = body.split("\n")
    first = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first is None:
        return None, (Refusal("header", "the reply is empty"),)
    header = _HEADER.match(lines[first].strip())
    if header is None:
        return None, (Refusal("header", "the first line must be 'REPORT <seat> <agent> "
                              f"<snapshot sha256>', not {lines[first].strip()[:90]!r}",
                              first + 1),)
    seat, agent, snapshot = header.groups()

    refusals: list[Refusal] = []
    blocks: list[tuple[int, re.Match, list[tuple[int, str]]]] = []
    opening: list[str] = []
    no_calls: list[int] = []
    current: list[tuple[int, str]] | None = None
    for index in range(first + 1, len(lines)):
        line = lines[index].rstrip()
        if line.startswith("CALL ") or line == "CALL":
            match = _CALL.match(line)
            if match is None:
                refusals.append(Refusal("call-shape", "a CALL line must be 'CALL <SYMBOL> "
                                        f"<0x address> <word> <confidence>', not {line[:100]!r}",
                                        index + 1))
                current = None
                continue
            current = []
            blocks.append((index + 1, match, current))
        elif line.strip() == NO_CALLS:
            no_calls.append(index + 1)
            current = None
        elif current is None:
            opening.append(line)
        else:
            current.append((index + 1, line))

    has_call_line = bool(blocks) or any(r.rule == "call-shape" for r in refusals)
    if not has_call_line and not no_calls:
        refusals.append(Refusal("no-calls", "a report with no CALL line must say NO CALLS"))
    if has_call_line and no_calls:
        refusals.append(Refusal("no-calls", "NO CALLS and CALL lines in one report", no_calls[0]))

    calls = tuple(
        Call(symbol=m.group(1), address=m.group(2).lower(), word=m.group(3),
             confidence=m.group(4), line=number, figures=_figures(block),
             text="\n".join([lines[number - 1].rstrip()] + [line for _, line in block]))
        for number, m, block in blocks)
    report = Report(seat=seat, agent=agent, snapshot=snapshot, calls=calls,
                    no_calls=bool(no_calls) and not has_call_line,
                    opening="\n".join(opening).strip(), text=body)
    return report, tuple(refusals)


# --- the snapshot it names -----------------------------------------------------------------------

def _field(entry: Mapping[str, Any], path: str) -> Any:
    node: Any = entry
    for part in path.split("."):
        if not isinstance(node, Mapping) or part not in node:
            return _MISSING
        node = node[part]
    return node


def _close(entry: Mapping[str, Any], date: str) -> Any:
    for point in (entry.get("timeline") or {}).get("points") or ():
        if point[0] == date:
            return point[2]
    return _MISSING


def _number(value: Any) -> Decimal | None:
    if isinstance(value, bool) or isinstance(value, (list, dict)) or value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


@dataclass(frozen=True)
class _Resolved:
    name: str  # as a refusal would name it, e.g. "AMD mark.price_usd"
    value: Any
    single: bool  # one value, not a whole series


class _Snapshot:
    def __init__(self, document: Mapping[str, Any]):
        self.assets = list(document.get("assets") or ())
        self.by_address = {a["asset"]["address"].lower(): a for a in self.assets}
        self.by_symbol: dict[str, Mapping[str, Any]] = {}
        for entry in self.assets:
            self.by_symbol.setdefault(entry["asset"]["symbol"], entry)
        self.tradeable = [a for a in self.assets if a["status"]["value"] == "tradeable"]

    def resolve(self, item: str, scope: Mapping[str, Any] | None
                ) -> tuple[list[_Resolved], str | None]:
        """One citation item, in the scope of a call's asset, or of every tradeable
        asset when it is outside a call. Returns what it names, or why it names
        nothing."""
        timeline = _ITEM_TIMELINE.match(item)
        named = timeline or _ITEM_FIELD.match(item)
        if named is None:
            return [], f"cannot read the citation {item!r}"
        symbol = named.group(1)
        if symbol is not None:
            entry = self.by_symbol.get(symbol)
            if entry is None:
                return [], f"no asset {symbol} in the snapshot"
            entries = [entry]
        else:
            entries = [scope] if scope is not None else self.tradeable
        found = []
        for entry in entries:
            label = entry["asset"]["symbol"]
            if timeline:
                date = timeline.group(2)
                if date is None:
                    if not (entry.get("timeline") or {}).get("points"):
                        return [], f"{label} has no timeline"
                    found.append(_Resolved(f"{label} timeline", None, single=False))
                    continue
                value = _close(entry, date)
                if value is _MISSING:
                    return [], f"{label} has no close for {date}"
                found.append(_Resolved(f"{label} timeline {date}", value, single=True))
                continue
            path, asserted = named.group(2), named.group(3)
            value = _field(entry, path)
            if value is _MISSING:
                return [], f"{label} has no field {path}"
            if asserted is not None and _number(value) != Decimal(asserted):
                return [], f"{label} {path} is {value}, not {asserted}"
            found.append(_Resolved(f"{label} {path}", value,
                                   single=_number(value) is not None))
        return found, None


def _citations(text: str) -> list[list[str]]:
    return [[" ".join(item.split()) for item in bracket.split(",")]
            for bracket in _BRACKET.findall(text)]


def _matches(claim: Decimal, value: Decimal) -> bool:
    """The field, written to the claim's precision: within half a unit of its last digit."""
    places = max(0, -claim.as_tuple().exponent)
    return abs(value - claim) <= Decimal(5).scaleb(-(places + 1))


def _claims(text: str) -> list[tuple[str, str, Decimal]]:
    """The figures a line writes: ($M, millions), (bps, bps), (plain, decimals).
    Percentages are computed, and integers are dates or counts; neither is a claim."""
    body = _BRACKET.sub(" ", text).replace("−", "-")
    claims: list[tuple[str, str, Decimal]] = []
    for kind, pattern in (("millions", _MILLIONS), ("bps", _BPS)):
        claims += [(kind, m.group(0), Decimal(m.group(1))) for m in pattern.finditer(body)]
        body = pattern.sub(" ", body)
    body = _PERCENT.sub(" ", body)
    claims += [("plain", m.group(0), Decimal(m.group(1))) for m in _DECIMAL.finditer(body)]
    return claims


def _check_figure(figure: Figure, fields: list[_Resolved]) -> Refusal | None:
    singles = [(f, _number(f.value)) for f in fields if f.single]
    if not singles:
        return None  # a computed figure: cited, not checked
    for kind, written, claim in _claims(figure.text):
        candidates = [(f, v) for f, v in singles
                      if kind == "plain"
                      or (kind == "bps" and f.name.endswith("_bps"))
                      or (kind == "millions" and f.name.endswith("_usd"))]
        scale = Decimal(1_000_000) if kind == "millions" else Decimal(1)
        if not any(_matches(claim, v / scale) for _, v in candidates):
            cited = "; ".join(f"{f.name} = {f.value}" for f, _ in singles)
            return Refusal("figure", f"{written} matches none of the fields it cites: {cited}",
                           figure.line)
    return None


def check(report: Report, snapshot: Mapping[str, Any], *, contract: Contract, agent: str,
          snapshot_sha256: str) -> tuple[Refusal, ...]:
    """Hold a parsed report to its seat's contract and to the snapshot it names."""
    refusals: list[Refusal] = []
    if report.seat != contract.seat:
        refusals.append(Refusal("header", f"seat {report.seat!r}, expected {contract.seat!r}", 1))
    if report.agent != agent:
        refusals.append(Refusal("header", f"agent {report.agent!r}, expected {agent!r}", 1))
    if report.snapshot != snapshot_sha256:
        refusals.append(Refusal("header", f"snapshot {report.snapshot[:12]}…, expected "
                                f"{snapshot_sha256[:12]}…", 1))

    snap = _Snapshot(snapshot)
    if len(report.calls) > contract.max_calls:
        refusals.append(Refusal("coverage", f"{len(report.calls)} calls, at most "
                                f"{contract.max_calls}"))
    seen: set[str] = set()
    for call in report.calls:
        if call.address in seen:
            refusals.append(Refusal("coverage", f"{call.symbol} called twice", call.line))
        seen.add(call.address)
        if call.word not in contract.vocabulary:
            refusals.append(Refusal("vocabulary", f"{call.word!r} is not one of "
                                    f"{', '.join(contract.vocabulary)} for {contract.seat}",
                                    call.line))
        if call.confidence not in contract.confidence:
            refusals.append(Refusal("confidence", f"{call.confidence!r} is not one of "
                                    f"{', '.join(contract.confidence)}", call.line))
        entry = snap.by_address.get(call.address)
        if entry is None:
            refusals.append(Refusal("asset", f"{call.address} is not in the snapshot", call.line))
            continue
        if entry["asset"]["symbol"] != call.symbol:
            refusals.append(Refusal("asset", f"{call.address} is {entry['asset']['symbol']}, "
                                    f"not {call.symbol}", call.line))
        if entry["status"]["value"] != "tradeable":
            refusals.append(Refusal("asset", f"{call.symbol} is {entry['status']['value']}, "
                                    "not tradeable", call.line))

    regions = [(report.opening, None, ())]
    regions += [(c.text, snap.by_address.get(c.address), c.figures) for c in report.calls]
    for text, scope, figures in regions:
        for items in _citations(text):
            for item in items:
                if _ITEM_ALL.match(item):
                    continue
                _, why = snap.resolve(item, scope)
                if why:
                    refusals.append(Refusal("citation", why))
        for figure in figures:
            fields: list[_Resolved] = []
            for items in _citations(figure.text):
                for item in items:
                    if not _ITEM_ALL.match(item):
                        fields += snap.resolve(item, scope)[0]
            refusal = _check_figure(figure, fields)
            if refusal:
                refusals.append(refusal)
    return tuple(refusals)


def validate(text: str, snapshot: Mapping[str, Any], *, contract: Contract, agent: str,
             snapshot_sha256: str) -> Verdict:
    """Parse and check. Never raises for anything a model could write."""
    report, refusals = parse(text)
    if report is None:
        return Verdict(None, refusals)
    return Verdict(report, refusals + check(report, snapshot, contract=contract, agent=agent,
                                            snapshot_sha256=snapshot_sha256))
