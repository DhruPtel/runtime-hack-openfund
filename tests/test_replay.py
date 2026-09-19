"""Unit 1.9, replay: each committed capture rebuilds its snapshot byte for byte with
every connection refused and no credential set, a changed byte in any source's
answers or clock changes the rebuilt hash, and a missing answer stops the replay."""

from __future__ import annotations

import gzip
import shutil

import pytest

from fund import credentials
from fund.adapters import cache
from fund.run import snapshot as run

CAPTURES = sorted(p for p in run.SNAPSHOTS.iterdir() if (p / cache.MANIFEST).exists())
CAPTURE = run.SNAPSHOTS / "66812461-8afe38a38b03"


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
    assert raw.count(before) == 1 and len(before) == len(after)
    assert sum(a != b for a, b in zip(before, after)) == 1
    (copy / name).write_bytes(gzip.compress(raw.replace(before, after)))
    return run.replay(copy)


@pytest.mark.parametrize("name, before, after", [
    ("chain.jsonl.gz", b"0x1a283ed8c1999", b"0x1a283ed8c1998"),   # the wallet's ETH balance
    ("gecko.jsonl.gz", b"763.8019212075", b"763.8019212076"),     # one GeckoTerminal price
    ("venue.jsonl.gz", b'swapImpactBps\\":1054', b'swapImpactBps\\":1055'),  # one quote's impact
    ("clock.json.gz", b"1789793799259", b"1789793799258"),        # when the first quote came back
], ids=["chain", "gecko", "venue", "clock"])
def test_a_changed_byte_in_any_source_changes_the_rebuilt_hash(tmp_path, name, before, after):
    replayed = changed(tmp_path, name, before, after)
    assert replayed.capture.altered == [name]
    assert replayed.snapshot.sha256 != replayed.expected and not replayed.identical


def test_a_changed_byte_the_snapshot_does_not_carry_still_fails_the_replay(tmp_path):
    # GeckoTerminal's cache-status header is kept in the capture and not in the
    # snapshot, so the hash cannot move; the manifest check names the file instead.
    copy = tmp_path / CAPTURE.name
    shutil.copytree(CAPTURE, copy)
    raw = gzip.decompress((copy / "gecko.jsonl.gz").read_bytes())
    (copy / "gecko.jsonl.gz").write_bytes(gzip.compress(raw.replace(b'"MISS"', b'"MIST"', 1)))
    replayed = run.replay(copy)
    assert replayed.same_snapshot and replayed.capture.altered == ["gecko.jsonl.gz"]
    assert not replayed.identical


def test_a_missing_answer_stops_the_replay_rather_than_reading_as_unreachable(tmp_path):
    copy = tmp_path / CAPTURE.name
    shutil.copytree(CAPTURE, copy)
    lines = gzip.decompress((copy / "venue.jsonl.gz").read_bytes()).splitlines(keepends=True)
    (copy / "venue.jsonl.gz").write_bytes(gzip.compress(b"".join(lines[:-1])))
    with pytest.raises(cache.ReplayMiss, match="does not hold"):
        run.replay(copy)


def test_a_capture_carries_its_provenance_and_names_the_rpc_only_by_name():
    capture = cache.Capture(CAPTURE)
    manifest = capture.manifest
    block = manifest["block"]
    assert (block["number"], block["time"]) == (66812461, "2026-09-19T04:54:53Z")
    assert manifest["captured"]["commit"] and "started_at" in manifest["captured"]
    assert manifest["endpoints"]["RPC_4663_MAINNET"] == "a declared credential: kept by name only"
    assert set(manifest["redaction"]["credentials_checked"]) == {
        f"[REDACTED:{c.name}]" for c in credentials.CREDENTIALS}  # all six were set, and checked
    chain = capture.exchanges("chain")
    assert {(r["endpoint"], r["path"]) for r in chain} == {("RPC_4663_MAINNET", "")}
    pinned = [r for r in chain if r["block"] is not None]
    assert len(pinned) == 187 and {r["block"] for r in pinned} == {block["hash"]}
    for source in ("chain", "gecko", "venue"):
        for r in capture.exchanges(source):
            assert r["sent_at"] <= r["received_at"] and r["status"] == 200
            assert "set-cookie" not in {k.lower() for k in r["headers"]}
