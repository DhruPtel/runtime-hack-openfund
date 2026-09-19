"""The one valuation function, and the price cross-check beside it. Unit 1.4.

**The mark.** Chainlink marks the book (PLAN §11). An asset's mark is the answer
of the feed pinned to its address by 1.2, and the reading must come from that
feed's proxy. It is matched by address, never by ticker: a counterfeit chooses
its own ticker and would inherit the real feed by name (F0.8.1, F0.8.3). A mark
must also be fresh, as 1.3 judges freshness: heartbeat plus margin in
open-session time (DECISION 2026-09-18).

**The multiplier is not applied again.** Per the documentation, a Chainlink
answer for a stock token already incorporates `uiMultiplier()`. 0.4 could not
measure that: the largest multiplier effect was 22 bps against a 142 bps noise
floor between feed and corroborator (findings F0.4.4). So this rule is
**documented and corroborated, not measured**. Applying the multiplier here as
well would count it twice.

**Value** is raw units times the mark, exact, with no rounding and no float.
`value()` is the only place in the codebase where a quantity becomes a USD
value. 1.6's snapshot and 6.x's books call it. Anything else that multiplies an
amount by a price is the bug CODEBASE §8 names. With no mark there is no value,
and never a zero: the holding stays in the book with the reason.

**The cross-check.** GeckoTerminal corroborates the mark. The divergence is
`(mark - corroborator) / corroborator` in basis points: the formula F0.4.5's
numbers came from (`probes/feed.py`, `bps(feed, gecko)`). So the 100 bps line
means what it meant when it was decided. The result is rounded away from zero at
0.01 bps, so rounding never understates it. The tier is the corroborator's 24h
volume, as `config/thresholds.json` sets it:
- below the line, the asset is excluded from the universe rather than vetoed
  each cycle (0.4 decision);
- above it, the veto fires past `divergence_max_bps` on either side.

A liquid name is not safe on that account. AMZN diverged 499.5 bps on $2.19M of
volume while feed and quote agreed to 20 bps (F0.4.5), and the veto fires there.

**Absent corroboration is undetermined, not agreement.** A corroborator that
did not answer blocks. It never becomes a divergence of zero.

**A named exception until 3.4.** CODEBASE §3 reserves threshold comparisons to
`core/gates.py`, which is 3.4's. The tier's two comparisons stay here, where the
plan put them, and 3.4 sweeps them into `gates.py` with the other two named
exceptions (DECISION, LESSONS 2026-09-18). They read their thresholds as
arguments, never literals.

`core/` imports nothing from `adapters/`: every reading, verdict and threshold
arrives as an argument.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .types import (
    BPS, USD, Amount, Asset, AssetId, Check, Fixed, Holding, Observation, Price, UniverseStatus,
)

# --- rules: each refusal names the one that refused ------------------------------

RULE_MARKABILITY = "markability"            # no Chainlink feed pinned for the address
RULE_READING = "reading"                    # the feed was not read
RULE_FEED_MATCH = "feed-match"              # the reading is not the pinned feed's answer for this asset
RULE_FRESHNESS = "freshness"                # the newest round is stale, or its age undetermined
RULE_BALANCE = "balance"                    # the holding's balance was not read
RULE_CORROBORATION = "corroboration"        # the corroborating price is missing
RULE_VOLUME = "volume"                      # the volume that selects the tier is missing
RULE_CORROBORATOR_LINE = "corroborator-line"  # below the line: excluded, not vetoed
RULE_DIVERGENCE = "divergence"              # above the line and past the limit: vetoed

FEED_SYSTEM = "chainlink-feed"


# --- the mark ---------------------------------------------------------------------

@dataclass(frozen=True)
class Mark:
    """Whether a feed reading is the asset's mark. `rule` names the rule that
    refused or left it undetermined, and is None when the reading is the mark."""

    asset: AssetId
    reading: Observation | None
    check: Check
    rule: str | None

    @property
    def price(self) -> Price | None:
        return self.reading.value if self.check.passes else None


def mark(asset: Asset, reading: Observation | None, fresh: Check) -> Mark:
    """Judge `reading` as `asset`'s mark. The rules run in a fixed order, and the
    first that does not pass is named: markability, reading, feed match,
    freshness. `fresh` is 1.3's verdict on this reading."""
    def refused(rule: str, value: bool | None, reason: str) -> Mark:
        return Mark(asset.id, reading, Check(value, f"[{rule}] {reason}"), rule)

    if not asset.markability.passes:  # a markable Asset always carries its pinned feed
        return refused(RULE_MARKABILITY, asset.markability.value,
                       asset.markability.reason or "no Chainlink feed pinned for this address")
    if reading is None or not reading.ok:
        return refused(RULE_READING, None, "the feed was not read" if reading is None
                       else f"{reading.status.value}: {reading.detail}")
    proxy = asset.feed.proxy.address
    value = reading.value
    if (reading.source.system != FEED_SYSTEM or reading.source.locator != proxy
            or not isinstance(value, Price) or value.base != asset.id or value.quote_unit != USD
            or value.decimals != asset.feed.decimals):
        return refused(RULE_FEED_MATCH, False,
                       f"not the answer of the feed pinned to this address ({proxy}): "
                       f"{reading.source.system}:{reading.source.locator}")
    if not fresh.passes:
        return refused(RULE_FRESHNESS, fresh.value, fresh.reason or "not judged fresh")
    return Mark(asset.id, reading, Check(True, f"{asset.feed.name} at {proxy}, round "
                                               f"{reading.source_ref}; {fresh.reason}"), None)


# --- value: the one place a quantity becomes USD -----------------------------------

def value(amount: Amount, price: Price) -> Fixed:
    """Raw units × the mark, exact: `amount.decimals + price.decimals` places, in USD.

    The multiplier is not applied: per the documentation the feed answer already
    incorporates it, which is documented, not measured (F0.4.4).
    """
    if price.base != amount.asset:
        raise TypeError("a price values only its own asset")
    if price.quote_unit != USD:
        raise ValueError("value is in USD")
    return Fixed(amount.raw * price.raw, amount.decimals + price.decimals, USD)


def value_holding(asset: Asset, balance: Observation, the_mark: Mark, *,
                  universe_status: UniverseStatus, universe_reason: str | None) -> Holding:
    """A holding, valued through `value()` when there is both a balance and a
    mark, and otherwise carried with no value and the reason. Never zero. The
    universe status is the caller's (1.6, 1.8); this only values."""
    if the_mark.asset != asset.id:
        raise ValueError("the mark is for another asset")
    if not balance.ok:
        return Holding(asset=asset.id, balance=balance, universe_status=universe_status,
                       universe_reason=universe_reason, mark=None, value=None,
                       value_reason=f"[{RULE_BALANCE}] balance not read: {balance.status.value}: "
                                    f"{balance.detail}")
    if not the_mark.check.passes:
        return Holding(asset=asset.id, balance=balance, universe_status=universe_status,
                       universe_reason=universe_reason, mark=None, value=None,
                       value_reason=f"no mark, so no value (not zero): {the_mark.check.reason}")
    return Holding(asset=asset.id, balance=balance, universe_status=universe_status,
                   universe_reason=universe_reason, mark=the_mark.reading,
                   value=value(balance.value, the_mark.price), value_reason=None)


# --- the cross-check -----------------------------------------------------------------

def _threshold(thresholds: Mapping[str, Any], name: str, unit: str) -> Fixed:
    raw = thresholds.get(name)
    if raw is None:
        raise ValueError(f"{name} is null: unresolved, and it blocks the check that reads it")
    if type(raw) is int:
        return Fixed(raw, 0, unit)
    if isinstance(raw, str):
        return Fixed.parse(raw, unit)
    raise TypeError(f"{name} must be an integer or a decimal string, never a float")


@dataclass(frozen=True)
class DivergenceRule:
    """The two-tier rule from `config/thresholds.json` (0.4 decision), both
    numbers provisional: the veto limit above the line, and the line itself."""

    max_bps: Fixed
    min_volume_usd: Fixed

    @classmethod
    def from_thresholds(cls, thresholds: Mapping[str, Any]) -> DivergenceRule:
        return cls(max_bps=_threshold(thresholds, "divergence_max_bps", BPS),
                   min_volume_usd=_threshold(thresholds, "corroborator_min_volume_usd_24h", USD))


def divergence_bps(the_mark: Price, corroborator: Price) -> Fixed:
    """`(mark - corroborator) / corroborator`, in basis points, signed: negative
    when the mark is below its corroborator. Rounded away from zero at 0.01 bps."""
    if (the_mark.base, the_mark.quote_unit) != (corroborator.base, corroborator.quote_unit):
        raise TypeError("a divergence compares two prices of one asset in one unit")
    if corroborator.raw <= 0:
        raise ValueError("a corroborator price is positive")
    scale = max(the_mark.decimals, corroborator.decimals)
    m = the_mark.raw * 10 ** (scale - the_mark.decimals)
    c = corroborator.raw * 10 ** (scale - corroborator.decimals)
    numerator = (m - c) * 10_000 * 100  # hundredths of a basis point
    magnitude = -(-abs(numerator) // c)
    return Fixed(magnitude if numerator >= 0 else -magnitude, 2, BPS)


@dataclass(frozen=True)
class CrossCheck:
    """One asset's mark against its corroborator, with everything the verdict
    read: the divergence, the volume and tier, and whether the corroborator is
    independent of the execution venue."""

    asset: AssetId
    mark: Mark
    corroboration: Observation
    volume: Observation
    divergence: Fixed | None
    independent: bool
    tier: str | None           # "above-line", "below-line", or None when undetermined
    verdict: Check
    rule: str | None

    @property
    def universe_status(self) -> UniverseStatus | None:
        """The status an exclusion books as, when this check excludes; 1.6 applies it."""
        return UniverseStatus.BELOW_CORROBORATOR_LINE if self.rule == RULE_CORROBORATOR_LINE else None


def cross_check(the_mark: Mark, corroboration: Observation, volume: Observation,
                rule: DivergenceRule, *, independent: bool) -> CrossCheck:
    """The tiered divergence verdict. The first rule that does not pass is
    named: the mark, the corroboration, the volume, the corroborator line, then
    the divergence."""
    def verdict(value: bool | None, name: str | None, reason: str, *, divergence=None,
                tier=None) -> CrossCheck:
        return CrossCheck(the_mark.asset, the_mark, corroboration, volume, divergence, independent,
                          tier, Check(value, f"[{name}] {reason}" if name else reason), name)

    if not the_mark.check.passes:
        return verdict(the_mark.check.value, the_mark.rule, f"no mark to corroborate: "
                                                            f"{the_mark.check.reason}")
    if not corroboration.ok:
        return verdict(None, RULE_CORROBORATION, "absent corroboration is undetermined and blocks; "
                       f"it is not agreement: {corroboration.status.value}: {corroboration.detail}")
    seen = corroboration.value
    if not isinstance(seen, Price) or seen.base != the_mark.asset or seen.quote_unit != USD:
        raise TypeError("a corroboration is a USD price of the marked asset")
    if seen.raw <= 0:
        return verdict(None, RULE_CORROBORATION, f"a corroborating price of {seen.raw} is not usable")
    d = divergence_bps(the_mark.price, seen)
    if not volume.ok:
        return verdict(None, RULE_VOLUME, f"the tier cannot be chosen without the 24h volume: "
                                          f"{volume.status.value}: {volume.detail}", divergence=d)
    traded = volume.value
    if not isinstance(traded, Fixed) or traded.unit != USD:
        raise TypeError("the corroborator's volume is USD")
    magnitude = Fixed(abs(d.raw), d.decimals, BPS)
    if traded < rule.min_volume_usd:
        return verdict(False, RULE_CORROBORATOR_LINE,
                       f"24h volume ${_text(traded)} is below the ${_text(rule.min_volume_usd)} line: "
                       f"excluded from the universe, not vetoed each cycle (0.4 decision); "
                       f"divergence {_text(d)} bps recorded", divergence=d, tier="below-line")
    if magnitude > rule.max_bps:
        return verdict(False, RULE_DIVERGENCE,
                       f"veto: divergence {_text(d)} bps exceeds {_text(rule.max_bps)} bps on "
                       f"${_text(traded)} of 24h volume", divergence=d, tier="above-line")
    return verdict(True, None, f"divergence {_text(d)} bps within {_text(rule.max_bps)} bps on "
                               f"${_text(traded)} of 24h volume", divergence=d, tier="above-line")


def _text(quantity: Fixed) -> str:
    """A Fixed as decimal text, for reasons only. Never parsed back."""
    sign = "-" if quantity.raw < 0 else ""
    digits = str(abs(quantity.raw)).rjust(quantity.decimals + 1, "0")
    if quantity.decimals == 0:
        return sign + digits
    whole, fraction = digits[:-quantity.decimals], digits[-quantity.decimals:].rstrip("0")
    return sign + whole + ("." + fraction if fraction else "")
