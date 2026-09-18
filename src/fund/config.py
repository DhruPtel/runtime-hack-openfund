"""Configuration loading: credentials from the environment, settings from JSON.

Two rules shape this module.

**Role scoping.** ``load()`` takes a ``Role`` and returns only the credentials
that role is permitted to hold. An analyst process asking for ``SIGNING_KEY``
raises rather than returning it, on a development laptop as much as in
deployment. This is planning/PLAN.md section 2 invariant 1 expressed where code
can trip over it; unit 4.12 proves the stronger environment-level version.

**No thresholds here.** planning/CODEBASE.md section 8 lists "a threshold
appearing as a literal anywhere outside config/" as a sign we got it wrong. It
JSON files and hands back their contents. It does not interpret them, supply
defaults, or know what any key means.

Environment precedence: a real environment variable always beats the ``.env``
file, so a deployed process cannot be silently overridden by a stray file.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import redaction
from .credentials import CREDENTIALS, Credential, Role, by_name, for_role

#: Repository root, found relative to this file: src/fund/config.py -> repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = REPO_ROOT / "config"
ENV_FILE = REPO_ROOT / ".env"


class MissingCredentialError(RuntimeError):
    """A credential required by this role is absent from the environment."""


class TransactingCredentialLeakError(RuntimeError):
    """A role without spend authority is holding a transacting key's value.

    Raised when a credential this role loads has the same value as a credential
    that can transact and that this role may not hold. Since all Bankr keys come
    from one account, per-key toggles are the only boundary, and two keys sharing
    a value erases it: the analyst process would hold the fund's spend authority
    under a different name. Refusing at load is the point where that is still
    cheap to notice.
    """


class CredentialNotPermittedError(RuntimeError):
    """This role is not allowed to hold this credential.

    Raised rather than returning ``None``, because a silent absence is how an
    analyst path ends up reaching for a signing key and getting a confusing
    failure three frames later.
    """


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a ``.env`` file. No dependency, no interpolation, no export syntax.

    Blank lines and ``#`` comments are ignored. Values may be single- or
    double-quoted; quotes are stripped. A line without ``=`` is ignored rather
    than raising, so a stray note in the file cannot stop the process.
    """
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if key:
            values[key] = value
    return values


def load_environment(env_file: Path | None = None) -> None:
    """Merge ``.env`` into ``os.environ`` without overriding what is already set."""
    path = ENV_FILE if env_file is None else env_file
    for key, value in parse_env_file(path).items():
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Config:
    """Everything one process is allowed to know.

    ``credentials`` holds only the values this role may hold. Its ``repr`` is
    overridden so that printing a Config -- in a traceback, a debugger, or a log
    line -- cannot reveal a secret.
    """

    role: Role
    credentials: dict[str, str]

    def __repr__(self) -> str:
        held = ", ".join(sorted(self.credentials))
        return f"Config(role={self.role.value!r}, credentials=[{held}])"

    __str__ = __repr__

    def secret(self, name: str) -> str:
        """Return one credential value, or explain precisely why it is unavailable."""
        credential = by_name(name)
        if self.role not in credential.used_by:
            permitted = ", ".join(sorted(r.value for r in credential.used_by))
            raise CredentialNotPermittedError(
                f"{name} is not available to the {self.role.value} role "
                f"(permitted: {permitted}). See planning/PLAN.md section 6."
            )
        if name not in self.credentials:
            raise MissingCredentialError(f"{name} is not set in the environment")
        return self.credentials[name]

    def has(self, name: str) -> bool:
        return name in self.credentials


def load(
    role: Role,
    *,
    require: bool = True,
    env_file: Path | None = None,
    install_redaction: bool = True,
) -> Config:
    """Load the credentials this role is permitted to hold.

    ``require=True`` fails fast when one is missing, which is the behaviour every
    entrypoint wants: a cycle that starts without its signing key should stop at
    startup, not at the moment it tries to sign. ``require=False`` exists for
    tooling that wants to inspect what is present without demanding it.

    Redaction is installed by default and derives its denylist from the whole
    credential table, not just this role's subset. See ``redaction`` for why.
    """
    load_environment(env_file)

    if install_redaction:
        redaction.install()

    permitted: tuple[Credential, ...] = for_role(role)
    held: dict[str, str] = {}
    missing: list[str] = []

    for credential in permitted:
        value = os.environ.get(credential.name, "")
        if value:
            held[credential.name] = value
        else:
            missing.append(credential.name)

    if require and missing:
        raise MissingCredentialError(
            f"{role.value} role is missing: {', '.join(missing)}. "
            f"Copy .env.example to .env and fill them in."
        )

    _refuse_leaked_spend_authority(role, held)

    return Config(role=role, credentials=held)


def _refuse_leaked_spend_authority(role: Role, held: Mapping[str, str]) -> None:
    """planning/PLAN.md section 2 invariant 1, checked against actual values.

    ``can_transact`` says which credential *should* be able to spend; this says
    whether one of them is in this role's hands under another name. The check is
    only possible where the risk exists -- a single host whose environment holds
    both -- and is silently satisfied in the deployed split, where the analyst
    process never sees the execution key at all.
    """
    for spender in CREDENTIALS:
        if not spender.can_transact or role in spender.used_by:
            continue
        spend_value = os.environ.get(spender.name)
        if not spend_value:
            continue
        for name, value in held.items():
            if value == spend_value:
                raise TransactingCredentialLeakError(
                    f"{name} has the same value as {spender.name}, which can "
                    f"transact and is not available to the {role.value} role. "
                    f"Issue a separate key with Read Only ON for {name}. "
                    f"See planning/PLAN.md section 13."
                )


def sharing_a_value(environ: Mapping[str, str] | None = None) -> list[list[str]]:
    """Groups of declared credentials that hold the same value.

    Two credentials with one value is almost always a paste error, and when one
    of them can transact it collapses the analyst/treasurer boundary entirely.
    Values are grouped, never returned: the caller learns *which names* collide,
    not what they are.
    """
    env = os.environ if environ is None else environ
    groups: dict[str, list[str]] = {}
    for credential in CREDENTIALS:
        value = env.get(credential.name)
        if value:
            groups.setdefault(value, []).append(credential.name)
    return sorted(
        (sorted(names) for names in groups.values() if len(names) > 1),
        key=lambda names: names[0],
    )


def audit(env_file: Path | None = None) -> dict[str, Any]:
    """Report which declared credentials are present, without revealing any value.

    Used by ``make check-env`` and, later, by the unit 4.12 isolation test.
    """
    load_environment(env_file)
    return {
        "present": sorted(c.name for c in CREDENTIALS if os.environ.get(c.name)),
        "absent": sorted(c.name for c in CREDENTIALS if not os.environ.get(c.name)),
        "sharing_a_value": sharing_a_value(),
        "too_short_to_mask_cleanly": list(redaction.short_credentials()),
        "redacted_value_count": len(redaction.Redactor()),
    }


def load_json(name: str, config_dir: Path | None = None) -> Any:
    """Load one file from ``config/``. Contents are returned uninterpreted."""
    directory = CONFIG_DIR if config_dir is None else config_dir
    path = directory / name
    if not path.exists():
        raise FileNotFoundError(f"no config file at {path}")
    return json.loads(path.read_text(encoding="utf-8"))
