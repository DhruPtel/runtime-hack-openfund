"""Unit 1.5: the quote adapter, offline.

The response bytes are probe 0.3's own TSLA quote at $25 (`probes/out/quote.json`,
2026-09-17): the four number formats, a negative impact, all 12 fields. The live
read is `python -m fund.adapters.bankr_quote --prove`, not part of `make test`.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from fund import config
from fund.adapters import bankr_quote as bq
from fund.core.types import (
    USD, Amount, AssetId, Check, FetchStatus, Fixed, Instant, Observation, Price, Source,
)
from fund.credentials import Role

CHAIN = 4663
USDG = AssetId(CHAIN, "0x5fc5360d0400a0fd4f2af552add042d716f1d168")
TSLA = AssetId(CHAIN, "0x322f0929c4625ed5bad873c95208d54e1c003b2d")
TWENTY_FIVE = Amount(25_000_000, 6, USDG)
REQUEST = bq.QuoteRequest(sell=TWENTY_FIVE, buy=TSLA, buy_decimals=18)
FETCHED = Instant(1_789_779_871_000)
LIMITS = bq.Limits(max_age=Fixed(60, 0, "s"), max_impact=Fixed(50, 0, "bps"),
                   nominal=Fixed(25, 0, USD))

#: Probe 0.3, TSLA at $25, byte for byte.
RECORDED = (b'{"from":{"chain":"robinhood","token":"0x5fc5360d0400a0fd4f2af552add042d716f1d168",'
            b'"amount":"25","formattedAmount":"25","symbol":"USDG","decimals":6,"usdValue":"25.06"},'
            b'"to":{"chain":"robinhood","token":"0x322f0929c4625ed5bad873c95208d54e1c003b2d",'
            b'"amount":"67948238487403141","formattedAmount":"0.06794823848740314","symbol":"TSLA",'
            b'"decimals":18,"usdValue":"25.09"},"minBuyAmount":"0.064550826563032984","feeBps":0,'
            b'"feeWaivedForEcosystemToken":false,"slippageBps":500,"priceImpactBps":-15,'
            b'"swapImpactBps":-15,"maxPriceImpactBps":1500,"sellTokenPriceUsd":1.0022236982588135,'
            b'"buyTokenPriceUsd":369.2925339180603,"quoteId":"c9f64995-fa7c-469b-a880-4796cfa739d9"}')


def recorded(**changes) -> bytes:
    """The recorded response with top-level fields replaced; None deletes one."""
    data = json.loads(RECORDED, parse_float=str)
    for key, value in changes.items():
        if value is None:
            data.pop(key, None)
        else:
            data[key] = value
    return json.dumps(data).encode()


def parsed(body: bytes = RECORDED, request=REQUEST) -> Observation:
    return bq.parse(body, request, "robinhood", FETCHED)


def judged(quote: Observation, seconds_later: float = 1.0, asked: Amount = TWENTY_FIVE):
    return bq.tradeability(quote, asked, Instant(FETCHED.epoch_ms + int(seconds_later * 1000)), LIMITS)


# --- sizing and the request --------------------------------------------------------------

def test_the_nominal_size_is_converted_at_the_cash_legs_mark_rounded_down():
    at_mark = bq.nominal_sell(Fixed(25, 0, USD), Price(99_995_090, 8, USDG, USD), 6)
    assert at_mark == Amount(25_001_227, 6, USDG)           # $25 / $0.99995090 = 25.0012275...
    at_venue = bq.nominal_sell(Fixed(25, 0, USD), Price.parse("1.0022236982588135", USDG, USD), 6)
    assert at_venue == Amount(24_944_530, 6, USDG)          # probe 0.3's "about 24.94 USDG"


def test_the_request_is_the_documented_five_fields_with_a_human_amount():
    body = bq.QuoteRequest(sell=Amount(25_001_227, 6, USDG), buy=TSLA, buy_decimals=18).body("robinhood")
    assert body == {"fromChain": "robinhood", "fromToken": USDG.address, "toChain": "robinhood",
                    "toToken": TSLA.address, "amount": "25.001227"}
    assert bq.human(TWENTY_FIVE) == "25" and bq.human(Amount(1, 6, USDG)) == "0.000001"


@pytest.mark.parametrize("sell, buy", [(Amount(0, 6, USDG), TSLA), (TWENTY_FIVE, USDG)])
def test_a_request_the_venue_would_answer_with_invalid_request_body_is_refused_here(sell, buy):
    with pytest.raises(ValueError):
        bq.QuoteRequest(sell=sell, buy=buy, buy_decimals=18)


# --- the four formats, converted exactly ----------------------------------------------------

def test_the_recorded_quote_converts_every_format_exactly():
    seen = parsed()
    q = seen.value
    assert seen.ok and seen.source_time is None and seen.block is None
    assert seen.source_ref == "c9f64995-fa7c-469b-a880-4796cfa739d9"
    assert q.sell == TWENTY_FIVE                                         # human echo
    assert q.buy == Amount(67_948_238_487_403_141, 18, TSLA)             # raw
    assert q.min_buy == Amount(64_550_826_563_032_984, 18, TSLA)         # human text
    assert q.swap_impact == Fixed(-15, 0, "bps") and q.price_impact == Fixed(-15, 0, "bps")
    assert q.sell_price == Price.parse("1.0022236982588135", USDG, USD)  # a JSON float, as text
    assert q.fee == Fixed(0, 0, "bps") and q.fee_waived is False and q.slippage == Fixed(500, 0, "bps")


def test_the_lossy_formatted_amount_is_never_read():
    data = json.loads(RECORDED, parse_float=str)
    data["to"]["formattedAmount"] = "garbage"
    assert parsed(json.dumps(data).encode()).value.buy == parsed().value.buy


def test_a_float_price_keeps_every_digit_that_was_sent():
    body = RECORDED.replace(b"369.2925339180603", b"369.29253391806031234567")
    assert parsed(body).value.buy_price == Price(36929253391806031234567, 20, TSLA, USD)


@pytest.mark.parametrize("side, said, pinned", [("from", 18, 6), ("to", 6, 18)])
def test_decimals_that_disagree_with_the_pins_are_refused(side, said, pinned):
    data = json.loads(RECORDED, parse_float=str)
    data[side]["decimals"] = said
    seen = parsed(json.dumps(data).encode())
    assert seen.status is FetchStatus.REFUSED and "10^12" in seen.detail


def test_a_request_built_on_the_documented_but_wrong_18_for_usdg_is_caught_by_the_response():
    wrong = bq.QuoteRequest(sell=Amount(25 * 10**18, 18, USDG), buy=TSLA, buy_decimals=18)
    seen = parsed(request=wrong)
    assert seen.status is FetchStatus.REFUSED and "from.decimals 6 disagrees with the pinned 18" in seen.detail


def test_a_quote_for_another_token_is_refused():
    data = json.loads(RECORDED, parse_float=str)
    data["to"]["token"] = "0x" + "ab" * 20
    assert parsed(json.dumps(data).encode()).status is FetchStatus.REFUSED


def test_an_absent_optional_field_is_null_and_named():
    seen = parsed(recorded(swapImpactBps=None, buyTokenPriceUsd=None))
    assert seen.ok and seen.value.swap_impact is None and seen.value.buy_price is None
    assert "swapImpactBps" in seen.detail and "buyTokenPriceUsd" in seen.detail


@pytest.mark.parametrize("missing", ["minBuyAmount"])
def test_an_absent_amount_refuses_the_quote(missing):
    assert parsed(recorded(**{missing: None})).status is FetchStatus.REFUSED


def test_a_body_that_is_not_json_is_refused():
    assert parsed(b"<html>502</html>").status is FetchStatus.REFUSED


# --- tradeability: three conditions, each refused at its own rule -----------------------------

def test_negative_impact_is_price_improvement_and_is_admitted():
    verdict = judged(parsed())
    assert verdict.verdict.passes and verdict.rule is None
    assert "price improvement" in verdict.verdict.reason


def test_tradeable_is_never_evidence_of_execution():
    verdict = judged(parsed())
    assert verdict.verdict.passes
    assert verdict.executable.value is None and "not a fill" in verdict.executable.reason


@pytest.mark.parametrize("impact, passes", [(50, True), (51, False), (-600, True)])
def test_impact_is_compared_signed(impact, passes):
    verdict = judged(parsed(recorded(swapImpactBps=impact)))
    assert verdict.verdict.passes is passes
    if not passes:
        assert verdict.rule == bq.RULE_IMPACT and verdict.verdict.value is False


def test_the_gate_reads_swap_impact_not_price_impact():
    verdict = judged(parsed(recorded(priceImpactBps=900, swapImpactBps=10)))
    assert verdict.verdict.passes


def test_an_unknown_impact_blocks_at_impact():
    verdict = judged(parsed(recorded(swapImpactBps=None)))
    assert verdict.rule == bq.RULE_IMPACT and verdict.verdict.value is None


@pytest.mark.parametrize("seconds, value", [(60.0, True), (60.001, False)])
def test_quote_age_is_measured_from_our_fetch_time(seconds, value):
    verdict = judged(parsed(), seconds)
    assert verdict.verdict.value is value
    if value is False:
        assert verdict.rule == bq.RULE_QUOTE_AGE


def test_a_quote_judged_before_it_was_fetched_has_no_age():
    verdict = judged(parsed(), -1)
    assert verdict.rule == bq.RULE_QUOTE_AGE and verdict.verdict.value is None


def test_a_quote_for_another_size_is_refused_at_size():
    verdict = judged(parsed(), asked=Amount(25_001_227, 6, USDG))
    assert verdict.rule == bq.RULE_SIZE and verdict.verdict.value is False


def test_a_refused_quote_is_false_and_an_unreachable_one_undetermined_both_at_quote():
    def failed(status):
        return Observation(value=None, source=bq.SOURCE, source_time=None, fetch_time=FETCHED,
                           block=None, status=status, detail="the venue answered HTTP 400")
    refused, unreachable = judged(failed(FetchStatus.REFUSED)), judged(failed(FetchStatus.UNREACHABLE))
    assert refused.rule == unreachable.rule == bq.RULE_QUOTE
    assert refused.verdict.value is False and unreachable.verdict.value is None


# --- the adapter, on the shared client ------------------------------------------------------------

def adapter(transport, sleeps=None, secret=lambda name: "test-read-key"):
    a = bq.Settings.load().adapter(secret, transport=transport, clock=lambda: FETCHED)
    a.client._sleep = (sleeps if sleeps is not None else []).append
    a.client.min_interval_s = 0
    return a


def replies(*items):
    queue = iter(items)
    return lambda url, body, timeout: next(queue)


def test_a_200_becomes_a_quote_observation():
    seen = adapter(replies((200, RECORDED, {}))).quote(REQUEST)
    assert seen.ok and seen.value.sell == TWENTY_FIVE


def test_a_venue_refusal_keeps_the_venues_words_and_is_not_called_unreachable():
    invalid = (400, b'{"message":"Invalid request body"}', {})
    seen = adapter(replies(invalid, invalid, invalid)).quote(REQUEST)
    assert seen.status is FetchStatus.REFUSED and "Invalid request body" in seen.detail
    assert judged(seen).rule == bq.RULE_QUOTE


def test_no_answer_at_all_is_unreachable():
    def refuse(url, body, timeout):
        raise ConnectionRefusedError("[Errno 111] Connection refused")
    seen = adapter(refuse).quote(REQUEST)
    assert seen.status is FetchStatus.UNREACHABLE and "BANKR_API" in seen.detail


def test_a_429_backs_off_through_the_shared_client():
    sleeps: list[float] = []
    seen = adapter(replies((429, b"{}", {}), (200, RECORDED, {})), sleeps).quote(REQUEST)
    assert seen.ok and sleeps == [2.0]


def test_the_real_transport_posts_the_key_in_its_header_and_the_key_never_reaches_a_failure(monkeypatch):
    key = "test-read-key-0123456789abcdef"
    monkeypatch.setenv("BANKR_KEY_READ", key)
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            seen["key"], seen["path"] = self.headers.get("X-API-Key"), self.path
            seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(200)
            self.send_header("Content-Length", str(len(RECORDED)))
            self.end_headers()
            self.wfile.write(RECORDED)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()
    try:
        settings = bq.Settings.load()
        local = bq.Settings(**{**settings.__dict__, "base_url": f"http://127.0.0.1:{server.server_port}"})
        assert local.adapter(lambda name: key, clock=lambda: FETCHED).quote(REQUEST).ok
    finally:
        server.server_close()
    assert seen["key"] == key and seen["path"] == "/wallet/swap-quote"
    assert seen["body"]["amount"] == "25"

    def leak(url, body, timeout):
        raise ConnectionResetError(f"reset while sending X-API-Key: {key}")
    failure = adapter(leak, secret=lambda name: key).quote(REQUEST)
    assert key not in failure.detail and "[REDACTED:BANKR_KEY_READ]" in failure.detail


# --- read-only, by construction -------------------------------------------------------------------

def test_the_module_cannot_reach_bankr_exec_or_the_signing_path():
    code = ("import sys, fund.adapters.bankr_quote; "
            "print([m for m in sys.modules if m.startswith(('fund.adapters.bankr_exec', "
            "'fund.treasurer')) or m.endswith('.sign')])")
    src = Path(bq.__file__).resolve().parents[2]
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True,
                         env={"PYTHONPATH": str(src), "PATH": ""}, check=True)
    assert out.stdout.strip() == "[]"
    tree = ast.parse(Path(bq.__file__).read_text())
    imported = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any(("bankr_exec" in m or "treasurer" in m or m.endswith("sign")) for m in imported)


def test_the_adapter_asks_for_the_read_key_and_nothing_else():
    asked: list[str] = []
    bq.Settings.load().adapter(lambda name: asked.append(name) or "k", clock=lambda: FETCHED)
    assert asked == ["BANKR_KEY_READ"]


def test_the_role_quotes_run_under_cannot_load_the_execution_or_signing_key():
    cfg = config.load(Role.ANALYST, require=False, install_redaction=False)
    for name in ("BANKR_KEY_EXEC", "SIGNING_KEY"):
        with pytest.raises(config.CredentialNotPermittedError):
            cfg.secret(name)


@pytest.mark.parametrize("credential, refusal", [("BANKR_KEY_EXEC", "can transact"),
                                                 ("SIGNING_KEY", "not the analyst role's")])
def test_settings_refuse_a_credential_that_is_not_a_read_key(tmp_path, credential, refusal):
    doc = json.loads(bq.QUOTE_CONFIG.read_text())
    doc["credential"] = credential
    path = tmp_path / "quote.json"
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match=refusal):
        bq.Settings.load(path)


# --- the limits come from config ----------------------------------------------------------------

def test_the_limits_and_the_nominal_size_come_from_thresholds_json():
    limits = bq.Limits.from_thresholds(json.loads(bq.THRESHOLDS.read_text()))
    assert limits.max_age.same_value(Fixed(60, 0, "s"))
    assert limits.max_impact.same_value(Fixed(50, 0, "bps"))
    assert limits.nominal.same_value(Fixed(25, 0, USD))


def test_a_null_limit_blocks_and_a_float_is_refused():
    base = {"quote_max_age_seconds": 60, "impact_max_bps": 50, "intended_trade_size_usd": 25}
    with pytest.raises(ValueError, match="null"):
        bq.Limits.from_thresholds({**base, "impact_max_bps": None})
    with pytest.raises(TypeError, match="float"):
        bq.Limits.from_thresholds({**base, "quote_max_age_seconds": 60.0})
