"""Unit 2.2: the report format approved at 2.1, parsed and checked.

The four examples in planning/REPORT-FORMAT.md are the contract, and they are
read from that file here rather than copied, so an edit to the approved text is
an edit to what is tested. They are checked against the snapshot they were
written on, the committed weekend capture.
"""

import hashlib
import json
import random
import string
from pathlib import Path

import pytest

from fund.agents import schema

REPO = Path(__file__).resolve().parents[1]
FORMAT = (REPO / "planning" / "REPORT-FORMAT.md").read_text()
SNAPSHOT_PATH = REPO / "fixtures" / "snapshots" / "66852293-253315c0e691" / "snapshot.json"
SNAPSHOT = json.loads(SNAPSHOT_PATH.read_text())
SHA = hashlib.sha256(SNAPSHOT_PATH.read_bytes()).hexdigest()
AGENTS = {"price-trend": "0x…", "cross-asset-macro": "0x…", "execution-quality": "0x…",
          "price-integrity": "0x42a9bd235aedd68e9f2881710577105cb46e3d27"}
SEATS = tuple(AGENTS)


def example(seat: str) -> str:
    """The approved report for a seat: the first fenced block under its heading."""
    section = FORMAT.split(f". {seat}\n", 1)[1]
    return section.split("```\n", 2)[1]


def no_calls_example() -> str:
    block = FORMAT.split("### How NO_CALL appears", 1)[1].split("```\n", 2)[1]
    return "\n".join(line[2:] if line.startswith("  ") else line for line in block.splitlines())


def verdict(text: str, seat: str = "price-trend") -> schema.Verdict:
    return schema.validate(text, SNAPSHOT, contract=schema.Contract.load(seat),
                           agent=AGENTS[seat], snapshot_sha256=SHA)


def rules(v: schema.Verdict) -> set[str]:
    return {r.rule for r in v.refusals}


# --- the approved examples ------------------------------------------------------------------------

def test_the_snapshot_is_the_one_the_examples_were_written_on():
    assert SHA.startswith("253315c0e691") and f"REPORT price-trend 0x… {SHA}" in FORMAT


@pytest.mark.parametrize("seat", SEATS)
def test_every_approved_example_is_accepted(seat):
    v = verdict(example(seat), seat)
    assert v.refusals == () and v.ok


def test_the_approved_examples_parse_to_what_the_aggregator_reads():
    read = {seat: [(c["symbol"], c["word"], c["confidence"])
                   for c in verdict(example(seat), seat).report.as_dict()["calls"]]
            for seat in SEATS}
    assert read["price-trend"] == [("AMD", "buy", "medium"), ("META", "buy", "medium"),
                                   ("INTC", "buy", "low"), ("NVDA", "hold", "low"),
                                   ("AMZN", "sell", "low")]
    assert read["cross-asset-macro"] == [("USO", "buy", "low"), ("COIN", "hold", "medium")]
    assert read["execution-quality"] == [("MSTR", "caution", "high"), ("NVDA", "proceed", "high"),
                                         ("SPY", "proceed", "high")]
    assert [w for _, w, _ in read["price-integrity"]] == ["caution", "caution", "proceed",
                                                         "proceed", "proceed"]
    nvda = verdict(example("price-trend")).report.calls[3]
    assert nvda.address == "0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec"
    assert len(nvda.figures) == 3 and "230.24" in nvda.figures[1].text


def test_a_whole_report_abstention_is_a_complete_report():
    v = verdict(no_calls_example(), "cross-asset-macro")
    assert v.ok and v.report.no_calls and v.report.calls == ()


def test_a_single_code_fence_around_the_reply_is_transport_not_content():
    assert verdict("```text\n" + example("price-trend") + "```\n").ok


# --- the check that matters most: a figure must be the field it cites ----------------------------

@pytest.mark.parametrize("seat, true, false, field", [
    ("price-trend", "- 559.42, Friday's close", "- 569.42, Friday's close", "AMD mark.price_usd"),
    ("price-trend", "- 644.00, the last pullback", "- 641.00, the last pullback",
     "META timeline 2026-09-10"),
    ("execution-quality", "- $50.85M of 24-hour volume", "- $60.85M of 24-hour volume",
     "NVDA corroboration.volume_24h_usd"),
    ("execution-quality", "- impact 9 bps", "- impact 4 bps", "NVDA quote.swap_impact_bps"),
    ("price-integrity", "GeckoTerminal 99.86 (−1.2%)", "GeckoTerminal 98.86 (−1.2%)",
     "SGOV corroboration.price_usd"),
])
def test_a_fabricated_figure_is_caught_by_name(seat, true, false, field):
    text = example(seat)
    assert true in text
    v = verdict(text.replace(true, false, 1), seat)
    refusal = next(r for r in v.refusals if r.rule == "figure")
    assert not v.ok and field in refusal.detail and false.split()[1].rstrip(",") in refusal.detail


def test_either_rounding_of_an_exact_midpoint_is_the_field():
    """The capture holds two closes exactly at a midpoint, and the approved reports round
    them opposite ways: AMZN's 266.085 as 266.08, USO's 161.405 as 161.41. Both are
    the field, and a digit further off is not."""
    closes = json.dumps(SNAPSHOT)
    assert '"266.085"' in closes and '"161.405"' in closes
    assert "266.08 on 28 August" in example("price-trend")
    assert "161.41" in example("cross-asset-macro")
    assert verdict(example("price-trend")).ok
    assert verdict(example("cross-asset-macro"), "cross-asset-macro").ok
    off = example("price-trend").replace("266.08 on 28 August", "266.07 on 28 August", 1)
    assert "figure" in rules(verdict(off))


def test_a_computed_figure_is_cited_but_not_checked():
    """The approved rule, and its limit: a percentage is the analyst's arithmetic."""
    text = example("price-trend").replace("- +9.0% in the last two sessions",
                                          "- +19.0% in the last two sessions")
    assert verdict(text).ok


# --- every other rule refuses by its own name -------------------------------------------------------

AMD = "0x86923f96303d656e4aa86d9d42d1e57ad2023fdc"
ASML = next(a["asset"]["address"] for a in SNAPSHOT["assets"] if a["asset"]["symbol"] == "ASML")

MUTATIONS = {
    "header: no first line": ("REPORT price-trend 0x… ", "", "header"),
    "header: wrong seat": ("REPORT price-trend", "REPORT price-integrity", "header"),
    "header: wrong snapshot": (SHA, "0" * 64, "header"),
    "call-shape": (f"CALL AMD {AMD} buy medium", "CALL AMD buy medium", "call-shape"),
    "vocabulary": (f"CALL AMD {AMD} buy medium", f"CALL AMD {AMD} caution medium", "vocabulary"),
    "confidence": (f"CALL AMD {AMD} buy medium", f"CALL AMD {AMD} buy 0.7", "confidence"),
    "asset: not in the snapshot": (AMD, "0x" + "0" * 39 + "1", "asset"),
    "asset: wrong symbol": (f"CALL AMD {AMD}", f"CALL AMZN {AMD}", "asset"),
    "asset: not tradeable": (f"CALL AMD {AMD}", f"CALL ASML {ASML}", "asset"),
    "no-calls: both": ("\nCALL AMD", "\nNO CALLS\nCALL AMD", "no-calls"),
    "citation: no such field": ("[mark.price_usd]", "[mark.price_usdx]", "citation"),
    "citation: no such close": ("[timeline 2026-09-03]", "[timeline 2026-08-22]", "citation"),
    "citation: no such asset": ("SPY mark.price_usd]", "XYZ mark.price_usd]", "citation"),
}


@pytest.mark.parametrize("name", MUTATIONS)
def test_each_rule_refuses_by_its_own_name(name):
    old, new, rule = MUTATIONS[name]
    text = example("price-trend")
    assert old in text
    v = verdict(text.replace(old, new, 1))
    assert not v.ok and rule in rules(v)


def test_a_report_with_no_calls_must_say_so():
    v = verdict(f"REPORT price-trend 0x… {SHA}\n\nNothing stands out this week.\n")
    assert rules(v) == {"no-calls"}


def test_coverage_is_at_most_the_configured_calls_one_per_asset():
    text = example("price-trend")
    extra = text.split("CALL NVDA", 1)[0].split("CALL AMD", 1)[1]  # AMD, META and INTC blocks
    twice = verdict(text + "\nCALL AMD" + extra)
    assert "coverage" in rules(twice)
    assert any("called twice" in r.detail for r in twice.refusals)
    assert any("6 calls" not in r.detail and "at most 6" in r.detail for r in twice.refusals)


def test_nothing_a_model_writes_raises():
    randomness = random.Random(20260919)
    text = example("price-integrity")
    cut_short = [text[:n] for n in range(0, len(text), 97)]
    noise = ["".join(randomness.choice(string.printable) for _ in range(randomness.randint(0, 400)))
             for _ in range(200)]
    for reply in cut_short + noise + [f"REPORT a b {SHA}\nCALL", "CALL\nREPORT", "[", "]["]:
        v = schema.validate(reply, SNAPSHOT, contract=schema.Contract.load("price-integrity"),
                            agent=AGENTS["price-integrity"], snapshot_sha256=SHA)
        assert isinstance(v, schema.Verdict)
    assert not any(schema.validate(t, SNAPSHOT, contract=schema.Contract.load("price-integrity"),
                                   agent=AGENTS["price-integrity"], snapshot_sha256=SHA).ok
                   for t in cut_short[:3])


# --- 2.6's first real reply, recorded (research/findings.md §2.6) --------------------------------

REPLY_2_6 = (REPO / "tests" / "data" / "2.6-price-integrity.reply.txt").read_text()
FUND_WALLET = "0x93faecde3c88a713e1edddf417c02c326889a3da"


def test_the_first_real_reply_is_the_one_recorded():
    """Byte for byte what the gateway returned for chatcmpl-ZIpvPVmNGmb4GQNT7CTWG."""
    assert len(REPLY_2_6) == 4073
    assert REPLY_2_6.startswith(f"REPORT price-integrity {FUND_WALLET} {SHA}\n")


def test_its_computed_bps_figures_are_cited_not_checked():
    """Five divergences the model computed between the prices it cited, all correct,
    that the earlier rule refused. Only the header refusal is left."""
    v = schema.validate(REPLY_2_6, SNAPSHOT, contract=schema.Contract.load("price-integrity"),
                        agent="0x…", snapshot_sha256=SHA)
    assert [r.rule for r in v.refusals] == ["header"]
    assert FUND_WALLET in v.refusals[0].detail


def test_with_only_the_placeholder_it_filled_in_put_back_the_reply_is_accepted():
    """The header refusal was provoked by the `0x…` placeholder (now `unassigned`).
    Put back only that token, and nothing else in the report fails."""
    restored = REPLY_2_6.replace(f"REPORT price-integrity {FUND_WALLET} ",
                                 "REPORT price-integrity 0x… ", 1)
    assert restored.count("\n") == REPLY_2_6.count("\n") and len(restored) < len(REPLY_2_6)
    v = schema.validate(restored, SNAPSHOT, contract=schema.Contract.load("price-integrity"),
                        agent="0x…", snapshot_sha256=SHA)
    assert v.ok, [str(r) for r in v.refusals]
    assert [(c.symbol, c.word, c.confidence) for c in v.report.calls] == [
        ("AMD", "caution", "medium"), ("AMZN", "proceed", "low"), ("GOOGL", "proceed", "low"),
        ("MSTR", "caution", "medium"), ("SGOV", "proceed", "low")]


def test_a_bps_figure_that_names_a_bps_field_is_still_checked():
    """The same reply's cited divergence field, altered by ten bps, is refused."""
    altered = REPLY_2_6.replace("divergence -450.32bps from mark", "divergence -440.32bps from mark")
    v = schema.validate(altered.replace(f" {FUND_WALLET} ", " 0x… ", 1), SNAPSHOT,
                        contract=schema.Contract.load("price-integrity"), agent="0x…",
                        snapshot_sha256=SHA)
    refusal = next(r for r in v.refusals if r.rule == "figure")
    assert "-440.32bps" in refusal.detail and "corroboration.divergence_bps = -450.32" in refusal.detail


# --- 3.8's recorded replies: what the live run showed the validator got wrong --------------------

def test_a_figure_with_thousands_separators_is_the_same_number():
    """3.8: price-integrity wrote AMZN's volume `$2,101,924.28`, and the comma split it."""
    text = example("price-integrity").replace("on $2.10M [corroboration.price_usd,",
                                              "on $2,101,924.28 [corroboration.price_usd,", 1)
    assert "$2,101,924.28" in text and verdict(text, "price-integrity").ok
    wrong = text.replace("$2,101,924.28", "$2,201,924.28", 1)
    refusal = next(r for r in verdict(wrong, "price-integrity").refusals if r.rule == "figure")
    assert "2201924.28" in refusal.detail
