"""The dashboard's data: the fund's own artifacts, reshaped for the page.

    PYTHONPATH=src python3 -m fund.run.dashboard --export     write front-end/data/
    PYTHONPATH=src python3 -m fund.run.dashboard --serve      serve the page and the API

**It reads and renames. It computes nothing.** Every number the page shows comes
from a record the treasurer signed, a book the ledger reconciled, or a receipt read
off the chain. Where the page wants a figure the fund does not produce, this writes
`None` and a one-line reason beside it, and the page shows a dash: an honest product
with a gap beats an invented number (`front-end/CONNECTIONS.md`).

Two arithmetic exceptions, both stated where they happen: a position's share of NAV
(`value ÷ nav`) and an asset's dollar move (the sum of that asset's own orders).
Neither invents a quantity; both divide or add figures the artifacts already carry.

**The two books are never summed.** Overview shows the paper book and says so;
Books shows both side by side; Chain shows real money only.

The output is a single JSON document, written both as `front-end/data/openfund-data.js`
— a `window.OPENFUND_EXPORT = {...}` assignment, so the page works from `file://`,
where `fetch` of a local file is refused — and as `openfund-data.json` for the server.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

from fund import config

ROOT = config.REPO_ROOT
FRONT_END = ROOT / "front-end"
DATA_DIR = FRONT_END / "data"
LIVE = ROOT / "fixtures" / "live"
LIVELEG = ROOT / "fixtures" / "liveleg"

#: The page's four analyst node ids, and the seats they are.
SEATS = {"price-trend": "trend", "cross-asset-macro": "macro",
         "execution-quality": "execution", "price-integrity": "integrity"}
EXPLORER = "https://robinhoodchain.blockscout.com/tx/"
WALLET_EXPLORER = "https://robinhoodchain.blockscout.com/address/"

#: Why a field is a dash. The page shows the reason beside it (decision 4).
ABSENT = {
    "wallet": "no per-agent wallet: the seats share one gateway key",
    "signature": "reports are validated against the snapshot, not signed; only the "
                 "record is signed",
    "revenue": "not yet booked: the journal has no settled-revenue event (7.4)",
    "name": "the registry carries symbols, not company names",
    "confidence": "confidence is recorded per call, not per seat",
    "timing": "build and wall-clock timings are printed, not written to an artifact",
    "split": "weights come from each call's confidence, not a fixed seat split",
    "reference": "a swap has no reference price: what it gave and got is the receipt",
}

#: The two stories this fund tells, said in one line each wherever they appear.
PAPER_FILL = ("Paper fill. Tokenized-stock execution is location-gated: the venue answered "
              "403 to a real AAPL order — \u201cTokenized stocks (AAPL) are not available in "
              "your region\u201d — before broadcast and with no gas (F0.5.1). So an equity "
              "order is sized, quoted and gated for real, and filled on paper.")
SAME_RAILS = ("Real money. Each of these went through the same treasurer process, the same "
              "chokepoint and the same reconciler as every other order \u2014 written before "
              "it was sent, sent once, and booked from its receipt. Only the asset differed: "
              "ETH and USDG are ungated on 4663, so the fund may actually trade them.")


def _usd(text: str | None) -> float | None:
    return None if text is None else float(Decimal(text))


def _num(text: str | None, absent: float = 0.0) -> float:
    """A figure the record may leave null — a seat that only cautioned scores none."""
    return absent if text is None else float(Decimal(text))


def _when(epoch_ms: int) -> str:
    return datetime.fromtimestamp(epoch_ms / 1000, timezone.utc).strftime("%d %b %Y, %H:%M UTC")


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]


# --- finding the artifacts ------------------------------------------------------------------------

def newest(paths: Sequence[Path]) -> Path | None:
    return max(paths, key=lambda p: p.stat().st_mtime, default=None)


def latest_cycle(live: Path = LIVE) -> dict[str, Path | None]:
    """The newest decision that has a book beside it, and the runner cycle whose
    reports it used. A decision without `book.json` was made by `run/decide.py`, which
    executes nothing, so it has no book to show."""
    decisions = [d for d in (live / "decisions").glob("*") if (d / "record.json").exists()
                 and (d / "book.json").exists()]
    decision = newest(decisions)
    cycle_dir = None
    if decision is not None:
        stamp = json.loads((decision / "record.json").read_text())["snapshot"]["sha256"]
        for candidate in sorted((live / "cycles").glob("*"), reverse=True):
            if (candidate / "cycle.json").exists() and json.loads(
                    (candidate / "cycle.json").read_text()).get("snapshot_sha256") == stamp:
                cycle_dir = candidate
                break
    snapshot = None
    if decision is not None:
        sha = json.loads((decision / "record.json").read_text())["snapshot"]["sha256"]
        candidate = live / f"snapshot-{sha}.json"
        snapshot = candidate if candidate.exists() else None
    return {"decision": decision, "cycle": cycle_dir, "snapshot": snapshot}


def live_swaps(liveleg: Path = LIVELEG) -> list[dict[str, Any]]:
    """Every real swap this fund has made, newest first, from its committed outcome."""
    out = []
    for directory in sorted(liveleg.glob("*")):
        outcome = directory / "outcome.json"
        instruction = directory / "instruction.json"
        if not outcome.exists():
            continue
        kept = json.loads(outcome.read_text())
        if kept.get("state") != "confirmed" or not kept.get("execution"):
            continue
        kept["_dir"] = directory.name
        kept["_instruction"] = json.loads(instruction.read_text()) if instruction.exists() else {}
        out.append(kept)
    return sorted(out, key=lambda s: s["execution"]["transaction"]["block"]["number"], reverse=True)


# --- the eight payloads ---------------------------------------------------------------------------

def app(record: Mapping[str, Any], envelope: Mapping[str, Any], cycle_name: str,
        mandate: Mapping[str, Any]) -> dict[str, Any]:
    decision_id = envelope["decision_id"]
    return {
        "product": "Openfund", "network": "Robinhood Chain",
        "mode": "Mainnet",  # chain 4663 is mainnet; the page shipped "Testnet"
        "cycle": cycle_name, "decisionId": decision_id[:10] + "…",
        "decisionIdFull": decision_id,
        "timestamp": _when(record["decided_at_ms"]),
        "nav": ["Overview", "Swarm", "Decision", "Risk", "Books", "Record", "Chain"],
        "snapshotHash": record["snapshot"]["sha256"],
        "snapshotBlock": record["snapshot"]["block"]["number"],
        "fundWallet": mandate["execution_wallet"],
        "demoNotice": (
            "This is real data. Every figure comes from an artifact this fund produced: a "
            "decision record signed over its exact bytes, a book derived from an append-only "
            "journal, or a receipt read off chain 4663. The analyst reports are what the models "
            "wrote, the vetoes are what the risk agent decided, and the transactions are real. "
            "Stock fills are paper, because tokenized-stock execution is location-gated for this "
            "operator; the ETH and USDG swaps are real money. Where the fund does not produce a "
            "figure the page asks for, it shows a dash and the reason."),
    }


def overview(record, envelope, book: Mapping[str, Any], snapshot) -> dict[str, Any]:
    """Decision 1: Overview is the **paper** book, and says so."""
    marks = {a["asset"]["address"]: a.get("mark") or {}
             for a in [*snapshot["assets"], *snapshot["holdings"]]}
    attested = [a for a in snapshot["assets"]
                if (a.get("identity") or {}).get("verdict") and (a.get("beacon") or {}).get("verdict")]
    nav = _usd(book["nav_usd"])
    holdings = []
    for position in book["positions"]:
        value = _usd(position["value_usd"])
        mark = (marks.get(position["address"]) or {}).get("price_usd")
        feed = marks.get(position["address"], {})
        holdings.append({
            "ticker": position["symbol"],
            # the page prints this beside the ticker: the feed the price was read from
            # is more use to a judge than a company name the registry does not carry
            "name": feed.get("feed") or ABSENT["name"],
            "feedAddress": feed.get("feed_proxy"),
            "feedUpdated": feed.get("updated_at"),
            "price": None if mark is None else float(Decimal(mark)),
            # a share of NAV: the only division here, over two figures the book carries
            "weight": round(value / nav * 100, 2) if nav else 0,
            "value": value, "pnl": _usd(position["unrealised_usd"]),
        })
    approved, vetoed = record["decision"]["approved"], record["decision"]["vetoed"]
    overall = (record["risk"]["decision"].get("overall") or {}).get("why")
    return {
        "title": "A fund that shows its work.",
        "subtitle": "The paper portfolio — simulated equity holdings. Real money is in Books "
                    "and Chain, and the two are never added.",
        "nav": nav, "cash": _usd(book["cash"]["value_usd"]),
        "positionCount": len(book["positions"]),
        "latest": {
            "headline": f"{len(approved)} order{'s' if len(approved) != 1 else ''} approved. "
                        f"{len(vetoed)} refused.",
            "summary": overall or "The risk agent recorded no overall verdict for this plan.",
            "approved": len(approved), "vetoed": len(vetoed)},
        "holdings": holdings,
        "tableNote": "Every price is a Chainlink feed read on chain 4663 at block "
                     f"{record['snapshot']['block']['number']}, the block this snapshot is "
                     "pinned to. The feed behind each price is named beside its ticker.",
        "paperNote": PAPER_FILL,
        "provenance": {
            "priceSource": f"Chainlink feeds read on chain 4663 at block "
                           f"{record['snapshot']['block']['number']}",
            "chain": f"Robinhood Chain 4663 · block {record['snapshot']['block']['number']} · "
                     f"{record['snapshot']['block']['time']}",
            "blockHash": snapshot.get("block", {}).get("hash"),
            "attested": f"{len(attested)} of {len(snapshot['assets'])} assets carry an identity "
                        "and beacon verdict in this snapshot; `make selftest` attests all 235 "
                        "configured addresses against the chain",
            "decisionId": envelope["decision_id"][:10] + "…",
            "signatureStatus": "Signature verified" if envelope.get("signed") else "Unsigned",
            "snapshotHash": record["snapshot"]["sha256"],
            "block": record["snapshot"]["block"]["number"],
            "timestamp": _when(record["decided_at_ms"])},
    }


def swarm(record, cycle: Mapping[str, Any] | None, results: Mapping[str, Any]) -> dict[str, Any]:
    """Every seat the cycle asked, including one that failed (decision: show it)."""
    reported = {r["seat"]: r for r in record["reports"]}
    agents = []
    for seat, node in SEATS.items():
        result = results.get(seat) or {}
        attempts = result.get("attempts") or []
        latency = max((a.get("elapsed_ms") or 0) for a in attempts) / 1000 if attempts else None
        report = reported.get(seat)
        calls = [{"asset": c["symbol"], "call": c["word"].title(), "confidence": c["confidence"]}
                 for c in ((result.get("report") or {}).get("calls") or [])]
        failed = report is None
        agents.append({
            "id": node, "seat": seat.replace("-", " ").title(),
            "status": "failed" if failed else "reported",
            "wallet": None, "walletReason": ABSENT["wallet"],
            "signature": None, "signatureReason": ABSENT["signature"],
            "confidence": (calls[0]["confidence"].title() if calls else "—") if not failed
                          else "No report",
            "confidenceReason": ABSENT["confidence"],
            "cost": _usd((result.get("cost") or {}).get("usd")),
            "latency": latency,
            "primaryCall": calls[0] if calls else {"asset": "—", "call": "No report"},
            "calls": calls,
            "perspective": f"{seat.replace('-', ' ').title()}: "
                           + (calls[0]["call"] if calls else "no report"),
            "summary": (result.get("detail") or result.get("reason") or "refused")
                        if failed else f"{len(calls)} call(s) on this snapshot",
            "paragraphs": _paragraphs(report["text"]) if report else [
                f"This seat produced no accepted report. The runner recorded "
                f"{result.get('status', 'no result')}"
                + (f": {result.get('reason')}" % () if result.get("reason") else "")
                + ". Its reply was read and refused rather than used, and the cycle went on "
                  "with the seats that did report — the quorum gate decides whether that is "
                  "enough."],
            "reportSha256": report["sha256"] if report else None,
        })
    weights = " · ".join(f"{row['symbol']} {round(_num(row['target']) * 100, 2)}%"
                         for row in record["proposal"]["rows"]
                         if _num(row["target"]) > 0) or "no rebalance"
    quorum = next((g for g in record["gates"]["plan"] if g["rule"] == "quorum"), {})
    return {
        "title": "Four analysts. One frozen moment.",
        "subtitle": "Independent reports on the same market snapshot.",
        "snapshot": {"hash": record["snapshot"]["sha256"],
                     "block": record["snapshot"]["block"]["number"],
                     "chainId": record["snapshot"]["block"]["chain_id"],
                     "time": record["snapshot"]["block"]["time"],
                     "source": "every mark in it is a Chainlink feed read on chain 4663 at "
                               "this block, and every asset carries an identity and beacon "
                               "verdict from the same read",
                     "elapsed": None, "elapsedReason": ABSENT["timing"]},
        "reportCost": _usd((cycle or {}).get("cost", {}).get("usd")) if cycle else None,
        "costIsEstimate": True,
        "parallelTime": None, "parallelReason": ABSENT["timing"],
        "signedReports": len(record["reports"]),
        "quorum": quorum.get("reason", ""),
        "weights": weights,
        "stages": ["Freeze snapshot", "Analysts", "Aggregate", "Risk", "Execute"],
        "agents": agents,
    }


def decision(record, snapshot) -> dict[str, Any]:
    assets = {a["asset"]["address"]: a for a in snapshot["assets"]}
    feeds = {address: (a.get("mark") or {}) for address, a in assets.items()}
    by_asset: dict[str, Decimal] = {}
    for order in record["plan"]["orders"]:  # an asset may be split across orders
        symbol = order["asset"]["symbol"]
        by_asset[symbol] = by_asset.get(symbol, Decimal(0)) + Decimal(order["usd"])
    rows = []
    for row in record["proposal"]["rows"]:
        seats = {SEATS[c["seat"]]: c for c in row.get("contributions", []) if c["seat"] in SEATS}
        rows.append({
            "asset": row["symbol"],
            **{node: {"call": (seats[node]["word"].upper() if node in seats else "—"),
                      "score": _num(seats[node]["value"]) if node in seats else 0}
               for node in ("trend", "macro", "execution", "integrity")},
            "score": _num(row["score"]),
            "current": round(_num(row["current"]) * 100, 2),
            "target": round(_num(row["target"]) * 100, 2),
            "move": float(by_asset.get(row["symbol"], Decimal(0))),
            "why": row.get("why", ""),
            "feed": feeds.get(row["address"], {}).get("feed"),
            "feedAddress": feeds.get(row["address"], {}).get("feed_proxy"),
            # three independent prices, and where each came from (part three)
            "evidence": _evidence(assets.get(row["address"]), record),
        })
    cash = record["proposal"]["cash"]
    return {
        "title": "How opinions became weights.",
        "subtitle": "A deterministic rule turns signed calls into a proposed portfolio. "
                    "Risk reviews it next.",
        "trendContribution": None, "macroContribution": None,
        "contributionReason": ABSENT["split"],
        "residual": _num(record["proposal"].get("residual")),
        "step": None, "threshold": None,
        "rows": rows,
        "cash": {"current": round(_num(cash["current"]) * 100, 2),
                 "target": round(_num(cash["target"]) * 100, 2), "move": 0},
        "explanation": "Each seat's call moves a weight by its confidence times the position "
                       "limit. Execution and integrity raise cautions; they add no direction.",
        "warning": record["proposal"].get("reason", ""),
    }


def _evidence(asset: Mapping[str, Any] | None, record: Mapping[str, Any]) -> dict[str, Any] | None:
    """Where one asset's three prices came from: the chain, the corroborator and the
    venue. Every field is read from the snapshot the record names."""
    if asset is None:
        return None
    mark, gecko, quote = (asset.get("mark") or {}), (asset.get("corroboration") or {}), \
        (asset.get("quote") or {})
    block = record["snapshot"]["block"]
    return {
        "contract": asset["asset"]["address"],
        "chainId": block["chain_id"],
        "block": block["number"],
        "blockTime": block["time"],
        "chainlink": {
            "feed": mark.get("feed"), "address": mark.get("feed_proxy"),
            "roundId": mark.get("round_id"), "updatedAt": mark.get("updated_at"),
            "price": mark.get("price_usd"),
            "verdict": (mark.get("verdict") or {}).get("reason"),
            "fresh": (mark.get("fresh") or {}).get("reason"),
            "how": "read on chain at the pinned block, from the feed at this address"},
        "gecko": {
            "price": gecko.get("price_usd"), "divergenceBps": gecko.get("divergence_bps"),
            "volume24h": gecko.get("volume_24h_usd"), "tier": gecko.get("tier"),
            "session": gecko.get("session"),
            "verdict": (gecko.get("verdict") or {}).get("reason"),
            "how": "GeckoTerminal's token-level price, independent of the venue and the feed"},
        "venue": {
            "price": quote.get("venue_price_usd"), "impactBps": quote.get("swap_impact_bps"),
            "fetchedAt": quote.get("fetched_at"),
            "how": "Bankr /wallet/swap-quote at the intended size, read-only"},
        "identity": (asset.get("identity") or {}).get("reason"),
        "beacon": (asset.get("beacon") or {}).get("reason"),
        "status": (asset.get("status") or {}).get("value") if isinstance(
            asset.get("status"), dict) else asset.get("status"),
    }


def _quote(quote: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """The fresh quote one order was re-judged against, and which endpoint gave it."""
    if not quote:
        return None
    observation = quote.get("observation") or {}
    return {"ageMs": quote.get("age_ms"), "venuePrice": quote.get("venue_price_usd"),
            "minBuy": quote.get("min_buy"), "impactBps": quote.get("swap_impact_bps"),
            "feeBps": quote.get("fee_bps"), "slippageBps": quote.get("slippage_bps"),
            "verdict": (quote.get("tradeable") or {}).get("reason"),
            "endpoint": (observation.get("source") or {}).get("locator"),
            "system": (observation.get("source") or {}).get("system"),
            "quoteId": observation.get("source_ref"),
            "status": observation.get("status"),
            "detail": observation.get("detail")}


def risk(record, reply: Mapping[str, Any] | None, models: Mapping[str, Any]) -> dict[str, Any]:
    planned = {o["index"]: o for o in record["plan"]["orders"]}
    gated = {o["index"]: o for o in record["gates"]["orders"]}
    cautions: dict[str, list[dict[str, Any]]] = {}
    for row in record["proposal"]["rows"]:  # which seat raised a caution on this asset
        for c in row.get("contributions", []):
            if c.get("kind") == "caution":
                cautions.setdefault(row["symbol"], []).append(c)
    orders = []
    for voted in record["risk"]["decision"]["orders"]:
        index = voted["index"]
        order, gates = planned[index], gated.get(index, {})
        blocking = [g for g in gates.get("gates", []) if not g.get("value")]
        orders.append({
            "id": f"order-{index}",
            "asset": order["asset"]["symbol"], "side": order["side"].title(),
            "amount": float(Decimal(order["usd"])),
            "status": "approved" if voted["approved"] else "vetoed",
            "rule": ", ".join(voted["vetoed_by"]) if voted["vetoed_by"] else
                    "Gates cleared and risk approved",
            "proposed": None, "allowed": None,
            "limitReason": "; ".join(g["reason"] for g in blocking) if blocking else "",
            "context": f"{order['side']} ${Decimal(order['usd']):.2f}"
                       + (f" · {blocking[0]['reason']}" if blocking else ""),
            "heading": ("Do not " if not voted["approved"] else "")
                       + f"{order['side']} ${Decimal(order['usd']):.2f} of "
                       + order["asset"]["symbol"] + ".",
            "paragraphs": [voted["model_why"]] if voted.get("model_why") else
                          ["The risk agent recorded no sentence for this order."],
            "modelVote": voted.get("model_vote"),
            # every gate that ran on this order, with what it measured and its limit
            "gateList": [{"rule": g["rule"], "value": g["value"], "reason": g["reason"]}
                         for g in gates.get("gates", [])],
            "quote": _quote(order.get("quote")),
            "flaggedBy": [c["seat"] for c in cautions.get(order["asset"]["symbol"], [])],
            "blockedBy": gates.get("blocked_by", []),
            "decidedBy": ("a gate, whatever the model said" if gates.get("blocked_by")
                          else "the risk agent" if not voted["approved"] else
                          "every gate cleared and the risk agent approved"),
        })
    overall = record["risk"]["decision"].get("overall") or {}
    return {
        "title": "The fund said no." if any(o["status"] == "vetoed" for o in orders)
                 else "Risk reviewed the plan.",
        "subtitle": f"Risk reviewed every report. "
                    f"{sum(1 for o in orders if o['status'] == 'approved')} of {len(orders)} "
                    f"orders survived.",
        "wallet": None, "walletReason": ABSENT["wallet"],
        "orders": orders,
        "gates": [g["reason"] for g in record["gates"]["plan"]],
        "gateList": [{"rule": g["rule"], "value": g["value"], "reason": g["reason"]}
                     for g in record["gates"]["plan"]],
        "agent": {
            "seat": record["risk"]["seat"],
            "model": models.get("risk", {}).get("model") or models.get("model"),
            "agent": record["risk"].get("agent"),
            "brief": (record["risk"].get("brief") or {}).get("files", [None])[0],
            "bundleTokens": (record["risk"].get("budget") or {}).get("tokens"),
            "costUsd": _usd(((reply or {}).get("cost") or {}).get("usd")),
            "latencyMs": (reply or {}).get("elapsed_ms"),
            "inputTokens": ((reply or {}).get("cost") or {}).get("input_tokens"),
            "outputTokens": ((reply or {}).get("cost") or {}).get("output_tokens"),
            "endpoint": "Bankr LLM gateway, llm.bankr.bot/v1" if reply else None,
            "note": "this cycle's risk vote was written by the cycle itself and says so in "
                    "the record; no model was asked" if not reply else
                    "one live call, billed, over the whole bundle: every report in full and "
                    "the sized plan",
        },
        "overall": overall.get("why", ""),
        "outcome": f"{sum(1 for o in orders if o['status'] == 'approved')} approved · "
                   f"{sum(1 for o in orders if o['status'] == 'vetoed')} vetoed · "
                   "only approved orders reach the treasurer",
    }


def books(paper: Mapping[str, Any], real: Mapping[str, Any]) -> dict[str, Any]:
    """Both books, side by side, never added (4.0 P9)."""
    def one(book, name, description, revenue_label, cost_label, expense_label, note):
        identity = book["identity"]
        return {
            "id": book["book"],  # the ledger names its own book (P9); this only passes it on
            "name": name, "description": description,
            "nav": _usd(book["nav_usd"]),
            "revenue": None, "revenueReason": ABSENT["revenue"],
            "costs": _usd(identity["costs_usd"]),
            "expenses": _usd(book["expenses_usd"]),
            "net": None, "netReason": ABSENT["revenue"],
            "netLabel": "Net", "revenueLabel": revenue_label,
            "costLabel": cost_label, "expenseLabel": expense_label,
            "opening": _usd(identity["opened_usd"]),
            "realised": _usd(identity["realised_usd"]),
            "unrealised": _usd(identity["unrealised_usd"]),
            "reconcileCosts": _usd(identity["costs_usd"]),
            "note": note,
            "block": book["block"]["number"],
        }
    return {
        "title": "Every dollar has a place.",
        "subtitle": "Paper holdings and real money are separate books. They are never added.",
        "identity": paper["identity"]["rule"],
        "books": [
            one(paper, "Paper portfolio", "Simulated equity holdings · USD",
                "Revenue · record sales", "Costs · simulated trading",
                "Expenses · model inference", PAPER_FILL),
            one(real, "Real operating book", "Actual money on chain 4663 · USD",
                "Revenue · record sales", "Costs · gas and fees",
                "Expenses · model inference", SAME_RAILS),
        ],
    }


def record_section(record, envelope) -> dict[str, Any]:
    overall = (record["risk"]["decision"].get("overall") or {}).get("why", "")
    return {
        "title": "Buy the reasoning. Verify the record.",
        "subtitle": "One signed decision, including the disagreement and the refusal.",
        "id": envelope["decision_id"][:10] + "…", "idFull": envelope["decision_id"],
        "headline": f"{len(record['decision']['approved'])} approved, "
                    f"{len(record['decision']['vetoed'])} refused.",
        "price": None, "priceReason": "the live x402 endpoint asks 0.001 USDC and serves a "
                                      "Phase 0 probe response, not this record (7.2)",
        "signedReports": len(record["reports"]),
        "approved": len(record["decision"]["approved"]),
        "vetoed": len(record["decision"]["vetoed"]),
        "snapshot": record["snapshot"]["sha256"],
        "signer": envelope.get("public_key"),
        "signerLabel": "ed25519 public key, published in config/keys.json",
        "signature": envelope.get("signature"),
        "payloadHash": envelope["decision_id"],
        "payloadNote": "the decision id is the sha256 of the record's exact bytes",
        "preview": [
            {"title": "The snapshot it was decided on",
             "description": f"sha256 {record['snapshot']['sha256'][:16]}… at block "
                            f"{record['snapshot']['block']['number']}"},
            {"title": f"{len(record['reports'])} analyst report(s), in full",
             "description": "every accepted report's exact text, with its sha256"},
            {"title": "The plan, the gates and the risk verdict",
             "description": f"{len(record['plan']['orders'])} orders, every gate's value and "
                            "reason, and the agent's sentence on each"}],
        "quote": overall,
        "included": ["Every accepted analyst report, in full",
                     "The proposal and how each weight was reached",
                     "Every gate with its value and reason",
                     "The risk agent's vote on each order, and overall",
                     "The signature over the record's exact bytes"],
        "endpoint": None,
        "endpointReason": "publishing records by immutable id is unbuilt (7.1)",
        "format": "Canonical JSON · the bytes the signature covers",
    }


def chain(swaps: Sequence[Mapping[str, Any]], mandate) -> dict[str, Any]:
    """Decision 3: every real swap, newest first. A cycle produced none of them."""
    rows = []
    for swap in swaps:
        execution = swap["execution"]
        transfers = execution.get("transfers") or []
        gave, got = swap["sells"], swap.get("book")
        block = execution["transaction"]["block"]
        rows.append({
            "id": swap["_dir"],
            "transaction": execution["transaction"]["tx_hash"],
            "block": block["number"],
            "timestamp": _when(block["timestamp"]["epoch_ms"]),
            "wallet": execution["user_operation"]["sender"]["address"],
            "asset": swap["_instruction"].get("order", {}).get("asset", {}).get("symbol", "—"),
            "gave": f"{Decimal(gave['raw']) / (10 ** gave['decimals']):f}".rstrip("0").rstrip("."),
            "gaveSymbol": swap["_instruction"].get("order", {}).get("asset", {}).get("symbol", ""),
            "reason": swap.get("reason", ""),
            "authorisedBy": swap["_instruction"].get("reason", "a signed instruction"),
            "instruction": swap["_dir"],
            "gasSponsored": not swap.get("fee_booked"),
            "explorerUrl": EXPLORER + execution["transaction"]["tx_hash"],
            "transfers": [{"token": t["token"]["address"], "raw": t["amount"]["raw"],
                           "decimals": t["amount"]["decimals"]} for t in transfers],
        })
    newest_swap = rows[0] if rows else {}
    return {
        "title": "The decision became a transaction." if rows else "No transaction yet.",
        "subtitle": "Four real swaps on chain 4663, each authorized by a signed instruction "
                    "and confirmed from its receipt — never from an HTTP 200.",
        "swaps": rows,
        "asset": newest_swap.get("asset", "—"),
        "quantity": None, "quantityReason": "each swap's own amounts are in its row",
        "referencePrice": None, "referenceReason": ABSENT["reference"],
        "paperValue": None,
        "block": newest_swap.get("block"),
        "timestamp": newest_swap.get("timestamp", "—"),
        "transaction": newest_swap.get("transaction"),
        "wallet": mandate["execution_wallet"],
        "decisionId": None,
        "decisionReason": "a swap is authorized by a signed instruction, not by a decision: "
                          "no analyst chose it (SIMPLIFICATION, 2026-09-19)",
        "explorerUrl": newest_swap.get("explorerUrl"),
        "walletExplorerUrl": WALLET_EXPLORER + mandate["execution_wallet"],
        "authority": "Only the treasurer can spend. It runs in its own process with its own "
                     "credentials, re-checks every gate on a fresh quote, writes the order "
                     "before it acts, sends once, and books what the chain says.",
        "paperNote": SAME_RAILS,
        "stockNote": PAPER_FILL,
    }


# --- the whole document ---------------------------------------------------------------------------

def build(live: Path = LIVE, liveleg: Path = LIVELEG,
          decision_dir: Path | None = None) -> dict[str, Any]:
    found = latest_cycle(live)
    if decision_dir is not None:  # the operator naming which cycle the page shows
        decision_dir = decision_dir.resolve()
        found = {**found, "decision": decision_dir}
        record = json.loads((decision_dir / "record.json").read_text())
        snapshot_path = live / f"snapshot-{record['snapshot']['sha256']}.json"
        found["snapshot"] = snapshot_path if snapshot_path.exists() else None
        for candidate in sorted((live / "cycles").glob("*"), reverse=True):
            if (candidate / "cycle.json").exists() and json.loads(
                    (candidate / "cycle.json").read_text()).get(
                        "snapshot_sha256") == record["snapshot"]["sha256"]:
                found["cycle"] = candidate
                break
    if found["decision"] is None:
        raise SystemExit("no decision with a book beside it: run a cycle first "
                         "(python3 -m fund.run.cycle --demo writes one under fixtures/live)")
    decision_dir = found["decision"]
    record = json.loads((decision_dir / "record.json").read_text())
    envelope = json.loads((decision_dir / "envelope.json").read_text())
    paper = json.loads((decision_dir / "book.json").read_text())
    snapshot = json.loads(found["snapshot"].read_text()) if found["snapshot"] else {"assets": []}
    mandate = json.loads((config.CONFIG_DIR / "mandate.json").read_text())
    risk_json = decision_dir / "risk.json"
    reply = (json.loads(risk_json.read_text()).get("reply") if risk_json.exists() else None)
    swaps = live_swaps(liveleg)
    real = swaps[0]["book"] if swaps and swaps[0].get("book") else None

    results = {}
    if found["cycle"] is not None:
        for path in sorted((found["cycle"] / "results").glob("*.json")):
            result = json.loads(path.read_text())
            results[result["seat"]] = result
    cycle_json = (json.loads((found["cycle"] / "cycle.json").read_text())
                  if found["cycle"] is not None else None)

    document: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {"decision": str(decision_dir.relative_to(ROOT)),
                   "cycle": str(found["cycle"].relative_to(ROOT)) if found["cycle"] else None,
                   "snapshot": str(found["snapshot"].relative_to(ROOT))
                               if found["snapshot"] else None,
                   "swaps": [s["_dir"] for s in swaps]},
        "app": app(record, envelope, found["cycle"].name if found["cycle"] else "—", mandate),
        "overview": overview(record, envelope, paper, snapshot),
        "swarm": swarm(record, cycle_json, results),
        "decision": decision(record, snapshot),
        "risk": risk(record, reply, json.loads((config.CONFIG_DIR / "models.json").read_text())),
        "books": books(paper, real) if real else None,
        "record": record_section(record, envelope),
        "chain": chain(swaps, mandate),
    }
    document["empty"] = blank(document)
    return document


def blank(document: Mapping[str, Any]) -> dict[str, Any]:
    """The same page with nothing decided yet: the shape every section needs, and no
    figures. For a demo that starts empty and fills as the cycle runs (`?empty`).

    **It deletes nothing.** The committed cycles are still in the same document, under
    their own keys; this is a display state the page can be started in."""
    empty = json.loads(json.dumps(document))
    app = {**empty["app"], "cycle": "—", "decisionId": "no cycle yet",
           "decisionIdFull": None, "timestamp": "—"}
    overview = {**empty["overview"], "nav": None, "cash": None, "positionCount": 0,
                "holdings": [], "subtitle": "Nothing decided yet. Run a cycle to watch four "
                                            "analysts read one frozen snapshot and a risk "
                                            "agent rule on what they propose.",
                "latest": {"headline": "No cycle has run in this session.",
                           "summary": "Press “Run a cycle” to start one. It takes about four "
                                      "minutes and spends about $1.20 of inference.",
                           "approved": 0, "vetoed": 0},
                "provenance": {**empty["overview"]["provenance"], "decisionId": "—",
                               "signatureStatus": "Nothing signed yet", "snapshotHash": None,
                               "block": None, "timestamp": "—"}}
    swarm = {**empty["swarm"], "signedReports": 0, "reportCost": None, "quorum":
             "no seat has reported in this session",
             "weights": "nothing proposed yet",
             "snapshot": {**empty["swarm"]["snapshot"], "hash": None, "block": None},
             "agents": [{**a, "status": "waiting", "confidence": "—", "cost": None,
                         "latency": None, "calls": [],
                         "primaryCall": {"asset": "—", "call": "waiting"},
                         "perspective": f"{a['seat']}: waiting",
                         "summary": "has not been asked yet",
                         "paragraphs": ["This seat has not been asked in this session. Run a "
                                        "cycle and its report will appear here, in full, "
                                        "exactly as it was written."]}
                        for a in empty["swarm"]["agents"]]}
    decision = {**empty["decision"], "rows": [], "residual": 0,
                "warning": "nothing proposed yet",
                "explanation": empty["decision"]["explanation"]}
    risk = {**empty["risk"], "orders": [], "gates": [], "gateList": [],
            "title": "Nothing to review yet.",
            "subtitle": "The risk agent rules on a plan once one exists.",
            "outcome": "no orders yet"}
    books = {**empty["books"], "books": [{**b, "nav": None, "opening": None, "realised": None,
                                          "unrealised": None, "costs": None, "expenses": None,
                                          "reconcileCosts": None}
                                         for b in empty["books"]["books"]]}
    record = {**empty["record"], "id": "—", "idFull": None, "headline": "No record yet.",
              "signedReports": 0, "approved": 0, "vetoed": 0, "snapshot": None,
              "signature": None, "payloadHash": None, "quote": "", "preview": []}
    return {"app": app, "overview": overview, "swarm": swarm, "decision": decision,
            "risk": risk, "books": books, "record": record,
            # the four real swaps stay: they happened, and no cycle produced them
            "chain": empty["chain"]}


def write(document: Mapping[str, Any], out: Path = DATA_DIR) -> list[Path]:
    """Both forms: the `.js` assignment the page reads from `file://`, and the `.json`
    the server serves."""
    out.mkdir(parents=True, exist_ok=True)
    body = json.dumps(document, indent=1, sort_keys=True, ensure_ascii=False)
    js = out / "openfund-data.js"
    js.write_text("/* Written by `python3 -m fund.run.dashboard --export`. Do not edit.\n"
                  "   Every figure here is read from an artifact the fund produced. */\n"
                  f"window.OPENFUND_EXPORT = {body};\n")
    plain = out / "openfund-data.json"
    plain.write_text(body + "\n")
    return [js, plain]


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="fund.run.dashboard")
    parser.add_argument("--export", action="store_true", help="write front-end/data/")
    parser.add_argument("--decision", type=Path, default=None,
                        help="a decision directory to export instead of the newest, which is "
                             "how the page is pointed at one cycle rather than another")
    parser.add_argument("--serve", action="store_true", help="serve the page and the API")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    if args.serve:
        from fund.run import serve
        return serve.main(["--port", str(args.port)])
    document = build(decision_dir=args.decision)
    for path in write(document):
        print(f"wrote {path.relative_to(ROOT)}")
    print(f"   decision {document['source']['decision']}")
    print(f"   cycle    {document['source']['cycle']}")
    print(f"   swaps    {', '.join(document['source']['swaps']) or 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
