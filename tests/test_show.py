"""A stored report, printed exactly as the model wrote it.

`agents/show.py` must print the reply and nothing else: no header, no summary,
no reformatting, no truncation. The recorded 2.6 reply is the case that matters.
"""

import hashlib
import json
from pathlib import Path

import pytest

from fund.agents import analyst, runner, show

REPO = Path(__file__).resolve().parents[1]
REPLY_2_6 = (REPO / "tests" / "data" / "2.6-price-integrity.reply.txt").read_text()
SNAPSHOT = REPO / "fixtures" / "snapshots" / "66852293-253315c0e691" / "snapshot.json"


def stored(tmp_path, result, seat="price-integrity"):
    (tmp_path / "results").mkdir(parents=True, exist_ok=True)
    path = tmp_path / "results" / f"{seat}.json"
    path.write_text(json.dumps(result))
    return path


def test_the_recorded_2_6_reply_prints_exactly_as_written(tmp_path, capsys):
    """2.6's result predates per-attempt text: its refused reply is `last_reply_text`."""
    stored(tmp_path, {"status": "failed", "reason": "invalid", "last_reply_text": REPLY_2_6,
                      "attempts": [{"attempt": 1, "refusals": ["header: …"]}]})
    assert show.main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert out == REPLY_2_6 + ("" if REPLY_2_6.endswith("\n") else "\n")
    assert "CALL AMD 0x86923f96303d656e4aa86d9d42d1e57ad2023fdc caution medium" in out


def test_the_last_attempts_reply_is_printed_accepted_or_not(tmp_path, capsys):
    result = {"status": "ok", "report_text": "the parsed body",
              "attempts": [{"reply_text": "first, refused"}, {"reply_text": "second\n  as written\n"}]}
    assert show.main([str(stored(tmp_path, result))]) == 0
    assert capsys.readouterr().out == "second\n  as written\n"


def test_a_cycle_with_several_results_needs_a_seat(tmp_path, capsys):
    stored(tmp_path, {"attempts": [{"reply_text": "a"}]}, seat="price-trend")
    stored(tmp_path, {"attempts": [{"reply_text": "b"}]}, seat="price-integrity")
    with pytest.raises(SystemExit, match="price-integrity, price-trend"):
        show.main([str(tmp_path)])
    assert show.main([str(tmp_path), "--seat", "price-trend"]) == 0
    assert capsys.readouterr().out == "a\n"


def test_a_result_with_no_text_says_so_and_prints_nothing(tmp_path, capsys):
    assert show.main([str(stored(tmp_path, {"status": "failed", "reason": "timeout",
                                            "attempts": [{"reply_text": ""}]}))]) == 1
    captured = capsys.readouterr()
    assert captured.out == "" and "timeout" in captured.err


def test_every_attempt_keeps_its_reply_in_full(tmp_path):
    """The worker keeps each reply whole, past the 20,000 characters it once cut at."""
    long_reply = "not a report\n" * 2000  # 26,000 characters, refused
    replies = iter([long_reply, long_reply])

    def send(url, body, headers, timeout_s):
        return 200, json.dumps({"id": "chatcmpl-x", "choices": [
            {"finish_reason": "stop", "message": {"content": next(replies)}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1}}).encode()

    job = {"seat": "price-trend", "agent": runner.UNASSIGNED_AGENT, "snapshot_path": str(SNAPSHOT),
           "snapshot_sha256": hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest(),
           "model": "claude-sonnet-5", "max_tokens": 12000, "transport_timeout_s": 600,
           "worker_deadline_s": 630, "retry_budget": 1, "gateway_url": "http://unused",
           "pricing": {"input": "2", "output": "10"}, "result_path": str(tmp_path / "r.json")}
    result = analyst.run(job, "bk_fake", send=send)
    assert [a["reply_text"] for a in result["attempts"]] == [long_reply, long_reply]
    assert result["last_reply_text"] == long_reply and show.reply_text(result) == long_reply
