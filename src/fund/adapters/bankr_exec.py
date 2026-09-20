"""POST `/wallet/swap`: the only path in the repository that can spend (unit 5.1).

Nothing outside `treasurer/` may import this module, and nothing under `agents/` or
`core/` may reach it at all (CODEBASE §3, `tests/test_boundaries.py`). It holds no
key: the caller passes the treasurer's secret, and only the treasurer role may load
one (`credentials.py`).

**A 200 is not a fill.** Bankr answers 200 with `success: false` for a swap that
mined and reverted, and charges gas for it (F0.10.3). Even `success: true` is a claim
about a transaction, not evidence that anything moved: what was booked is read from
the chain by `treasurer/reconcile.py` (PLAN §2 invariant 9), and settlement is
asynchronous to this reply — probe 0.10's balance had not moved when it returned.

**One send.** This module never retries. A second send under a new key could broadcast
twice; the same key replayed returns the original result and does not broadcast again
(F0.10.1), and that is the only safe repeat. It belongs to whoever is resolving an
unknown outcome, not here.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from fund.adapters import bankr_quote, http
from fund.core.types import Amount, AssetId, Instant
from fund.credentials import Role, by_name

EXECUTE_CONFIG = Path(__file__).resolve().parents[3] / "config" / "execute.json"


@dataclass(frozen=True)
class Settings:
    base_url: str
    path: str
    chain: str
    credential: str
    auth_header: str
    timeout_s: float
    user_agent: str

    @classmethod
    def load(cls, path: Path = EXECUTE_CONFIG) -> Settings:
        c = json.loads(path.read_text())
        credential = by_name(c["credential"])
        if Role.TREASURER not in credential.used_by:
            raise ValueError(f"{credential.name} is not the treasurer's, and only the treasurer "
                             "may send a swap")
        return cls(base_url=c["base_url"], path=c["path"], chain=c["chain"],
                   credential=credential.name, auth_header=c["auth_header"],
                   timeout_s=c["request_timeout_seconds"], user_agent=c["user_agent"])


def _human(amount: Amount) -> str:
    """A raw amount as the venue's human text: `0.00003`, never a float."""
    whole, part = divmod(amount.raw, 10 ** amount.decimals)
    return f"{whole}.{part:0{amount.decimals}d}".rstrip("0").rstrip(".")


@dataclass(frozen=True)
class SwapRequest:
    """One swap: sell this amount of one asset for another, under this key, and take
    no less than `min_buy` for it.

    **The body is the one probe 0.10 measured** (`probes/out/idempotency.json`): the
    two chains and tokens, the human amount, `minBuyAmount`, `quoteId` and
    `idempotencyKey`. `minBuyAmount` is the floor the *order* was authorized with, not
    a slippage percentage: the venue enforces it, so a swap that cannot fill above what
    was authorized reverts instead of filling badly. A revert costs gas and buys
    nothing, which is the trade this fund prefers (PLAN §4)."""

    sell: Amount
    buy: AssetId
    idempotency_key: str
    min_buy: Amount
    quote_id: str | None = None

    def body(self, settings: Settings) -> dict[str, Any]:
        if self.min_buy.asset != self.buy:
            raise ValueError("the floor is in the asset being bought")
        return {"fromChain": settings.chain, "fromToken": self.sell.asset.address,
                "toChain": settings.chain, "toToken": self.buy.address,
                "amount": _human(self.sell), "minBuyAmount": _human(self.min_buy),
                "quoteId": self.quote_id, "idempotencyKey": self.idempotency_key}


@dataclass(frozen=True)
class SwapReply:
    """What the venue said. Not what happened: that is the chain's to say."""

    status: int
    success: bool | None          # the body's own `success`, when it has one
    tx_hash: str | None
    sent_at: Instant
    body: Mapping[str, Any]
    detail: str

    @property
    def claims_a_transaction(self) -> bool:
        """A 200 that says it succeeded and names a transaction. Still not a fill."""
        return self.status == 200 and self.success is True and bool(self.tx_hash)

    @property
    def reverted(self) -> bool:
        """200 with `success: false`: it mined, it reverted, and gas was charged."""
        return self.status == 200 and self.success is False


def submit(request: SwapRequest, secret: str, *, settings: Settings | None = None,
           transport=None, clock=None) -> SwapReply:
    """Send one swap. Never retried, never looped, and never read as a fill."""
    settings = settings or Settings.load()
    if request.sell.raw <= 0:
        raise ValueError("a swap sells a positive amount")
    if request.sell.asset == request.buy:
        raise ValueError("a swap sells one asset for another")
    if not request.idempotency_key:
        raise ValueError("a swap carries the order's idempotency key")
    if request.min_buy.raw <= 0:
        raise ValueError("a swap names the floor it will not fill below")
    send = transport or bankr_quote.keyed_transport(settings.user_agent, settings.auth_header,
                                                    secret)
    now = clock or (lambda: Instant(__import__("time").time_ns() // 1_000_000))
    body = json.dumps(request.body(settings)).encode("utf-8")
    status, answer, _ = send(settings.base_url + settings.path, body, settings.timeout_s)
    sent_at = now()
    try:
        parsed = json.loads(answer.decode("utf-8", "replace"))
    except ValueError:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}
    success = parsed.get("success") if isinstance(parsed.get("success"), bool) else None
    tx_hash = parsed.get("hash") or parsed.get("txHash") or parsed.get("transactionHash")
    detail = str(parsed.get("message") or parsed.get("error") or "")[:300]
    return SwapReply(status=status, success=success,
                     tx_hash=tx_hash if isinstance(tx_hash, str) else None,
                     sent_at=sent_at, body=parsed,
                     detail=detail or f"HTTP {status}")
