"""Four analysts, fanned out (unit 2.4). The H-risk unit of Phase 2.

The runner starts one process per seat, at most `max_parallel_workers` at once,
and collects what each writes. It does four things the cycle depends on:
  - **Bounded width.** Never more processes at once than configured.
  - **Deadlines.** A worker still running past its deadline is killed, and so is
    every worker once the whole cycle is past its own deadline. A seat never
    started by then fails without starting.
  - **Pre-allocated slots.** Every seat has a result slot, marked `pending`,
    before any process starts. A worker that dies, is killed or writes nothing
    leaves its slot `failed`, with the reason, and never missing.
  - **A partial result is visibly partial.** The cycle carries `partial: true`
    whenever any seat failed. Whether a partial cycle may decide is Phase 3's
    quorum, not this module's.

**The guarantee it keeps: spend authority never reaches an analyst.**
- **Each child's environment is built from nothing.** It holds its one gateway
  key under `analyst.KEY_VARIABLE`, plus `PATH` and `PYTHONPATH`, and nothing
  else. The runner's own environment is never passed through.
- **Why that matters.** `config.load()` merges the whole of `.env`, execution
  and signing keys included, into the environment of whatever process calls it.
  Passing an environment through would hand an analyst the treasurer's keys.
- **Checked before any process starts.** Every seat's key is compared with
  every credential the analyst role may not hold: `BANKR_KEY_EXEC` and
  `SIGNING_KEY`, from the credential table. A match raises, and nothing runs.
- **What this cannot see:** what a key may do at the provider. As measured on
  2026-09-19, `BANKR_LLM_KEY` passes the read-only gate and has the Agent API on
  (LESSONS). That is a dashboard setting. It is why nothing here has been run
  live.

**Where keys come from is a parameter.** It is a `KeySource`: one key per agent
(`PerAgentKeys`), or one gateway key shared by every seat (`SharedGatewayKey`).
The runner hard-codes neither. The agent-wallet question from 2.0 is still open,
and the offline tests need no real key at all.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from fund import config, credentials
from fund.adapters import bankr_llm
from fund.agents import analyst

SRC = Path(__file__).resolve().parents[2]

#: The header's agent field for a seat that has no wallet of its own yet. It is
#: the form the approved examples use (planning/REPORT-FORMAT.md).
UNASSIGNED_AGENT = "0x…"


class SpendAuthorityError(Exception):
    """A seat's key is one only the treasurer may hold. Nothing was started."""


@dataclass(frozen=True)
class SeatCredential:
    seat: str
    key: str = field(repr=False)
    agent: str
    variable: str  # the name the key was read under: never its value
    shared: bool

    @property
    def source(self) -> str:
        return f"{self.variable} ({'shared' if self.shared else 'own account'})"


class KeySource(Protocol):
    def for_seat(self, seat: str) -> SeatCredential: ...


@dataclass(frozen=True)
class SharedGatewayKey:
    """One gateway key for every seat, each still in its own process. Each seat's
    agent address is its own wallet where one exists, and unassigned otherwise."""

    environ: Mapping[str, str] = field(repr=False)
    name: str = "BANKR_LLM_KEY"
    agents: Mapping[str, str] = field(default_factory=dict)

    def for_seat(self, seat: str) -> SeatCredential:
        return SeatCredential(seat, self.environ.get(self.name, ""),
                              self.agents.get(seat, UNASSIGNED_AGENT), self.name, shared=True)


@dataclass(frozen=True)
class PerAgentKeys:
    """Each seat's own key, from its own account, with its own wallet address."""

    environ: Mapping[str, str] = field(repr=False)
    names: Mapping[str, str] = field(default_factory=dict)  # seat -> variable name
    agents: Mapping[str, str] = field(default_factory=dict)  # seat -> wallet address

    def for_seat(self, seat: str) -> SeatCredential:
        name = self.names[seat]
        return SeatCredential(seat, self.environ.get(name, ""),
                              self.agents.get(seat, UNASSIGNED_AGENT), name, shared=False)


def refuse_spend_authority(credential: SeatCredential, environ: Mapping[str, str]) -> None:
    """Raise unless this seat's key is present and is no credential the analyst role
    may not hold. Checked by value, so a treasurer key under another name is caught."""
    if not credential.key:
        raise SpendAuthorityError(f"{credential.seat}: no key from {credential.source}")
    for forbidden in credentials.CREDENTIALS:
        if credentials.Role.ANALYST in forbidden.used_by:
            continue
        if forbidden.name == credential.variable:
            raise SpendAuthorityError(f"{credential.seat}: {forbidden.name} is the treasurer's")
        value = environ.get(forbidden.name)
        if value and value == credential.key:
            raise SpendAuthorityError(f"{credential.seat}: its key from {credential.source} "
                                      f"is {forbidden.name}'s value")


def child_environment(credential: SeatCredential) -> dict[str, str]:
    """Everything one analyst process may know, built from nothing."""
    return {"PATH": os.environ.get("PATH", os.defpath), "PYTHONPATH": str(SRC),
            analyst.KEY_VARIABLE: credential.key}


@dataclass(frozen=True)
class Settings:
    model: str
    max_tokens: int
    transport_timeout_s: float
    worker_deadline_s: float
    cycle_deadline_s: float
    retry_budget: int
    width: int
    pricing: Mapping[str, str] = field(default_factory=dict)  # the model's listed price
    gateway_url: str = bankr_llm.GATEWAY

    @classmethod
    def from_config(cls) -> "Settings":
        models, cadence = config.load_json("models.json"), config.load_json("cadence.json")
        return cls(model=models["analyst_model"], max_tokens=models["max_output_tokens"],
                   transport_timeout_s=models["transport_timeout_seconds"],
                   worker_deadline_s=models["worker_deadline_seconds"],
                   cycle_deadline_s=cadence["cycle_deadline_seconds"],
                   retry_budget=cadence["retry_budget_per_worker"],
                   width=cadence["max_parallel_workers"],
                   pricing=models["pricing_per_million"][models["analyst_model"]])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class _Events:
    """The cycle's log, one JSON line per step. The page reads it; no secret is in it."""

    def __init__(self, path: Path):
        self.path = path

    def write(self, **event: Any) -> None:
        with self.path.open("a") as log:
            log.write(json.dumps({"at": _now(), **event}, sort_keys=True) + "\n")


def run_cycle(snapshot_path: Path, key_source: KeySource, *, cycle_dir: Path,
              settings: Settings, seats: Sequence[str] | None = None,
              environ: Mapping[str, str] | None = None,
              python: str = sys.executable) -> dict[str, Any]:
    """Fan the seats out on one snapshot and collect every outcome. Raises only
    SpendAuthorityError, and only before anything has started."""
    seats = list(seats or [a["id"] for a in config.load_json("analysts.json")["analysts"]])
    environ = os.environ if environ is None else environ
    held = {seat: key_source.for_seat(seat) for seat in seats}
    for credential in held.values():
        refuse_spend_authority(credential, environ)

    snapshot = snapshot_path.read_bytes()
    cycle_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    (cycle_dir / "results").mkdir(parents=True, exist_ok=True)
    (cycle_dir / "jobs").mkdir(parents=True, exist_ok=True)
    events = _Events(cycle_dir / "events.jsonl")
    slots: dict[str, dict[str, Any]] = {}
    for seat in seats:
        slots[seat] = {"seat": seat, "agent": held[seat].agent, "status": "pending"}
        (cycle_dir / "results" / f"{seat}.json").write_text(json.dumps(slots[seat]) + "\n")
    events.write(event="cycle started", cycle=cycle_id, seats=seats,
                 snapshot=hashlib.sha256(snapshot).hexdigest(),
                 keys={seat: c.source for seat, c in held.items()})

    queue = list(seats)
    running: dict[str, tuple[subprocess.Popen, float]] = {}
    cycle_started = time.monotonic()

    def finish(seat: str, outcome: dict[str, Any]) -> None:
        slots[seat] = outcome
        (cycle_dir / "results" / f"{seat}.json").write_text(
            json.dumps(outcome, indent=1, sort_keys=True) + "\n")
        events.write(event="finished", seat=seat, status=outcome["status"],
                     reason=outcome.get("reason"), attempts=len(outcome.get("attempts") or ()),
                     agent=outcome.get("agent"))

    def collect(seat: str, process: subprocess.Popen, killed: str | None) -> None:
        stderr = (process.stderr.read() if process.stderr else b"").decode(errors="replace")
        path = cycle_dir / "results" / f"{seat}.json"
        try:
            outcome = json.loads(path.read_text())
        except ValueError:
            outcome = {"status": "pending"}
        if killed or outcome.get("status") == "pending":
            outcome = {**outcome, "seat": seat, "agent": held[seat].agent, "status": "failed",
                       "reason": killed or "crashed",
                       "detail": killed and f"killed at the {killed}" or stderr[-600:]}
        key = held[seat].key
        finish(seat, json.loads(json.dumps(outcome).replace(key, "[GATEWAY_KEY]")))

    while queue or running:
        over = time.monotonic() - cycle_started > settings.cycle_deadline_s
        while queue and len(running) < settings.width and not over:
            seat = queue.pop(0)
            job = {"seat": seat, "agent": held[seat].agent,
                   "snapshot_path": str(snapshot_path.resolve()),
                   "snapshot_sha256": hashlib.sha256(snapshot).hexdigest(),
                   "model": settings.model, "max_tokens": settings.max_tokens,
                   "transport_timeout_s": settings.transport_timeout_s,
                   "worker_deadline_s": settings.worker_deadline_s,
                   "retry_budget": settings.retry_budget, "gateway_url": settings.gateway_url,
                   "pricing": dict(settings.pricing),
                   "result_path": str(cycle_dir / "results" / f"{seat}.json")}
            job_path = cycle_dir / "jobs" / f"{seat}.json"
            job_path.write_text(json.dumps(job, indent=1) + "\n")
            process = subprocess.Popen([python, "-m", "fund.agents.analyst", "--job",
                                        str(job_path)], env=child_environment(held[seat]),
                                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            running[seat] = (process, time.monotonic())
            events.write(event="started", seat=seat, agent=held[seat].agent)
        if over:
            for seat in queue:
                finish(seat, {"seat": seat, "agent": held[seat].agent, "status": "failed",
                              "reason": "cycle deadline", "detail": "never started",
                              "attempts": []})
            queue.clear()
        for seat, (process, started) in list(running.items()):
            if process.poll() is not None:
                collect(seat, process, None)
                del running[seat]
            elif over or time.monotonic() - started > settings.worker_deadline_s:
                process.kill()
                process.wait()
                collect(seat, process, "cycle deadline" if over else "worker deadline")
                del running[seat]
        time.sleep(0.05)

    failed = [seat for seat, slot in slots.items() if slot["status"] == "failed"]
    attempts = [a for slot in slots.values() for a in slot.get("attempts") or ()]
    cycle = {"cycle": cycle_id, "snapshot_sha256": hashlib.sha256(snapshot).hexdigest(),
             "seats": slots, "partial": bool(failed), "failed": failed,
             "counts": {status: sum(s["status"] == status for s in slots.values())
                        for status in ("ok", "no_call", "failed")},
             "cost": {**analyst.seat_cost(attempts),
                      "basis": "the sum of every analyst call in the cycle, each from its own "
                               "usage block; a seat killed at its deadline adds calls of "
                               "unknown cost that are not counted here"}}
    (cycle_dir / "cycle.json").write_text(json.dumps(cycle, indent=1, sort_keys=True) + "\n")
    events.write(event="cycle finished", cycle=cycle_id, partial=cycle["partial"],
                 counts=cycle["counts"])
    return cycle
