"""A whole paper cycle, in one command (unit 4.8).

    PYTHONPATH=src python3 -m fund.run.cycle --snapshot CAPTURE (--cycle DIR | --approved-reports)
        --db PATH --out DIR --at 2026-09-19T20:24:32Z [--config-dir DIR] [--env-file PATH]

    make cycle-demo     the same, twice, on the exit run's capture and reports

From a capture to a book:
0. **the lock and the last run** (4.9, 4.10): one runner holds the lock, and every
   order the last run left is resolved before this one is accepted;
1. **the ledger** opens the paper book once, with `capital_usd` of USDG at the
   snapshot's own mark for it (the operator's decision: paper cash is USDG);
2. **the reports** are read and checked again against this snapshot (2.2);
3. **the decision** is `run/decide.py`'s, whole: weights (3.1), a sized plan on fresh
   quotes (3.3), the gates (3.4), the context budget (3.6), the risk vote (3.5), and
   a signed record (3.7). A holding the snapshot cannot mark stops valuation, and the
   cycle still signs a record that says so (S12);
4. **the intents** are the record's approved orders, refused unless the record
   verifies against the published key and the mandate is in force (4.2). Each is
   written `prepared` before anything is attempted (4.3);
5. **the treasurer**, in its own process with its own credentials (4.12), reads
   those orders from the database and takes each through the chokepoint, the fill
   and the books in one act (4.4, 4.5, 4.6). This process starts it from an empty
   environment and holds no key itself;
6. **the book** is read back from the journal and reconciled exactly (4.7).

**Nothing here touches the chain.** Stock legs are paper (PLAN §13). The venue is the
fake venue, labelled in every answer, and the risk vote is scripted: this command
makes no model call and spends nothing. The pieces that do are behind the same
interfaces and are built: real quotes and a real risk call in `run/decide.py`, and the
live leg in `run/liveleg.py` (5.1, 5.2), which is the only command that spends on
chain. What joins them into one scheduled cycle is 5.7's and 8.3's.

**The clock is an input,** `--at`: a paper cycle on a committed capture runs at that
capture's time, so it decides on evidence that was fresh (S11) and rebuilds the same
way tomorrow. A live cycle passes the time of day.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from fund import config
from fund.adapters import bankr_quote
from fund.agents import risk
from fund.core import cash, gates, ledger, plan
from fund.core.types import Amount, Instant, OrderState
from fund.adapters import fake_venue
from fund.run import decide, startup
from fund.store import db, positions
from fund.store.journal import Journal
from fund.store.orders import OrderStore
from fund.store import reports as report_store
from fund.treasurer import execute, intent, keys
from fund.treasurer import mandate as mandates

ROOT = config.REPO_ROOT
EXIT_RUN = ROOT / "fixtures" / "cycles" / "20260919T202259Z"
EXIT_CAPTURE = ROOT / "fixtures" / "snapshots" / "67364057-c06abd9e89f0"
DEMO = ROOT / "fixtures" / "live" / "cycle-demo"  # gitignored


@dataclass(frozen=True)
class Ran:
    """One order, as the treasurer's process reported it."""

    order_id: str
    state: OrderState
    reason: str | None
    booked: bool


@dataclass(frozen=True)
class Cycle:
    """What one cycle did."""

    decision: Mapping[str, Any]
    orders: list[Ran]
    book: Any | None
    statement: str
    resolved: list[startup.Resolved] = ()
    treasurer: Mapping[str, Any] | None = None

    @property
    def filled(self) -> list[Ran]:
        return [r for r in self.orders if r.booked]

    @property
    def refused(self) -> list[Ran]:
        return [r for r in self.orders if r.state is OrderState.REFUSED]


def scripted(vote: str = "approve") -> Callable[[Mapping[str, Any], str], str]:
    """A risk reply this cycle writes itself, in the brief's shape. It is scripted, and
    says so: no model is asked, and none is billed."""
    def reply(written: Mapping[str, Any], plan_sha256: str) -> str:
        lines = [f"RISK {plan_sha256}"]
        for order in written["orders"]:
            lines += [f"ORDER {order['index']} {order['asset']['symbol']} {vote}",
                      "Scripted by the paper cycle, not a model's words."]
        return "\n".join(lines + [f"OVERALL {vote}", "Scripted by the paper cycle."]) + "\n"
    return reply


def open_paper_book(journal: Journal, snapshot: Mapping[str, Any], units: Decimal) -> None:
    """Open the paper book once, with `units` of USDG at the snapshot's mark for it.
    Paper cash is USDG, not a dollar figure (the operator, 2026-09-19)."""
    if ledger.holdings(journal.events(), book=ledger.PAPER):
        return
    asset, decimals = cash.cash_leg(snapshot)
    journal.append(ledger.Opening(ledger.PAPER, Amount.from_units(format(units, "f"), decimals,
                                                                  asset),
                                  cash.mark_of(snapshot, asset.address)))


def treasurer(*, db_path: Path, decision_dir: Path | None, snapshot_path: Path, at: Instant,
              config_dir: Path, env_file: Path | None, venue_fetched_at: Instant | None,
              instruction_dir: Path | None = None,
              python: str = sys.executable) -> Mapping[str, Any]:
    """Start the treasurer in its own process, from an empty environment, and read back
    what it did. This process hands it no credential: it loads its own (4.12).

    Its authority is one or the other: a decision's directory, or — on the live leg —
    a signed instruction's (5.2)."""
    authority = (["--decision", str(decision_dir)] if instruction_dir is None
                 else ["--instruction", str(instruction_dir)])
    command = [python, "-m", "fund.treasurer.execute", "--db", str(db_path), *authority,
               "--snapshot", str(snapshot_path),
               "--at", str(at.epoch_ms), "--config-dir", str(config_dir)]
    if env_file is not None:
        command += ["--env-file", str(env_file)]
    if venue_fetched_at is not None:
        command += ["--venue-fetched-at", str(venue_fetched_at.epoch_ms)]
    empty = {"PATH": os.environ.get("PATH", os.defpath), "PYTHONPATH": str(ROOT / "src")}
    done = subprocess.run(command, env=empty, capture_output=True, text=True, timeout=600)
    if done.returncode != 0:
        raise RuntimeError(f"the treasurer refused to run: {done.stderr[-2000:]}")
    return json.loads(done.stdout)


def cycle(*, snapshot_path: Path, offered: Sequence[decide.Offered], conn: Any, out_dir: Path,
          at: Instant, config_dir: Path, env_file: Path | None,
          venue: execute.Venue | None = None, venue_fetched_at: Instant | None = None,
          vote: str = "approve", checkpoint: Callable[..., None] | None = None) -> Cycle:
    """One paper cycle: reports to a signed decision to fills to a book.

    The caller holds the lock (`startup.owning`) around this."""
    snapshot = json.loads(snapshot_path.read_bytes())
    resolved = startup.resolve(conn)  # what the last run left, before this one decides
    store, journal = OrderStore(conn), Journal(conn)
    thresholds = config.load_json("thresholds.json", config_dir)
    open_paper_book(journal, snapshot, Decimal(str(thresholds["capital_usd"])))
    venue = venue or fake_venue.FakeVenue(snapshot, lambda: Instant(at.epoch_ms - 5_000))

    try:  # the book the planner plans from, out of the ledger (4.0 P10)
        the_book = ledger.planner_book(journal.events(), snapshot)
    except (cash.NoMark, plan.PlanError) as unvalued:  # S12
        done = decide.no_rebalance(snapshot_path=snapshot_path, offered=offered, out_dir=out_dir,
                                   why=str(unvalued), at=at, env_file=env_file,
                                   config_dir=config_dir)
        return Cycle(done, [], None, f"no rebalance: {unvalued}", resolved)

    def quotes(intents):
        return ({i.index: venue.quote(bankr_quote.QuoteRequest(i.sell, i.buy, i.buy_decimals))
                 for i in intents}, at)

    done = decide.decide(
        snapshot_path=snapshot_path, offered=offered, holdings=the_book.holdings,
        cash_usd=the_book.cash_usd, out_dir=out_dir, quotes=quotes,
        quote_label=f"{fake_venue.DETAIL}, judged at {at.epoch_ms}",
        risk_settings=risk.Settings.from_config(config_dir), risk_credential=None,
        risk_agent="scripted: no model was asked", environ={}, recorded_reply=scripted(vote),
        store=report_store.ReportStore(out_dir / "store"), env_file=env_file,
        config_dir=config_dir)

    decision = execute.Decision((out_dir / "record.json").read_bytes(), done["envelope"],
                               snapshot_path.read_bytes())
    the_mandate = mandates.load(config_dir)
    limits = gates.Limits.from_config(thresholds, the_mandate,
                                      config.load_json("models.json", config_dir))
    public_key = keys.published_key(config_dir)
    try:
        orders = intent.intents(decision.record_bytes, decision.envelope, public_key=public_key,
                                mandate=the_mandate, at=at)
    except intent.IntentError as refused:  # nothing authorizes: no order is written
        book = positions.read(journal, book=ledger.PAPER, snapshot=snapshot)
        return Cycle(done, [], book, f"no orders: {refused}\n\n"
                     + positions.statement(book, snapshot), resolved)
    for order in orders:  # written before anything is attempted
        store.add(order)
    if checkpoint is not None:
        checkpoint("prepared", orders)

    reported = treasurer(db_path=Path(conn.execute("PRAGMA database_list").fetchone()[2]),
                         decision_dir=out_dir, snapshot_path=snapshot_path, at=at,
                         config_dir=config_dir, env_file=env_file,
                         venue_fetched_at=venue_fetched_at)
    ran = [Ran(o["order_id"], OrderState(o["state"]), o["reason"], o["booked"])
           for o in reported["orders"]]
    book = positions.read(journal, book=ledger.PAPER, snapshot=snapshot)
    statement = positions.statement(book, snapshot)
    (out_dir / "book.txt").write_text(statement + "\n")
    decide._write(out_dir / "orders.json", reported["orders"])
    return Cycle(done, ran, book, statement, resolved, reported)


def summary(ran: Cycle) -> str:
    lines = [f"startup    resolved {r.order_id.rpartition('/')[2]}: {r.state.value}, {r.why}"[:150]
             for r in ran.resolved]
    lines += [decide.summary(ran.decision), "",
             "--- the treasurer: the decision above executed nothing; these orders did ---", ""]
    for order in ran.orders:
        lines.append(f"order {order.order_id.rpartition('/')[2]:>2}  "
                     f"{order.state.value:<9} {order.reason or ''}"[:160])
    if not ran.orders:
        lines.append("no order was written")
    if ran.treasurer is not None:
        lines.append(f"treasurer  its own process, given {ran.treasurer['environment_given']}, "
                     f"holding {ran.treasurer['credentials_held'] or 'no credential'}")
    return "\n".join([*lines, "", ran.statement])


# --- the demo ------------------------------------------------------------------------------------

def demo(out_dir: Path = DEMO, runs: int = 2) -> list[Cycle]:
    """The exit run's capture and its four real reports, taken through two paper cycles.

    It publishes a scratch key of its own and signs with that: the fund's key never
    signs fake inputs. Its clock is the capture's, a few minutes after the block, so
    the decision is judged on evidence that was fresh (S11)."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding, NoEncryption, PrivateFormat, PublicFormat,
    )

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = out_dir / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    env_file = out_dir / "treasurer.env"
    env_file.write_text("SIGNING_KEY=" + key.private_bytes(
        Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex() + "\n")
    env_file.chmod(0o600)
    config_dir = out_dir / "config"
    shutil.copytree(config.CONFIG_DIR, config_dir)
    (config_dir / "keys.json").write_text(json.dumps({
        "_about": "The paper cycle's own scratch key, made for this demo. The fund's key "
                  "signs no fake input.",
        "decision_signing": {"algorithm": keys.ALGORITHM,
                             "public_key": key.public_key().public_bytes(
                                 Encoding.Raw, PublicFormat.Raw).hex()}},
        indent=1) + "\n")

    snapshot_path = EXIT_CAPTURE / "snapshot.json"
    block = datetime.fromisoformat(json.loads(snapshot_path.read_bytes())["block"]["time"]
                                   .replace("Z", "+00:00"))
    conn = db.connect(out_dir / "fund.sqlite")
    ran = []
    with startup.owning(conn):  # one runner spends, or none (4.10)
        for number in range(runs):
            at = Instant(int((block + timedelta(minutes=4 * (number + 1))).timestamp() * 1000))
            ran.append(cycle(snapshot_path=snapshot_path,
                             offered=decide.cycle_reports(EXIT_RUN / "cycle"), conn=conn,
                             out_dir=out_dir / f"cycle-{number + 1}", at=at,
                             config_dir=config_dir, env_file=env_file))
    return ran


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fund.run.cycle")
    parser.add_argument("--demo", action="store_true", help="two cycles on the exit run's capture")
    parser.add_argument("--snapshot", type=Path, help="a capture directory or a snapshot.json")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--approved-reports", action="store_true")
    source.add_argument("--cycle", type=Path, help="a runner cycle's directory")
    parser.add_argument("--db", type=Path, help="the fund's SQLite file")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--at", help="the cycle's clock, as 2026-09-19T20:24:32Z")
    parser.add_argument("--config-dir", type=Path, default=config.CONFIG_DIR)
    parser.add_argument("--env-file", type=Path, default=None, help="for the signer only")
    args = parser.parse_args(argv)
    if args.demo:
        for number, ran in enumerate(demo(), start=1):
            print(f"\n=== paper cycle {number} " + "=" * 60 + "\n")
            print(summary(ran))
        return 0
    if not (args.snapshot and args.db and args.out and args.at):
        parser.error("--snapshot, --db, --out and --at are required without --demo")
    snapshot_path = args.snapshot / "snapshot.json" if args.snapshot.is_dir() else args.snapshot
    offered = (decide.approved_reports() if args.approved_reports
               else decide.cycle_reports(args.cycle))
    at = Instant(int(datetime.fromisoformat(args.at.replace("Z", "+00:00")).timestamp() * 1000))
    conn = db.connect(args.db)
    with startup.owning(conn):
        ran = cycle(snapshot_path=snapshot_path, offered=offered, conn=conn, out_dir=args.out,
                    at=at, config_dir=args.config_dir, env_file=args.env_file)
    print(summary(ran))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
