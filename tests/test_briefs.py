"""Unit 2.3: what each analyst receives.

Four versioned briefs, one per seat, each stating its own question and the
questions it leaves to the others, and every seat receiving the same snapshot
bytes, named by their hash.
"""

import hashlib
import json
from pathlib import Path

import pytest

from fund import config
from fund.agents import analyst

REPO = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = REPO / "fixtures" / "snapshots" / "66852293-253315c0e691" / "snapshot.json"
SNAPSHOT = SNAPSHOT_PATH.read_bytes()
SHA = hashlib.sha256(SNAPSHOT).hexdigest()
ANALYSTS = config.load_json("analysts.json")
SEATS = [a["id"] for a in ANALYSTS["analysts"]]


def brief(seat):
    return analyst.render(seat, SNAPSHOT, "0x…")


def test_there_are_four_seats_and_two_vocabularies():
    assert SEATS == ["price-trend", "cross-asset-macro", "execution-quality", "price-integrity"]
    assert {a["id"]: a["vocabulary"] for a in ANALYSTS["analysts"]} == {
        "price-trend": "direction", "cross-asset-macro": "direction",
        "execution-quality": "condition", "price-integrity": "condition"}


@pytest.mark.parametrize("seat", SEATS)
def test_each_brief_states_its_own_question_and_leaves_the_others_theirs(seat):
    entry = next(a for a in ANALYSTS["analysts"] if a["id"] == seat)
    b = brief(seat)
    assert f"## Your question\n\n{entry['question']}\n" in b.system
    for other in entry["not_asked"]:
        assert f"- {other}\n" in b.system
    assert "{question}" not in b.system and "{not_asked}" not in b.system
    assert b.files == (entry["brief"], "analyst.v1.md")


def test_the_four_questions_differ_and_each_seat_hands_off_to_at_least_two_others():
    """Disjoint in question: each seat names, by seat, the questions it leaves to others.
    The direction seats name all three others; each condition seat names the direction
    seat and the other condition seat it is most easily confused with."""
    questions = [a["question"] for a in ANALYSTS["analysts"]]
    assert len(set(questions)) == 4
    for entry in ANALYSTS["analysts"]:
        named = " ".join(entry["not_asked"])
        others = [s for s in SEATS if s != entry["id"]]
        assert sum(other in named for other in others) >= 2


@pytest.mark.parametrize("seat", SEATS)
def test_each_brief_speaks_only_its_own_vocabulary(seat):
    entry = next(a for a in ANALYSTS["analysts"] if a["id"] == seat)
    own = entry["vocabulary"]
    other = "condition" if own == "direction" else "direction"
    b = brief(seat)
    assert f"## Your vocabulary: {own}" in b.system
    for word in ANALYSTS["vocabularies"][own]:
        assert f"- `{word}`" in b.system
    for word in ANALYSTS["vocabularies"][other]:
        assert f"- `{word}`" not in b.system


def test_every_seat_receives_the_same_snapshot_bytes_named_by_their_hash():
    sections = []
    for seat in SEATS:
        user = brief(seat).user
        head, rest = user.split("\n", 1)
        body = rest.split("\nEND SNAPSHOT", 1)[0]
        assert head == f"SNAPSHOT {SHA} {len(SNAPSHOT)} bytes"
        assert body.encode("utf-8") == SNAPSHOT
        sections.append(user.split("\n\nWrite your report now.", 1)[0])
    assert len(set(sections)) == 1
    assert {brief(seat).snapshot_sha256 for seat in SEATS} == {SHA}


@pytest.mark.parametrize("seat", SEATS)
def test_the_brief_ends_with_the_exact_first_line_its_report_must_carry(seat):
    b = analyst.render(seat, SNAPSHOT, "0x42a9bd235aedd68e9f2881710577105cb46e3d27")
    assert b.header == f"REPORT {seat} 0x42a9bd235aedd68e9f2881710577105cb46e3d27 {SHA}"
    assert b.user.endswith(b.header + "\n")


def test_the_example_in_the_shared_brief_is_the_approved_one():
    approved = (REPO / "planning" / "REPORT-FORMAT.md").read_text()
    nvda = approved.split("CALL NVDA", 1)[1].split("\n\nCALL", 1)[0]
    shared = (analyst.BRIEFS / "analyst.v1.md").read_text()
    indented = "\n".join("    " + line if line else line
                         for line in ("CALL NVDA" + nvda).splitlines())
    assert indented in shared


def test_a_seat_the_config_does_not_define_or_question_is_refused():
    with pytest.raises(KeyError):
        analyst.render("fundamentals-calendar", SNAPSHOT, "0x…")
    vague = json.loads(json.dumps(ANALYSTS))
    vague["analysts"][0]["question"] = ""
    with pytest.raises(ValueError):
        analyst.render("price-trend", SNAPSHOT, "0x…", analysts=vague)
