"""Unit 4.2: a signed decision becomes exactly the orders it approved. H: spend authority.

The record is the exit run's, `fixtures/cycles/20260919T202259Z/decision/`, signed with
the fund's key: six buys approved, two vetoed. S13: it is checked against the key
`config/keys.json` publishes, never the one its envelope names.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fund.core import orders
from fund.core.types import ExecutionMode, Instant, OrderState, from_canonical
from fund.treasurer import intent, mandate, sign

REPO = Path(__file__).resolve().parents[1]
DECISION = REPO / "fixtures" / "cycles" / "20260919T202259Z" / "decision"
RECORD = (DECISION / "record.json").read_bytes()
ENVELOPE = json.loads((DECISION / "envelope.json").read_text())
PUBLISHED = sign.published_key()
MANDATE = mandate.load()
PROVISIONAL = json.loads((DECISION / "config" / "mandate.json").read_text())


def at(iso: str, plus_ms: int = 0) -> Instant:
    return Instant(int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)
                   + plus_ms)


AT = at(MANDATE["approved_at"], 3_600_000)  # an hour into the mandate's term


def listed(record=RECORD, envelope=ENVELOPE, public_key=PUBLISHED, the_mandate=MANDATE, when=AT):
    return intent.intents(record, envelope, public_key=public_key, mandate=the_mandate, at=when)


def test_the_published_key_is_the_one_both_3_8_decisions_were_signed_with():
    assert PUBLISHED.startswith("1c23243531ff47be") and len(PUBLISHED) == 64
    assert ENVELOPE["public_key"] == PUBLISHED


def test_the_exit_runs_six_approved_orders_come_out_in_order_prepared_with_stable_keys():
    record = json.loads(RECORD)
    out = listed()
    indices = [o["index"] for o in record["decision"]["approved"]]
    assert indices == [1, 3, 4, 5, 6, 8] == sorted(indices)
    assert [o.order_id for o in out] == [orders.order_id(ENVELOPE["decision_id"], i) for i in indices]
    assert [o.idempotency_key for o in out] == [orders.idempotency_key(ENVELOPE["decision_id"], i)
                                                for i in indices]
    assert listed() == out  # the same record gives the same orders, the same keys
    planned = {o["index"]: o for o in record["plan"]["orders"]}
    for order, index in zip(out, indices):
        plan = planned[index]
        assert order.state is OrderState.PREPARED and order.mode is ExecutionMode.PAPER
        assert order.sell.asset.address == plan["sell"]["address"]
        assert str(order.sell.raw) == plan["quote"]["observation"]["value"]["sell"]["raw"]
        assert order.buy_asset.address == plan["buy"]["address"]
        recorded = from_canonical(json.dumps(plan["quote"]["observation"]).encode()).value
        assert order.min_buy == recorded.min_buy
        assert order.wallet.address == MANDATE["execution_wallet"]


# --- S13: the published key, and nothing else ---------------------------------------------------

def scratch() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


@pytest.mark.parametrize("case", ["unsigned", "altered", "signed by another key",
                                  "names the published key, signed by another", "nothing published"])
def test_a_record_that_does_not_authorize_against_the_published_key_is_refused(case):
    record, envelope, public_key = RECORD, dict(ENVELOPE), PUBLISHED
    if case == "unsigned":
        envelope = sign.unsigned(RECORD, "constructed")
    elif case == "altered":
        record = RECORD.replace(b'"vetoed_by":["risk"]', b'"vetoed_by":[]', 1)
    elif case == "signed by another key":
        envelope = sign.sign(RECORD, scratch())  # it names its own key
    elif case == "names the published key, signed by another":
        envelope = {**sign.sign(RECORD, scratch()), "public_key": PUBLISHED}
    else:
        public_key = None
    with pytest.raises(intent.IntentError):
        listed(record=record, envelope=envelope, public_key=public_key)


def test_the_signer_checks_against_the_published_key_by_default(tmp_path, capsys):
    record, envelope = DECISION / "record.json", DECISION / "envelope.json"
    assert sign.main(["--verify", str(record), str(envelope)]) == 0
    other = tmp_path / "envelope.json"
    other.write_text(json.dumps(sign.sign(RECORD, scratch())))
    assert sign.main(["--verify", str(record), str(other)]) == 1
    (tmp_path / "config").mkdir()
    assert sign.main(["--verify", str(record), str(envelope), "--config-dir",
                      str(tmp_path / "config")]) == 1
    assert '"authorizes": null' in capsys.readouterr().out.splitlines()[-1]


# --- a fresh mandate -----------------------------------------------------------------------------

def test_a_mandate_not_in_force_refuses_every_order():
    with pytest.raises(intent.IntentError, match="expired at"):
        listed(when=at(MANDATE["expires_at"]))
    with pytest.raises(intent.IntentError, match="approved_by is not an approval"):
        listed(the_mandate=PROVISIONAL)
    with pytest.raises(intent.IntentError, match="revoked"):
        listed(the_mandate={**MANDATE, "revoked": True})
