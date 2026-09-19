"""Unit 4.4: the chokepoint every order passes before anything is attempted. H.

The decision is the exit run's (`fixtures/cycles/20260919T202259Z/`), signed with the
fund's key, on the capture `67364057-c06abd9e89f0`: six buys approved. Fresh quotes come
from the fake venue (`run/fake_venue.py`), labelled in every answer. Each known-bad order
below is refused, and by the rule it breaks.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fund import config
from fund.core import cash, gates, ledger, orders
from fund.core.types import USD, Amount, Instant, Price
from fund.adapters.fake_venue import FakeVenue
from fund.treasurer import execute, intent, keys, mandate, sign

REPO = Path(__file__).resolve().parents[1]
CYCLE = REPO / "fixtures" / "cycles" / "20260919T202259Z" / "decision"
RECORD = (CYCLE / "record.json").read_bytes()
ENVELOPE = json.loads((CYCLE / "envelope.json").read_text())
SNAPSHOT_BYTES = (REPO / "fixtures" / "snapshots" / "67364057-c06abd9e89f0"
                  / "snapshot.json").read_bytes()
SNAPSHOT = json.loads(SNAPSHOT_BYTES)
OTHER_SNAPSHOT = (REPO / "fixtures" / "snapshots" / "66852293-253315c0e691"
                  / "snapshot.json").read_bytes()
MANDATE = mandate.load()
THRESHOLDS = config.load_json("thresholds.json")
LIMITS = gates.Limits.from_config(THRESHOLDS, MANDATE, config.load_json("models.json"))
PUBLISHED = keys.published_key()
AT = Instant(int(datetime.fromisoformat(MANDATE["approved_at"].replace("Z", "+00:00"))
                 .timestamp() * 1000) + 3_600_000)
USDG, _ = cash.cash_leg(SNAPSHOT)
DECISION = execute.Decision(RECORD, ENVELOPE, SNAPSHOT_BYTES)
SIX = intent.intents(RECORD, ENVELOPE, public_key=PUBLISHED, mandate=MANDATE, at=AT)


def opened(usdg: str = "200") -> list:
    mark = cash.mark_of(SNAPSHOT, USDG.address)
    return [ledger.Opening("paper", Amount.from_units(usdg, 6, USDG), mark)]


def admit(order, *, decision=DECISION, public_key=PUBLISHED, the_mandate=MANDATE, when=AT,
          fetched=None, events=None, venue=None, **rest):
    venue = venue or FakeVenue(SNAPSHOT, lambda: Instant((fetched or when).epoch_ms - 5_000))
    fresh = execute.requote(order, venue, when, THRESHOLDS)
    return execute.admit(order, decision, public_key=public_key, mandate=the_mandate,
                         limits=LIMITS, fresh=fresh, at=when,
                         events=opened() if events is None else events, **rest)


def refused_by(admission) -> set[str]:
    return {g.rule for g in admission.refusals}


def resigned(change) -> tuple[execute.Decision, str]:
    """The exit run's record, changed, and signed by a scratch key published for the test."""
    record = json.loads(RECORD)
    change(record)
    key = Ed25519PrivateKey.generate()
    body = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    return execute.Decision(body, sign.sign(body, key), SNAPSHOT_BYTES), sign.public_hex(key)


# --- the exit run's six orders pass ---------------------------------------------------------------

def test_the_exit_runs_six_approved_orders_are_admitted_on_fresh_quotes():
    for order in SIX:
        admission = admit(order)
        assert admission.admitted, admission.reason
        rules = {g.rule for g in admission.checks}
        assert {"signature", "snapshot", "in-record", "mandate-term", "mandate-legs",
                "snapshot-age", "quote", "held", "cash-floor"} <= rules
        assert admission.fresh.observation.fetch_time.epoch_ms == AT.epoch_ms - 5_000
        assert "FAKE VENUE" in admission.fresh.observation.detail


# --- the regression vectors: each refused by its own rule -----------------------------------------

def test_s13_a_record_signed_by_another_key_is_refused_at_the_signature():
    foreign = execute.Decision(RECORD, sign.sign(RECORD, Ed25519PrivateKey.generate()),
                               SNAPSHOT_BYTES)
    assert "signature" in refused_by(admit(SIX[0], decision=foreign))
    assert "signature" in refused_by(admit(SIX[0], public_key=None))


def test_a_decision_regated_on_another_snapshot_is_refused():
    other = execute.Decision(RECORD, ENVELOPE, OTHER_SNAPSHOT)
    assert refused_by(admit(SIX[0], decision=other)) == {"snapshot"}


def test_an_order_the_record_vetoed_or_one_changed_by_a_unit_is_not_in_the_record():
    vetoed = dataclasses.replace(SIX[0], order_id=orders.order_id(ENVELOPE["decision_id"], 2),
                                 idempotency_key=orders.idempotency_key(ENVELOPE["decision_id"], 2))
    assert refused_by(admit(vetoed)) == {"in-record"}
    more = dataclasses.replace(SIX[0], sell=Amount(SIX[0].sell.raw + 1, 6, USDG))
    assert refused_by(admit(more)) == {"in-record"}
    rekeyed = dataclasses.replace(SIX[0], idempotency_key="another-key")
    assert refused_by(admit(rekeyed)) == {"in-record"}


def test_a_mandate_that_has_expired_by_the_time_of_submission_refuses():
    expires = int(datetime.fromisoformat(MANDATE["expires_at"].replace("Z", "+00:00"))
                  .timestamp() * 1000)
    assert refused_by(admit(SIX[0], when=Instant(expires))) == {"mandate-term"}


def test_s10_a_buy_whose_usdg_leg_the_mandate_does_not_allow_is_refused():
    no_cash = {**MANDATE, "allowed_assets": [a for a in MANDATE["allowed_assets"]
                                             if a["address"] != USDG.address]}
    assert refused_by(admit(SIX[0], the_mandate=no_cash)) == {"mandate-legs"}


def test_s11_a_decision_judged_16_minutes_after_its_snapshot_is_refused():
    block = int(datetime.fromisoformat("2026-09-19T20:20:32+00:00").timestamp() * 1000)

    def late(record):
        record["decided_at_ms"] = record["plan"]["judged_at_ms"] = block + 16 * 60_000

    decision, key = resigned(late)
    order = dataclasses.replace(
        SIX[0], order_id=orders.order_id(decision.envelope["decision_id"], 1),
        idempotency_key=orders.idempotency_key(decision.envelope["decision_id"], 1))
    admission = admit(order, decision=decision, public_key=key)
    assert refused_by(admission) == {"snapshot-age"}
    assert "960" in next(g for g in admission.refusals).reason


def test_a_fresh_quote_older_than_the_limit_is_refused_at_quote_age():
    assert refused_by(admit(SIX[0], fetched=Instant(AT.epoch_ms - 120_000))) == {"quote-age"}


def test_a_fresh_quote_for_another_amount_is_refused_as_another_orders():
    class Elsewhere(FakeVenue):
        def quote(self, request):
            other = dataclasses.replace(request, sell=Amount(request.sell.raw * 2, 6, USDG))
            return super().quote(other)

    admission = admit(SIX[0], venue=Elsewhere(SNAPSHOT, lambda: Instant(AT.epoch_ms - 5_000)))
    assert refused_by(admission) == {"quote"}
    assert "for another order" in admission.reason


def test_an_order_that_gives_more_than_the_book_holds_is_refused_at_held():
    assert "held" in refused_by(admit(SIX[0], events=opened("10")))


def test_the_floor_refuses_the_last_buy_when_booked_cash_cannot_carry_it():
    """140 USDG: after the six buys, $13.42 would be left, under the $20 floor. The last
    buy is refused by the floor; the others are admitted."""
    events = opened("140")
    verdicts = {o.order_id.rpartition("/")[2]: admit(o, events=events) for o in SIX}
    assert refused_by(verdicts["8"]) == {"cash-floor"}
    assert all(v.admitted for i, v in verdicts.items() if i != "8")
    assert "dropped" in verdicts["8"].reason


def test_partway_through_the_floor_counts_what_filled_at_what_it_booked():
    """The first five filled on paper, booked into the ledger: the sixth is judged on
    the cash the ledger holds after them, not the plan's projection of them."""
    events = opened("150")
    for order in SIX[:5]:
        submitted = orders.transition(order, orders.S)
        events.append(ledger.paper_fill(submitted, admit(order, events=events).fresh
                                        .observation.value, SNAPSHOT))
    filled = [int(o.order_id.rpartition("/")[2]) for o in SIX[:5]]
    assert admit(SIX[5], events=events, filled=filled).admitted
    fewer = opened("140") + events[1:]
    assert refused_by(admit(SIX[5], events=fewer, filled=filled)) == {"cash-floor"}


def test_a_live_order_is_refused_until_phase_5_sets_the_live_budget():
    live = dataclasses.replace(SIX[0], mode=ledger.ExecutionMode.LIVE)
    assert "live-budget" in refused_by(admit(live, events=[
        ledger.Opening("real", Amount.from_units("200", 6, USDG),
                       cash.mark_of(SNAPSHOT, USDG.address))]))
