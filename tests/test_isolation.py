"""Unit 4.12: no key an analyst holds may transact, checked by trying it. H.

The live run is `python -m fund.run.isolation --live`, and its measurement is in
tracker/LOGS.md. These tests hold the two rules that keep it safe to run: the
treasurer's key is never sent, and a request that is not refused is a finding, not a
pass. That every agent process is built from an empty environment is tested where it
happens: tests/test_runner.py, and tests/test_cycle.py for the treasurer's process.
"""

from __future__ import annotations

import json

import pytest

from fund import config, credentials
from fund.run import isolation

REFUSAL = (403, b'{"error":"Read-only API key","message":"cannot execute swaps"}', {})
ACCEPTED = (200, b'{"success":true,"hash":"0xdead"}', {})


def recorder(answer):
    sent = []

    def transport(url, body, timeout_s):
        sent.append((url, json.loads(body)))
        return answer
    return transport, sent


def test_the_treasurers_key_is_never_sent():
    transport, sent = recorder(ACCEPTED)
    with pytest.raises(config.CredentialNotPermittedError, match="never sends it"):
        isolation.attempt("BANKR_KEY_EXEC", "a-secret", transport=transport)
    assert sent == []
    # and it is not among the keys the check tries, even when it is set
    every = {c.name: "a-secret" for c in credentials.CREDENTIALS}
    transport, sent = recorder(REFUSAL)
    tried = {result["key"] for result in isolation.check(every, transport=transport)}
    assert "BANKR_KEY_EXEC" not in tried and tried == {"BANKR_KEY_READ", "BANKR_LLM_KEY"}
    assert len(sent) == 2 and all(url == isolation.SWAP_URL for url, _ in sent)


def test_a_refusal_is_the_pass_and_a_200_is_the_finding():
    transport, _ = recorder(REFUSAL)
    refused = isolation.attempt("BANKR_KEY_READ", "a-secret", transport=transport)
    assert refused["refused"] and refused["status"] == 403 and "read-only" in refused["body"].lower()
    transport, sent = recorder(ACCEPTED)
    through = isolation.attempt("BANKR_KEY_READ", "a-secret", transport=transport)
    assert through["refused"] is False
    assert sent[0][1]["amount"] == isolation.AMOUNT_ETH  # the smallest size that quotes
