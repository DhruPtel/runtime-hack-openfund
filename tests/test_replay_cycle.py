"""Unit 3.9: a recorded cycle's decision record, rebuilt byte for byte with no network.

The cycle is the exit run that ended Phase 3, `fixtures/cycles/20260919T202259Z/`:
four real analyst reports, live quotes and one live risk call, signed with the
fund's key. Replay comes from recorded outputs, the risk agent's included (PLAN §2
invariant 7). Nothing is asked of a model and nothing touches the network.
- **The inputs:** the capture's snapshot, the recorded reports, the quotes and
  the instant they were judged at, the risk reply, and the config the decision
  was made under, which the cycle carries in `decision/config/`.
- **The layout:** the plan is written in the layout the record's schema names
  (`core/plan.py` LAYOUTS). So the record rebuilds by its own layout after the
  plan's presentation changed (F3.8.12).
- **The config:** the record names each config file's sha256. A replay reads the
  cycle's copy, never the working tree, so tuning config later (4.1's mandate,
  S11's limit, the confidence weights) cannot change this rebuild. Until then the
  replay read the working tree, and its first edit would have broken the test.

An H unit: the signed record is what the fund sells.
"""

from __future__ import annotations

import json
import shutil
import socket
from pathlib import Path

import pytest

from fund import config
from fund.core import plan, record
from fund.run import decide
from fund.treasurer import sign

REPO = Path(__file__).resolve().parents[1]
CYCLE = REPO / "fixtures" / "cycles" / "20260919T202259Z"
SNAPSHOT = REPO / "fixtures" / "snapshots" / "67364057-c06abd9e89f0" / "snapshot.json"
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
    return decide.replay(cycle, SNAPSHOT, tmp_path / "out", layout=layout)


def copied(tmp_path: Path) -> Path:
    copy = tmp_path / "cycle"
    shutil.copytree(CYCLE, copy)
    return copy


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
    copy = copied(tmp_path)
    quotes = json.loads((copy / "decision" / "quotes.json").read_text())
    quotes["judged_at_ms"] += 1
    (copy / "decision" / "quotes.json").write_text(json.dumps(quotes))
    assert rebuild(tmp_path / "a", cycle=copy) != RECORDED


def test_the_working_trees_config_does_not_reach_the_replay(tmp_path, monkeypatch):
    """Every config file the record names, changed in the working tree the way a later
    unit will change it: the rebuild is still byte for byte. A replay that read one of
    them from `config/` would differ here."""
    tree = tmp_path / "tree"
    shutil.copytree(config.CONFIG_DIR, tree)

    def edit(name, change):
        document = json.loads((tree / name).read_text())
        change(document)
        (tree / name).write_text(json.dumps(document))

    edit("mandate.json", lambda m: m.update(allowed_assets=[], max_trade_usd=5,
                                            approved_by="the operator"))  # 4.1
    edit("thresholds.json", lambda t: t.update(cash_floor_usd="150", max_position_weight="0.1",
                                               quote_max_age_seconds=1, impact_max_bps=1,
                                               snapshot_max_age_seconds=900))  # S11
    edit("models.json", lambda m: m.update(context_bytes_per_token="3", max_output_tokens=4000,
                                           context_budget_tokens=1000))
    edit("analysts.json", lambda a: a.update(
        confidence_weights={w: "0.9" for w in a["confidence_weights"]}, confidence=["certain"]))
    monkeypatch.setattr(config, "CONFIG_DIR", tree)
    assert config.load_json("mandate.json")["allowed_assets"] == []  # the tree is changed

    assert rebuild(tmp_path) == RECORDED


@pytest.mark.parametrize("name", record.CONFIG_FILES)
def test_a_changed_carried_config_file_refuses_the_replay(tmp_path, name):
    """The carried copy is a recorded input like any other. Altered, it is not the
    config the record names, and the replay refuses by name rather than rebuild a
    different record."""
    copy = copied(tmp_path)
    carried = copy / "decision" / "config" / name
    carried.write_bytes(carried.read_bytes() + b"\n")  # one byte: the same JSON, other bytes
    with pytest.raises(decide.ReplayError, match=name):
        rebuild(tmp_path / "a", cycle=copy)


def test_a_cycle_without_its_config_cannot_be_replayed(tmp_path):
    copy = copied(tmp_path)
    shutil.rmtree(copy / "decision" / "config")
    with pytest.raises(decide.ReplayError, match="carries no"):
        rebuild(tmp_path / "a", cycle=copy)


def test_the_current_layout_is_not_the_recorded_one(tmp_path):
    """Written in today's layout, the plan shows each part of GME's and INTC's split
    move, so the bytes differ. That is why a record names its layout."""
    assert plan.LAYOUT == 2
    rebuilt = json.loads(rebuild(tmp_path, layout=2))
    assert rebuilt["schema"] == "openfund.decision/2"
    gme = [o for o in rebuilt["plan"]["orders"] if o["asset"]["symbol"] == "GME"]
    assert [o["move"]["part"] for o in gme] == [1, 2]
