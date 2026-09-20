"""The live leg, one command (units 5.1, 5.2).

    PYTHONPATH=src python3 -m fund.run.liveleg --snapshot PATH --sell ETH --amount 0.00005
        --db PATH --out DIR [--config-dir DIR] [--env-file PATH] [--window-seconds 300]
        [--confirm]

**Without `--confirm` it prints what would happen and stops.** With it, it spends: one
swap of `--amount` of `--sell` into the other of the two assets the mandate allows on
4663, ETH and USDG. Nothing else. It is *a demonstration of the money path that no
analyst chose* (`planning/SIMPLIFICATION.md`, DECISION 2026-09-19), which is why it is
authorized by a signed instruction (`treasurer/instruct.py`) and not by a decision
record that never happened.

What it does, in order:
1. **takes the lock and resolves what the last run left** (4.9, 4.10). A live order
   still in flight refuses the leg: it is read and resolved before anything new is
   sent, and never re-sent under a new key;
2. **opens the real book** once, with what the wallet holds at the snapshot's marks;
3. **quotes the swap live**, under the analyst role's read key, and judges that quote
   by the same age, size and impact rule the chokepoint uses (`execute.judge`);
4. **writes and signs the instruction**, and derives the order from it: the order's id
   and idempotency key are the instruction's own sha256 and index, so they cannot be
   minted again (4.0 P2);
5. **prints the asset, the size, the wallet and the chain**, and stops there unless
   `--confirm` was given;
6. **starts the treasurer in its own process** (4.12), from an empty environment, with
   the instruction. That process loads `BANKR_KEY_EXEC` itself, admits the order at
   the chokepoint, sends it once, reconciles it from the chain (5.3) and books it;
7. **prints what the chain said**: the transaction, the order's state, and the real
   book.

**This process holds no key but the analyst's read key.** Signing is the treasurer's
signing process (`run/decide.py:signed`, as the cycle signs a record), and spending is
the treasurer's own process: the only module that can spend is
`adapters/bankr_exec.py`, only `treasurer/` may import it, and both subprocesses start
from an empty environment and load their own credentials (4.12).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

from fund import config
from fund.adapters import bankr_quote
from fund.core import cash, ledger, plan
from fund.core.types import Amount, AssetId, ChainAddress, Instant, to_canonical
from fund.credentials import Role
from fund.run import cycle, decide, startup
from fund.store import db, positions
from fund.store.journal import Journal
from fund.store.orders import OrderStore
from fund.treasurer import execute, instruct, keys, reconcile
from fund.treasurer import mandate as mandates

#: The two assets the live leg may trade, by the mandate. A stock leg is paper, and
#: this command refuses one rather than asking the venue about it (PLAN §13).
LIVE_SYMBOLS = ("ETH", "USDG")


def now() -> Instant:
    return Instant(time.time_ns() // 1_000_000)


def holding_of(snapshot: Mapping[str, Any], symbol: str) -> Mapping[str, Any]:
    """The snapshot's holding for one of the two live symbols."""
    for held in snapshot["holdings"]:
        if held["asset"]["symbol"] == symbol:
            return held
    raise SystemExit(f"the snapshot holds no {symbol}")


def open_real_book(journal: Journal, snapshot: Mapping[str, Any]) -> list[ledger.Opening]:
    """Open the real book once, with what the wallet actually holds at the snapshot's
    marks. The paper book's opening is a decided figure of USDG (`run/cycle.py`); the
    real book's is not decided at all — it is the balance the chain reports, and its
    basis is the mark it was first booked at (4.0 P6)."""
    if ledger.holdings(journal.events(), book=ledger.REAL):
        return []
    opened = []
    for held in snapshot["holdings"]:
        asset = AssetId(snapshot["block"]["chain_id"], held["asset"]["address"])
        amount = Amount.from_units(held["balance"], held["asset"]["decimals"], asset)
        if amount.raw <= 0:
            continue
        opening = ledger.Opening(ledger.REAL, amount, cash.mark_of(snapshot, asset.address))
        journal.append(opening)
        opened.append(opening)
    return opened


def reader(snapshot: Mapping[str, Any], mandate: Mapping[str, Any], config_dir: Path | None):
    """How an order found in flight is settled: by reading its own transaction (5.3).

    4.9 left this here deliberately. The receipt says whether the swap filled, what it
    moved and what gas it paid, and `treasurer/execute.booked` turns that into the same
    outcome the executor would have returned, so an order settles identically whether
    the run that sent it saw the answer or a later one did. An order with no
    transaction to read is not settled here: there is nothing to read, and a human
    looks. Reading needs no spend authority — only the chain — so this process does it.
    """
    from fund.adapters import chain_4663

    chain = chain_4663.Settings.load()
    cadence = config.load_json("cadence.json", config_dir)
    held = config.load(Role.ANALYST, require=False)
    rpc = chain.client(held.secret)
    wallet = ChainAddress(chain.chain_id, mandate["execution_wallet"])

    def read(order):
        if order.execution is None:
            return None  # nothing was ever read for it: no hash, nothing to settle
        seen = reconcile.read(rpc, order.execution.transaction.tx_hash, wallet=wallet,
                              chain_id=chain.chain_id,
                              confirmations=cadence["confirmation_depth"],
                              sell=order.sell.asset, sell_decimals=order.sell.decimals,
                              buy=order.buy_asset, buy_decimals=order.min_buy.decimals)
        return execute.booked(order, order.execution.transaction.tx_hash, seen, snapshot)
    return read


def about(order, instruction: Mapping[str, Any], seen: plan.QuoteSeen, mandate: Mapping[str, Any],
          spent: Decimal, buying: str) -> str:
    """What is about to happen, before anything is sent."""
    quote = seen.observation.value
    sold = Decimal(order.sell.raw).scaleb(-order.sell.decimals).normalize()
    lines = [
        "--- about to submit one live swap -------------------------------------------",
        f"  asset    {instruction['order']['asset']['symbol']} -> {buying}",
        f"  size     {sold} (${Decimal(instruction['order']['usd']):.6f} at the "
        "snapshot's mark)",
        f"  wallet   {order.wallet.address}",
        f"  chain    {order.sell.asset.chain_id}",
        f"  quote    {quote.quote_id}: buys {Decimal(quote.buy.raw).scaleb(-quote.buy.decimals)}, "
        f"at least {Decimal(order.min_buy.raw).scaleb(-order.min_buy.decimals)}; "
        f"verdict {seen.verdict.value} ({seen.rule}): {seen.verdict.reason}",
        f"           quoted {seen.age_ms} ms before this judgement",
        f"  budget   ${spent} of ${mandate['cumulative_budget_usd']} live already traded",
        f"  order    {order.order_id}",
        f"  key      {order.idempotency_key}",
        "  once     one send, no retry; the outcome is read from the chain, never the reply",
        "-----------------------------------------------------------------------------",
    ]
    return "\n".join(lines)


def record(out_dir: Path, order, reported: Mapping[str, Any], statement: str) -> Path:
    """What happened, written beside what was authorized. The books live in SQLite,
    which is not source and is not committed, so this is the repository's own evidence
    of the live leg: the order as the store holds it, the chain evidence the
    reconciler read, and the book the fill left behind."""
    path = out_dir / "outcome.json"
    execution = None if order.execution is None else json.loads(to_canonical(order.execution))
    path.write_text(json.dumps({
        "order_id": order.order_id, "idempotency_key": order.idempotency_key,
        "state": order.state.value, "reason": order.state_reason, "mode": order.mode.value,
        "sells": json.loads(to_canonical(order.sell)),
        "buys": order.buy_asset.address, "min_buy": json.loads(to_canonical(order.min_buy)),
        "execution": execution, "treasurer": reported, "real_book": statement.splitlines(),
    }, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    return path


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fund.run.liveleg")
    parser.add_argument("--snapshot", required=True, type=Path,
                        help="a snapshot built minutes ago: S11 gives it 15 minutes")
    parser.add_argument("--sell", required=True, choices=LIVE_SYMBOLS)
    parser.add_argument("--amount", required=True, help="in whole units, e.g. 0.00005")
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path, help="where the instruction is written")
    parser.add_argument("--config-dir", type=Path, default=None)
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--window-seconds", type=int, default=300,
                        help="how long the instruction authorizes the order for")
    parser.add_argument("--confirm", action="store_true",
                        help="without it, this prints what would happen and stops")
    args = parser.parse_args(argv)

    snapshot_bytes = args.snapshot.read_bytes()
    snapshot = json.loads(snapshot_bytes)
    chain = snapshot["block"]["chain_id"]
    mandate = mandates.load(args.config_dir)
    thresholds = config.load_json("thresholds.json", args.config_dir)
    sell_held = holding_of(snapshot, args.sell)
    buy_held = holding_of(snapshot, "USDG" if args.sell == "ETH" else "ETH")
    sell = Amount.from_units(args.amount, sell_held["asset"]["decimals"],
                             AssetId(chain, sell_held["asset"]["address"]))
    buy = AssetId(chain, buy_held["asset"]["address"])

    conn = db.connect(args.db)
    with startup.owning(conn):  # one runner spends (4.10)
        settle = reader(snapshot, mandate, args.config_dir)
        for was in startup.resolve(conn, settle):  # what the last run left, read first (4.9)
            print(f"startup  {was.order_id}: {was.state.value}, {was.why}"[:160])
        journal, store = Journal(conn), OrderStore(conn)
        for opening in open_real_book(journal, snapshot):
            print(f"opened   the real book with {opening.amount.raw} raw of "
                  f"{opening.amount.asset.address}")

        analyst = config.load(Role.ANALYST, require=False)  # the read key, no more
        quotes = bankr_quote.Settings.load()
        observation = quotes.adapter(analyst.secret).quote(
            bankr_quote.QuoteRequest(sell=sell, buy=buy,
                                     buy_decimals=buy_held["asset"]["decimals"]))
        at = now()  # judged after the evidence was fetched, never before it (S11, quote age)
        seen = execute.judge(observation, sell, at, thresholds)

        doc = instruct.document(sell=sell, symbol=sell_held["asset"]["symbol"], buy=buy,
                                buy_decimals=buy_held["asset"]["decimals"], quote=seen,
                                snapshot=snapshot,
                                snapshot_sha256=hashlib.sha256(snapshot_bytes).hexdigest(),
                                mandate=mandate, issued_at=at,
                                expires_at=Instant(at.epoch_ms + args.window_seconds * 1000))
        path, envelope_path = instruct.write(args.out, doc)
        envelope = decide.signed(path, envelope_path, args.env_file)  # in its own process
        written = path.read_bytes()
        order = instruct.order_of(written, envelope, public_key=keys.published_key(args.config_dir),
                                  mandate=mandate, at=at)
        spent = ledger.traded_usd(journal.events(), book=ledger.REAL)
        print(about(order, doc, seen, mandate, spent, buy_held["asset"]["symbol"]))
        if not args.confirm:
            print("not confirmed: nothing was sent. Re-run with --confirm to spend.")
            return 0

        store.add(order)  # written prepared, before anything is attempted (4.3)
        reported = cycle.treasurer(db_path=args.db, decision_dir=None, snapshot_path=args.snapshot,
                                   at=at, config_dir=args.config_dir or config.CONFIG_DIR,
                                   env_file=args.env_file, venue_fetched_at=None,
                                   instruction_dir=args.out)
        for ran in reported["orders"]:
            print(f"order    {ran['state']}: {ran['reason']}")
            if ran.get("tx_hash"):
                print(f"chain    {ran['tx_hash']}")
        print(f"treasurer  its own process, given {reported['environment_given']}, holding "
              f"{reported['credentials_held'] or 'no credential'}")
        book = positions.read(journal, book=ledger.REAL, snapshot=snapshot)
        statement = positions.statement(book, snapshot)
        print("\n" + statement)
        print(f"written  {record(args.out, store.get(order.order_id), reported, statement)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
