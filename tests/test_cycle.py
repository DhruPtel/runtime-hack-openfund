"""Unit 4.8: a whole paper cycle, end to end, as one command. L.

The capture is the exit run's, and the reports are its four real ones. The venue is
the fake venue and the risk vote is scripted, so nothing is asked of a model and
nothing touches the chain. The cycle signs with a scratch key it publishes itself:
the fund's key signs no fake input.
"""

from __future__ import annotations

import json
import shutil
import signal
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, NoEncryption, PrivateFormat, PublicFormat,
)

from fund import config
from fund.core import cash, ledger
from fund.core.types import Instant, OrderState
from fund.run import cycle as run_cycle
from fund.adapters import fake_venue
from fund.run import decide
from fund.store import db, positions
from fund.store.journal import Journal
from fund.store.orders import OrderStore

REPO = Path(__file__).resolve().parents[1]
CAPTURE = REPO / "fixtures" / "snapshots" / "67364057-c06abd9e89f0" / "snapshot.json"
REPORTS = REPO / "fixtures" / "cycles" / "20260919T202259Z" / "cycle"
SNAPSHOT = json.loads(CAPTURE.read_bytes())
BLOCK = datetime.fromisoformat(SNAPSHOT["block"]["time"].replace("Z", "+00:00"))


def clock(minutes: int) -> Instant:
    return Instant(int((BLOCK + timedelta(minutes=minutes)).timestamp() * 1000))


def paper(tmp_path, **mandate_changes):
    """A config of the fund's, with this cycle's own scratch key published in it."""
    config_dir = tmp_path / "config"
    shutil.copytree(config.CONFIG_DIR, config_dir, dirs_exist_ok=True)
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
    (config_dir / "keys.json").write_text(json.dumps(
        {"decision_signing": {"algorithm": "ed25519", "public_key": public}}))
    if mandate_changes:
        mandate = json.loads((config_dir / "mandate.json").read_text())
        (config_dir / "mandate.json").write_text(json.dumps({**mandate, **mandate_changes}))
    env_file = tmp_path / "treasurer.env"
    env_file.write_text("SIGNING_KEY=" + key.private_bytes(
        Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex() + "\n")
    return config_dir, env_file


def run(tmp_path, *, minutes=4, conn=None, snapshot=CAPTURE, config_dir=None, env_file=None,
        out="out", **rest):
    if config_dir is None:
        config_dir, env_file = paper(tmp_path)
    return run_cycle.cycle(snapshot_path=snapshot, offered=decide.cycle_reports(REPORTS),
                           conn=conn or db.connect(tmp_path / "fund.sqlite"),
                           out_dir=tmp_path / out, at=clock(minutes), config_dir=config_dir,
                           env_file=env_file, **rest)


def test_a_whole_paper_cycle_runs_from_the_capture_to_a_book(tmp_path):
    ran = run(tmp_path)
    assert ran.decision["record"]["schema"] == "openfund.decision/3"
    assert ran.decision["authorizes"]["authorizes"] is True
    assert len(ran.orders) == 8 and len(ran.filled) == 8 and ran.refused == []
    assert all(r.state is OrderState.CONFIRMED for r in ran.orders)
    # the treasurer ran alone: this process handed it nothing, and it held its own key
    assert set(ran.treasurer["environment_given"]) <= {"PATH", "PYTHONPATH", "LC_CTYPE"}
    assert ran.treasurer["credentials_held"] == ["SIGNING_KEY"]

    events = Journal(db.connect(tmp_path / "fund.sqlite")).events()
    assert [type(e).__name__ for e in events] == ["Opening"] + ["Fill"] * 8
    book = ran.book
    assert len(book.positions) == 6 and book.cash.amount.asset == cash.cash_leg(SNAPSHOT)[0]
    with localcontext(cash.EXACT):
        assert book.nav_usd == (book.opened_usd + book.realised_usd + book.unrealised_usd
                                - book.costs_usd)
    assert (tmp_path / "out" / "book.txt").read_text().startswith("the paper book at block")


def test_the_book_as_json_says_exactly_what_the_book_as_text_says(tmp_path):
    """`book.json` is the same book for a reader without a terminal (6.1, 7.6). It is
    built from the same `BookValue` and computes nothing of its own, so every figure
    in it must appear in `book.txt` once rounded the way that file rounds."""
    run(tmp_path)
    text = (tmp_path / "out" / "book.txt").read_text()
    doc = json.loads((tmp_path / "out" / "book.json").read_text())

    def cents(figure: str) -> str:
        return f"${Decimal(figure).quantize(Decimal('0.01'), rounding=ROUND_HALF_EVEN):,.2f}"

    assert f"the {doc['book']} book at block {doc['block']['number']} " \
           f"({doc['block']['time']})" in text
    assert doc["book"] == "paper" and len(doc["positions"]) == 6
    for label, row in [*((p["symbol"], p) for p in doc["positions"]), ("cash", doc["cash"])]:
        line = next(l for l in text.splitlines() if l.strip().startswith(label))
        assert row["units"] in line
        for figure in ("value_usd", "basis_usd", "unrealised_usd"):
            assert cents(row[figure]) in line, (label, figure, line)
    assert f"  NAV" in text and cents(doc["nav_usd"]) in text
    i = doc["identity"]
    assert (f"opened {cents(i['opened_usd'])} + realised {cents(i['realised_usd'])} "
            f"+ unrealised {cents(i['unrealised_usd'])} − costs {cents(i['costs_usd'])} "
            f"= NAV {cents(i['nav_usd'])}, exactly") in text
    assert f"inference {cents(doc['expenses_usd'])}, an expense beside the NAV" in text
    with localcontext(cash.EXACT):  # and the identity holds on the exact figures
        assert Decimal(i["nav_usd"]) == (Decimal(i["opened_usd"]) + Decimal(i["realised_usd"])
                                         + Decimal(i["unrealised_usd"]) - Decimal(i["costs_usd"]))


def test_the_paper_book_opens_once_with_usdg_at_its_own_mark(tmp_path):
    conn = db.connect(tmp_path / "fund.sqlite")
    run(tmp_path, conn=conn)
    run(tmp_path, conn=conn, minutes=8, out="out2")
    openings = [e for e in Journal(conn).events() if isinstance(e, ledger.Opening)]
    assert len(openings) == 1
    assert openings[0].amount.asset == cash.cash_leg(SNAPSHOT)[0]
    units, usd = ledger.cash_held([openings[0]], book="paper", snapshot=SNAPSHOT)
    assert Decimal(units.raw).scaleb(-6) == 200 and usd == Decimal("199.984558")  # not $200


def test_the_second_cycle_plans_from_the_book_the_first_left(tmp_path):
    config_dir, env_file = paper(tmp_path)
    conn = db.connect(tmp_path / "fund.sqlite")
    first = run(tmp_path, conn=conn, config_dir=config_dir, env_file=env_file)
    after = ledger.value(Journal(conn).events(), book="paper", snapshot=SNAPSHOT)
    second = run(tmp_path, conn=conn, minutes=8, out="out2", config_dir=config_dir,
                 env_file=env_file)
    book = second.decision["plan"]["book"]
    assert Decimal(book["cash_usd"]) == after.cash.value_usd
    assert {a: Decimal(p["amount"]) for a, p in book["positions"].items()} == {
        asset.address: Decimal(position.amount.raw).scaleb(-position.amount.decimals)
        for asset, position in after.positions.items()}
    assert second.filled and first.filled  # and it traded from there


def test_an_expired_mandate_refuses_the_cycle_and_writes_no_order(tmp_path):
    config_dir, env_file = paper(tmp_path, approved_at="2026-09-01T00:00:00Z",
                                 expires_at="2026-09-08T00:00:00Z")
    ran = run(tmp_path, config_dir=config_dir, env_file=env_file)
    assert ran.orders == [] and "expired at 2026-09-08T00:00:00Z" in ran.statement
    assert ran.decision["record"]["decision"]["approved"] == []
    assert all("mandate-term" in o["blocked_by"]
               for o in ran.decision["record"]["gates"]["orders"])
    assert OrderStore(db.connect(tmp_path / "fund.sqlite")).all() == []
    assert [type(e).__name__ for e in Journal(db.connect(tmp_path / "fund.sqlite")).events()] == [
        "Opening"]


def test_s12_a_holding_the_snapshot_cannot_mark_still_signs_a_record(tmp_path):
    config_dir, env_file = paper(tmp_path)
    conn = db.connect(tmp_path / "fund.sqlite")
    run(tmp_path, conn=conn, config_dir=config_dir, env_file=env_file)

    doctored = json.loads(CAPTURE.read_bytes())
    for asset in doctored["assets"]:
        if asset["asset"]["symbol"] == "GME":
            asset["mark"]["verdict"] = {"value": False, "reason": "constructed: the feed paused"}
    path = tmp_path / "unmarkable.json"
    path.write_text(json.dumps(doctored))
    ran = run(tmp_path, conn=conn, minutes=8, out="out2", snapshot=path, config_dir=config_dir,
              env_file=env_file)
    record = ran.decision["record"]
    assert ran.orders == [] and record["decision"]["rebalance"] is False
    assert ran.decision["envelope"]["signed"] is True
    assert "GME" in record["plan"]["book"]["unvalued"]
    assert record["decision"]["approved"] == [] and record["plan"]["orders"] == []


def test_an_order_the_chokepoint_refuses_is_written_refused_and_books_nothing(tmp_path):
    """Quotes two minutes old when the treasurer judges them: every order is refused at
    quote-age, written refused with that reason, and nothing is booked."""
    config_dir, env_file = paper(tmp_path)
    # the plan is quoted fresh; the treasurer's re-quotes come back two minutes old
    ran = run(tmp_path, config_dir=config_dir, env_file=env_file,
              venue_fetched_at=Instant(clock(4).epoch_ms - 120_000))
    assert len(ran.orders) == 8 and ran.filled == [] and len(ran.refused) == 8
    assert all(r.state is OrderState.REFUSED for r in ran.orders)
    assert all("quote-age" in r.reason for r in ran.orders)
    assert [type(e).__name__ for e in Journal(db.connect(tmp_path / "fund.sqlite")).events()] == [
        "Opening"]


def test_the_orders_a_killed_run_left_are_settled_at_the_next_startup(tmp_path):
    """The run is killed once its orders are written and before any is attempted. The
    next cycle's startup settles them — nothing was sent, so they are stale — and then
    decides again. An order left `submitted` is settled by the same call, from the
    journal: tests/test_startup.py."""
    config_dir, env_file = paper(tmp_path)
    script = textwrap.dedent(f"""
        import os, signal, sys
        sys.path[:0] = [{str(REPO / 'src')!r}]
        from pathlib import Path
        from fund.core.types import Instant
        from fund.run import cycle, decide
        from fund.store import db

        cycle.cycle(snapshot_path=Path({str(CAPTURE)!r}),
                    offered=decide.cycle_reports(Path({str(REPORTS)!r})),
                    conn=db.connect({str(tmp_path / 'fund.sqlite')!r}),
                    out_dir=Path({str(tmp_path / 'killed')!r}), at=Instant({clock(4).epoch_ms}),
                    config_dir=Path({str(config_dir)!r}), env_file=Path({str(env_file)!r}),
                    checkpoint=lambda step, what: os.kill(os.getpid(), signal.SIGKILL))
    """)
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert done.returncode == -signal.SIGKILL, done.stderr[-2000:]
    conn = db.connect(tmp_path / "fund.sqlite")
    left = {o.state for o in OrderStore(conn).all()}
    assert left == {OrderState.PREPARED} and [
        type(e).__name__ for e in Journal(conn).events()] == ["Opening"]

    ran = run(tmp_path, minutes=8, conn=conn, config_dir=config_dir, env_file=env_file,
              out="after")
    assert {r.state for r in ran.resolved} == {OrderState.REFUSED}
    assert all("never sent" in r.why for r in ran.resolved)
    assert ran.filled and ran.book.nav_usd > 0  # and the cycle went on to trade


def test_nothing_is_attempted_before_every_order_is_written_prepared(tmp_path):
    """The run is killed at the checkpoint, after the orders are written and before the
    first is admitted. On reopen they are all prepared and nothing is booked."""
    config_dir, env_file = paper(tmp_path)
    script = textwrap.dedent(f"""
        import os, signal, sys, json
        sys.path[:0] = [{str(REPO / 'src')!r}]
        from pathlib import Path
        from fund.core.types import Instant
        from fund.run import cycle, decide
        from fund.store import db
        cycle.cycle(snapshot_path=Path({str(CAPTURE)!r}),
                    offered=decide.cycle_reports(Path({str(REPORTS)!r})),
                    conn=db.connect({str(tmp_path / 'fund.sqlite')!r}),
                    out_dir=Path({str(tmp_path / 'out')!r}), at=Instant({clock(4).epoch_ms}),
                    config_dir=Path({str(config_dir)!r}), env_file=Path({str(env_file)!r}),
                    checkpoint=lambda step, what: os.kill(os.getpid(), signal.SIGKILL))
    """)
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert done.returncode == -signal.SIGKILL, done.stderr[-2000:]
    conn = db.connect(tmp_path / "fund.sqlite")
    written = OrderStore(conn).all()
    assert written and {o.state for o in written} == {OrderState.PREPARED}
    assert [type(e).__name__ for e in Journal(conn).events()] == ["Opening"]
