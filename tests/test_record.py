"""Unit 3.7: the decision record. Kept whole (= equal): it is what is sold."""

from __future__ import annotations

import hashlib
from decimal import Decimal

from fund import config
from fund.agents import risk
from fund.core import record
from fund.core.types import document_id
from phase3 import LIMITS, SEATS, SNAPSHOT, SNAPSHOT_SHA256, example_text, propose, written

MANDATE = config.load_json("mandate.json")
REPORTS = [{"seat": s, "agent": "unassigned", "text": example_text(s)} for s in SEATS]
CONFIG = {name: hashlib.sha256((config.CONFIG_DIR / name).read_bytes()).hexdigest()
          for name in record.CONFIG_FILES}
SETTINGS = risk.Settings(model="claude-sonnet-5", max_tokens=12000, transport_timeout_s=1,
                         worker_deadline_s=2, bytes_per_token=Decimal("1.8"))


def reply_for(plan, veto=()):
    lines = [f"RISK {document_id(plan)}"]
    for o in plan["orders"]:
        vote = "veto" if o["asset"]["symbol"] in veto else "approve"
        lines += [f"ORDER {o['index']} {o['asset']['symbol']} {vote}", "Scripted, not a model's."]
    return "\n".join(lines + ["OVERALL approve", "Scripted."]) + "\n"


def built(tmp_path, veto=(), **changes):
    plan = written(**changes)
    reply = reply_for(plan, veto)
    outcome = risk.review(plan, document_id(plan), snapshot=SNAPSHOT, mandate=MANDATE,
                          limits=LIMITS, settings=SETTINGS, work_dir=tmp_path,
                          reports=[risk.ReportText(r["seat"], r["text"]) for r in REPORTS],
                          recorded_reply=reply)
    return record.build(snapshot=SNAPSHOT, snapshot_sha256=SNAPSHOT_SHA256, reports=REPORTS,
                        config_sha256=CONFIG, proposal=propose().as_dict(), plan=plan,
                        review=outcome, risk_agent="unassigned", risk_reply=reply)


def test_the_record_cites_every_input_by_hash_and_carries_every_finding(tmp_path):
    r = built(tmp_path, veto=("AMD",))
    assert r["schema"] == "openfund.decision/2" and r["snapshot"]["sha256"] == SNAPSHOT_SHA256
    assert sorted(r["hashes"]["reports"]) == sorted(SEATS)
    assert r["hashes"]["reports"]["price-trend"] == hashlib.sha256(
        example_text("price-trend").encode()).hexdigest()
    assert set(r["hashes"]["config"]) == set(record.CONFIG_FILES)
    assert r["hashes"]["plan"] == document_id(r["plan"])
    assert r["hashes"]["gates"] == document_id(r["gates"])
    assert r["risk"]["reply_sha256"] == hashlib.sha256(r["risk"]["reply_text"].encode()).hexdigest()
    assert {f["symbol"] for f in r["findings"]} == {"AMD", "AMZN", "GOOGL", "MSTR", "SGOV"}
    assert [o["symbol"] for o in r["decision"]["approved"]] == ["USO", "META", "INTC"]
    assert r["decision"]["vetoed"] == [{"index": 1, "symbol": "AMD", "side": "buy",
                                        "usd": r["plan"]["orders"][0]["usd"],
                                        "vetoed_by": ["risk"]}]
    assert r["decision"]["executed"].startswith("nothing")


def test_the_same_inputs_give_the_same_bytes_and_no_clock_enters(tmp_path):
    first, second = built(tmp_path / "a"), built(tmp_path / "b")
    assert record.encode(first) == record.encode(second)
    assert record.decision_id(first) == hashlib.sha256(record.encode(first)).hexdigest()
    assert first["decided_at_ms"] == first["plan"]["judged_at_ms"]
    text = record.encode(first).decode()
    for timing in ("elapsed_ms", "request_id", "environment_names", "recorded"):
        assert f'"{timing}"' not in text, timing


def test_a_vetoed_order_names_every_rule_that_vetoed_it(tmp_path):
    r = built(tmp_path, veto=("META",), META={"fetched_ms": 1_790_000_000_000 - 120_000})
    meta = next(o for o in r["decision"]["vetoed"] if o["symbol"] == "META")
    assert meta["vetoed_by"] == ["quote-age", "risk"]


def test_a_loose_citation_is_carried_into_the_signed_record(tmp_path):
    """A reader of the record sees which citations were imprecise (2.2, since 3.8)."""
    loose = {"cited": "swap_impact_bps", "found": "MSTR quote.swap_impact_bps",
             "written": None, "line": 12, "why": "MSTR has no field swap_impact_bps"}
    plan = written()
    reply = reply_for(plan)
    outcome = risk.review(plan, document_id(plan), snapshot=SNAPSHOT, mandate=MANDATE,
                          limits=LIMITS, settings=SETTINGS, work_dir=tmp_path,
                          reports=[risk.ReportText(r["seat"], r["text"]) for r in REPORTS],
                          recorded_reply=reply)
    reports = [{**r, "imprecise_citations": [loose] if r["seat"] == "execution-quality" else []}
               for r in REPORTS]
    r = record.build(snapshot=SNAPSHOT, snapshot_sha256=SNAPSHOT_SHA256, reports=reports,
                     config_sha256=CONFIG, proposal=propose().as_dict(), plan=plan,
                     review=outcome, risk_agent="unassigned", risk_reply=reply)
    carried = {c["seat"]: c["imprecise_citations"] for c in r["reports"]}
    assert carried["execution-quality"] == [loose] and carried["price-trend"] == []
    assert b'"imprecise_citations"' in record.encode(r)
