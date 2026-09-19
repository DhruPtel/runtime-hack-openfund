"""The fund's published keys: the public half, and nothing secret (unit 4.2).

`config/keys.json` names the key a decision record must verify against, and that is
the only key a record is ever checked with (S13). Reading it needs no secret, so this
sits apart from `treasurer/sign.py`, which loads the private half: nothing outside
`treasurer/` may import the signer (CODEBASE §3), and the paper cycle needs the
published key.
"""

from __future__ import annotations

from pathlib import Path

from fund import config

ALGORITHM = "ed25519"


def published_key(config_dir: Path | None = None) -> str | None:
    """The fund's published decision-signing key, from `keys.json` in `config_dir`
    (`config/` without one). None if none is published: then nothing authorizes."""
    try:
        keys = config.load_json("keys.json", config_dir)
    except FileNotFoundError:
        return None
    signing = keys.get("decision_signing") or {}
    if signing.get("algorithm") != ALGORITHM or not isinstance(signing.get("public_key"), str):
        return None
    return signing["public_key"]
