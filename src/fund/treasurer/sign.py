"""ed25519. The only signer in the system (unit 3.7).

The decision record is signed by the treasurer's key, `SIGNING_KEY`, a 32-byte
ed25519 seed written as 64 hex characters. The signature covers the record's
canonical bytes exactly, and the decision id is their sha256. A buyer who holds
the published public key can check both.

**Only the treasurer role may load the key,** through `config.load`
(`credentials.py`). Nothing outside `treasurer/` imports this module
(`tests/test_boundaries.py`). A caller elsewhere, such as the decision command,
runs it as its own process instead: `python -m fund.treasurer.sign --sign`. That
process loads the key itself, so the key never enters the caller. Every agent
process is built from an empty environment, so it never sees the key either. At
4.12 the whole treasurer becomes its own process.

**`signed=false` never authorizes** (PLAN §8 3.7). `authorizes` passes a record
only when all of these hold:
- the envelope says it is signed;
- the record's bytes hash to the envelope's decision id;
- the envelope names the trusted public key;
- the signature verifies against those bytes.
Anything else is refused, and the reason is named.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from fund import config
from fund.core.types import Check
from fund.credentials import Role

ALGORITHM = "ed25519"
_SEED = re.compile(r"^[0-9a-fA-F]{64}$")


class SigningKeyError(Exception):
    """The signing key is absent or is not a 32-byte ed25519 seed. The message
    never contains the key."""


def load_key(seed_hex: str) -> Ed25519PrivateKey:
    if not seed_hex or not _SEED.match(seed_hex):
        raise SigningKeyError("SIGNING_KEY must be 64 hex characters: a 32-byte ed25519 seed")
    return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed_hex))


def public_hex(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()


def sign(record: bytes, key: Ed25519PrivateKey) -> dict[str, Any]:
    """The envelope for one record's exact bytes."""
    return {"decision_id": hashlib.sha256(record).hexdigest(), "signed": True,
            "algorithm": ALGORITHM, "public_key": public_hex(key),
            "signature": key.sign(record).hex()}


def unsigned(record: bytes, why: str) -> dict[str, Any]:
    """The envelope for a record that was not signed. It never authorizes."""
    return {"decision_id": hashlib.sha256(record).hexdigest(), "signed": False,
            "algorithm": None, "public_key": None, "signature": None, "why": why}


def authorizes(envelope: Mapping[str, Any], record: bytes, trusted_public_key: str) -> Check:
    """True only for these exact bytes, signed by the trusted key."""
    if envelope.get("signed") is not True:
        return Check(False, "unsigned: signed=false never authorizes")
    if hashlib.sha256(record).hexdigest() != envelope.get("decision_id"):
        return Check(False, "the record's bytes are not the ones this envelope names")
    if envelope.get("algorithm") != ALGORITHM or envelope.get("public_key") != trusted_public_key:
        return Check(False, "signed by a key that is not the trusted one")
    try:
        public = Ed25519PublicKey.from_public_bytes(bytes.fromhex(trusted_public_key))
        public.verify(bytes.fromhex(envelope.get("signature") or ""), record)
    except (InvalidSignature, ValueError):
        return Check(False, "the signature does not verify against the record's bytes")
    return Check(True, f"signed by {trusted_public_key[:16]}… over decision "
                       f"{envelope['decision_id'][:16]}…")


def treasurer_key(env_file: Path | None = None) -> Ed25519PrivateKey:
    """The signing key, loaded under the treasurer role and no other."""
    held = config.load(Role.TREASURER, require=False, env_file=env_file)
    if not held.has("SIGNING_KEY"):
        raise SigningKeyError("SIGNING_KEY is not set")
    return load_key(held.secret("SIGNING_KEY"))


def main(argv: list[str] | None = None) -> int:
    """The treasurer's signing process:

        python -m fund.treasurer.sign --sign RECORD --out ENVELOPE [--env-file PATH]
        python -m fund.treasurer.sign --verify RECORD ENVELOPE --public-key HEX

    `--sign` writes an unsigned envelope, with the reason, when there is no usable
    key, so a record is never mistaken for a signed one."""
    import argparse

    parser = argparse.ArgumentParser(prog="fund.treasurer.sign")
    parser.add_argument("--sign", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--verify", nargs=2, type=Path, metavar=("RECORD", "ENVELOPE"))
    parser.add_argument("--public-key")
    args = parser.parse_args(argv)
    if args.verify:
        record, envelope = args.verify[0].read_bytes(), json.loads(args.verify[1].read_text())
        check = authorizes(envelope, record, args.public_key or "")
        print(json.dumps({"authorizes": check.value, "reason": check.reason}))
        return 0 if check.value else 1
    record = args.sign.read_bytes()
    try:
        envelope = sign(record, treasurer_key(args.env_file))
    except SigningKeyError as error:
        envelope = unsigned(record, str(error))
    args.out.write_text(json.dumps(envelope, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"signed": envelope["signed"], "decision_id": envelope["decision_id"],
                      "public_key": envelope["public_key"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
