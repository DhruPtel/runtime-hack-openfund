"""One analyst: brief, call, parse, validate (units 2.3 and 2.4).

**The brief (2.3).** What each seat receives is built from versioned files, not
inline strings:
  - the seat's own file, `briefs/<seat>.v1.md`: its mandate, its vocabulary,
    what to read, and effort guidance. Its question and the questions it leaves
    to the others come from `config/analysts.json` and are written into the
    file's `{question}` and `{not_asked}` markers, so the brief and the config
    cannot drift apart;
  - the part every seat shares, `briefs/analyst.v1.md`: the output contract
    approved at 2.1;
  - the snapshot, as its own bytes, between `SNAPSHOT <sha256> <n> bytes` and
    `END SNAPSHOT`. It is byte-identical for every seat and named by its hash
    (invariant 2);
  - the exact first line the report must begin with.

The system message is the seat's file plus the shared part. The user message is
the snapshot plus the first line.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from fund import config

BRIEFS = Path(__file__).resolve().parent / "briefs"
SHARED_BRIEF = "analyst.v1.md"


@dataclass(frozen=True)
class Brief:
    seat: str
    system: str
    user: str
    files: tuple[str, ...]  # the versioned files it was built from
    snapshot_sha256: str
    header: str  # the first line the report must carry

    @property
    def sha256(self) -> str:
        return hashlib.sha256((self.system + "\x00" + self.user).encode("utf-8")).hexdigest()


def snapshot_section(snapshot: bytes) -> str:
    """The snapshot as every seat receives it: its own bytes, named by their hash."""
    digest = hashlib.sha256(snapshot).hexdigest()
    return f"SNAPSHOT {digest} {len(snapshot)} bytes\n{snapshot.decode('utf-8')}\nEND SNAPSHOT"


def render(seat: str, snapshot: bytes, agent: str, *, analysts: Mapping[str, Any] | None = None,
           briefs: Path = BRIEFS) -> Brief:
    """The brief for one seat on one snapshot. Raises for a seat the config does not
    define or does not give a question: a vague brief is what makes two seats do
    the same work."""
    analysts = config.load_json("analysts.json") if analysts is None else analysts
    entry = next((a for a in analysts["analysts"] if a["id"] == seat), None)
    if entry is None:
        raise KeyError(f"{seat} is not a seat in config/analysts.json")
    if not entry.get("question") or not entry.get("not_asked"):
        raise ValueError(f"{seat} has no question, or no list of the questions it leaves "
                         "to others, in config/analysts.json")
    own = (briefs / entry["brief"]).read_text()
    not_asked = "\n".join(f"- {question}" for question in entry["not_asked"])
    system = (own.replace("{question}", entry["question"]).replace("{not_asked}", not_asked)
              + "\n\n" + (briefs / SHARED_BRIEF).read_text())
    digest = hashlib.sha256(snapshot).hexdigest()
    header = f"REPORT {seat} {agent} {digest}"
    user = (snapshot_section(snapshot)
            + f"\n\nWrite your report now. Its first line must be exactly:\n{header}\n")
    return Brief(seat=seat, system=system, user=user, files=(entry["brief"], SHARED_BRIEF),
                 snapshot_sha256=digest, header=header)
