"""The credential table. The single source of truth for every secret.

Mirrors planning/PLAN.md section 6. This module is deliberately the only
place in the repository where a credential name is written down:

  - ``config.py`` loads values from it,
  - ``redaction.py`` derives its denylist from it,
  - the deployed-isolation test (unit 4.12) asserts against it.

Adding a row here is therefore sufficient to make a new credential both loadable
and unloggable. There is no second list to keep in step, which is the property
planning/PHASE-0-1.md unit 0.1 asks for: adding a credential cannot create an
unredacted path.

Roles exist because planning/PLAN.md section 2 invariant 1 is an authority
boundary, not a style rule. The analyst role cannot load execution or signing
secrets even on a single-host development machine, so code that reaches for them
fails immediately rather than at the point where it would have spent money.

The three Bankr keys are issued from **one account** (see planning/PLAN.md
section 13), so account-level separation does not exist and the boundary rests
entirely on per-key toggles. The rule that keeps invariant 1 true is therefore:
**no key held by the analyst role may be able to transact.** `BANKR_KEY_READ`
and `BANKR_LLM_KEY` carry Read Only ON; only `BANKR_KEY_EXEC` has the Wallet
API with Read Only OFF, and only the treasurer role may load it. Probe 0.2
verifies these toggles against the live surfaces rather than trusting the
console.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    """A process identity. Determines which credentials may be loaded.

    Only two exist, and that is the point: one of them can spend.
    """

    #: Snapshot building, analysts, aggregation, planning, risk inference.
    #: Read-only. Never receives execution or signing secrets.
    ANALYST = "analyst"

    #: The sole spend authority (planning/PLAN.md section 2 invariant 1). Runs
    #: as its own process with its own credentials from unit 4.12 onward.
    TREASURER = "treasurer"


@dataclass(frozen=True)
class Credential:
    """One row of planning/PLAN.md section 6."""

    #: Environment variable name. Also the label used in redaction masks.
    name: str

    #: Roles permitted to load this value. A role absent from this set cannot
    #: read the credential through ``config.load()`` at all.
    used_by: frozenset[Role]

    #: What it is for, in the words of planning/PLAN.md section 6.
    purpose: str

    #: The access scope the credential is expected to carry on the provider side.
    #: Probe 0.2 verifies these against reality; until then they are documented,
    #: not measured.
    scope: str

    #: False for values that are not themselves secret but are still masked,
    #: because the value may embed one (a provider RPC URL with an inline key).
    secret: bool = True

    #: True if this credential can move funds. Since all three Bankr keys come
    #: from one account, per-key toggles are the only thing separating spend
    #: authority from read access, so the distinction is recorded here and
    #: asserted in tests rather than left to the prose in ``scope``. A
    #: transacting credential may only ever belong to the treasurer role.
    can_transact: bool = False


#: The table. Ordered as planning/PLAN.md section 6 orders it.
CREDENTIALS: tuple[Credential, ...] = (
    Credential(
        name="BANKR_KEY_READ",
        used_by=frozenset({Role.ANALYST}),
        purpose="quotes and market data for the snapshot and analyst path",
        scope="Read Only ON, Agent API off. Cannot transact.",
    ),
    Credential(
        name="BANKR_KEY_EXEC",
        used_by=frozenset({Role.TREASURER}),
        purpose="the treasurer's swaps",
        scope=(
            "Wallet API ON, Read Only OFF, Agent API off, IP allowlist, low "
            "platform caps. The only key in the system that can transact."
        ),
        can_transact=True,
    ),
    Credential(
        name="BANKR_LLM_KEY",
        used_by=frozenset({Role.ANALYST}),
        purpose="analyst and risk inference via the LLM gateway",
        scope=(
            "Read Only ON, LLM Gateway ON. Not gateway-only: measured in probe "
            "0.2 reading the Wallet API. Scoping is by capability toggle, not "
            "by surface. Either auth header works; we send X-API-Key. Cannot "
            "transact: it is held by the analyst process."
        ),
    ),
    Credential(
        name="RPC_4663_MAINNET",
        used_by=frozenset({Role.ANALYST, Role.TREASURER}),
        purpose=(
            "block-pinned chain reads on 4663 mainnet; the treasurer also reads "
            "the named execution wallet's balances here rather than trusting "
            "another account's portfolio (planning/PLAN.md section 6)"
        ),
        scope="request timeout, fail loudly, no archive reads assumed",
        # Not a secret in itself on the public endpoint, but a paid provider URL
        # carries an inline key. Masked either way; see LESSONS 2026-09-17.
        secret=False,
    ),
    Credential(
        name="RPC_4663_TESTNET",
        used_by=frozenset({Role.ANALYST, Role.TREASURER}),
        purpose=(
            "chain 46630, for probes and drills that should not touch mainnet "
            "state. Never the source of a published mark or a booked fill."
        ),
        scope="request timeout, fail loudly, no archive reads assumed",
        secret=False,
    ),
    Credential(
        name="SIGNING_KEY",
        used_by=frozenset({Role.TREASURER}),
        purpose="ed25519 private key for the decision-record envelope",
        scope="never leaves the treasurer process; public key is published",
    ),
)


def by_name(name: str) -> Credential:
    """Look up one row. Raises ``KeyError`` for an undeclared name."""
    for credential in CREDENTIALS:
        if credential.name == name:
            return credential
    raise KeyError(f"{name} is not a declared credential")


def names() -> tuple[str, ...]:
    """Every declared credential name."""
    return tuple(credential.name for credential in CREDENTIALS)


def for_role(role: Role) -> tuple[Credential, ...]:
    """The credentials a given process identity is permitted to load."""
    return tuple(c for c in CREDENTIALS if role in c.used_by)


def transacting() -> tuple[Credential, ...]:
    """Every credential that can move funds. Should only ever be treasurer-held."""
    return tuple(c for c in CREDENTIALS if c.can_transact)
