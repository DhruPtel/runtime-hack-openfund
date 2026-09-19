"""Immutable, content-addressed report store (unit 2.7).

Every analyst reply that came back is kept here once, under the sha256 of its
stored bytes. The decision record cites a report by that id, and a buyer can be
handed exactly what the risk agent read: the text the model wrote, byte for byte.
- **Refused replies are kept too,** with their refusals, so the record holds
  every reply that arrived and not only the accepted ones.

**Storage and retrieval only, not a query layer.**
- **`put`** writes a record once and returns its id. The same content gives the
  same id and the same file. Different bytes at an id that exists raise, so
  nothing stored is ever rewritten.
- **`get`** reads a record back and checks that its bytes still hash to its id.
  A changed byte on disk raises rather than being served.
- **`text`** returns the report's text exactly as the model wrote it.

**The encoding follows `core/types.to_canonical`'s rules, for plain mappings:**
sorted keys, no whitespace, UTF-8, no float and no integer past 2**53. The
record holds money only as decimal text.

One JSON file per report, named `<id>.json`, in one directory. Files are enough
for one runner; SQLite is the full version (PLAN §5).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

SCHEMA = "openfund.report/1"
MAX_SAFE_JSON_INT = 2**53 - 1
_ID = re.compile(r"^[0-9a-f]{64}$")


class ReportStoreError(Exception):
    pass


class ImmutableError(ReportStoreError):
    """An id already holds different bytes. Nothing stored is rewritten."""


class TamperedError(ReportStoreError):
    """A stored file no longer hashes to its id."""


class UnknownReport(ReportStoreError, KeyError):
    pass


def _checked(obj: Any) -> Any:
    if obj is None or isinstance(obj, (bool, str)):
        return obj
    if isinstance(obj, float):
        raise TypeError("a float is never stored; write money as decimal text")
    if type(obj) is int:
        if abs(obj) > MAX_SAFE_JSON_INT:
            raise ValueError(f"{obj} exceeds 2**53; store it as text")
        return obj
    if isinstance(obj, (list, tuple)):
        return [_checked(item) for item in obj]
    if isinstance(obj, Mapping):
        if not all(isinstance(key, str) for key in obj):
            raise TypeError("every key is text")
        return {key: _checked(value) for key, value in obj.items()}
    raise TypeError(f"cannot store {type(obj).__name__}")


def encode(record: Mapping[str, Any]) -> bytes:
    """The one byte form of a record. Same record, same bytes, same id."""
    return json.dumps(_checked({**record, "schema": SCHEMA}), sort_keys=True,
                      separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _valid(report_id: str) -> str:
    if not isinstance(report_id, str) or not _ID.match(report_id):
        raise ValueError(f"not a report id: {report_id!r}")
    return report_id


class ReportStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def path(self, report_id: str) -> Path:
        return self.root / f"{_valid(report_id)}.json"

    def put(self, record: Mapping[str, Any]) -> str:
        """Store a record once. Returns its id, the sha256 of its bytes."""
        data = encode(record)
        report_id = hashlib.sha256(data).hexdigest()
        path = self.path(report_id)
        if path.exists():
            if path.read_bytes() != data:
                raise ImmutableError(f"{report_id} already holds different bytes")
            return report_id
        self.root.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(".partial")
        partial.write_bytes(data)
        os.replace(partial, path)  # the id appears only once its bytes are whole
        return report_id

    def get(self, report_id: str) -> dict[str, Any]:
        path = self.path(report_id)
        if not path.exists():
            raise UnknownReport(report_id)
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != report_id:
            raise TamperedError(f"{path} no longer hashes to its id")
        return json.loads(data)

    def text(self, report_id: str) -> str:
        """The report exactly as the model wrote it: what the risk agent reads."""
        return self.get(report_id)["text"]

    def __contains__(self, report_id: str) -> bool:
        return self.path(report_id).exists()
