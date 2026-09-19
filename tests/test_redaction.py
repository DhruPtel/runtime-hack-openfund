"""Unit 0.1 and PLAN §2 invariant 1: every declared credential is masked in logs, by a
denylist derived from the credential table, and the analyst role can load neither
the execution key nor the signing key, under any name."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from fund import config, credentials, redaction
from fund.credentials import Role

# Long enough that masking them cannot shred an unrelated log line, and
# distinctive enough that a partial leak is visible in a failure message.
FAKE_VALUES = {
    "BANKR_KEY_READ": "bk_read_9f4c1ae2d7b84c0391ee6a5d2f8b07c4",
    "BANKR_KEY_EXEC": "bk_exec_51b7e0c3a94d42f8b60c7d1e9a3f5b28",
    "BANKR_LLM_KEY": "bk_llm_e3a7d92f60b14c85af23c7d0b6e918f4",
    "RPC_4663_MAINNET": "https://rpc.example.invalid/v1/6d2f9b4e7a0c15d83fb2e694c7a01d5b",
    "RPC_4663_TESTNET": "https://rpc-test.example.invalid/v1/a1c8f503e29b7d641f0e3b82c95d7604",
    "SIGNING_KEY": "ed25519_7c4b19e0a6d385f2b47c0e91d6a2f835",
}


@pytest.fixture
def credential_env(monkeypatch):
    """Populate the environment with a distinct fake value per declared credential."""
    for credential in credentials.CREDENTIALS:
        assert credential.name in FAKE_VALUES, (
            f"{credential.name} was added to the credential table but this test "
            f"has no fake value for it. Add one to FAKE_VALUES."
        )
        monkeypatch.setenv(credential.name, FAKE_VALUES[credential.name])
    return FAKE_VALUES


@pytest.fixture
def capturing_logger(credential_env):
    """A logger with redaction installed, writing into a list we can inspect."""

    class Capture(logging.Handler):
        def __init__(self):
            super().__init__()
            self.lines: list[str] = []

        def emit(self, record):
            self.lines.append(self.format(record))

    logger = logging.getLogger("test.redaction")
    logger.handlers.clear()
    logger.filters.clear()
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    handler = Capture()
    handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    logger.addHandler(handler)

    redaction.install(logger)
    return logger, handler


# --- the done-condition -----------------------------------------------------

@pytest.mark.parametrize("name", list(FAKE_VALUES))
def test_each_declared_credential_is_masked_in_a_log_line(capturing_logger, name):
    logger, handler = capturing_logger
    value = FAKE_VALUES[name]

    logger.info("calling upstream with token %s now", value)

    output = "\n".join(handler.lines)
    assert value not in output, f"{name} leaked into the log"
    assert f"[REDACTED:{name}]" in output


def test_every_credential_in_the_table_has_a_masked_value(credential_env):
    """The denylist covers the whole table, not a hand-picked subset."""
    redactor = redaction.Redactor()
    assert len(redactor) == len(credentials.CREDENTIALS)

    masked = set(redactor.masked_values)
    for credential in credentials.CREDENTIALS:
        assert FAKE_VALUES[credential.name] in masked


def test_a_new_credential_is_masked_without_touching_the_filter(monkeypatch):
    """Adding a row to the table is sufficient. Nothing else has to change.

    This is the unit 0.1 property. If this test fails, some second list of names
    has crept in somewhere and the redaction path can be outgrown by the
    credential table.
    """
    invented = credentials.Credential(
        name="FUTURE_CREDENTIAL_X",
        used_by=frozenset({Role.TREASURER}),
        purpose="a credential that did not exist when redaction.py was written",
        scope="hypothetical",
    )
    monkeypatch.setattr(
        credentials, "CREDENTIALS", credentials.CREDENTIALS + (invented,)
    )
    secret = "fx_2b9d7e01c6a45f83b0e27d914c6a3e85"
    monkeypatch.setenv("FUTURE_CREDENTIAL_X", secret)

    assert secret not in redaction.Redactor().redact(f"authorization: {secret}")
    assert "[REDACTED:FUTURE_CREDENTIAL_X]" in redaction.Redactor().redact(secret)


# --- the ways a secret actually escapes -------------------------------------

def test_masked_inside_an_exception_traceback(capturing_logger):
    """The hole a filter alone leaves open: the formatter closes it."""
    logger, handler = capturing_logger
    try:
        raise ValueError(f"bad key {FAKE_VALUES['SIGNING_KEY']}")
    except ValueError:
        logger.exception("signing failed")

    output = "\n".join(handler.lines)
    assert FAKE_VALUES["SIGNING_KEY"] not in output
    assert "[REDACTED:SIGNING_KEY]" in output


def test_longer_values_are_masked_before_shorter_prefixes():
    """A credential that is a prefix of another must not leave a tail exposed."""
    redactor = redaction.Redactor(
        {"abc123": "[REDACTED:SHORT]", "abc123456789": "[REDACTED:LONG]"}
    )
    assert redactor.redact("value=abc123456789") == "value=[REDACTED:LONG]"


def test_install_is_idempotent(capturing_logger):
    logger, _ = capturing_logger
    before = len([f for f in logger.filters if isinstance(f, redaction.RedactingFilter)])
    redaction.install(logger)
    redaction.install(logger)
    after = len([f for f in logger.filters if isinstance(f, redaction.RedactingFilter)])
    assert before == after == 1


def test_short_values_are_reported_as_over_masking(monkeypatch):
    for credential in credentials.CREDENTIALS:
        monkeypatch.delenv(credential.name, raising=False)
    monkeypatch.setenv("BANKR_KEY_READ", "xy")
    assert redaction.short_credentials() == ("BANKR_KEY_READ",)
    # Still masked. Safety beats legibility.
    assert "[REDACTED:BANKR_KEY_READ]" in redaction.Redactor().redact("xy")


# --- role scoping (planning/PLAN.md section 2 invariant 1) ---------------------------

def test_analyst_role_cannot_load_execution_or_signing_secrets(credential_env):
    analyst = config.load(Role.ANALYST, install_redaction=False)

    assert analyst.has("BANKR_KEY_READ")
    assert analyst.has("BANKR_LLM_KEY")
    assert not analyst.has("BANKR_KEY_EXEC")
    assert not analyst.has("SIGNING_KEY")

    for forbidden in ("BANKR_KEY_EXEC", "SIGNING_KEY"):
        with pytest.raises(config.CredentialNotPermittedError):
            analyst.secret(forbidden)


def test_analyst_load_refuses_a_key_that_is_really_the_execution_key(
    monkeypatch, credential_env
):
    """The failure the can_transact field cannot catch on its own.

    The table says BANKR_LLM_KEY cannot transact. If its *value* is the
    execution key, that is false, and the analyst process holds spend authority
    under another name. Load must refuse.
    """
    monkeypatch.setenv("BANKR_LLM_KEY", FAKE_VALUES["BANKR_KEY_EXEC"])
    with pytest.raises(config.TransactingCredentialLeakError) as excinfo:
        config.load(Role.ANALYST, install_redaction=False)
    message = str(excinfo.value)
    assert "BANKR_LLM_KEY" in message and "BANKR_KEY_EXEC" in message
    for value in FAKE_VALUES.values():
        assert value not in message


def test_leak_guard_is_silent_when_the_execution_key_is_absent(
    monkeypatch, credential_env
):
    """In the deployed split the analyst environment has no execution key at all."""
    monkeypatch.delenv("BANKR_KEY_EXEC", raising=False)
    analyst = config.load(Role.ANALYST, install_redaction=False)
    assert analyst.has("BANKR_LLM_KEY")


def test_treasurer_role_holds_the_spend_authority(credential_env):
    treasurer = config.load(Role.TREASURER, install_redaction=False)
    assert treasurer.secret("BANKR_KEY_EXEC") == FAKE_VALUES["BANKR_KEY_EXEC"]
    assert treasurer.secret("SIGNING_KEY") == FAKE_VALUES["SIGNING_KEY"]
    with pytest.raises(config.CredentialNotPermittedError):
        treasurer.secret("BANKR_LLM_KEY")


def test_config_repr_never_contains_a_value(credential_env):
    treasurer = config.load(Role.TREASURER, install_redaction=False)
    rendered = repr(treasurer)
    for value in FAKE_VALUES.values():
        assert value not in rendered
    assert "BANKR_KEY_EXEC" in rendered


def test_missing_required_credential_fails_at_load(monkeypatch, credential_env):
    monkeypatch.delenv("SIGNING_KEY", raising=False)
    with pytest.raises(config.MissingCredentialError, match="SIGNING_KEY"):
        config.load(Role.TREASURER, install_redaction=False)
    # ...but inspection without demanding is allowed.
    partial = config.load(Role.TREASURER, require=False, install_redaction=False)
    assert not partial.has("SIGNING_KEY")


def test_audit_reports_credentials_sharing_a_value(monkeypatch, credential_env):
    """A shared value is a paste error, and the report must name it.

    `redacted_value_count` only implies a collision by arithmetic. The names have
    to be stated, because two credentials with one value is how the analyst
    process ends up holding the execution key.
    """
    assert config.audit()["sharing_a_value"] == []

    monkeypatch.setenv("BANKR_LLM_KEY", FAKE_VALUES["BANKR_KEY_EXEC"])
    report = config.audit()
    assert report["sharing_a_value"] == [["BANKR_KEY_EXEC", "BANKR_LLM_KEY"]]
    for value in FAKE_VALUES.values():
        assert value not in repr(report)


def test_audit_reports_names_only(credential_env):
    report = config.audit()
    rendered = repr(report)
    for value in FAKE_VALUES.values():
        assert value not in rendered
    assert set(report["present"]) == set(FAKE_VALUES)
    assert report["absent"] == []


# --- .env parsing -----------------------------------------------------------

def test_env_file_is_parsed_but_never_overrides_the_real_environment(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("BANKR_KEY_READ", "from-real-environment")
    monkeypatch.delenv("BANKR_LLM_KEY", raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# a comment",
                "",
                "BANKR_KEY_READ=from-dotenv-file",
                'BANKR_LLM_KEY="quoted-value"',
                "a line with no equals sign",
            ]
        ),
        encoding="utf-8",
    )

    config.load_environment(env_file)

    import os

    assert os.environ["BANKR_KEY_READ"] == "from-real-environment"
    assert os.environ["BANKR_LLM_KEY"] == "quoted-value"


def test_env_example_declares_every_credential_and_no_values():
    """.env.example must stay in step with the table, and must hold no secrets."""
    example = (config.REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    declared = {
        line.split("=", 1)[0].strip()
        for line in example.splitlines()
        if "=" in line and not line.strip().startswith("#")
    }
    assert declared == set(credentials.names())
    for line in example.splitlines():
        if "=" in line and not line.strip().startswith("#"):
            assert line.split("=", 1)[1].strip() == "", (
                f".env.example must carry no values: {line!r}"
            )


# --- the table itself -------------------------------------------------------

def test_every_credential_belongs_to_at_least_one_role():
    for credential in credentials.CREDENTIALS:
        assert credential.used_by, f"{credential.name} is unreachable by any role"


def test_no_analyst_credential_can_transact():
    """The rule that keeps invariant 1 true when all keys share one account.

    Account-level separation does not exist, so the boundary is per-key toggles.
    A transacting credential reachable by the analyst role would make the role
    scoping decorative and unit 4.12's isolation test unpassable.
    """
    for credential in credentials.CREDENTIALS:
        if credential.can_transact:
            assert credential.used_by == frozenset({Role.TREASURER}), (
                f"{credential.name} can transact but is reachable by "
                f"{sorted(r.value for r in credential.used_by)}"
            )
    for credential in credentials.for_role(Role.ANALYST):
        assert not credential.can_transact, (
            f"{credential.name} is held by the analyst role and can transact"
        )


def test_exactly_one_credential_can_transact():
    """One spend authority. A second transacting key is a plan change, not a config tweak."""
    assert [c.name for c in credentials.transacting()] == ["BANKR_KEY_EXEC"]


def test_role_scoping_survives_a_credential_being_reassigned(monkeypatch, credential_env):
    """A row moved to the analyst role changes what the analyst can load.

    Guards against role checks being satisfied by a cached or hard-coded list
    rather than by reading the table when the role loads.
    """
    original = credentials.by_name("SIGNING_KEY")
    widened = replace(original, used_by=frozenset({Role.ANALYST, Role.TREASURER}))
    patched = tuple(
        widened if c.name == "SIGNING_KEY" else c for c in credentials.CREDENTIALS
    )
    monkeypatch.setattr(credentials, "CREDENTIALS", patched)
    monkeypatch.setattr(config, "CREDENTIALS", patched)

    analyst = config.load(Role.ANALYST, install_redaction=False)
    assert analyst.secret("SIGNING_KEY") == FAKE_VALUES["SIGNING_KEY"]
