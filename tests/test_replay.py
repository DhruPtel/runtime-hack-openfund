"""Unit 1.9, replay: each committed capture rebuilds its snapshot byte for byte with
every connection refused and no credential set, the snapshot cites the capture's
answers by hash, so any changed byte moves it, and a missing answer stops the replay."""

from __future__ import annotations

import gzip
import hashlib
import json
import shutil

import pytest

from fund import credentials
from fund.adapters import cache
from fund.run import snapshot as run

CAPTURES = sorted(p for p in run.SNAPSHOTS.iterdir() if (p / cache.MANIFEST).exists())
CAPTURE = run.SNAPSHOTS / "66852293-253315c0e691"


@pytest.fixture(autouse=True)
def no_credentials(monkeypatch):
    """A replay needs no key and no RPC URL: none is set while these run."""
    for credential in credentials.CREDENTIALS:
        monkeypatch.delenv(credential.name, raising=False)


def test_each_committed_capture_replays_byte_for_byte_with_every_connection_refused():
    assert CAPTURE in CAPTURES
    for directory in CAPTURES:
        replayed = run.replay(directory)  # inside cache.no_network(): any socket raises
        assert replayed.capture.altered == [], directory.name
        assert replayed.unused == {s: (0, 0) for s in ("chain", "gecko", "venue", "run")}
        assert replayed.snapshot.body == replayed.capture.snapshot_body
        assert replayed.snapshot.sha256 == replayed.expected and replayed.identical


def changed(tmp_path, name: str, before: bytes, after: bytes) -> run.Replayed:
    """Replay a copy of the capture with one byte of one file changed."""
    copy = tmp_path / CAPTURE.name
    shutil.copytree(CAPTURE, copy)
    raw = gzip.decompress((copy / name).read_bytes())
    assert raw.count(before) >= 1 and len(before) == len(after)
    assert sum(a != b for a, b in zip(before, after)) == 1
    (copy / name).write_bytes(gzip.compress(raw.replace(before, after, 1)))
    return run.replay(copy)


@pytest.mark.parametrize("name, before, after", [
    ("chain.jsonl.gz", b"0x1a283ed8c1999", b"0x1a283ed8c1998"),   # the wallet's ETH balance
    ("gecko.jsonl.gz", b"763.6608160369", b"763.6608160368"),     # one GeckoTerminal price
    ("venue.jsonl.gz", b'swapImpactBps\\":947', b'swapImpactBps\\":948'),  # one quote's impact
    ("clock.json.gz", b"1789797823760", b"1789797823761"),        # when the first quote came back
    ("gecko.jsonl.gz", b'"MISS"', b'"MIST"'),                     # a header the snapshot never reads
], ids=["chain", "gecko", "venue", "clock", "unread-header"])
def test_a_changed_byte_in_any_source_changes_the_rebuilt_hash(tmp_path, name, before, after):
    replayed = changed(tmp_path, name, before, after)
    assert replayed.capture.altered == [name]
    assert replayed.snapshot.sha256 != replayed.expected and not replayed.identical


def test_the_snapshot_cites_the_answers_a_buyer_can_hash_for_themselves():
    """What a buyer holding a decision record does: hash each raw-answer file on
    disk, then the listing, and find both in the snapshot the record cites."""
    cited = json.loads((CAPTURE / "snapshot.json").read_bytes())["inputs"]["capture"]
    files = {name: hashlib.sha256(gzip.decompress((CAPTURE / name).read_bytes())).hexdigest()
             for name in cited["files"]}
    assert set(files) == {"chain.jsonl.gz", "clock.json.gz", "gecko.jsonl.gz", "venue.jsonl.gz"}
    assert files == cited["files"]
    listing = json.dumps(dict(sorted(files.items())), separators=(",", ":")).encode()
    assert hashlib.sha256(listing).hexdigest() == cited["sha256"]


def test_a_missing_answer_stops_the_replay_rather_than_reading_as_unreachable(tmp_path):
    copy = tmp_path / CAPTURE.name
    shutil.copytree(CAPTURE, copy)
    lines = gzip.decompress((copy / "venue.jsonl.gz").read_bytes()).splitlines(keepends=True)
    (copy / "venue.jsonl.gz").write_bytes(gzip.compress(b"".join(lines[:-1])))
    with pytest.raises(cache.ReplayMiss, match="does not hold"):
        run.replay(copy)


def test_an_answer_the_replay_never_asked_for_fails_it(tmp_path):
    # A replay that asks for less than the live build did has diverged from it,
    # even if the snapshot happens to come out the same.
    copy = tmp_path / CAPTURE.name
    shutil.copytree(CAPTURE, copy)
    lines = gzip.decompress((copy / "venue.jsonl.gz").read_bytes()).splitlines(keepends=True)
    (copy / "venue.jsonl.gz").write_bytes(gzip.compress(b"".join(lines + lines[-1:])))
    replayed = run.replay(copy)
    assert replayed.unused["venue"] == (1, 0) and not replayed.all_used and not replayed.identical


def test_a_replay_reads_the_captures_config_not_todays(tmp_path, monkeypatch):
    # Months later config/ will have moved on. Here today's divergence limit is
    # halved; the replay must still build with the thresholds the capture was built with.
    today = tmp_path / "config"
    shutil.copytree(run.CONFIG, today)
    thresholds = json.loads((today / "thresholds.json").read_text())
    thresholds["divergence_max_bps"] = 50
    (today / "thresholds.json").write_text(json.dumps(thresholds))
    monkeypatch.setattr(run, "CONFIG", today)
    assert run.replay(CAPTURE).identical


def test_a_capture_carries_its_provenance_and_names_the_rpc_only_by_name():
    capture = cache.Capture(CAPTURE)
    manifest = capture.manifest
    block = manifest["block"]
    assert (block["number"], block["time"]) == (66852293, "2026-09-19T06:01:49Z")
    assert manifest["captured"]["commit"] and "started_at" in manifest["captured"]
    assert manifest["endpoints"]["RPC_4663_MAINNET"] == "a declared credential: kept by name only"
    assert set(manifest["redaction"]["credentials_checked"]) == {
        f"[REDACTED:{c.name}]" for c in credentials.CREDENTIALS}  # all six were set, and checked
    chain = capture.exchanges("chain")
    assert {(r["endpoint"], r["path"]) for r in chain} == {("RPC_4663_MAINNET", "")}
    pinned = [r for r in chain if r["block"] is not None]
    assert len(pinned) == 189 and {r["block"] for r in pinned} == {block["hash"]}
    for source in ("chain", "gecko", "venue"):
        exchanges = capture.exchanges(source)
        for r, after in zip(exchanges, exchanges[1:] + [None]):
            assert r["sent_at"] <= r["received_at"]
            assert "set-cookie" not in {k.lower() for k in r["headers"]}
            if r["status"] != 200:  # the RPC's one 429 here, retried; a replay serves both
                assert r["status"] == 429 and after["request"] == r["request"]
                assert after["status"] == 200
