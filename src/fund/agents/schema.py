"""The analyst report, parsed and checked (unit 2.2).

A report is one plain text, in the format approved at 2.1
(planning/REPORT-FORMAT.md). Code reads two kinds of line and nothing else:

    REPORT <seat> <agent address> <snapshot sha256>
    CALL <SYMBOL> <address> <word> <confidence>

Everything else is prose, for people and for the risk agent. A report with no
CALL line must say `NO CALLS`, so an empty report is a decision rather than a
reply cut short. The line may be dressed (`NO CALLS.`, `**NO CALLS**`), and beside
calls it means none beyond them (the 3.8 sweep's S5).

Two steps. Both return named refusals rather than raising, so a bad report fails
its own worker and never the cycle:

  - `parse` reads the shape: the first line, each CALL line, NO CALLS, and the
    figure lines (`- ` lines) under each call;
  - `check` holds the report to the snapshot it names:
      - the header: seat, agent and snapshot;
      - the seat's vocabulary and the three confidence words;
      - each called asset: present at its address, under its own symbol, and
        tradeable, unless the call is a sell (S8);
      - at most the configured number of calls, one per asset;
      - every citation naming a field, or recorded as imprecise;
      - every figure matching a value the snapshot holds.

**The figure check is the one that matters most.** A figure line that cites a
single field (`[mark.price_usd]`, `[timeline 2026-09-03]`) must write that
field's value. Each decimal, each `N bps` and each `$N.NNM` in the line must be
one of the line's cited single fields, to the precision written. That means the
field lies within half a unit of the last digit written, the midpoint included.

Either rounding of an exact midpoint is correct. The capture holds AMZN's close
of 266.085, which the approved report writes 266.08, and USO's of 161.405,
written 161.41. A strict half-up rule refused the first; that was the rule's
error, not the report's.

**A real value under a loose reference is accepted and recorded** (the
operator's rule after 3.8, where four real reports were refused and none had
invented a figure). When a figure is not the field its line cites, it is looked
for among the values of the assets the line is about: the call's own asset,
and every asset the line names by symbol, in its citations or its words. Found,
the report stands, and an `Imprecision` records what was cited and where the
value is. A citation that names no field as written is recorded the same way,
with the field it resolves to when exactly one field ends in it
(`[swap_impact_bps]` is `quote.swap_impact_bps`). **A figure found nowhere
still refuses the report:** it is fabricated. When a line's citation names
nothing, every figure on it is checked by value, bps included, because nothing
on the line marks a figure as computed.

The search stays inside the assets the line is about, not the whole snapshot:
about 2,500 numbers, among which a figure written to two places could match by
chance, and the fabrication check would be weaker for it.

**Computed figures are cited but not checked,** as REPORT-FORMAT.md states:
- a ratio: a percentage (`1.9%`, `1.9 %`, `1.9 percent`), points (`4.5pp`) or a
  multiple (`8.3x`), since the 3.8 sweep's S1;
- a plain decimal one arithmetic step from two fields its line cites: a
  difference, sum, ratio or change. `a 2.02 premium` citing the venue's price and
  the mark is the one less the other. The brief tells an analyst to cite the
  fields a computed figure came from, and at the sweep doing so got it refused as
  fabricated (S1). A figure that is no such step still refuses;
- a figure in bps, unless its line cites a field that is itself in bps, such as
  `quote.swap_impact_bps` or `corroboration.divergence_bps`. Then it names that
  field and is checked against it;
- anything on a line that cites only a whole series (`[timeline]`).

2.6's first real report wrote five divergences it had computed between prices
it cited, such as `~136bps`. An earlier version of this rule checked every bps
figure against a bps field, and refused all five correct figures.

**A bracket that is not a field reference is not a citation** (3.8). It is
prose, and the numbers inside it stay figures. **A figure line with no citation,
whether its brackets are prose or it has none, is checked by value** (the 3.8
sweep's R5), so leaving the citation out cannot hide a figure from the
fabrication check. A decimal is read where a full stop follows it.

**A figure written with thousands separators is the same number.**
`$2,101,924.28` is 2101924.28. Until 3.8's live run found it, the comma split it,
and `924.28` was refused against the field.

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

#: Millions of dollars, however written: `$4.42M`, `$4.42m`, `$4.4 million`,
#: `4.42M`. A lowercase m counts only after a dollar sign, so `5m` stays minutes.
_MILLIONS = re.compile(r"(?:\$(\d+(?:\.\d+)?) ?(?:M|m|mn|million)|(?<![\w$.])(\d+(?:\.\d+)?) ?"
                       r"(?:M|million))(?![A-Za-z0-9])")
_BPS = re.compile(r"(?<![\d.])(-?\d+(?:\.\d+)?) ?(?:bps|basis points?)\b")
#: A ratio, which is computed and never a field: `1.9%`, `1.9 %`, `1.9 percent`,
#: `4.5pp`, and a multiple, `8.3x` (S1).
_PERCENT = re.compile(r"[+-]?\d+(?:\.\d+)?(?: ?%| ?percent\b| ?pp\b| ?percentage points?\b)")
_TIMES = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?: ?x| ?×)(?![A-Za-z0-9])")
#: A number written with thousands separators, such as `2,101,924.28`: groups of
#: three after a first group of one to three, never after a decimal point.
_GROUPED = re.compile(r"(?<![\d.,])\d{1,3}(?:,\d{3})+(?![\d,])")
#: A decimal, which a full stop may follow: `559.42.` ends a sentence (R5).
_DECIMAL = re.compile(r"(?<![\d.])(-?\d+\.\d+)(?!\d|\.\d)")

_SYMBOL = re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Z0-9.]{0,9})(?![A-Za-z0-9])")

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
class Imprecision:
    """A citation that was loose, kept so a reader sees it. Never a refusal.

    Either a citation named no field as written (`found` is where it resolves,
    or None), or a figure was not the field its line cites but is a value the
    snapshot holds for an asset the line is about (`found` names that value)."""

    cited: str  # the citation item as written, or the fields the figure's line cites
    found: str | None  # where the value really is, as a citation would name it
    written: str | None = None  # the figure, when a figure was found elsewhere
    line: int | None = None
    why: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"cited": self.cited, "found": self.found, "written": self.written,
                "line": self.line, "why": self.why}

    def __str__(self) -> str:
        where = f" (line {self.line})" if self.line else ""
        if self.written is not None:
            return f"{self.written} cites {self.cited}; it is {self.found}{where}"
        return (f"[{self.cited}] names no field; it resolves to {self.found}{where}" if self.found
                else f"[{self.cited}] names no field: {self.why}{where}")


@dataclass(frozen=True)
class Verdict:
    report: Report | None
    refusals: tuple[Refusal, ...]
    imprecisions: tuple[Imprecision, ...] = ()

    @property
    def ok(self) -> bool:
        return self.report is not None and not self.refusals

    @property
    def rule(self) -> str | None:
        return self.refusals[0].rule if self.refusals else None

    def as_dict(self) -> dict[str, Any]:
        """The parsed report, and every citation that was loose in it."""
        parsed = self.report.as_dict() if self.report is not None else {}
        return {**parsed, "imprecise_citations": [i.as_dict() for i in self.imprecisions]}


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


#: Emphasis a model may wrap a line in: `**CALL …**`, `` `CALL …` ``.
_WRAPPERS = ("**", "__", "`", "*", "_")


def _bare(line: str) -> str:
    """A line as code reads it: no indentation, and no emphasis wrapped around it."""
    bare = line.strip()
    changed = True
    while changed:
        changed = False
        for mark in _WRAPPERS:
            if len(bare) > 2 * len(mark) and bare.startswith(mark) and bare.endswith(mark):
                bare, changed = bare[len(mark):-len(mark)].strip(), True
    return bare


def _no_calls(line: str) -> bool:
    """The abstention line, however it is dressed: `NO CALLS`, `NO CALLS.`,
    `**NO CALLS**`, `No calls.` (S5). A line that goes on after it is prose."""
    return _bare(line).rstrip(".!:;").strip().upper() == NO_CALLS


def _dedent(line: str, indent: int) -> str:
    """A line of an indented CALL block, with the block's indentation removed, so its
    figure lines and their continuations read as they would unindented."""
    lead = len(line) - len(line.lstrip(" "))
    return line[min(lead, indent):]


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
    indent = 0
    for index in range(first + 1, len(lines)):
        line = lines[index].rstrip()
        bare = _bare(line)
        if bare.startswith("CALL ") or bare == "CALL":
            # Indented, as the brief's own template is, or wrapped in emphasis, a CALL
            # line is still a call. At the sweep it was silently prose (R6).
            match = _CALL.match(bare)
            if match is None:
                refusals.append(Refusal("call-shape", "a CALL line must be 'CALL <SYMBOL> "
                                        f"<0x address> <word> <confidence>', not {line[:100]!r}",
                                        index + 1))
                current = None
                continue
            current = []
            indent = len(line) - len(line.lstrip(" "))
            blocks.append((index + 1, match, current))
        elif _no_calls(line):
            no_calls.append(index + 1)
            current = None
        elif current is None:
            opening.append(line)
        else:
            current.append((index + 1, _dedent(line, indent)))

    has_call_line = bool(blocks) or any(r.rule == "call-shape" for r in refusals)
    if not has_call_line and not no_calls:
        refusals.append(Refusal("no-calls", "a report with no CALL line must say NO CALLS"))
    # Beside calls, NO CALLS says there are none beyond them: not a contradiction (S5).

    calls = tuple(
        Call(symbol=m.group(1), address=m.group(2).lower(), word=m.group(3),
             confidence=m.group(4), line=number, figures=_figures(block),
             text="\n".join([_bare(lines[number - 1])] + [line for _, line in block]))
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
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return number if number.is_finite() else None


def _leaves(node: Any, prefix: str = "") -> list[tuple[str, Any]]:
    """Every numeric value under an asset's entry, by its field path. The closes
    are named by date instead (`timeline 2026-09-03`)."""
    found: list[tuple[str, Any]] = []
    if isinstance(node, Mapping):
        for key, value in node.items():
            if key != "timeline":
                found += _leaves(value, f"{prefix}.{key}" if prefix else key)
    elif isinstance(node, list):
        for index, value in enumerate(node):
            if isinstance(value, (Mapping, list)):
                found += _leaves(value, f"{prefix}.{index}")
    elif _number(node) is not None:
        found.append((prefix, node))
    return found


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

    def loosely(self, item: str, scope: Mapping[str, Any] | None) -> _Resolved | None:
        """A field cited without the block that holds it: `[swap_impact_bps]` for
        `quote.swap_impact_bps`. Found only when exactly one field ends so."""
        named = _ITEM_FIELD.match(item)
        if named is None:
            return None
        entry = self.by_symbol.get(named.group(1)) if named.group(1) else scope
        if entry is None:
            return None
        path = named.group(2)
        ends = [(p, v) for p, v in _leaves(entry) if p == path or p.endswith("." + path)]
        if len(ends) != 1:
            return None
        return _Resolved(f"{entry['asset']['symbol']} {ends[0][0]}", ends[0][1], single=True)

    def about(self, scope: Mapping[str, Any] | None, text: str) -> list[Mapping[str, Any]]:
        """The assets a figure line is about: the call's own, and every asset the
        line names by symbol, in its citations or its words."""
        entries = [scope] if scope is not None else []
        for word in _SYMBOL.findall(text):
            entry = self.by_symbol.get(word) or self.by_symbol.get(word.rstrip("."))
            if entry is not None and entry not in entries:
                entries.append(entry)
        return entries

    def values(self, entries: Sequence[Mapping[str, Any]]) -> list[_Resolved]:
        """Every single value these assets hold: each numeric field and each close."""
        out = []
        for entry in entries:
            label = entry["asset"]["symbol"]
            out += [_Resolved(f"{label} {path}", value, single=True)
                    for path, value in _leaves(entry)]
            out += [_Resolved(f"{label} timeline {point[0]}", point[2], single=True)
                    for point in (entry.get("timeline") or {}).get("points") or ()]
        return out


def _items(bracket: str) -> list[str]:
    return [" ".join(item.split()) for item in bracket.split(",")]


def _is_citation(bracket: str) -> bool:
    """A bracket is a citation when at least one of its items reads as a field
    reference, a close or a whole series. Anything else in brackets is prose: 3.8's
    price-integrity wrote `["us_equities_24/5"]` inside a code span."""
    return any(_ITEM_ALL.match(i) or _ITEM_TIMELINE.match(i) or _ITEM_FIELD.match(i)
               for i in _items(bracket))


def _citations(text: str) -> list[list[str]]:
    return [_items(bracket) for bracket in _BRACKET.findall(text) if _is_citation(bracket)]


def _matches(claim: Decimal, value: Decimal) -> bool:
    """The field, written to the claim's precision: within half a unit of its last digit."""
    places = max(0, -claim.as_tuple().exponent)
    return abs(value - claim) <= Decimal(5).scaleb(-(places + 1))


def _claims(text: str) -> list[tuple[str, str, Decimal]]:
    """The figures a line writes: ($M, millions), (bps, bps), (plain, decimals).
    Ratios (percentages, points, multiples) are computed, and integers are dates or
    counts; neither is a claim.
    Whether a bps figure is a claim depends on what the line cites (_check_figure)."""
    # A citation is not a figure; a bracket of prose keeps its numbers, which are.
    body = _BRACKET.sub(lambda m: " " if _is_citation(m.group(1)) else f" {m.group(1)} ",
                        text).replace("−", "-")
    body = _GROUPED.sub(lambda m: m.group(0).replace(",", ""), body)  # 2,101,924.28 is one number
    claims: list[tuple[str, str, Decimal]] = []
    for kind, pattern in (("millions", _MILLIONS), ("bps", _BPS)):
        claims += [(kind, m.group(0), Decimal(next(g for g in m.groups() if g)))
                   for m in pattern.finditer(body)]
        body = pattern.sub(" ", body)
    body = _TIMES.sub(" ", _PERCENT.sub(" ", body))
    claims += [("plain", m.group(0), Decimal(m.group(1))) for m in _DECIMAL.finditer(body)]
    return claims


def _fits(kind: str, pairs: Sequence[tuple[_Resolved, Decimal]]) -> list[tuple[_Resolved, Decimal]]:
    """The values a figure of this kind can be: any for a plain decimal, a bps
    field for `N bps`, a USD field for `$N.NNM`."""
    return [(f, v) for f, v in pairs
            if kind == "plain" or (kind == "bps" and f.name.endswith("_bps"))
            or (kind == "millions" and f.name.endswith("_usd"))]


def _derived(claim: Decimal, values: Sequence[Decimal]) -> bool:
    """A figure one arithmetic step from two values its line cites: their
    difference, sum or ratio, or the change from one to the other in percent or
    bps (S1). `a 2.02 premium [quote.venue_price_usd, mark.price_usd]` is the
    venue less the mark. A fabricated figure is none of these."""
    for i, a in enumerate(values):
        for b in values[i + 1:]:
            steps = [a - b, b - a, a + b]
            if b:
                steps += [a / b, (a - b) / b * 100, (a - b) / b * 10_000]
            if a:
                steps += [b / a, (b - a) / a * 100, (b - a) / a * 10_000]
            if any(_matches(claim, step) for step in steps):
                return True
    return False


def _check_figure(figure: Figure, fields: list[_Resolved], *, loose: bool,
                  about: Sequence[str], pool: Any) -> tuple[Refusal | None, list[Imprecision]]:
    """Each figure on the line is a field it cites, or a value an asset the line is
    about holds, or it refuses the report as fabricated.

    `loose` says a citation on the line named no field. Then no figure on it can be
    told from a computed one by what it cites, so every figure is checked by value,
    bps included. `pool()` lists the values of the assets the line is about."""
    singles = [(f, _number(f.value)) for f in fields if f.single]
    if not singles and not loose:
        return None, []  # a computed figure: cited, not checked
    check_bps = loose or any(f.name.endswith("_bps") for f, _ in singles)
    cited = "; ".join(f"{f.name} = {f.value}" for f, _ in singles) or "no field that exists"
    found: list[Imprecision] = []
    held: list[tuple[_Resolved, Decimal]] | None = None
    for kind, written, claim in _claims(figure.text):
        if kind == "bps" and not check_bps:
            continue  # computed from the prices it cites, like a percentage: not checked
        scale = Decimal(1_000_000) if kind == "millions" else Decimal(1)
        if any(_matches(claim, v / scale) for _, v in _fits(kind, singles)):
            continue
        if kind == "plain" and _derived(claim, [v for _, v in singles]):
            continue  # computed from the fields the line cites, as the brief asks
        held = held if held is not None else [(f, _number(f.value)) for f in pool()]
        match = next((f for f, v in _fits(kind, held) if _matches(claim, v / scale)), None)
        if match is not None:  # a real value, cited under the wrong reference
            found.append(Imprecision(cited=", ".join(f.name for f, _ in singles) or "no field",
                                     found=match.name, written=written, line=figure.line))
            continue
        return (Refusal("figure", f"{written} matches none of the fields it cites: {cited}; "
                                  f"nor any value of {', '.join(about) or 'the snapshot'}",
                        figure.line), found)
    return None, found


def _examine(report: Report, snapshot: Mapping[str, Any], *, contract: Contract, agent: str,
             snapshot_sha256: str) -> tuple[tuple[Refusal, ...], tuple[Imprecision, ...]]:
    refusals: list[Refusal] = []
    imprecisions: list[Imprecision] = []
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
        if entry["status"]["value"] != "tradeable" and call.word != "sell":
            # A sell may name an asset out of the buy universe: selling what is held is
            # a different risk from buying (the operator's decision on S8).
            refusals.append(Refusal("asset", f"{call.symbol} is {entry['status']['value']}, "
                                    "not tradeable", call.line))

    lines = report.text.split("\n")

    def line_of(item: str) -> int | None:
        """The line whose citation holds the item; else the first line naming it."""
        for n, text in enumerate(lines, start=1):
            if any(item in items for items in _citations(text)):
                return n
        return next((n for n, text in enumerate(lines, start=1) if item in text), None)

    regions = [(report.opening, None, ())]
    regions += [(c.text, snap.by_address.get(c.address), c.figures) for c in report.calls]
    for text, scope, figures in regions:
        for items in _citations(text):
            for item in items:
                if _ITEM_ALL.match(item):
                    continue
                _, why = snap.resolve(item, scope)
                if why:  # a reference that names nothing as written: recorded, not refused
                    loosely = snap.loosely(item, scope)
                    imprecisions.append(Imprecision(cited=item, found=loosely and loosely.name,
                                                    line=line_of(item), why=why))
        for figure in figures:
            fields: list[_Resolved] = []
            # No citation on the line, whether it has brackets of prose or none at all:
            # nothing marks a figure as computed, so every figure is checked by value (R5).
            loose = not _citations(figure.text)
            for items in _citations(figure.text):
                for item in items:
                    if _ITEM_ALL.match(item):
                        continue
                    resolved, why = snap.resolve(item, scope)
                    if why:
                        loosely = snap.loosely(item, scope)
                        if loosely is None:
                            loose = True
                        else:
                            resolved = [loosely]
                    fields += resolved
            entries = snap.about(scope, figure.text)
            refusal, found = _check_figure(
                figure, fields, loose=loose, about=[e["asset"]["symbol"] for e in entries],
                pool=lambda entries=entries: snap.values(entries))
            imprecisions += found
            if refusal:
                refusals.append(refusal)
    return tuple(refusals), tuple(imprecisions)


def check(report: Report, snapshot: Mapping[str, Any], *, contract: Contract, agent: str,
          snapshot_sha256: str) -> tuple[Refusal, ...]:
    """Hold a parsed report to its seat's contract and to the snapshot it names."""
    return _examine(report, snapshot, contract=contract, agent=agent,
                    snapshot_sha256=snapshot_sha256)[0]


def validate(text: str, snapshot: Mapping[str, Any], *, contract: Contract, agent: str,
             snapshot_sha256: str) -> Verdict:
    """Parse and check. Never raises for anything a model could write."""
    report, refusals = parse(text)
    if report is None:
        return Verdict(None, refusals)
    checked, imprecise = _examine(report, snapshot, contract=contract, agent=agent,
                                  snapshot_sha256=snapshot_sha256)
    return Verdict(report, refusals + checked, imprecise)
