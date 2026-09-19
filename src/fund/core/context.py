"""How big risk's bundle is, measured before the call (unit 3.6).

Invariant 3: risk reads every full report and the sized plan, and if they do not
fit the context budget the cycle vetoes. Nothing is summarized to make it fit.

**The gateway has no token-count endpoint** (F1.7.2), so the count is an
estimate from the prompt's own bytes. It divides by the lower of the two
measured ratios of bytes to tokens (`context_bytes_per_token`, 1.8), which
overcounts, and rounds up. It then adds the reply's whole output cap, since the
reply shares the model's context. So the estimate errs toward a veto.

This measures only. Whether the count is within the budget is
`gates.context_budget`'s question, the one place that limit is compared.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal
from typing import Any


@dataclass(frozen=True)
class Estimate:
    prompt_bytes: int
    prompt_tokens: int  # the bytes over the ratio, rounded up
    reserved_tokens: int  # the reply's output cap
    bytes_per_token: Decimal

    @property
    def tokens(self) -> int:
        return self.prompt_tokens + self.reserved_tokens

    def as_dict(self) -> dict[str, Any]:
        return {"prompt_bytes": self.prompt_bytes, "prompt_tokens": self.prompt_tokens,
                "reserved_tokens": self.reserved_tokens, "tokens": self.tokens,
                "bytes_per_token": format(self.bytes_per_token, "f"), "is_estimate": True,
                "basis": "bytes over the lower measured ratio, rounded up, plus the reply's "
                         "whole output cap; the gateway has no token count (F1.7.2)"}


def measure(prompt: str, *, reserved_tokens: int, bytes_per_token: Decimal) -> Estimate:
    """The tokens a prompt and its reply may take, estimated from above."""
    size = len(prompt.encode("utf-8"))
    tokens = int((Decimal(size) / bytes_per_token).to_integral_value(rounding=ROUND_CEILING))
    return Estimate(size, tokens, reserved_tokens, bytes_per_token)
