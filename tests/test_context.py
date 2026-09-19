"""Unit 3.6: the context budget, measured before the risk call; over it vetoes."""

from __future__ import annotations

import dataclasses
from decimal import Decimal

from fund import config
from fund.core import context, gates

MODELS = config.load_json("models.json")
LIMITS = gates.Limits.from_config(config.load_json("thresholds.json"),
                                  config.load_json("mandate.json"), MODELS)
RATIO = Decimal(MODELS["context_bytes_per_token"])
CAP = MODELS["max_output_tokens"]


def test_the_estimate_rounds_up_and_reserves_the_reply():
    e = context.measure("é" * 10, reserved_tokens=CAP, bytes_per_token=RATIO)  # 20 bytes
    assert (e.prompt_bytes, e.prompt_tokens, e.tokens) == (20, 12, 12 + 12_000)


def test_the_budget_holds_to_the_byte_and_one_more_vetoes():
    fits = int((LIMITS.context_budget_tokens - CAP) * RATIO)  # 104,400 bytes: 58,000 tokens
    at = context.measure("x" * fits, reserved_tokens=CAP, bytes_per_token=RATIO)
    over = context.measure("x" * (fits + 1), reserved_tokens=CAP, bytes_per_token=RATIO)
    assert at.tokens == 70_000 and gates.context_budget(at.tokens, LIMITS).passes
    gate = gates.context_budget(over.tokens, LIMITS)
    assert gate.value is False and gate.rule == "context-budget" and "never a summary" in gate.reason


def test_an_unresolved_budget_blocks():
    unset = dataclasses.replace(LIMITS, context_budget_tokens=None)
    assert gates.context_budget(1, unset).value is None
