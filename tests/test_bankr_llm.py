"""Unit 2.4: the gateway client makes one request per call, and never raises.

The reply shape is the one the gateway returned at 1.7 (probes/out/analyst_cost.json):
`choices[0].message.content`, `finish_reason`, a `usage` block with
`prompt_tokens` and `completion_tokens`, and a `chatcmpl-` id.
"""

import json
import socket
import time

from fund.adapters import bankr_llm

KEY = "bk_test_gateway_key_0123456789abcdef"


def recorded_reply(text="REPORT …", finish="stop", prompt=94716, completion=7484):
    return json.dumps({
        "id": "chatcmpl-9ex92yWm7wqb2oFVBnPX3", "object": "chat.completion",
        "model": "claude-sonnet-5", "created": 1789785446,
        "choices": [{"index": 0, "finish_reason": finish,
                     "message": {"role": "assistant", "content": text}}],
        "usage": {"prompt_tokens": prompt, "completion_tokens": completion,
                  "total_tokens": prompt + completion, "prompt_tokens_details": {"cached_tokens": 0}},
        "cost": {"diem": 0.691809, "usd": 0},
    }).encode()


class Recorder:
    """A fake gateway that counts what it is sent."""

    def __init__(self, answer):
        self.answer, self.sent = answer, []

    def __call__(self, url, body, headers, timeout_s):
        self.sent.append((url, json.loads(body), dict(headers), timeout_s))
        return self.answer(url, body, headers, timeout_s)


def call(send, timeout_s=5.0):
    return bankr_llm.complete(KEY, model="claude-sonnet-5", system="S", user="U", max_tokens=12000,
                              timeout_s=timeout_s, send=send)


def test_a_reply_is_read_with_its_usage_and_request_id():
    send = Recorder(lambda *a: (200, recorded_reply("the report")))
    reply = call(send)
    assert reply.arrived and reply.text == "the report" and reply.finish_reason == "stop"
    assert reply.usage["prompt_tokens"] == 94716 and reply.usage["completion_tokens"] == 7484
    assert reply.request_id == "chatcmpl-9ex92yWm7wqb2oFVBnPX3"
    assert reply.provider["cost"] == {"diem": 0.691809, "usd": 0}
    url, body, headers, timeout_s = send.sent[0]
    assert url == "https://llm.bankr.bot/v1/chat/completions" and timeout_s == 5.0
    assert body["temperature"] == 0 and body["max_tokens"] == 12000
    assert [m["role"] for m in body["messages"]] == ["system", "user"]
    assert headers["X-API-Key"] == KEY


def test_a_refusal_is_one_request_with_its_body_kept():
    for status, body in ((402, b'{"error":{"type":"insufficient_credits"}}'),
                         (500, b'{"message":"upstream"}'), (429, b'{}')):
        send = Recorder(lambda *a, s=status, b=body: (s, b))
        reply = call(send)
        assert len(send.sent) == 1, "the shared client would have tried again; this must not"
        assert reply.status == status and not reply.arrived and reply.body == body.decode()


def test_a_timeout_is_one_request_and_a_named_error():
    def socket_timeout(*a):
        raise socket.timeout("timed out")

    def trickle(*a):
        time.sleep(1.5)
        return 200, recorded_reply()

    for answer, limit in ((socket_timeout, 5.0), (trickle, 0.3)):
        send = Recorder(answer)
        reply = call(send, timeout_s=limit)
        assert len(send.sent) == 1 and reply.error == "timeout" and reply.status is None


def test_a_transport_failure_is_a_result_and_never_shows_the_key():
    def refused(url, body, headers, timeout_s):
        raise ConnectionRefusedError(f"refused while sending {headers['X-API-Key']}")

    reply = call(Recorder(refused))
    assert reply.error.startswith("transport: ConnectionRefusedError") and KEY not in reply.error


def test_an_echoed_key_is_masked_and_an_unreadable_body_is_named():
    echoed = call(Recorder(lambda *a: (401, f'{{"bad key": "{KEY}"}}'.encode())))
    assert KEY not in echoed.body and "[GATEWAY_KEY]" in echoed.body
    garbled = call(Recorder(lambda *a: (200, b"<html>not json</html>")))
    assert garbled.error == "unreadable body" and not garbled.arrived


def test_a_reply_cut_off_at_the_cap_says_so():
    reply = call(Recorder(lambda *a: (200, recorded_reply(finish="length"))))
    assert reply.arrived and reply.finish_reason == "length"
