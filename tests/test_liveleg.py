"""Units 5.1 and 5.2: the live leg — its signed authority, its chokepoint, and the one
executor that can spend. H throughout: this is real money.

Nothing here reaches the network. The venue is a transport answering a recorded shape,
and the chain is `test_reconcile.FakeRpc`, serving probe 0.10's real receipt: 0.00003
ETH into 0.078742 USDG, gas-sponsored, inside a bundler's transaction. So every amount
asserted below is one the chain actually produced.

**The clock.** The committed capture is the Saturday exit run's, whose block predates
the mandate's approval by an hour and a half. A live leg is judged at the clock it runs
at — S11 gives the snapshot fifteen minutes — so these tests run a minute after that
block and hold the approved mandate's terms with its window moved back to it. The
mandate's own dates are tested in `test_mandate.py`; what is tested here is the rest.
"""

from __future__ import annotations

import dataclasses
import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fund import config
from fund.adapters import bankr_quote
from fund.core import cash, gates, ledger
from fund.core.types import (
    BPS, USD, Amount, AssetId, ExecutionMode, FetchStatus, Fixed, Instant, Observation,
    OrderState, Quote,
)
from fund.store import db
from fund.store.journal import Journal
from fund.store.orders import OrderStore
from fund.treasurer import execute, instruct, sign
from fund.treasurer import mandate as mandates
from test_reconcile import RECORDED, SOLD, WALLET, FakeRpc, charged

REPO = Path(__file__).resolve().parents[1]
SNAPSHOT_BYTES = (REPO / "fixtures" / "snapshots" / "67364057-c06abd9e89f0"
                  / "snapshot.json").read_bytes()
SNAPSHOT = json.loads(SNAPSHOT_BYTES)
OTHER_SNAPSHOT = (REPO / "fixtures" / "snapshots" / "66852293-253315c0e691"
                  / "snapshot.json").read_bytes()
CHAIN = SNAPSHOT["block"]["chain_id"]
ETH = AssetId.native(CHAIN)
USDG, USDG_DECIMALS = cash.cash_leg(SNAPSHOT)
THRESHOLDS = config.load_json("thresholds.json")
APPROVED = mandates.load()
LIMITS = gates.Limits.from_config(THRESHOLDS, APPROVED, config.load_json("models.json"))

BLOCK_AT = datetime.fromisoformat(SNAPSHOT["block"]["time"].replace("Z", "+00:00"))
AT = Instant(int(BLOCK_AT.timestamp() * 1000) + 60_000)  # a minute after the evidence
#: The approved mandate, with its week moved to the capture it is exercised on.
IN_FORCE = {**APPROVED,
            "approved_at": (BLOCK_AT - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "expires_at": (BLOCK_AT + timedelta(days=6)).strftime("%Y-%m-%dT%H:%M:%SZ")}
KEY = Ed25519PrivateKey.generate()  # a scratch key: the fund's signs nothing in a test
PUBLIC = sign.public_hex(KEY)
SELL = Amount(SOLD, 18, ETH)  # 0.00003 ETH, the size probe 0.10 actually swapped


# --- the pieces ----------------------------------------------------------------------------------

def quoted(sell: Amount = SELL, buy: AssetId = USDG, *, fetched_ms: int | None = None,
           buys: int | None = None) -> Observation:
    """A quote for the swap at the snapshot's own marks, fetched 5 s before `AT`."""
    sell_mark = cash.mark_of(SNAPSHOT, sell.asset.address)
    buy_mark = cash.mark_of(SNAPSHOT, buy.address)
    decimals = USDG_DECIMALS if buy == USDG else 18
    worth = cash.worth(sell, sell_mark)
    got = buys if buys is not None else int(
        (worth / Decimal(buy_mark.raw).scaleb(-buy_mark.decimals)).scaleb(decimals))
    bought = Amount(got, decimals, buy)
    quote = Quote(sell=sell, buy=bought, min_buy=Amount(got * 95 // 100, decimals, buy),
                  price_impact=Fixed(4, 0, BPS), swap_impact=Fixed(4, 0, BPS),
                  max_price_impact=Fixed(1500, 0, BPS), fee=Fixed(0, 0, BPS), fee_waived=False,
                  slippage=Fixed(500, 0, BPS), sell_price=sell_mark, buy_price=buy_mark,
                  quote_id="test-live-leg")
    return Observation(value=quote, source=bankr_quote.SOURCE, source_time=None,
                       fetch_time=Instant(fetched_ms if fetched_ms is not None
                                          else AT.epoch_ms - 5_000),
                       block=None, status=FetchStatus.OK, detail="a recorded shape, not a quote",
                       source_ref=quote.quote_id)


def instructed(tmp_path: Path, *, sell: Amount = SELL, buy: AssetId = USDG,
               observation: Observation | None = None, window_ms: int = 300_000,
               issued: Instant = AT, mandate=None, key=KEY):
    """One signed instruction, and the order it authorizes."""
    seen = execute.judge(observation or quoted(sell, buy), sell, issued, THRESHOLDS)
    doc = instruct.document(
        sell=sell, symbol="ETH" if sell.asset == ETH else "USDG", buy=buy,
        buy_decimals=USDG_DECIMALS if buy == USDG else 18, quote=seen, snapshot=SNAPSHOT,
        snapshot_sha256=__import__("hashlib").sha256(SNAPSHOT_BYTES).hexdigest(),
        mandate=mandate or IN_FORCE, issued_at=issued,
        expires_at=Instant(issued.epoch_ms + window_ms))
    path, envelope_path = instruct.write(tmp_path / "instruction", doc)
    written = path.read_bytes()
    envelope = sign.sign(written, key)
    envelope_path.write_text(json.dumps(envelope, indent=1, sort_keys=True) + "\n")
    order = instruct.order_of(written, envelope, public_key=sign.public_hex(key),
                              mandate=mandate or IN_FORCE, at=issued)
    return written, envelope, order


def real_book(tmp_path: Path):
    """A database whose real book holds what the wallet held at the capture."""
    conn = db.connect(tmp_path / "fund.sqlite")
    journal, store = Journal(conn), OrderStore(conn)
    for held in SNAPSHOT["holdings"]:
        asset = AssetId(CHAIN, held["asset"]["address"])
        journal.append(ledger.Opening(
            ledger.REAL, Amount.from_units(held["balance"], held["asset"]["decimals"], asset),
            cash.mark_of(SNAPSHOT, asset.address)))
    return conn, store, journal


def admitting(written, envelope, journal, *, mandate=None, at: Instant = AT, key=KEY,
              snapshot_bytes: bytes = SNAPSHOT_BYTES):
    return execute.by_instruction(written, envelope, snapshot_bytes,
                                  public_key=sign.public_hex(key), mandate=mandate or IN_FORCE,
                                  limits=LIMITS, at=at, journal=journal)


def refused_by(admission) -> set[str]:
    return {gate.rule for gate in admission.refusals}


class Venue:
    """A venue answering the swap's reply, and counting how often it is asked."""

    def __init__(self, status=200, body=None):
        self.status, self.body, self.sent = status, body, []

    def __call__(self, url, payload, timeout):
        self.sent.append(json.loads(payload.decode()))
        body = self.body if self.body is not None else {
            "success": True, "hash": RECORDED["tx_hash"],
            "amountSold": 0.00003, "amountReceived": 99.0}  # a claim, not evidence
        return self.status, json.dumps(body).encode(), {}


def live(snapshot=SNAPSHOT, *, venue=None, rpc=None, deadline_s=0.0, **rest):
    return execute.LiveExecutor(
        "TEST-EXEC-SECRET", settings=execute.bankr_exec.Settings.load(),
        rpc=rpc or FakeRpc(), wallet=WALLET, chain_id=CHAIN, confirmations=100,
        snapshot=snapshot, deadline_s=deadline_s, poll_s=0.0, sleep=lambda _: None,
        transport=venue or Venue(), **rest)


def ran(order, executor, store, journal, written, envelope, at: Instant = AT):
    store.add(order)
    return execute.run_order(order.order_id, admission=admitting(written, envelope, journal, at=at),
                             thresholds=THRESHOLDS,
                             venue=instruct.Carried(instruct.carried_quote(json.loads(written))),
                             executor=executor, store=store, journal=journal, at=at)


# --- the signed authority (5.2) --------------------------------------------------------------------

def test_the_order_is_the_instructions_own_bytes_and_a_changed_one_authorizes_nothing(tmp_path):
    """The id and the idempotency key derive from the sha256 of what was signed, so
    they name exactly what the operator authorized (4.0 P2)."""
    written, envelope, order = instructed(tmp_path)
    assert order.mode is ExecutionMode.LIVE and order.state is OrderState.PREPARED
    assert order.order_id == f"{envelope['decision_id']}/1"
    assert order.sell == SELL and order.buy_asset == USDG
    assert order.wallet.address == IN_FORCE["execution_wallet"]

    doc = json.loads(written)
    tampered = json.dumps({**doc, "order": {**doc["order"], "sell": {
        **doc["order"]["sell"], "amount": "0.0003"}}}, indent=1, sort_keys=True).encode() + b"\n"
    assert tampered != written
    with pytest.raises(instruct.InstructionError, match="does not authorize"):
        instruct.order_of(tampered, envelope, public_key=PUBLIC, mandate=IN_FORCE, at=AT)


def test_an_expired_instruction_and_an_unpublished_key_authorize_nothing(tmp_path):
    written, envelope, _ = instructed(tmp_path, window_ms=60_000)
    later = Instant(AT.epoch_ms + 61_000)
    with pytest.raises(instruct.InstructionError, match="expired"):
        instruct.order_of(written, envelope, public_key=PUBLIC, mandate=IN_FORCE, at=later)
    with pytest.raises(instruct.InstructionError, match="no key is published"):
        instruct.order_of(written, envelope, public_key=None, mandate=IN_FORCE, at=AT)
    with pytest.raises(instruct.InstructionError, match="mandate is not in force"):
        instruct.order_of(written, envelope, public_key=PUBLIC,
                          mandate={**IN_FORCE, "revoked": True}, at=AT)


# --- the chokepoint on the live leg (5.2) ----------------------------------------------------------

def test_the_live_leg_passes_the_same_gates_and_the_budget_bounds_it(tmp_path):
    written, envelope, order = instructed(tmp_path)
    conn, _, journal = real_book(tmp_path)
    admission = admitting(written, envelope, journal)(order, execute.judge(
        instruct.carried_quote(json.loads(written)), order.sell, AT, THRESHOLDS), [])
    assert admission.admitted, admission.reason
    assert {g.rule for g in admission.checks} == {
        "signature", "snapshot", "in-instruction", "instruction-term", "snapshot-age",
        "mandate-term", "priced", "mandate", "mandate-legs", "order-size", "quote", "held",
        "live-budget"}
    #: quorum, turnover, position-weight, tradeable and cash-floor are not asked, and
    #: this is the list that says so.
    assert not {"quorum", "turnover", "position-weight", "tradeable", "cash-floor"} & {
        g.rule for g in admission.checks}


def test_the_chokepoint_refuses_what_the_book_cannot_give_or_the_budget_cannot_cover(tmp_path):
    written, envelope, order = instructed(tmp_path)
    conn, _, journal = real_book(tmp_path)
    fresh = execute.judge(instruct.carried_quote(json.loads(written)), order.sell, AT, THRESHOLDS)

    empty = Journal(db.connect(tmp_path / "empty.sqlite"))
    assert "held" in refused_by(admitting(written, envelope, empty)(order, fresh, []))

    spent = {**IN_FORCE, "cumulative_budget_usd": "0.01"}
    assert "live-budget" in refused_by(
        admitting(written, envelope, journal, mandate=spent)(order, fresh, []))
    unset = {**IN_FORCE, "cumulative_budget_usd": None}
    assert "live-budget" in refused_by(
        admitting(written, envelope, journal, mandate=unset)(order, fresh, []))


def test_the_chokepoint_refuses_another_snapshot_a_foreign_key_and_a_stale_quote(tmp_path):
    written, envelope, order = instructed(tmp_path)
    conn, _, journal = real_book(tmp_path)
    fresh = execute.judge(instruct.carried_quote(json.loads(written)), order.sell, AT, THRESHOLDS)

    other = admitting(written, envelope, journal, snapshot_bytes=OTHER_SNAPSHOT)(order, fresh, [])
    assert refused_by(other) == {"snapshot"}

    stranger = sign.public_hex(Ed25519PrivateKey.generate())
    assert "signature" in refused_by(
        execute.by_instruction(written, envelope, SNAPSHOT_BYTES, public_key=stranger,
                               mandate=IN_FORCE, limits=LIMITS, at=AT,
                               journal=journal)(order, fresh, []))

    old = execute.judge(instruct.carried_quote(json.loads(written)), order.sell,
                        Instant(AT.epoch_ms + 3_600_000), THRESHOLDS)
    late = refused_by(admitting(written, envelope, journal,
                                at=Instant(AT.epoch_ms + 3_600_000))(order, old, []))
    assert {"quote-age", "snapshot-age"} <= late  # the quote aged, and so did the evidence


def test_an_instruction_outside_its_window_is_refused_at_the_chokepoint_too(tmp_path):
    """`order_of` refuses to derive an expired instruction's order; an order derived
    in time and run late is refused again, by name, at the chokepoint."""
    written, envelope, order = instructed(tmp_path, window_ms=60_000)
    conn, _, journal = real_book(tmp_path)
    late = Instant(AT.epoch_ms + 120_000)
    fresh = execute.judge(quoted(fetched_ms=late.epoch_ms - 5_000), order.sell, late, THRESHOLDS)
    assert "instruction-term" in refused_by(
        admitting(written, envelope, journal, at=late)(order, fresh, []))


# --- the executor: one send, and the chain decides (5.1) -------------------------------------------

def test_a_reply_with_no_transaction_is_unknown_and_books_nothing(tmp_path):
    """A 400, a 500 or a 200 with nothing to read leaves the order in flight under its
    own key. Nothing is booked from a guess, and no new key is ever minted."""
    written, envelope, order = instructed(tmp_path)
    conn, store, journal = real_book(tmp_path)
    before = len(journal.events())
    venue = Venue(status=400, body={"error": "insufficient balance"})
    done = ran(order, live(venue=venue), store, journal, written, envelope)
    assert done.order.state is OrderState.UNKNOWN and not done.booked
    assert "no transaction to read" in done.order.state_reason
    assert len(journal.events()) == before and len(venue.sent) == 1


def test_a_two_hundred_is_not_a_fill_what_is_booked_is_what_the_chain_moved(tmp_path):
    """The reply claims 99 USDG. The chain's `Transfer` log says 0.078742, and the
    wallet's balance says it gave 0.00003 ETH. The book takes the chain's figures."""
    written, envelope, order = instructed(tmp_path)
    conn, store, journal = real_book(tmp_path)
    done = ran(order, live(), store, journal, written, envelope)
    assert done.order.state is OrderState.CONFIRMED and done.booked
    fill = done.outcome.fill
    assert fill.got.raw == 78_742 and fill.got.asset == USDG
    assert fill.gave.raw == SOLD and fill.gave.asset == ETH
    assert fill.mode is ExecutionMode.LIVE and ledger.book_of(fill) == ledger.REAL
    assert done.order.execution.transaction.tx_hash == RECORDED["tx_hash"]
    assert done.outcome.fee is None  # probe 0.10's operation was sponsored


def test_a_mined_revert_is_a_cost_with_no_fill(tmp_path):
    """200 or not, an operation the EntryPoint says reverted bought nothing and was
    charged gas. The gas is booked, the fill is not, and the order is failed."""
    written, envelope, order = instructed(tmp_path)
    conn, store, journal = real_book(tmp_path)
    reverted = FakeRpc(receipt=charged(RECORDED["receipt"], 21_000_000_000_000, success=False))
    venue = Venue(body={"success": False, "hash": RECORDED["tx_hash"], "message": "reverted"})
    costs_before = ledger.value(journal.events(), book=ledger.REAL, snapshot=SNAPSHOT).costs_usd
    done = ran(order, live(venue=venue, rpc=reverted), store, journal, written, envelope)

    assert done.order.state is OrderState.FAILED and not done.booked
    assert done.outcome.fill is None and done.outcome.fee is not None
    assert done.outcome.fee.amount.raw == 21_000_000_000_000
    after = ledger.value(journal.events(), book=ledger.REAL, snapshot=SNAPSHOT)
    assert after.costs_usd > costs_before
    # gas used the authority even though it bought nothing: it counts against the budget
    assert ledger.traded_usd(journal.events(), book=ledger.REAL) == after.costs_usd
    assert [type(e).__name__ for e in journal.events()[-1:]] == ["Fee"]


def test_a_swap_that_has_not_settled_is_unknown_not_failed(tmp_path):
    """Under the confirmation depth the answer is unknown: the order stays in flight,
    nothing is booked, and 4.9 resolves it at the next start."""
    written, envelope, order = instructed(tmp_path)
    conn, store, journal = real_book(tmp_path)
    shallow = FakeRpc(head=int(RECORDED["receipt"]["blockNumber"], 16) + 3)
    before = len(journal.events())
    done = ran(order, live(rpc=shallow), store, journal, written, envelope)
    assert done.order.state is OrderState.UNKNOWN and not done.booked
    assert "3 of 100 confirmations" in done.order.state_reason
    assert len(journal.events()) == before


def test_it_sends_once_and_a_repeat_returns_the_first_outcome(tmp_path):
    """One send, never a retry. A repeat under the same key returns what the first
    said, as the venue's own `idempotencyKey` does (F0.10.1)."""
    written, envelope, order = instructed(tmp_path)
    conn, store, journal = real_book(tmp_path)
    executor, venue = None, Venue()
    executor = live(venue=venue)
    submitted = dataclasses.replace(order, state=OrderState.SUBMITTED)
    first = executor.submit(submitted, instruct.carried_quote(json.loads(written)).value)
    again = executor.submit(submitted, instruct.carried_quote(json.loads(written)).value)
    assert first is again and len(venue.sent) == 1
    assert venue.sent[0]["idempotencyKey"] == order.idempotency_key


def test_the_fill_and_its_gas_are_one_write_and_the_identity_holds(tmp_path):
    """A confirmed swap that was charged gas books the fill and the fee together, and
    the real book still reconciles: opened + realised + unrealised − costs = NAV."""
    written, envelope, order = instructed(tmp_path)
    conn, store, journal = real_book(tmp_path)
    paid = FakeRpc(receipt=charged(RECORDED["receipt"], 5_000_000_000_000))
    done = ran(order, live(rpc=paid), store, journal, written, envelope)
    assert done.order.state is OrderState.CONFIRMED
    assert [type(e).__name__ for e in journal.events()[-2:]] == ["Fill", "Fee"]

    book = ledger.value(journal.events(), book=ledger.REAL, snapshot=SNAPSHOT)
    assert (book.opened_usd + book.realised_usd + book.unrealised_usd
            - book.costs_usd) == book.nav_usd
    assert ledger.traded_usd(journal.events(), book=ledger.REAL) > 0
    assert ledger.holdings(journal.events(), book=ledger.PAPER) == {}  # paper is untouched


def test_the_ledger_refuses_evidence_that_is_not_this_orders_and_nothing_is_booked(tmp_path):
    """If the chain's amounts are not the order's legs, or are more than it authorized,
    the outcome is unknown — not a fill of whatever was found."""
    written, envelope, order = instructed(tmp_path)
    conn, store, journal = real_book(tmp_path)
    with pytest.raises(ledger.LedgerError, match="authorised"):
        ledger.live_fill(dataclasses.replace(order, state=OrderState.SUBMITTED),
                         Amount(SELL.raw * 2, 18, ETH), Amount(78_742, 6, USDG), SNAPSHOT)
    with pytest.raises(ledger.LedgerError, match="sells"):
        ledger.live_fill(dataclasses.replace(order, state=OrderState.SUBMITTED),
                         Amount(SOLD, 6, USDG), Amount(1, 18, ETH), SNAPSHOT)
    with pytest.raises(ledger.LedgerError, match="paper"):
        ledger.live_fill(dataclasses.replace(order, mode=ExecutionMode.PAPER,
                                             state=OrderState.SUBMITTED),
                         Amount(SOLD, 18, ETH), Amount(78_742, 6, USDG), SNAPSHOT)


# --- the body that spends (5.1) --------------------------------------------------------------------

WORKED = json.loads((Path(__file__).parent / "data" / "swap_request_0_10.json").read_text())


def test_the_swap_body_is_the_one_that_filled_on_chain():
    """Probe 0.10's submission is the only swap body this fund has ever had accepted.
    The adapter sends that shape: the same eight fields, the floor as human text, and
    no slippage figure — the floor is the order's own, from the quote it was
    authorized on."""
    request = execute.bankr_exec.SwapRequest(
        sell=SELL, buy=USDG, idempotency_key=WORKED["body"]["idempotencyKey"],
        min_buy=Amount.from_units(WORKED["body"]["minBuyAmount"], USDG_DECIMALS, USDG),
        quote_id=WORKED["body"]["quoteId"])
    assert request.body(execute.bankr_exec.Settings.load()) == WORKED["body"]


def test_a_swap_with_no_floor_is_refused_before_the_wire():
    with pytest.raises(ValueError, match="floor"):
        execute.bankr_exec.submit(
            execute.bankr_exec.SwapRequest(sell=SELL, buy=USDG, idempotency_key="k",
                                           min_buy=Amount(0, USDG_DECIMALS, USDG)),
            "SECRET", settings=execute.bankr_exec.Settings.load(),
            transport=lambda *a: (_ for _ in ()).throw(AssertionError("nothing is sent")))
