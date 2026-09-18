"""Test-suite isolation from the operator's real environment.

`make test` promises no network and no credentials, and that promise has to hold
on a machine where `.env` exists and is full. `config.load_environment` reads
that file by default, so without this a test that deletes a credential from the
environment would find it silently restored from disk — and the suite would be
exercising real secrets.

Pointing `ENV_FILE` at a path that cannot exist, for every test, makes the
isolation structural rather than something each test has to remember.
"""

from __future__ import annotations

import pytest

from fund import config


@pytest.fixture(autouse=True)
def isolate_from_real_env_file(monkeypatch, tmp_path_factory):
    absent = tmp_path_factory.mktemp("no-env") / "absent.env"
    monkeypatch.setattr(config, "ENV_FILE", absent)
    return absent
