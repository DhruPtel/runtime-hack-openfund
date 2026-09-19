"""Unit 3.9: a recorded cycle's decision record, rebuilt byte for byte with no network.

The cycle is the exit run that ended Phase 3, `fixtures/cycles/20260919T202259Z/`:
four real analyst reports, live quotes and one live risk call, signed with the
fund's key. Replay comes from recorded outputs, the risk agent's included (PLAN §2
invariant 7). Nothing is asked of a model and nothing touches the network.
- **The inputs:** the capture's snapshot, the recorded reports, the quotes and
  the instant they were judged at, and the risk reply.
- **The layout:** the plan is written in the layout the record's schema names
  (`core/plan.py` LAYOUTS). So the record rebuilds by its own layout after the
  plan's presentation changed (F3.8.12).

An H unit: the signed record is what the fund sells.
"""

from __future__ import annotations

import json
import shutil
import socket
from decimal import Decimal
from pathlib import Path

import pytest

from fund.agents import risk
from fund.core import plan, record
from fund.core.types import AssetId, Amount
from fund.run import decide
from fund.store import reports
from fund.treasurer import sign

REPO = Path(__file__).resolve().parents[1]
CYCLE = REPO / "fixtures" / "cycles" / "20260919T202259Z"
RECORDED = (CYCLE / "decision" / "record.json").read_bytes()
ENVELOPE = json.loads((CYCLE / "decision" / "envelope.json").read_text())


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Every connection refused, as `make replay` refuses them for a capture."""
    def refused(*args, **kwargs):
        raise AssertionError("a replay touched the network")
    monkeypatch.setattr(socket.socket, "connect", refused)
    monkeypatch.setattr(socket, "create_connection", refused)


def rebuild(tmp_path: Path, *, cycle: Path = CYCLE, layout: int | None = None) -> bytes:
    """The record, rebuilt from the cycle's own recorded inputs alone."""
    recorded = json.loads((cycle / "decision" / "record.json").read_text())
    layout = layout or next(n for n, name in record.SCHEMAS.items() if name == recorded["schema"])
    snapshot_path = REPO / "fixtures" / "snapshots" / "67364057-c06abd9e89f0" / "snapshot.json"
    snapshot = json.loads(snapshot_path.read_text())
    assert recorded["snapshot"]["sha256"] == __import__("hashlib").sha256(
        snapshot_path.read_bytes()).hexdigest()
    book = recorded["plan"]["book"]
    decimals = {a["asset"]["address"]: a["asset"]["decimals"] for a in snapshot["assets"]}
    holdings = {address: Amount.from_units(p["amount"], decimals[address],
                                           AssetId(snapshot["block"]["chain_id"], address))
                for address, p in book["positions"].items()}
    done = decide.decide(
        snapshot_path=snapshot_path, offered=decide.cycle_reports(cycle / "cycle"),
        holdings=holdings, cash_usd=Decimal(book["cash_usd"]), out_dir=tmp_path / "out",
        quotes=lambda intents: decide.recorded_quotes(cycle / "decision" / "quotes.json"),
        quote_label="replayed", risk_settings=risk.Settings.from_config(),
        risk_credential=None, risk_agent=recorded["risk"]["agent"], environ={},
        recorded_reply=recorded["risk"]["reply_text"],
        store=reports.ReportStore(tmp_path / "store"), env_file=tmp_path / "absent.env",
        layout=layout)
    assert done["envelope"]["signed"] is False  # a replay never signs
    return (tmp_path / "out" / "record.json").read_bytes()


def test_the_recorded_cycles_decision_record_rebuilds_byte_for_byte(tmp_path):
    rebuilt = rebuild(tmp_path)
    assert rebuilt == RECORDED
    assert json.loads(RECORDED)["schema"] == "openfund.decision/1"
    assert record.decision_id(json.loads(rebuilt)) == ENVELOPE["decision_id"] == (
        "732161ded89aee8367509069809b34e4fec901035a83011ebbf839d1bbe126fc")


def test_its_signature_holds_over_those_bytes_and_no_others():
    fund_key = ENVELOPE["public_key"]
    assert fund_key.startswith("1c232435")
    assert sign.authorizes(ENVELOPE, RECORDED, fund_key).value is True
    altered = RECORDED.replace(b'"vetoed_by":["risk"]', b'"vetoed_by":[]', 1)
    assert altered != RECORDED and sign.authorizes(ENVELOPE, altered, fund_key).value is False


def test_a_changed_recorded_input_changes_the_rebuilt_record(tmp_path):
    """The rebuild reads what was recorded, not a copy of the answer."""
    copy = tmp_path / "cycle"
    shutil.copytree(CYCLE, copy)
    quotes = json.loads((copy / "decision" / "quotes.json").read_text())
    quotes["judged_at_ms"] += 1
    (copy / "decision" / "quotes.json").write_text(json.dumps(quotes))
    assert rebuild(tmp_path / "a", cycle=copy) != RECORDED


def test_the_current_layout_is_not_the_recorded_one(tmp_path):
    """Written in today's layout, the plan shows each part of GME's and INTC's split
    move, so the bytes differ. That is why a record names its layout."""
    assert plan.LAYOUT == 2
    rebuilt = json.loads(rebuild(tmp_path, layout=2))
    assert rebuilt["schema"] == "openfund.decision/2"
    gme = [o for o in rebuilt["plan"]["orders"] if o["asset"]["symbol"] == "GME"]
    assert [o["move"]["part"] for o in gme] == [1, 2]
