"""Unit 2.4: four analysts fanned out, each in its own process, against a fake
gateway on 127.0.0.1. No real key is used, and nothing leaves the machine.

The H-risk property is tested by what each analyst process could actually see:
every worker reports the names (never the values) of its environment. The test
plants fake treasurer secrets in the runner's own environment and asserts that
none of them reaches any analyst.
"""

import ast
import json
import re
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from fund import credentials
from fund.agents import analyst, runner
from fund.store import reports

REPO = Path(__file__).resolve().parents[1]
FORMAT = (REPO / "planning" / "REPORT-FORMAT.md").read_text()
SNAPSHOT = REPO / "fixtures" / "snapshots" / "66852293-253315c0e691" / "snapshot.json"
SEATS = ["price-trend", "cross-asset-macro", "execution-quality", "price-integrity"]
INTEGRITY_AGENT = "0x42a9bd235aedd68e9f2881710577105cb46e3d27"
ALLOWED_NAMES = {"PATH", "PYTHONPATH", analyst.KEY_VARIABLE, "LC_CTYPE"}  # LC_CTYPE: Python's


def example(seat):
    """The approved report, with the header's agent as the runner now assigns it: the
    approved examples wrote `0x…` for a seat with no wallet, and the runner writes
    UNASSIGNED_AGENT."""
    text = FORMAT.split(f". {seat}\n", 1)[1].split("```\n", 2)[1]
    return text.replace(f"REPORT {seat} 0x… ", f"REPORT {seat} {runner.UNASSIGNED_AGENT} ", 1)


def no_calls(seat):
    block = FORMAT.split("### How NO_CALL appears", 1)[1].split("```\n", 2)[1]
    text = "\n".join(line[2:] if line.startswith("  ") else line for line in block.splitlines())
    return text.replace("REPORT cross-asset-macro 0x…",
                        f"REPORT {seat} {runner.UNASSIGNED_AGENT}", 1)


MALFORMED = "CALL MSTR caution high\nThe header is missing and this line is short.\n"


def completion(text, finish="stop"):
    return json.dumps({"id": "chatcmpl-fake", "object": "chat.completion",
                       "model": "claude-sonnet-5",
                       "choices": [{"finish_reason": finish,
                                    "message": {"role": "assistant", "content": text}}],
                       "usage": {"prompt_tokens": 94716, "completion_tokens": 7484}}).encode()


class FakeGateway:
    """Answers each seat from a script: ("report", text), ("hang", seconds) or
    ("status", code). The last step repeats. Records every request's seat and key."""

    def __init__(self, script):
        self.script, self.requests = script, []
        gateway = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                seat = re.search(r"# Brief: (\S+), v1", body["messages"][0]["content"]).group(1)
                gateway.requests.append({"seat": seat, "key": self.headers["X-API-Key"],
                                         "user": body["messages"][1]["content"],
                                         "at": time.monotonic()})
                steps = gateway.script[seat]
                step = steps[min(sum(r["seat"] == seat for r in gateway.requests) - 1,
                                 len(steps) - 1)]
                if step[0] == "hang":
                    time.sleep(step[1])
                status, payload = ((step[1], b'{"error":"scripted"}') if step[0] == "status"
                                   else (200, completion(step[1])))
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"

    def count(self, seat):
        return sum(r["seat"] == seat for r in self.requests)

    def close(self):
        self.server.shutdown()


@pytest.fixture
def gateway():
    made = []

    def make(script):
        made.append(FakeGateway(script))
        return made[-1]

    yield make
    for g in made:
        g.close()


def settings(url, **changes):
    base = dict(model="claude-sonnet-5", max_tokens=12000, transport_timeout_s=2.5,
                worker_deadline_s=3.5, cycle_deadline_s=30, retry_budget=1, width=4,
                pricing=PRICE, gateway_url=url)
    return runner.Settings(**{**base, **changes})


SHARED = {"BANKR_LLM_KEY": "bk_fake_shared_gateway_key_0000000001"}
PRICE = {"input": "2", "output": "10", "currency": "usd"}  # config/models.json, claude-sonnet-5


def shared_keys():
    return runner.SharedGatewayKey(SHARED, agents={"price-integrity": INTEGRITY_AGENT})


# --- the proof: one ok, one abstaining, one malformed, one timed out ------------------------------

def test_four_workers_one_malformed_one_timed_out_one_abstaining_and_the_cycle_completes(
        gateway, tmp_path):
    g = gateway({"price-trend": [("report", example("price-trend"))],
                 "cross-asset-macro": [("report", no_calls("cross-asset-macro"))],
                 "execution-quality": [("report", MALFORMED)],
                 "price-integrity": [("hang", 10)]})
    started = time.monotonic()
    store = reports.ReportStore(tmp_path / "store")
    cycle = runner.run_cycle(SNAPSHOT, shared_keys(), cycle_dir=tmp_path, environ=SHARED,
                             settings=settings(g.url), store=store)
    took = time.monotonic() - started
    seats = cycle["seats"]

    assert seats["price-trend"]["status"] == "ok"
    assert [c["symbol"] for c in seats["price-trend"]["report"]["calls"]] == [
        "AMD", "META", "INTC", "NVDA", "AMZN"]
    assert seats["cross-asset-macro"]["status"] == "no_call"
    assert seats["cross-asset-macro"]["report"]["no_calls"] is True

    malformed = seats["execution-quality"]
    assert malformed["status"] == "failed" and malformed["reason"] == "invalid"
    assert len(malformed["attempts"]) == 2 and g.count("execution-quality") == 2  # one retry
    assert "header" in malformed["detail"]

    hung = seats["price-integrity"]
    assert hung["status"] == "failed" and hung["reason"] in ("timeout", "worker deadline")
    assert g.count("price-integrity") == 1  # a timeout is never retried

    assert cycle["partial"] is True
    assert set(cycle["failed"]) == {"execution-quality", "price-integrity"}
    # 2.5: four calls came back with a usage block, one timed out and has none.
    assert cycle["cost"]["usd"] == "1.057088" and cycle["cost"]["calls"] == 5
    assert cycle["cost"]["calls_of_unknown_cost"] == 1 and cycle["cost"]["is_estimate"] is True
    # 2.7: every reply that arrived is stored, accepted or refused; the hung seat's is not.
    assert "report_id" not in seats["price-integrity"]
    assert store.text(seats["price-trend"]["report_id"]) == example("price-trend")
    assert store.get(seats["price-trend"]["report_id"])["accepted"] is True
    assert store.text(seats["cross-asset-macro"]["report_id"]) == no_calls("cross-asset-macro")
    refused = store.get(seats["execution-quality"]["report_id"])
    assert refused["text"] == MALFORMED and refused["accepted"] is False and refused["refusals"]
    assert cycle["counts"] == {"ok": 1, "no_call": 1, "failed": 2}
    assert took < 8, "the four ran together, not one after another"
    firsts = [min(r["at"] for r in g.requests if r["seat"] == s) for s in SEATS]
    assert max(firsts) - min(firsts) < 2.0

    events = [json.loads(line) for line in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert [e["event"] for e in events].count("started") == 4
    assert [e["event"] for e in events].count("finished") == 4
    assert events[-1]["event"] == "cycle finished" and events[-1]["partial"] is True
    on_disk = {s: json.loads((tmp_path / "results" / f"{s}.json").read_text())["status"]
               for s in SEATS}
    assert on_disk == {s: seats[s]["status"] for s in SEATS}
    assert SHARED["BANKR_LLM_KEY"] not in (tmp_path / "events.jsonl").read_text()
    for path in tmp_path.rglob("*.json"):
        assert SHARED["BANKR_LLM_KEY"] not in path.read_text()


def test_a_cycle_past_its_deadline_kills_what_runs_and_starts_nothing_more(gateway, tmp_path):
    g = gateway({"price-integrity": [("hang", 10)],
                 "price-trend": [("report", example("price-trend"))]})
    cycle = runner.run_cycle(SNAPSHOT, shared_keys(), cycle_dir=tmp_path, environ=SHARED,
                             seats=["price-integrity", "price-trend"],
                             settings=settings(g.url, width=1, cycle_deadline_s=1.0))
    assert cycle["seats"]["price-integrity"]["reason"] in ("cycle deadline", "timeout")
    assert cycle["seats"]["price-trend"] == {**cycle["seats"]["price-trend"],
                                             "status": "failed", "reason": "cycle deadline"}
    assert g.count("price-trend") == 0 and cycle["partial"] is True


# --- the H-risk property: nothing but its own key reaches an analyst -----------------------------

TREASURER_SECRETS = {"BANKR_KEY_EXEC": "bk_fake_exec_key_must_never_reach_an_analyst",
                     "SIGNING_KEY": "fake_ed25519_signing_key_must_never_reach_an_analyst",
                     "BANKR_KEY_READ": "bk_fake_read_key_not_an_analysts_either",
                     "RPC_4663_MAINNET": "https://rpc.example/with-an-inline-key",
                     "UNRELATED_SECRET": "anything else in the runner's environment"}
OWN = {"KEY_PT": "bk_fake_own_price_trend_000000000001",
       "KEY_CAM": "bk_fake_own_cross_asset_0000000000002",
       "KEY_EQ": "bk_fake_own_execution_q_0000000000003",
       "KEY_PI": "bk_fake_own_price_integ_0000000000004"}
OWN_NAMES = dict(zip(SEATS, OWN))


def test_each_analyst_process_holds_its_own_key_and_nothing_else(gateway, tmp_path, monkeypatch):
    for name, value in {**TREASURER_SECRETS, **OWN}.items():
        monkeypatch.setenv(name, value)  # the runner's environment holds everything
    g = gateway({seat: [("report", example(seat))] for seat in SEATS})
    keys = runner.PerAgentKeys({**TREASURER_SECRETS, **OWN}, names=OWN_NAMES,
                               agents={"price-integrity": INTEGRITY_AGENT})
    cycle = runner.run_cycle(SNAPSHOT, keys, cycle_dir=tmp_path,
                             environ={**TREASURER_SECRETS, **OWN}, settings=settings(g.url))

    declared = {c.name for c in credentials.CREDENTIALS}
    for seat in SEATS:
        names = set(cycle["seats"][seat]["environment_names"])
        assert names <= ALLOWED_NAMES, f"{seat} could see {sorted(names - ALLOWED_NAMES)}"
        assert not names & declared and not names & set(TREASURER_SECRETS) and not names & set(OWN)
        assert cycle["seats"][seat]["status"] == "ok"
    for request in g.requests:  # and each seat's calls carried its own key, no other
        assert request["key"] == OWN[OWN_NAMES[request["seat"]]]


def test_a_treasurer_key_is_refused_before_anything_starts(gateway, tmp_path):
    g = gateway({seat: [("report", example(seat))] for seat in SEATS})
    environ = {**TREASURER_SECRETS, **OWN}
    by_name = runner.SharedGatewayKey(environ, name="BANKR_KEY_EXEC")
    by_value = runner.PerAgentKeys({**environ, "KEY_PI": TREASURER_SECRETS["SIGNING_KEY"]},
                                   names=OWN_NAMES)
    missing = runner.PerAgentKeys({}, names=OWN_NAMES)
    for source, why in ((by_name, "is the treasurer's"), (by_value, "SIGNING_KEY's value"),
                        (missing, "no key")):
        with pytest.raises(runner.SpendAuthorityError, match=why):
            runner.run_cycle(SNAPSHOT, source, cycle_dir=tmp_path / why.replace(" ", "_"),
                             environ=environ, settings=settings(g.url))
    assert g.requests == [] and not any(tmp_path.rglob("*.json"))


def test_no_analyst_module_loads_the_environment_file():
    """The worker and the runner never call config.load() or load_environment(),
    which would merge every secret in .env into the process."""
    for module in ("analyst", "runner", "schema"):
        tree = ast.parse((REPO / "src" / "fund" / "agents" / f"{module}.py").read_text())
        calls = [ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)]
        assert not [c for c in calls if c in ("config.load", "config.load_environment",
                                              "load_environment")], module


# --- the retry rule, one worker in-process ---------------------------------------------------------

def job(tmp_path, seat="price-trend", agent=runner.UNASSIGNED_AGENT):
    import hashlib
    return {"seat": seat, "agent": agent, "snapshot_path": str(SNAPSHOT),
            "snapshot_sha256": hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest(),
            "model": "claude-sonnet-5", "max_tokens": 12000, "transport_timeout_s": 600,
            "worker_deadline_s": 630, "retry_budget": 1, "gateway_url": "http://unused",
            "pricing": PRICE, "result_path": str(tmp_path / "result.json")}


def scripted(*answers):
    sent = []

    def send(url, body, headers, timeout_s):
        sent.append(json.loads(body))
        answer = answers[min(len(sent), len(answers)) - 1]
        if isinstance(answer, BaseException):
            raise answer
        return answer

    return send, sent


def test_a_malformed_reply_is_retried_once_and_the_retry_says_why(tmp_path):
    send, sent = scripted((200, completion(MALFORMED)), (200, completion(example("price-trend"))))
    result = analyst.run(job(tmp_path), "bk_fake", send=send)
    assert result["status"] == "ok" and len(result["attempts"]) == 2 and len(sent) == 2
    assert "Your previous reply was refused: header" in sent[1]["messages"][1]["content"]
    assert sent[0]["messages"][1]["content"].split("END SNAPSHOT")[0] == \
        sent[1]["messages"][1]["content"].split("END SNAPSHOT")[0]


def test_a_reply_cut_off_at_the_cap_is_malformed_and_retried(tmp_path):
    send, sent = scripted((200, completion("REPORT …", finish="length")),
                          (200, completion(example("price-trend"))))
    result = analyst.run(job(tmp_path), "bk_fake", send=send)
    assert result["status"] == "ok" and result["attempts"][0]["refusals"][0].startswith("truncated")


@pytest.mark.parametrize("answer, reason", [
    (socket.timeout("timed out"), "timeout"),
    (ConnectionResetError("reset"), "transport"),
    ((402, b'{"error":{"type":"insufficient_credits"}}'), "refused"),
])
def test_a_timeout_a_transport_failure_or_a_refusal_is_never_retried(tmp_path, answer, reason):
    send, sent = scripted(answer, (200, completion(example("price-trend"))))
    result = analyst.run(job(tmp_path), "bk_fake", send=send)
    assert result["status"] == "failed" and result["reason"] == reason and len(sent) == 1


def test_a_retry_that_would_outrun_the_deadline_is_not_sent(tmp_path):
    ticks = iter([0, 0, 629.5, 629.5, 629.5])
    send, sent = scripted((200, completion(MALFORMED)))
    result = analyst.run(job(tmp_path), "bk_fake", send=send, clock=lambda: next(ticks))
    assert result["reason"] == "no time" and len(sent) == 1


def test_the_unassigned_agent_cannot_be_read_as_an_address():
    """2.6: `0x…` read as an elided address, and the model filled in the fund's wallet."""
    token = runner.UNASSIGNED_AGENT
    assert not token.startswith("0x") and not re.search(r"[0-9a-fA-F]{6}", token)
    assert token.isalpha() and token.isascii()
    header = analyst.render("price-integrity", SNAPSHOT.read_bytes(), token).header
    assert header.split()[2] == token and header.startswith(f"REPORT price-integrity {token} ")


# --- the live entry point, main() (2.6) -------------------------------------------------------------

FAKE_ENV = {"BANKR_LLM_KEY": "bk_fake_llm_key_from_the_env_file_0001",
            "BANKR_KEY_EXEC": "bk_fake_exec_key_from_the_env_file_0002",
            "SIGNING_KEY": "fake_signing_key_from_the_env_file_0003"}


@pytest.fixture
def env_file(tmp_path, monkeypatch):
    """A .env of fake values, and no real credential in this process's environment,
    whatever an earlier test loaded."""
    from fund import config
    for credential in credentials.CREDENTIALS:
        monkeypatch.delenv(credential.name, raising=False)

    def write(values):
        path = tmp_path / ".env"
        path.write_text("".join(f"{k}={v}\n" for k, v in values.items()))
        monkeypatch.setattr(config, "ENV_FILE", path)
        return path

    return write


def test_without_confirm_it_prints_the_plan_and_sends_nothing(env_file, monkeypatch, capsys):
    env_file(FAKE_ENV)
    monkeypatch.setattr(runner, "run_cycle", lambda *a, **k: pytest.fail("a cycle started"))
    assert runner.main(["--snapshot", str(SNAPSHOT), "--seats", "price-integrity",
                        "--retries", "0"]) == 0
    out = capsys.readouterr().out
    assert "at most   1 billed call(s)" in out and "Nothing sent" in out
    assert f"BANKR_LLM_KEY (shared), agent {runner.UNASSIGNED_AGENT}" in out
    assert FAKE_ENV["BANKR_LLM_KEY"] not in out
    assert runner.main(["--snapshot", str(SNAPSHOT)]) == 0  # every seat, config's one retry
    assert "at most   8 billed call(s)" in capsys.readouterr().out


def test_a_treasurer_key_stops_even_the_dry_run(env_file, capsys):
    env_file({**FAKE_ENV, "BANKR_LLM_KEY": FAKE_ENV["BANKR_KEY_EXEC"]})
    with pytest.raises(runner.SpendAuthorityError, match="BANKR_KEY_EXEC"):
        runner.main(["--snapshot", str(SNAPSHOT), "--seats", "price-integrity"])
    assert "billed" not in capsys.readouterr().out


def test_confirm_runs_one_cycle_with_the_key_from_the_env_file(env_file, gateway, monkeypatch,
                                                               tmp_path, capsys):
    env_file(FAKE_ENV)
    g = gateway({"price-integrity": [("report", no_calls("price-integrity"))]})
    monkeypatch.setattr(runner.Settings, "from_config", classmethod(lambda cls: settings(g.url)))
    monkeypatch.setattr(runner, "LIVE_REPORTS", tmp_path / "store")  # never the real live store
    assert runner.main(["--snapshot", str(SNAPSHOT), "--seats", "price-integrity",
                        "--retries", "0", "--cycle-dir", str(tmp_path / "cycle"),
                        "--confirm"]) == 0
    assert len(g.requests) == 1 and g.requests[0]["key"] == FAKE_ENV["BANKR_LLM_KEY"]
    cycle = json.loads((tmp_path / "cycle" / "cycle.json").read_text())
    assert cycle["seats"]["price-integrity"]["status"] == "no_call" and cycle["partial"] is False
    stored = reports.ReportStore(tmp_path / "store")
    assert stored.text(cycle["seats"]["price-integrity"]["report_id"]) == no_calls("price-integrity")
    out = capsys.readouterr().out
    assert "partial   False" in out and FAKE_ENV["BANKR_LLM_KEY"] not in out
