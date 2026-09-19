"""Unit 3.7: the signature. H: this is what makes a decision authoritative.

Every key here is generated for the test. The real SIGNING_KEY is never read.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

from fund.treasurer import sign

SRC = Path(__file__).resolve().parents[1] / "src"
RECORD = b'{"decision":"constructed for the test","schema":"openfund.decision/1"}'


def seed() -> str:
    return Ed25519PrivateKey.generate().private_bytes(
        Encoding.Raw, PrivateFormat.Raw, NoEncryption()).hex()


KEY = sign.load_key(seed())
TRUSTED = sign.public_hex(KEY)


def test_a_signed_record_authorizes():
    envelope = sign.sign(RECORD, KEY)
    check = sign.authorizes(envelope, RECORD, TRUSTED)
    assert check.value is True and envelope["decision_id"] in json.dumps(envelope)


def test_an_unsigned_record_never_authorizes():
    envelope = sign.unsigned(RECORD, "no key")
    check = sign.authorizes(envelope, RECORD, TRUSTED)
    assert check.value is False and check.reason == "unsigned: signed=false never authorizes"
    forged = {**sign.sign(RECORD, KEY), "signed": False}  # a good signature, marked unsigned
    assert sign.authorizes(forged, RECORD, TRUSTED).value is False


def test_a_changed_byte_another_key_or_a_bad_signature_is_refused():
    envelope = sign.sign(RECORD, KEY)
    altered = RECORD.replace(b"constructed", b"Constructed")
    assert "not the ones" in sign.authorizes(envelope, altered, TRUSTED).reason
    stranger = sign.load_key(seed())
    theirs = sign.sign(RECORD, stranger)
    assert "not the trusted one" in sign.authorizes(theirs, RECORD, TRUSTED).reason
    swapped = {**theirs, "public_key": TRUSTED}  # their signature, claiming our key
    assert "does not verify" in sign.authorizes(swapped, RECORD, TRUSTED).reason
    rehashed = {**envelope, "decision_id": __import__("hashlib").sha256(altered).hexdigest()}
    assert "does not verify" in sign.authorizes(rehashed, altered, TRUSTED).reason


def test_a_malformed_key_is_refused_without_repeating_it():
    for bad in ("", "abc", "g" * 64, "a" * 63):
        with pytest.raises(sign.SigningKeyError) as raised:
            sign.load_key(bad)
        assert bad not in str(raised.value) or bad == ""


def test_the_signing_process_loads_its_own_key_and_nothing_leaks(tmp_path):
    """What the decision command runs: the treasurer's own process, reading the key
    from an env file under the treasurer role. The caller never holds it."""
    secret = seed()
    env_file = tmp_path / "treasurer.env"
    env_file.write_text(f"SIGNING_KEY={secret}\n")
    record = tmp_path / "record.json"
    record.write_bytes(RECORD)
    out = tmp_path / "envelope.json"
    clean = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(SRC)}
    done = subprocess.run([sys.executable, "-m", "fund.treasurer.sign", "--sign", str(record),
                           "--out", str(out), "--env-file", str(env_file)],
                          env=clean, capture_output=True, text=True, timeout=60)
    assert done.returncode == 0, done.stderr
    envelope = json.loads(out.read_text())
    assert envelope["signed"] is True and envelope["public_key"] == sign.public_hex(
        sign.load_key(secret))
    assert secret not in done.stdout + done.stderr + out.read_text()
    verified = subprocess.run([sys.executable, "-m", "fund.treasurer.sign", "--verify",
                               str(record), str(out), "--public-key", envelope["public_key"]],
                              env=clean, capture_output=True, text=True, timeout=60)
    assert verified.returncode == 0 and json.loads(verified.stdout)["authorizes"] is True


def test_with_no_key_the_process_writes_an_unsigned_envelope_that_does_not_authorize(tmp_path):
    record = tmp_path / "record.json"
    record.write_bytes(RECORD)
    out = tmp_path / "envelope.json"
    clean = {"PATH": os.environ.get("PATH", ""), "PYTHONPATH": str(SRC)}
    subprocess.run([sys.executable, "-m", "fund.treasurer.sign", "--sign", str(record), "--out",
                    str(out), "--env-file", str(tmp_path / "absent.env")], env=clean,
                   check=True, capture_output=True, timeout=60)
    envelope = json.loads(out.read_text())
    assert envelope["signed"] is False and envelope["why"] == "SIGNING_KEY is not set"
    assert sign.authorizes(envelope, RECORD, TRUSTED).value is False
