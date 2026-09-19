"""Unit 2.7: every report kept once, under the hash of its bytes, and handed back
exactly as written or not at all."""

import hashlib
from pathlib import Path

import pytest

from fund.store import reports

REPO = Path(__file__).resolve().parents[1]
REPLY_2_6 = (REPO / "tests" / "data" / "2.6-price-integrity.reply.txt").read_text()


def record(text=REPLY_2_6, **extra):
    return {"seat": "price-integrity", "agent": "0x…", "text": text,
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "accepted": False,
            "refusals": ["header: …"], "cost": {"usd": "0.273156", "is_estimate": True},
            **extra}


def test_a_report_is_stored_under_the_hash_of_its_bytes_and_read_back_whole(tmp_path):
    store = reports.ReportStore(tmp_path)
    report_id = store.put(record())
    assert report_id == hashlib.sha256((tmp_path / f"{report_id}.json").read_bytes()).hexdigest()
    assert store.text(report_id) == REPLY_2_6  # byte for byte what the model wrote
    back = store.get(report_id)
    assert back["schema"] == reports.SCHEMA and back["cost"]["usd"] == "0.273156"
    assert report_id in store


def test_the_same_report_is_one_file_and_a_different_one_is_another(tmp_path):
    store = reports.ReportStore(tmp_path)
    first, again = store.put(record()), store.put(record())
    other = store.put(record(text=REPLY_2_6 + " "))
    assert first == again and other != first
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted([f"{first}.json", f"{other}.json"])


def test_a_changed_byte_on_disk_is_never_served(tmp_path):
    store = reports.ReportStore(tmp_path)
    report_id = store.put(record())
    path = tmp_path / f"{report_id}.json"
    path.write_bytes(path.read_bytes().replace(b"caution medium", b"caution high", 1))
    with pytest.raises(reports.TamperedError):
        store.get(report_id)


def test_nothing_stored_is_rewritten(tmp_path):
    store = reports.ReportStore(tmp_path)
    report_id = hashlib.sha256(reports.encode(record())).hexdigest()
    (tmp_path / f"{report_id}.json").write_bytes(b"something else")
    with pytest.raises(reports.ImmutableError):
        store.put(record())
    assert (tmp_path / f"{report_id}.json").read_bytes() == b"something else"


def test_an_id_is_a_hash_or_nothing_and_an_unknown_one_says_so(tmp_path):
    store = reports.ReportStore(tmp_path)
    for bad in ("../../.env", "ABC", "0" * 63, None):
        with pytest.raises(ValueError):
            store.get(bad)
    with pytest.raises(reports.UnknownReport):
        store.get("0" * 64)


def test_money_is_text_never_a_float(tmp_path):
    with pytest.raises(TypeError):
        reports.ReportStore(tmp_path).put(record(cost={"usd": 0.273156}))
    assert list(tmp_path.iterdir()) == []
