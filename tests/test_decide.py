"""Units 3.1 to 3.7 together: four approved reports in, a signed decision out.

Offline. The quotes are the labelled fake venue's (phase3.py), recorded to a
file the command replays. The risk call goes through the real process path to
2.4's fake gateway on 127.0.0.1, and its reply is scripted. The signing key is
generated for the test. Nothing is executed, because nothing in Phase 3 can
execute.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

from fund.agents import risk, runner
from fund.core import plan
from fund.core.types import Instant, document_id
from fund.run import decide
from fund.store import reports
from phase3 import (
    CAPTURE, FOUR, JUDGED_MS, LIMITS, SNAPSHOT, book, fake_quote, propose, worth, written,
)
from test_runner import ALLOWED_NAMES, PRICE, FakeGateway

SHARED = {"BANKR_LLM_KEY": "bk_fake_shared_gateway_key_0000000001"}
SEED = Ed25519PrivateKey.generate().private_bytes(Encoding.Raw, PrivateFormat.Raw,
                                                  NoEncryption()).hex()


@pytest.fixture
def gateway():
    made = []

    def make(script):
        made.append(FakeGateway(script))
        return made[-1]

    yield make
    for g in made:
        g.close()


def quotes_file(tmp_path, the_book=None, **changes) -> Path:
    """The fake venue's answers for the plan the approved reports make, recorded."""
    the_book = the_book or book()
    intents = plan.size(propose(FOUR, the_book), the_book, SNAPSHOT, LIMITS)
    observations = {i.index: fake_quote(i, **changes.get(i.symbol, {})) for i in intents}
    path = tmp_path / "quotes-in.json"
    path.write_text(json.dumps(decide.quotes_file(
        observations, Instant(JUDGED_MS), "FAKE VENUE: scaled from the capture; not quotes")))
    return path


def scripted(plan_document, veto=()) -> str:
    lines = [f"RISK {document_id(plan_document)}"]
    for o in plan_document["orders"]:
        vote = "veto" if o["asset"]["symbol"] in veto else "approve"
        lines += [f"ORDER {o['index']} {o['asset']['symbol']} {vote}",
                  "Scripted for the test, not a model's words."]
    return "\n".join(lines + ["OVERALL approve", "Scripted."]) + "\n"


def run(tmp_path, *, quotes, g=None, reply=None, holdings=None, cash="200", key=True,
        environ=SHARED):
    tmp_path.mkdir(parents=True, exist_ok=True)
    env_file = tmp_path / "treasurer.env"
    env_file.write_text(f"SIGNING_KEY={SEED}\n" if key else "")
    settings = risk.Settings(model="claude-sonnet-5", max_tokens=12000, transport_timeout_s=2.5,
                             worker_deadline_s=3.5, bytes_per_token=Decimal("1.8"),
                             pricing=PRICE, gateway_url=g.url if g else "http://127.0.0.1:9")
    return decide.decide(
        snapshot_path=CAPTURE / "snapshot.json", offered=decide.approved_reports(),
        holdings=holdings or {}, cash_usd=Decimal(cash), out_dir=tmp_path / "out",
        quotes=lambda intents: decide.recorded_quotes(quotes), quote_label="test",
        risk_settings=settings,
        risk_credential=None if reply else runner.SharedGatewayKey(environ).for_seat("risk"),
        environ=environ, recorded_reply=reply, store=reports.ReportStore(tmp_path / "store"),
        env_file=env_file)


def test_four_approved_reports_become_a_signed_decision(gateway, tmp_path, monkeypatch):
    monkeypatch.setenv("SIGNING_KEY", "e" * 64)  # a parent secret the risk child must not see
    expected = written()
    g = gateway({"risk": [("report", scripted(expected, veto=("AMD",)))]})
    done = run(tmp_path, quotes=quotes_file(tmp_path), g=g)

    assert done["accepted"] == ["price-trend", "cross-asset-macro", "execution-quality",
                                "price-integrity"] and done["refused"] == []
    assert done["plan"] == expected  # the command and the units agree to the byte
    decision = done["record"]["decision"]
    assert [o["symbol"] for o in decision["approved"]] == ["USO", "META", "INTC"]
    assert decision["vetoed"] == [{"index": 1, "symbol": "AMD", "side": "buy",
                                   "usd": expected["orders"][0]["usd"], "vetoed_by": ["risk"]}]
    envelope = done["envelope"]
    assert envelope["signed"] is True and done["authorizes"]["authorizes"] is True
    record_bytes = (tmp_path / "out" / "record.json").read_bytes()
    assert hashlib.sha256(record_bytes).hexdigest() == done["decision_id"] == envelope[
        "decision_id"]
    names = set(done["review"]["reply"]["environment_names"])
    assert names <= ALLOWED_NAMES and "SIGNING_KEY" not in names
    for path in (tmp_path / "out").rglob("*"):
        if path.is_file():
            text = path.read_text(errors="replace")
            assert SEED not in text and SHARED["BANKR_LLM_KEY"] not in text, path
    shown = decide.summary(done)
    assert "VETOED by risk" in shown and "authorizes True" in shown
    assert "nothing was executed" in shown


def test_a_stale_quote_is_vetoed_by_name_even_when_risk_approves(gateway, tmp_path):
    quotes = quotes_file(tmp_path, META={"fetched_ms": 1_790_000_000_000 - 120_000})
    expected = written(META={"fetched_ms": 1_790_000_000_000 - 120_000})
    g = gateway({"risk": [("report", scripted(expected))]})
    done = run(tmp_path, quotes=quotes, g=g)
    meta = next(o for o in done["record"]["decision"]["vetoed"] if o["symbol"] == "META")
    assert meta["vetoed_by"] == ["quote-age"]
    assert "BLOCKED by quote-age" in decide.summary(done)


def test_without_a_signing_key_the_record_is_unsigned_and_does_not_authorize(tmp_path):
    expected = written()
    done = run(tmp_path, quotes=quotes_file(tmp_path), reply=scripted(expected), key=False)
    assert done["envelope"]["signed"] is False
    assert done["authorizes"] == {"authorizes": False,
                                  "reason": "unsigned: signed=false never authorizes"}


def test_in_cycle_two_a_held_asset_on_hold_and_one_nobody_mentions_are_not_traded(tmp_path):
    held = {"NVDA": worth("NVDA", "20"), "TSLA": worth("TSLA", "10")}
    the_book = book(held, cash="170")
    expected = written(the_book=the_book)
    done = run(tmp_path, quotes=quotes_file(tmp_path, the_book), reply=scripted(expected),
               holdings={a.asset.address: a for a in held.values()}, cash="170")
    traded = {o["asset"]["symbol"] for o in done["plan"]["orders"]}
    assert traded == {"AMD", "USO", "META", "INTC"}
    rows = {r["symbol"]: r for r in done["record"]["proposal"]["rows"]}
    assert rows["NVDA"]["target"] == rows["NVDA"]["current"] != "0"
    assert rows["TSLA"]["target"] == rows["TSLA"]["current"] and rows["TSLA"]["why"] == (
        "no seat mentioned it: kept")


def test_the_same_recorded_inputs_rebuild_the_same_record_bytes(tmp_path):
    expected = written()
    quotes, reply = quotes_file(tmp_path), scripted(expected, veto=("INTC",))
    first = run(tmp_path / "a", quotes=quotes, reply=reply)
    second = run(tmp_path / "b", quotes=quotes, reply=reply)
    assert first["decision_id"] == second["decision_id"]
    assert (tmp_path / "a" / "out" / "record.json").read_bytes() == (
        tmp_path / "b" / "out" / "record.json").read_bytes()


def test_the_command_runs_from_its_arguments(tmp_path, capsys):
    expected = written()
    reply_path = tmp_path / "reply.txt"
    reply_path.write_text(scripted(expected))
    env_file = tmp_path / "treasurer.env"
    env_file.write_text(f"SIGNING_KEY={SEED}\n")
    code = decide.main(["--snapshot", str(CAPTURE), "--approved-reports",
                        "--quotes", str(quotes_file(tmp_path)), "--risk-reply", str(reply_path),
                        "--out", str(tmp_path / "out"), "--env-file", str(env_file)])
    shown = capsys.readouterr().out
    assert code == 0 and "authorizes True" in shown and shown.count("APPROVED") == 4
    assert {p.name for p in (tmp_path / "out").iterdir()} >= {
        "record.json", "envelope.json", "plan.json", "quotes.json", "risk.json",
        "proposal.json", "table.txt", "reports.json"}


def test_the_record_names_each_loose_citation_of_the_reports_it_accepted(tmp_path):
    """One approved report with a citation cut short: it is still accepted, and the
    signed record says which citation was loose and where the value is."""
    offered = decide.approved_reports()
    trend = next(o for o in offered if o.seat == "price-trend")
    cut = trend.text.replace("- 559.42, Friday's close and the 30-day high [mark.price_usd]",
                             "- 559.42, Friday's close and the 30-day high [price_usd]", 1)
    assert cut != trend.text
    offered = [decide.Offered(o.seat, o.agent, cut, o.source) if o is trend else o
               for o in offered]
    expected = written()
    env_file = tmp_path / "treasurer.env"
    env_file.write_text(f"SIGNING_KEY={SEED}\n")
    settings = risk.Settings(model="claude-sonnet-5", max_tokens=12000, transport_timeout_s=2.5,
                             worker_deadline_s=3.5, bytes_per_token=Decimal("1.8"), pricing=PRICE)
    quotes = quotes_file(tmp_path)
    done = decide.decide(snapshot_path=CAPTURE / "snapshot.json", offered=offered, holdings={},
                         cash_usd=Decimal(200), out_dir=tmp_path / "out",
                         quotes=lambda intents: decide.recorded_quotes(quotes), quote_label="t",
                         risk_settings=settings, risk_credential=None, environ=SHARED,
                         recorded_reply=scripted(expected),
                         store=reports.ReportStore(tmp_path / "store"), env_file=env_file)
    assert len(done["accepted"]) == 4 and done["envelope"]["signed"] is True
    carried = {r["seat"]: r["imprecise_citations"] for r in done["record"]["reports"]}
    # Two fields end in price_usd (the mark and the corroboration), so the citation
    # names none; the figure is then found by value at the mark.
    assert [(c["cited"], c["found"], c["written"]) for c in carried["price-trend"]] == [
        ("price_usd", None, None), ("no field", "AMD mark.price_usd", "559.42")]
    assert carried["cross-asset-macro"] == []
