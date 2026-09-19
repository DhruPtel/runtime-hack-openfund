"""Print a stored report to the terminal, exactly as the model wrote it.

    PYTHONPATH=src python3 -m fund.agents.show <result.json | cycle dir> [--seat SEAT]

It prints the report's text and nothing else. There is no header, no summary,
no reformatting and no truncation, so what is read is what the model returned
and what the record keeps. The only addition is a final newline when the text
has none, so the terminal's prompt starts on its own line.

It prints the reply of the result's last attempt, the one that decided the
outcome, whether the report was accepted or refused. Results from before every
attempt kept its text (2.6's) carry the refused reply as `last_reply_text`, and
that is printed instead.

Given a cycle directory, `--seat` picks the result. With only one result there,
it needs none.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


def reply_text(result: Mapping[str, Any]) -> str | None:
    for attempt in reversed(result.get("attempts") or ()):
        if attempt.get("reply_text"):
            return attempt["reply_text"]
    return result.get("last_reply_text") or result.get("report_text")


def locate(path: Path, seat: str | None) -> Path:
    if path.is_file():
        return path
    results = path / "results"
    if seat is not None:
        return results / f"{seat}.json"
    found = sorted(results.glob("*.json"))
    if len(found) != 1:
        seats = ", ".join(f.stem for f in found) or "none"
        raise SystemExit(f"{path} holds several results ({seats}): name one with --seat")
    return found[0]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fund.agents.show")
    parser.add_argument("path", type=Path, help="a result file, or a cycle directory")
    parser.add_argument("--seat", default=None)
    args = parser.parse_args(argv)
    path = locate(args.path, args.seat)
    result = json.loads(path.read_text())
    text = reply_text(result)
    if not text:
        print(f"{path}: no report text ({result.get('status')}, {result.get('reason')})",
              file=sys.stderr)
        return 1
    sys.stdout.write(text if text.endswith("\n") else text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
