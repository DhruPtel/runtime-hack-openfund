"""Reports to target weights, or no rebalance. A total function (unit 3.1).

**What goes in:** the accepted reports, each already parsed by
`agents/schema.py`, as the seat and, per call, the asset's address, the word
and the confidence word. Also each seat's kind, and the book as it stands: each
position's weight and the cash weight. `core/` takes these as data and fetches
nothing.

**The arithmetic, per asset,** as the report format decided (LESSONS
2026-09-19):
- **direction:** the mean, over the direction seats that called the asset, of
  +1 for buy, 0 for hold and −1 for sell, each times its confidence;
- **caution:** the largest confidence among condition seats that said
  caution. Proceed adds nothing, and neither does silence;
- **score:** direction × (1 − caution).

Confidence words become numbers through `config/analysts.json`'s
`confidence_weights`, provisional since 3.1.

**A target starts where the position is** (operator, 2026-09-19, the Phase 3
batch brief). The approved format says hold means keep and don't add, and a held
asset nobody mentions is kept. So:
- **a positive score raises** the position by `score × max_position_weight`,
  never past that limit;
- **a negative score cuts** it by the same measure, never below zero;
- **hold, a score of zero, silence, and caution with no direction call** leave
  it exactly where it is;
- **a new position comes only from a buy.** A sell on an asset not held has
  nothing to cut.

A score is therefore a fraction of one position limit per cycle. A buy at high
confidence, uncautioned, moves an asset three quarters of the way to the
limit.

**Cash takes the rest, and the floor holds.** New buys are paid from cash above
`cash_floor_usd`, plus what the cycle's cuts free. If that is not enough, every
raise is scaled by the same share. Each change is rounded toward zero at six
decimal places, so no trade is larger than decided, and what rounding drops is
shown as the residual, left in cash. Rows are ordered by address, so the result
does not depend on the order reports arrive in.

**No rebalance keeps every holding** (PLAN §2 invariant 6, §11). It happens when:
- fewer seats reported than the quorum;
- every seat that reported abstained;
- a limit it needs is unresolved.
It never liquidates anything.

Every limit is applied by `core/gates.py`, which is the only module that
compares against one.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from typing import Any, Mapping, Sequence

from . import gates

#: The approved vocabularies' arithmetic (planning/REPORT-FORMAT.md). A word
#: outside these never reaches here: 2.2 refuses the report.
DIRECTION = {"buy": Decimal(1), "hold": Decimal(0), "sell": Decimal(-1)}
CAUTION = "caution"

#: The precision a target is kept to: a millionth of the NAV.
QUANTUM = Decimal("0.000001")


def _text(value: Decimal | None) -> str | None:
    """Exact decimal text for the record, with no exponent and no trailing zeros."""
    if value is None:
        return None
    text = format(value.normalize(), "f")
    return "0" if text in ("-0", "0") else text


@dataclass(frozen=True)
class Contribution:
    """One seat's word on one asset, and the number it adds."""

    seat: str
    kind: str  # "direction" or "condition"
    word: str
    confidence: str
    value: Decimal  # ±confidence for direction, the confidence for caution, 0 for proceed

    def as_dict(self) -> dict[str, Any]:
        return {"seat": self.seat, "kind": self.kind, "word": self.word,
                "confidence": self.confidence, "value": _text(self.value)}


@dataclass(frozen=True)
class Row:
    address: str
    symbol: str
    contributions: tuple[Contribution, ...]
    direction: Decimal | None  # None: no direction seat called it
    caution: Decimal
    score: Decimal | None
    current: Decimal
    target: Decimal
    why: str

    def as_dict(self) -> dict[str, Any]:
        return {"address": self.address, "symbol": self.symbol,
                "contributions": [c.as_dict() for c in self.contributions],
                "direction": _text(self.direction), "caution": _text(self.caution),
                "score": _text(self.score), "current": _text(self.current),
                "target": _text(self.target), "why": self.why}


@dataclass(frozen=True)
class Proposal:
    rebalance: bool
    reason: str
    reported: tuple[str, ...]  # the seats whose reports were accepted, abstentions included
    quorum: gates.Gate
    rows: tuple[Row, ...]
    cash_current: Decimal
    cash_target: Decimal
    residual: Decimal  # what rounding each change toward zero left in cash
    funded: Decimal  # the share of the wanted raises that cash above the floor paid for
    confidence_weights: Mapping[str, Decimal]

    def target(self, address: str) -> Decimal | None:
        return next((r.target for r in self.rows if r.address == address), None)

    def as_dict(self) -> dict[str, Any]:
        return {"rebalance": self.rebalance, "reason": self.reason,
                "reported": list(self.reported), "quorum": self.quorum.as_dict(),
                "rows": [r.as_dict() for r in self.rows],
                "cash": {"current": _text(self.cash_current), "target": _text(self.cash_target)},
                "residual": _text(self.residual), "funded": _text(self.funded),
                "confidence_weights": {w: _text(v) for w, v in self.confidence_weights.items()}}


def _contributions(reports: Sequence[Mapping[str, Any]], kinds: Mapping[str, str],
                   weights: Mapping[str, Decimal]) -> dict[str, list[Contribution]]:
    by_asset: dict[str, list[Contribution]] = {}
    for report in reports:
        seat = report["seat"]
        kind = kinds[seat]
        for call in report.get("calls") or ():
            confidence = weights[call["confidence"]]
            if kind == "direction":
                value = DIRECTION[call["word"]] * confidence
            else:
                value = confidence if call["word"] == CAUTION else Decimal(0)
            by_asset.setdefault(call["address"].lower(), []).append(
                Contribution(seat, kind, call["word"], call["confidence"], value))
    return by_asset


def _kept(rows: list[Row], cash_weight: Decimal, reason: str, reported: tuple[str, ...],
          quorum: gates.Gate, weights: Mapping[str, Decimal]) -> Proposal:
    """No rebalance: every target is the position as it stands."""
    kept = tuple(Row(r.address, r.symbol, r.contributions, r.direction, r.caution, r.score,
                     r.current, r.current, f"no rebalance: {reason}") for r in rows)
    return Proposal(False, reason, reported, quorum, kept, cash_weight, cash_weight,
                    Decimal(0), Decimal(0), weights)


def aggregate(reports: Sequence[Mapping[str, Any]], *, kinds: Mapping[str, str],
              current: Mapping[str, Decimal], cash_weight: Decimal, nav_usd: Decimal,
              limits: gates.Limits, confidence_weights: Mapping[str, Decimal],
              symbols: Mapping[str, str]) -> Proposal:
    """Target weights from accepted reports. Never raises for what the reports
    say. `current` holds each position's weight, keyed by lowercased address.
    `reports` are `schema.Report.as_dict()` of accepted reports only."""
    current = {address.lower(): weight for address, weight in current.items()}
    reported = tuple(sorted(report["seat"] for report in reports))
    by_asset = _contributions(reports, kinds, confidence_weights)

    rows: list[Row] = []
    for address in sorted(set(by_asset) | set(current)):
        said = tuple(sorted(by_asset.get(address, ()), key=lambda c: c.seat))
        directions = [c.value for c in said if c.kind == "direction"]
        cautions = [c.value for c in said if c.kind == "condition" and c.word == CAUTION]
        direction = sum(directions, Decimal(0)) / len(directions) if directions else None
        caution = max(cautions, default=Decimal(0))
        score = None if direction is None else direction * (1 - caution)
        held = current.get(address, Decimal(0))
        rows.append(Row(address, symbols.get(address, address), said, direction, caution, score,
                        held, held, ""))

    quorum = gates.quorum(len(reported), limits)
    if not quorum.passes:
        return _kept(rows, cash_weight, quorum.reason, reported, quorum, confidence_weights)
    if all(not report.get("calls") for report in reports):
        return _kept(rows, cash_weight, "every seat that reported abstained", reported, quorum,
                     confidence_weights)
    if limits.max_position_weight is None:
        return _kept(rows, cash_weight, "max_position_weight is null: unresolved, and it blocks",
                     reported, quorum, confidence_weights)

    wanted: dict[str, Decimal] = {}
    why: dict[str, str] = {}
    for row in rows:
        if row.score is None:
            why[row.address] = ("caution with no direction call: kept" if row.contributions
                                else "no seat mentioned it: kept")
            continue
        if row.score == 0:
            why[row.address] = "the direction calls net to zero: kept" if any(
                c.value for c in row.contributions if c.kind == "direction") else "hold: kept"
            continue
        step = abs(row.score) * limits.max_position_weight
        if row.score > 0:
            rise = gates.raise_by(row.current, step, limits)
            wanted[row.address] = rise
            why[row.address] = (f"buy: raised by {_text(rise)}" if rise == step
                                else f"buy: raised by {_text(rise)}, capped at the position limit"
                                if rise else "buy: already at the position limit, kept")
        else:
            cut = gates.cut_by(row.current, step)
            wanted[row.address] = -cut
            why[row.address] = (f"sell: cut by {_text(cut)}" if cut else
                                "sell on an asset not held: nothing to cut")

    raises = sum((d for d in wanted.values() if d > 0), Decimal(0))
    released = -sum((d for d in wanted.values() if d < 0), Decimal(0))
    share = gates.funded_share(cash_weight, released, raises, nav_usd, limits)
    if share is None:
        return _kept(rows, cash_weight, "cash_floor_usd is null: unresolved, and it blocks",
                     reported, quorum, confidence_weights)

    final: list[Row] = []
    residual = Decimal(0)
    for row in rows:
        change = wanted.get(row.address, Decimal(0))
        note = why[row.address]
        if change > 0 and share < 1:
            change = change * share
            note += f"; scaled to {_text((share * 100).quantize(Decimal('0.01')))}% by the cash floor"
        kept = change.quantize(QUANTUM, rounding=ROUND_DOWN)  # toward zero, either way
        residual += change - kept
        final.append(Row(row.address, row.symbol, row.contributions, row.direction, row.caution,
                         row.score, row.current, row.current + kept, note))

    moved = sum((r.target - r.current for r in final), Decimal(0))
    return Proposal(True, "quorum met: targets from the calls", reported, quorum, tuple(final),
                    cash_weight, cash_weight - moved, residual, share, confidence_weights)
