"""Log redaction whose denylist is derived from the credential table.

planning/PHASE-0-1.md unit 0.1: "a log filter whose denylist is **derived**
from the credential table rather than hand-written, so adding a credential
cannot create an unredacted path."

The denylist is built by reading every name in ``credentials.CREDENTIALS`` out of
the environment. Nothing here enumerates credential names itself, so a new row in
that table is masked from the moment it exists.

Deliberately, the denylist is built from *all* declared credentials regardless of
process role, while ``config.load()`` only exposes the role-permitted subset. The
two rules point in opposite directions on purpose: the loader is narrow so code
cannot use what it should not have, and the redactor is wide so a value that
reached the process by some other route still cannot be printed. In the deployed
arrangement (unit 4.12) the analyst process's environment holds none of the
treasurer's credentials, and the isolation test proves it.

Coverage and its limits:

  - ``redact()`` masks literal occurrences in any string.
  - ``RedactingFilter`` masks the log message and its arguments.
  - ``RedactingFormatter`` masks the fully formatted record, which is what closes
    the exception-traceback hole a filter alone leaves open.

Not covered, and not claimed: a secret that has been transformed before it is
logged (URL-encoded, base64'd, split across lines, or JSON-escaped). Adapters
must not log raw request bodies; ``adapters/http.py`` (unit 1.3) owns that rule.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable, Mapping

from . import credentials

#: Below this length, a credential value will over-mask: a three-character value
#: would blank every incidental occurrence of those characters in the logs. Such
#: values are still masked -- safety wins -- but ``short_credentials()`` reports
#: them so the operator can see why the logs look shredded.
MIN_SAFE_SECRET_LENGTH = 8


def build_denylist(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Map every declared credential's present value to its mask.

    Derived from ``credentials.CREDENTIALS``. Empty and unset values are skipped:
    there is nothing to mask, and masking the empty string would match
    everywhere.
    """
    env = os.environ if environ is None else environ
    denylist: dict[str, str] = {}
    for credential in credentials.CREDENTIALS:
        value = env.get(credential.name)
        if value:
            denylist[value] = f"[REDACTED:{credential.name}]"
    return denylist


def short_credentials(environ: Mapping[str, str] | None = None) -> tuple[str, ...]:
    """Declared credentials whose value is set but too short to mask cleanly."""
    env = os.environ if environ is None else environ
    return tuple(
        c.name
        for c in credentials.CREDENTIALS
        if 0 < len(env.get(c.name, "")) < MIN_SAFE_SECRET_LENGTH
    )


class Redactor:
    """Replaces known credential values with named masks.

    Longer values are replaced first so that a credential which contains another
    as a prefix cannot leave the shorter one's tail exposed.
    """

    def __init__(self, denylist: Mapping[str, str] | None = None) -> None:
        source = build_denylist() if denylist is None else denylist
        self._pairs: tuple[tuple[str, str], ...] = tuple(
            sorted(source.items(), key=lambda item: len(item[0]), reverse=True)
        )

    def __len__(self) -> int:
        return len(self._pairs)

    @property
    def masked_values(self) -> tuple[str, ...]:
        return tuple(value for value, _ in self._pairs)

    def redact(self, text: str) -> str:
        for value, mask in self._pairs:
            if value in text:
                text = text.replace(value, mask)
        return text

    def redact_any(self, obj: object) -> object:
        """Redact a value of unknown type, leaving non-strings structurally intact."""
        if isinstance(obj, str):
            return self.redact(obj)
        if isinstance(obj, Mapping):
            return {k: self.redact_any(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple, set)):
            return type(obj)(self.redact_any(v) for v in obj)
        return obj


class RedactingFilter(logging.Filter):
    """Masks the message and arguments of every record passing through."""

    def __init__(self, redactor: Redactor | None = None) -> None:
        super().__init__()
        self.redactor = Redactor() if redactor is None else redactor

    def filter(self, record: logging.LogRecord) -> bool:
        if not len(self.redactor):
            return True
        # Render first, then redact, then clear args: a secret passed as a %s
        # argument is only visible once the message is interpolated.
        try:
            rendered = record.getMessage()
        except Exception:  # pragma: no cover - a broken format string is not ours to fix
            return True
        redacted = self.redactor.redact(rendered)
        if redacted != rendered:
            record.msg = redacted
            record.args = ()
        if record.exc_text:
            record.exc_text = self.redactor.redact(record.exc_text)
        return True


class RedactingFormatter(logging.Formatter):
    """Masks the final formatted record, tracebacks included.

    Wraps another formatter so an existing handler's format string survives.
    """

    def __init__(
        self,
        inner: logging.Formatter | None = None,
        redactor: Redactor | None = None,
    ) -> None:
        super().__init__()
        self.inner = inner if inner is not None else logging.Formatter()
        self.redactor = Redactor() if redactor is None else redactor

    def format(self, record: logging.LogRecord) -> str:
        return self.redactor.redact(self.inner.format(record))


def install(
    logger: logging.Logger | None = None,
    redactor: Redactor | None = None,
) -> Redactor:
    """Attach redaction to a logger and every handler it currently owns.

    Idempotent: calling it twice does not double-wrap. Returns the redactor so a
    caller can report how many values are being masked without printing them.
    """
    target = logging.getLogger() if logger is None else logger
    active = Redactor() if redactor is None else redactor

    if not any(isinstance(f, RedactingFilter) for f in target.filters):
        target.addFilter(RedactingFilter(active))

    for handler in target.handlers:
        if isinstance(handler.formatter, RedactingFormatter):
            continue
        handler.setFormatter(RedactingFormatter(handler.formatter, active))

    return active


def redact(text: str, denylist: Iterable[tuple[str, str]] | None = None) -> str:
    """Convenience wrapper for one-off redaction of a string."""
    if denylist is None:
        return Redactor().redact(text)
    return Redactor(dict(denylist)).redact(text)
