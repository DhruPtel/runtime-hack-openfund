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
}


@pytest.mark.parametrize("name", MUTATIONS)
def test_each_rule_refuses_by_its_own_name(name):
    old, new, rule = MUTATIONS[name]
    text = example("price-trend")
    assert old in text
    v = verdict(text.replace(old, new, 1))
    assert not v.ok and rule in rules(v)


# --- an imprecise citation is recorded, not refused; its figure is still checked (3.8) -------------

IMPRECISE = {
    "no such field": ("[mark.price_usd]", "[mark.price_usdx]", "mark.price_usdx", "AMD mark.price_usd"),
    "no such close": ("[timeline 2026-09-03]", "[timeline 2026-08-22]", "timeline 2026-08-22",
                      "AMD timeline 2026-09-03"),
    "no such asset": ("SPY mark.price_usd]", "XYZ mark.price_usd]", "XYZ mark.price_usd", None),
}


@pytest.mark.parametrize("name", IMPRECISE)
def test_an_imprecise_citation_is_recorded_and_the_report_accepted(name):
    """The operator's rule after 3.8: a reference that names nothing as written does
    not refuse the report. It is recorded, and the figure under it is found by value."""
    old, new, cited, found = IMPRECISE[name]
    text = example("price-trend")
    v = verdict(text.replace(old, new, 1))
    assert v.ok, v.refusals
    assert cited in [i.cited for i in v.imprecisions]
    if found:
        assert found in [i.found for i in v.imprecisions if i.written is not None]
    assert v.as_dict()["imprecise_citations"]


@pytest.mark.parametrize("name", ["no such field", "no such close"])
def test_a_fabricated_figure_under_an_imprecise_citation_still_refuses(name):
    old, new, _, _ = IMPRECISE[name]
    figure = {"no such field": ("559.42, Friday's close", "569.42, Friday's close"),
              "no such close": ("454.99, the low", "444.99, the low")}[name]
    text = example("price-trend").replace(old, new, 1).replace(*figure, 1)
    refusal = next(r for r in verdict(text).refusals if r.rule == "figure")
    assert figure[1].split(",")[0] in refusal.detail and "nor any value of AMD" in refusal.detail


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


CYCLE_3_8 = REPO / "fixtures" / "cycles" / "20260919T171351Z" / "cycle" / "results"


def recorded_3_8(seat: str) -> str:
    from fund.agents import show
    return show.reply_text(json.loads((CYCLE_3_8 / f"{seat}.json").read_text()))


def live(text: str, seat: str) -> schema.Verdict:
    return schema.validate(text, SNAPSHOT, contract=schema.Contract.load(seat),
                           agent="unassigned", snapshot_sha256=SHA)


def test_the_3_8_replies_revalidated_from_their_stored_text():
    """No new call. All four pass, each loose citation recorded. cross-asset-macro's
    last refusal, `+(-0.09)%`, is SPY's change between the two closes its line cites,
    one arithmetic step (S1). The parser still does not read the notation as a
    percentage (S4): a figure that is no such step refuses."""
    verdicts = {s: live(recorded_3_8(s), s) for s in SEATS}
    assert {s: v.ok for s, v in verdicts.items()} == {s: True for s in SEATS}
    macro = recorded_3_8("cross-asset-macro")
    assert "SPY +(-0.09)% over 30 days: 762.21 to 761.55079369" in macro
    wrong = live(macro.replace("SPY +(-0.09)%", "SPY +(-0.19)%", 1), "cross-asset-macro")
    assert [r.rule for r in wrong.refusals] == ["figure"] and "-0.19" in wrong.refusals[0].detail
    loose = {str(i) for i in verdicts["price-trend"].imprecisions}
    assert loose == {"109.05 cites INTC timeline 2026-09-09, INTC timeline 2026-09-17; "
                     "it is INTC mark.price_usd (line 34)"}
    found = {(i.written, i.found) for i in verdicts["cross-asset-macro"].imprecisions}
    assert ("544.70535", "META timeline 2026-08-20") in found
    assert ("751.28", "SPY timeline 2026-09-16") in found
    assert verdicts["price-integrity"].imprecisions == ()  # its bracket was prose, not a citation
    paths = {(i.cited, i.found) for i in verdicts["execution-quality"].imprecisions}
    assert ("swap_impact_bps", "MSTR quote.swap_impact_bps") in paths
    assert all(i.line and i.line > 3 for i in verdicts["execution-quality"].imprecisions)


@pytest.mark.parametrize("seat, real, fabricated", [
    ("price-trend", "cleared to 109.20-109.05", "cleared to 109.20-110.05"),
    ("cross-asset-macro", "544.70535 to 666.7615", "545.70535 to 666.7615"),
    ("cross-asset-macro", "SPY fell to 751.28 on 9/16 while SGOV", "SPY fell to 741.28 on 9/16 while SGOV"),
    ("execution-quality", "quote age 0.725s", "quote age 0.925s"),
    ("price-integrity", "mark 559.42445 vs corroboration", "mark 569.42445 vs corroboration"),
    ("price-integrity", "on $2,101,924.28 of 24h volume", "on $2,191,924.28 of 24h volume"),
])
def test_every_3_8_figure_changed_to_a_value_the_snapshot_does_not_hold_refuses(
        seat, real, fabricated):
    """The fabrication check, unweakened: each of these lines was loose or newly read,
    and a figure on it that matches nothing still refuses the report."""
    text = recorded_3_8(seat)
    assert real in text
    v = live(text.replace(real, fabricated, 1), seat)
    assert not v.ok and "figure" in rules(v), fabricated


def test_a_real_value_of_an_asset_the_line_does_not_name_still_refuses():
    """The search is the assets the line is about, not the whole snapshot: META's
    close written on AMD's line, with META named nowhere, is refused."""
    text = example("price-trend").replace("- 454.99, the low on 3 September [timeline 2026-09-03]",
                                          "- 544.71, the low on 3 September [timeline 2026-09-03]",
                                          1)
    assert "figure" in rules(verdict(text))


def test_a_bracket_that_is_not_a_field_reference_is_not_a_citation():
    """3.8: price-integrity quoted `["us_equities_24/5"]` in its prose, and was refused."""
    text = example("price-integrity").replace(
        "none\nwill move until Monday", 'none\nwill move until Monday (`["us_equities_24/5"]`)', 1)
    assert '["us_equities_24/5"]' in text
    v = verdict(text, "price-integrity")
    assert v.ok and v.imprecisions == ()


@pytest.mark.parametrize("line, ok", [
    ("- 559.42, Friday's close and the 30-day high [see above]", True),
    ("- 569.42, Friday's close and the 30-day high [see above]", False),
    ("- Friday's close and the 30-day high [569.42]", False),
    ("- Friday's close and the 30-day high [559.42]", True),
])
def test_a_figure_behind_a_bracket_of_prose_is_still_checked(line, ok):
    """Not a citation is not a way around the fabrication check."""
    real = "- 559.42, Friday's close and the 30-day high [mark.price_usd]"
    text = example("price-trend")
    assert real in text
    v = verdict(text.replace(real, line, 1))
    assert v.ok is ok, v.refusals


def test_an_asset_named_at_the_end_of_a_sentence_is_one_the_line_is_about():
    text = recorded_3_8("cross-asset-macro").replace(
        "- META over the same window: 544.70535 to 666.7615, +22.4%",
        "- 544.70535 to 666.7615 over the same window, +22.4%, for META.", 1)
    assert "for META." in text
    found = {(i.written, i.found) for i in live(text, "cross-asset-macro").imprecisions}
    assert ("544.70535", "META timeline 2026-08-20") in found


# --- R5: the two holes the 3.8 sweep found in the fabrication check, attacked -----------------------

@pytest.mark.parametrize("line, ok", [
    ("- 559.42, Friday's close and the 30-day high", True),
    ("- 999.99, Friday's close and the 30-day high", False),
    ("- The close was 559.42. [mark.price_usd]", True),
    ("- The close was 999.99. [mark.price_usd]", False),
    ("- The close was 999.99.", False),
    ("- Friday's close, up 9.0% this week", True),
])
def test_a_figure_with_no_citation_or_before_a_full_stop_is_still_checked(line, ok):
    """At the sweep, `- 999.99, Friday's close` and `- The close was 999.99.
    [mark.price_usd]` were both accepted: the first never checked, the second never
    read. A percentage stays computed, cited or not."""
    real = "- 559.42, Friday's close and the 30-day high [mark.price_usd]"
    text = example("price-trend")
    assert real in text
    v = verdict(text.replace(real, line, 1))
    assert v.ok is ok, v.refusals
    if not ok:
        assert "999.99" in next(r for r in v.refusals if r.rule == "figure").detail


# --- R6: an indented or bolded CALL line is a call, and its figures are checked -------------------

META_BLOCK = """CALL META 0xc0d6457c16cc70d6790dd43521c899c87ce02f35 buy medium"""


def _indented_meta(text: str, prefix: str = "    ") -> str:
    """META's whole block indented, as the brief's template is."""
    start = text.index(META_BLOCK)
    end = text.index("\n\nCALL INTC")
    block = "\n".join(prefix + line if line else line for line in text[start:end].split("\n"))
    return text[:start] + block + text[end:]


@pytest.mark.parametrize("dress", ["indented", "bold", "backticks"])
def test_an_indented_or_bolded_call_is_a_call_the_aggregator_sees(dress):
    """At the sweep an indented or bolded CALL line was silently prose: the aggregator
    never saw the call, while the risk agent and a buyer read it."""
    text = example("price-trend")
    if dress == "indented":
        text = _indented_meta(text)
    else:
        mark = "**" if dress == "bold" else "`"
        text = text.replace(META_BLOCK, f"{mark}{META_BLOCK}{mark}", 1)
    v = verdict(text)
    assert v.ok, v.refusals
    assert "META" in [c["symbol"] for c in v.as_dict()["calls"]]
    meta = next(c for c in v.report.calls if c.symbol == "META")
    assert len(meta.figures) == 3


def test_a_fabricated_figure_under_an_indented_call_still_refuses():
    text = _indented_meta(example("price-trend")).replace(
        "- 644.00, the last pullback low", "- 641.00, the last pullback low", 1)
    assert "    - 641.00" in text
    assert "figure" in rules(verdict(text))


# --- S1: a computed figure on a cited line is computed, not fabricated -----------------------------

AMD_LINE = "- 559.42, Friday's close and the 30-day high [mark.price_usd]"


@pytest.mark.parametrize("line, ok", [
    # ratios, however written, are computed and never fields
    ("- 559.42, Friday's close, up 1.9 % on the week [mark.price_usd]", True),
    ("- 559.42, Friday's close, up 1.9 percent [mark.price_usd]", True),
    ("- 559.42, Friday's close, 4.5pp ahead of the index [mark.price_usd]", True),
    ("- 559.42, Friday's close, 8.3x its impact [mark.price_usd]", True),
    # one arithmetic step from two cited fields: here the mark less the venue's price
    ("- a 7.51 gap, 559.42 against 551.91 [mark.price_usd, quote.venue_price_usd]", True),
    ("- a 1.36 premium over the venue [mark.price_usd, quote.venue_price_usd]", True),
    # millions, however written, are still checked against a USD field
    ("- 559.42 on $1.06m of volume [mark.price_usd, corroboration.volume_24h_usd]", True),
    ("- 559.42 on $1.1 million of volume [mark.price_usd, corroboration.volume_24h_usd]", True),
    ("- 559.42 on $4.42m of volume [mark.price_usd, corroboration.volume_24h_usd]", False),
    # a figure that is no field and no one step from two is still fabricated
    ("- a 9.51 gap, 559.42 against 551.91 [mark.price_usd, quote.venue_price_usd]", False),
    ("- a 2.02 premium over the venue [mark.price_usd]", False),
])
def test_a_computed_figure_on_a_cited_line_is_computed_and_a_fabricated_one_is_not(line, ok):
    """S1: `a 2.02 premium`, `8.3x` and `1.9 %` were refused as fabricated at the
    sweep, though the brief asks for exactly such lines."""
    text = example("price-trend")
    assert AMD_LINE in text
    v = verdict(text.replace(AMD_LINE, line, 1))
    assert v.ok is ok, v.refusals


# --- S5: NO CALLS, however dressed, and beside calls ------------------------------------------------

@pytest.mark.parametrize("line", ["NO CALLS", "NO CALLS.", "**NO CALLS**", "`NO CALLS`",
                                  "No calls.", "  NO CALLS  "])
def test_a_whole_report_abstention_however_it_is_written(line):
    text = no_calls_example().replace("\nNO CALLS", "\n" + line, 1)
    v = verdict(text, "cross-asset-macro")
    assert v.ok and v.report.no_calls, (line, v.refusals)


def test_no_calls_beside_calls_means_none_beyond_them():
    """At the sweep this refused the report: `NO CALLS and CALL lines in one report`."""
    text = example("price-trend") + "\nNO CALLS on anything else.\nNO CALLS\n"
    v = verdict(text)
    assert v.ok and not v.report.no_calls and len(v.report.calls) == 5


def test_a_report_with_no_call_and_no_abstention_is_still_refused():
    v = verdict(no_calls_example().replace("\nNO CALLS", "\nNothing to add.", 1),
                "cross-asset-macro")
    assert rules(v) == {"no-calls"}


# --- S2: basis points and the sign of divergence_bps -------------------------------------------------

def _integrity_line(symbol: str, line: str) -> str:
    """price-integrity's approved report with one figure line added under a call."""
    text = example("price-integrity")
    head = next(l for l in text.splitlines() if l.startswith(f"CALL {symbol} "))
    return text.replace(head, head + "\n" + line, 1)


@pytest.mark.parametrize("symbol, line, ok", [
    ("AMZN", "- 450.32 bps above the mark [corroboration.divergence_bps]", True),
    ("AMZN", "- -450.32 bps [corroboration.divergence_bps]", True),
    ("AMD", "- a -105.98 bps divergence [corroboration.divergence_bps]", True),
    ("MSTR", "- the venue sits 54 bps below GeckoTerminal, a -183.84 bps divergence "
             "[quote.venue_price_usd, corroboration.price_usd, corroboration.divergence_bps]", True),
    ("AMZN", "- 460.32 bps above the mark [corroboration.divergence_bps]", False),
    ("MSTR", "- the venue sits 84 bps below GeckoTerminal, a -183.84 bps divergence "
             "[quote.venue_price_usd, corroboration.price_usd, corroboration.divergence_bps]", False),
])
def test_a_bps_figure_is_the_field_in_either_sign_or_computed_from_cited_prices(symbol, line, ok):
    """At the sweep, `450.32 bps above` against AMZN's -450.32 was refused, and so was
    a computed gap on a line that also cites divergence_bps. A bps figure that is
    neither the field nor one step from cited prices still refuses."""
    v = verdict(_integrity_line(symbol, line), "price-integrity")
    assert v.ok is ok, v.refusals


def test_the_brief_states_the_sign_of_divergence_bps_and_the_capture_agrees():
    from fund.agents import analyst
    shared = (analyst.BRIEFS / "analyst.v1.md").read_text()
    assert "positive when the mark is above" in shared
    for symbol, sign in (("AMD", 1), ("AMZN", -1)):
        entry = next(a for a in SNAPSHOT["assets"] if a["asset"]["symbol"] == symbol)
        mark, gecko = (float(entry["mark"]["price_usd"]),
                       float(entry["corroboration"]["price_usd"]))
        assert (mark > gecko) == (sign > 0)
        assert (float(entry["corroboration"]["divergence_bps"]) > 0) == (sign > 0)
