/* Written by `python3 -m fund.run.dashboard --export`. Do not edit.
   Every figure here is read from an artifact the fund produced. */
window.OPENFUND_EXPORT = {
 "app": {
  "cycle": "20260920T022826Z",
  "decisionId": "41bde62b1f…",
  "decisionIdFull": "41bde62b1f02d552cc94333afd8388de1933205fd476dc5bb120956a13b50589",
  "demoNotice": "This is real data. Every figure comes from an artifact this fund produced: a decision record signed over its exact bytes, a book derived from an append-only journal, or a receipt read off chain 4663. The analyst reports are what the models wrote, the vetoes are what the risk agent decided, and the transactions are real. Stock fills are paper, because tokenized-stock execution is location-gated for this operator; the ETH and USDG swaps are real money. Where the fund does not produce a figure the page asks for, it shows a dash and the reason.",
  "fundWallet": "0x93faecde3c88a713e1edddf417c02c326889a3da",
  "mode": "Mainnet",
  "nav": [
   "Overview",
   "Swarm",
   "Decision",
   "Risk",
   "Books",
   "Record",
   "Chain"
  ],
  "network": "Robinhood Chain",
  "product": "Openfund",
  "snapshotBlock": 67581730,
  "snapshotHash": "9ce2581b88bb4e02c4c7f39df0b621537bd0b8f302ea9568d1cfd5733a950456",
  "timestamp": "20 Sep 2026, 02:29 UTC"
 },
 "books": {
  "books": [
   {
    "block": 67581730,
    "costLabel": "Costs · simulated trading",
    "costs": 0.0,
    "description": "Simulated equity holdings · USD",
    "expenseLabel": "Expenses · model inference",
    "expenses": 0.0,
    "id": "paper",
    "name": "Paper portfolio",
    "nav": 199.9865008799012,
    "net": null,
    "netLabel": "Net",
    "netReason": "not yet booked: the journal has no settled-revenue event (7.4)",
    "note": "Paper fill. Tokenized-stock execution is location-gated: the venue answered 403 to a real AAPL order — “Tokenized stocks (AAPL) are not available in your region” — before broadcast and with no gas (F0.5.1). So an equity order is sized, quoted and gated for real, and filled on paper.",
    "opening": 199.984558,
    "realised": 0.0,
    "reconcileCosts": 0.0,
    "revenue": null,
    "revenueLabel": "Revenue · record sales",
    "revenueReason": "not yet booked: the journal has no settled-revenue event (7.4)",
    "unrealised": 0.0019428799011928053
   },
   {
    "block": 67529959,
    "costLabel": "Costs · gas and fees",
    "costs": 0.0,
    "description": "Actual money on chain 4663 · USD",
    "expenseLabel": "Expenses · model inference",
    "expenses": 0.0,
    "id": "real",
    "name": "Real operating book",
    "nav": 1.2857698971109484,
    "net": null,
    "netLabel": "Net",
    "netReason": "not yet booked: the journal has no settled-revenue event (7.4)",
    "note": "Real money. Each of these went through the same treasurer process, the same chokepoint and the same reconciler as every other order — written before it was sent, sent once, and booked from its receipt. Only the asset differed: ETH and USDG are ungated on 4663, so the fund may actually trade them.",
    "opening": 1.286041228056708,
    "realised": 2.8460790928390258e-05,
    "reconcileCosts": 0.0,
    "revenue": null,
    "revenueLabel": "Revenue · record sales",
    "revenueReason": "not yet booked: the journal has no settled-revenue event (7.4)",
    "unrealised": -0.00029979173668794024
   }
  ],
  "identity": "opened + realised + unrealised - costs = NAV, exactly",
  "subtitle": "Paper holdings and real money are separate books. They are never added.",
  "title": "Every dollar has a place."
 },
 "chain": {
  "asset": "USDG",
  "authority": "Only the treasurer can spend. It runs in its own process with its own credentials, re-checks every gate on a fresh quote, writes the order before it acts, sends once, and books what the chain says.",
  "block": 67532956,
  "decisionId": null,
  "decisionReason": "a swap is authorized by a signed instruction, not by a decision: no analyst chose it (SIMPLIFICATION, 2026-09-19)",
  "explorerUrl": "https://robinhoodchain.blockscout.com/tx/0x871944093e1fbb2bca6ee46aa81aaa522211ae6a086138d990b7c6c7af1f21a0",
  "paperNote": "Real money. Each of these went through the same treasurer process, the same chokepoint and the same reconciler as every other order — written before it was sent, sent once, and booked from its receipt. Only the asset differed: ETH and USDG are ungated on 4663, so the fund may actually trade them.",
  "paperValue": null,
  "quantity": null,
  "quantityReason": "each swap's own amounts are in its row",
  "referencePrice": null,
  "referenceReason": "a swap has no reference price: what it gave and got is the receipt",
  "stockNote": "Paper fill. Tokenized-stock execution is location-gated: the venue answered 403 to a real AAPL order — “Tokenized stocks (AAPL) are not available in your region” — before broadcast and with no gas (F0.5.1). So an equity order is sized, quoted and gated for real, and filled on paper.",
  "subtitle": "Four real swaps on chain 4663, each authorized by a signed instruction and confirmed from its receipt — never from an HTTP 200.",
  "swaps": [
   {
    "asset": "USDG",
    "authorisedBy": "a demonstration of the money path that no analyst chose (planning/SIMPLIFICATION.md, DECISION 2026-09-19)",
    "block": 67532956,
    "explorerUrl": "https://robinhoodchain.blockscout.com/tx/0x871944093e1fbb2bca6ee46aa81aaa522211ae6a086138d990b7c6c7af1f21a0",
    "gasSponsored": true,
    "gave": "0.1",
    "gaveSymbol": "USDG",
    "id": "run2-leg2-usdg-eth",
    "instruction": "run2-leg2-usdg-eth",
    "reason": "0x871944093e1fbb2bca6ee46aa81aaa522211ae6a086138d990b7c6c7af1f21a0: the operation succeeded in block 67532956, 119 confirmations deep; paid 100000 from its Transfer logs, received 38077691442267 from its balance across block 67532956, gas sponsored",
    "timestamp": "20 Sep 2026, 01:04 UTC",
    "transaction": "0x871944093e1fbb2bca6ee46aa81aaa522211ae6a086138d990b7c6c7af1f21a0",
    "transfers": [
     {
      "decimals": 6,
      "raw": "100000",
      "token": "0x5fc5360d0400a0fd4f2af552add042d716f1d168"
     }
    ],
    "wallet": "0x93faecde3c88a713e1edddf417c02c326889a3da"
   },
   {
    "asset": "ETH",
    "authorisedBy": "a demonstration of the money path that no analyst chose (planning/SIMPLIFICATION.md, DECISION 2026-09-19)",
    "block": 67532677,
    "explorerUrl": "https://robinhoodchain.blockscout.com/tx/0x2d5438708b6a14b0b3d18da0b9f0f592f04fad7d8bcac824c63c4328e42123aa",
    "gasSponsored": true,
    "gave": "0.00003",
    "gaveSymbol": "ETH",
    "id": "run2-leg1-eth-usdg",
    "instruction": "run2-leg1-eth-usdg",
    "reason": "0x2d5438708b6a14b0b3d18da0b9f0f592f04fad7d8bcac824c63c4328e42123aa: the operation succeeded in block 67532677, 113 confirmations deep; paid 30000000000000 from its balance across block 67532677, gas sponsored, received 78760 from its Transfer logs; 18000000000 wei the logs do not name (F0.10.4)",
    "timestamp": "20 Sep 2026, 01:03 UTC",
    "transaction": "0x2d5438708b6a14b0b3d18da0b9f0f592f04fad7d8bcac824c63c4328e42123aa",
    "transfers": [
     {
      "decimals": 6,
      "raw": "78760",
      "token": "0x5fc5360d0400a0fd4f2af552add042d716f1d168"
     }
    ],
    "wallet": "0x93faecde3c88a713e1edddf417c02c326889a3da"
   },
   {
    "asset": "USDG",
    "authorisedBy": "a demonstration of the money path that no analyst chose (planning/SIMPLIFICATION.md, DECISION 2026-09-19)",
    "block": 67501988,
    "explorerUrl": "https://robinhoodchain.blockscout.com/tx/0x737e32b4ea091110fa0dc42daf8992c705a5d89edc24c5bdd4fae3553a802a27",
    "gasSponsored": true,
    "gave": "0.1",
    "gaveSymbol": "USDG",
    "id": "leg2-usdg-eth",
    "instruction": "leg2-usdg-eth",
    "reason": "0x737e32b4ea091110fa0dc42daf8992c705a5d89edc24c5bdd4fae3553a802a27: the operation succeeded in block 67501988, 119 confirmations deep; paid 100000 from its Transfer logs, received 38026356590733 from its balance across block 67501988, gas sponsored",
    "timestamp": "20 Sep 2026, 00:12 UTC",
    "transaction": "0x737e32b4ea091110fa0dc42daf8992c705a5d89edc24c5bdd4fae3553a802a27",
    "transfers": [
     {
      "decimals": 6,
      "raw": "100000",
      "token": "0x5fc5360d0400a0fd4f2af552add042d716f1d168"
     }
    ],
    "wallet": "0x93faecde3c88a713e1edddf417c02c326889a3da"
   },
   {
    "asset": "ETH",
    "authorisedBy": "a demonstration of the money path that no analyst chose (planning/SIMPLIFICATION.md, DECISION 2026-09-19)",
    "block": 67501588,
    "explorerUrl": "https://robinhoodchain.blockscout.com/tx/0x9c8ea67dd8c17c9a7315f38ad427f8e0b3852d55b68af463d5f17027d3cfbbfa",
    "gasSponsored": true,
    "gave": "0.00003",
    "gaveSymbol": "ETH",
    "id": "leg1-eth-usdg",
    "instruction": "leg1-eth-usdg",
    "reason": "0x9c8ea67dd8c17c9a7315f38ad427f8e0b3852d55b68af463d5f17027d3cfbbfa: the operation succeeded in block 67501588, 119 confirmations deep; paid 30000000000000 from its balance across block 67501588, gas sponsored, received 78714 from its Transfer logs; 18000000000 wei the logs do not name (F0.10.4)",
    "timestamp": "20 Sep 2026, 00:11 UTC",
    "transaction": "0x9c8ea67dd8c17c9a7315f38ad427f8e0b3852d55b68af463d5f17027d3cfbbfa",
    "transfers": [
     {
      "decimals": 6,
      "raw": "78714",
      "token": "0x5fc5360d0400a0fd4f2af552add042d716f1d168"
     }
    ],
    "wallet": "0x93faecde3c88a713e1edddf417c02c326889a3da"
   }
  ],
  "timestamp": "20 Sep 2026, 01:04 UTC",
  "title": "The decision became a transaction.",
  "transaction": "0x871944093e1fbb2bca6ee46aa81aaa522211ae6a086138d990b7c6c7af1f21a0",
  "wallet": "0x93faecde3c88a713e1edddf417c02c326889a3da",
  "walletExplorerUrl": "https://robinhoodchain.blockscout.com/address/0x93faecde3c88a713e1edddf417c02c326889a3da"
 },
 "decision": {
  "cash": {
   "current": 20.3,
   "move": 0,
   "target": -48.78
  },
  "contributionReason": "weights come from each call's confidence, not a fixed seat split",
  "explanation": "Each seat's call moves a weight by its confidence times the position limit. Execution and integrity raise cautions; they add no direction.",
  "macroContribution": null,
  "residual": 1.0128057479810215e-06,
  "rows": [
   {
    "asset": "SPY",
    "current": 10.24,
    "evidence": {
     "beacon": "resolves to the issuer beacon 0xe10b6f6b275de231345c20d14ab812db62151b00",
     "block": 67581730,
     "blockTime": "2026-09-20T02:26:20Z",
     "chainId": 4663,
     "chainlink": {
      "address": "0x319724394d3a0e3669269846abe664cd621f9f6a",
      "feed": "Robinhood SPY / USD",
      "fresh": "age 137059s, of which 94880s in the closed session inferred for us_equities_24/5 (Sat 00:05:00Z to Sun 23:55:00Z every week): 42179s of open session against heartbeat 86400s + margin 3600s",
      "how": "read on chain at the pinned block, from the feed at this address",
      "price": "761.55079369",
      "roundId": "18446744073709551754",
      "updatedAt": "2026-09-18T12:22:01Z",
      "verdict": "the fresh answer of the feed pinned to this address"
     },
     "contract": "0x117cc2133c37b721f49de2a7a74833232b3b4c0c",
     "gecko": {
      "divergenceBps": "-46.57",
      "how": "GeckoTerminal's token-level price, independent of the venue and the feed",
      "price": "765.1138385285",
      "session": "closed",
      "tier": "above-line",
      "verdict": "closed session: divergence -46.57 bps on $16514085.2928804 of 24h volume is a finding, not a veto",
      "volume24h": "16514085.2928804"
     },
     "identity": "listed in rhj_assets 442718b5843e…",
     "status": "tradeable",
     "venue": {
      "fetchedAt": "2026-09-20T02:27:57.307Z",
      "how": "Bankr /wallet/swap-quote at the intended size, read-only",
      "impactBps": "-3",
      "price": "766.5942490258377"
     }
    },
    "execution": {
     "call": "—",
     "score": 0
    },
    "feed": "Robinhood SPY / USD",
    "feedAddress": "0x319724394d3a0e3669269846abe664cd621f9f6a",
    "integrity": {
     "call": "—",
     "score": 0
    },
    "macro": {
     "call": "—",
     "score": 0
    },
    "move": 0.0,
    "score": 0.0,
    "target": 10.24,
    "trend": {
     "call": "—",
     "score": 0
    },
    "why": "no seat mentioned it: kept"
   },
   {
    "asset": "AMZN",
    "current": 2.57,
    "evidence": {
     "beacon": "resolves to the issuer beacon 0xe10b6f6b275de231345c20d14ab812db62151b00",
     "block": 67581730,
     "blockTime": "2026-09-20T02:26:20Z",
     "chainId": 4663,
     "chainlink": {
      "address": "0xd5a1508ced74c084ebf3cbe853e2c968fb2a651c",
      "feed": "Robinhood AMZN / USD",
      "fresh": "age 122828s, of which 94880s in the closed session inferred for us_equities_24/5 (Sat 00:05:00Z to Sun 23:55:00Z every week): 27948s of open session against heartbeat 86400s + margin 3600s",
      "how": "read on chain at the pinned block, from the feed at this address",
      "price": "253.863",
      "roundId": "18446744073709552408",
      "updatedAt": "2026-09-18T16:19:12Z",
      "verdict": "the fresh answer of the feed pinned to this address"
     },
     "contract": "0x12f190a9f9d7d37a250758b26824b97ce941bf54",
     "gecko": {
      "divergenceBps": "-367.53",
      "how": "GeckoTerminal's token-level price, independent of the venue and the feed",
      "price": "263.5491074947",
      "session": "closed",
      "tier": "above-line",
      "verdict": "closed session: divergence -367.53 bps on $1030913.97422667 of 24h volume is a finding, not a veto",
      "volume24h": "1030913.97422667"
     },
     "identity": "listed in rhj_assets 442718b5843e…",
     "status": "tradeable",
     "venue": {
      "fetchedAt": "2026-09-20T02:27:58.208Z",
      "how": "Bankr /wallet/swap-quote at the intended size, read-only",
      "impactBps": "10",
      "price": "254.77814090145975"
     }
    },
    "execution": {
     "call": "—",
     "score": 0
    },
    "feed": "Robinhood AMZN / USD",
    "feedAddress": "0xd5a1508ced74c084ebf3cbe853e2c968fb2a651c",
    "integrity": {
     "call": "PROCEED",
     "score": 0.0
    },
    "macro": {
     "call": "—",
     "score": 0
    },
    "move": 0.0,
    "score": 0.0,
    "target": 2.57,
    "trend": {
     "call": "—",
     "score": 0
    },
    "why": "caution with no direction call: kept"
   },
   {
    "asset": "GME",
    "current": 15.49,
    "evidence": {
     "beacon": "resolves to the issuer beacon 0xe10b6f6b275de231345c20d14ab812db62151b00",
     "block": 67581730,
     "blockTime": "2026-09-20T02:26:20Z",
     "chainId": 4663,
     "chainlink": {
      "address": "0x27c71df6a64fb476468edf256cf72c038bab5b67",
      "feed": "Robinhood GME / USD",
      "fresh": "age 108454s, of which 94880s in the closed session inferred for us_equities_24/5 (Sat 00:05:00Z to Sun 23:55:00Z every week): 13574s of open session against heartbeat 86400s + margin 3600s",
      "how": "read on chain at the pinned block, from the feed at this address",
      "price": "22.55175",
      "roundId": "18446744073709552466",
      "updatedAt": "2026-09-18T20:18:46Z",
      "verdict": "the fresh answer of the feed pinned to this address"
     },
     "contract": "0x1b0e319c6a659f002271b69db8a7df2f911c153e",
     "gecko": {
      "divergenceBps": "41.95",
      "how": "GeckoTerminal's token-level price, independent of the venue and the feed",
      "price": "22.4575429674",
      "session": "closed",
      "tier": "above-line",
      "verdict": "closed session: divergence 41.95 bps on $1249574.91933192 of 24h volume is a finding, not a veto",
      "volume24h": "1249574.91933192"
     },
     "identity": "listed in rhj_assets 442718b5843e…",
     "status": "tradeable",
     "venue": {
      "fetchedAt": "2026-09-20T02:27:59.671Z",
      "how": "Bankr /wallet/swap-quote at the intended size, read-only",
      "impactBps": "8",
      "price": "22.498903713602765"
     }
    },
    "execution": {
     "call": "—",
     "score": 0
    },
    "feed": "Robinhood GME / USD",
    "feedAddress": "0x27c71df6a64fb476468edf256cf72c038bab5b67",
    "integrity": {
     "call": "—",
     "score": 0
    },
    "macro": {
     "call": "—",
     "score": 0
    },
    "move": 5.48999908444017,
    "score": 0.75,
    "target": 25.0,
    "trend": {
     "call": "BUY",
     "score": 0.75
    },
    "why": "buy: raised by 0.0951116939592250405983314115, capped at the position limit"
   },
   {
    "asset": "SPCX",
    "current": 10.29,
    "evidence": {
     "beacon": "resolves to the issuer beacon 0xe10b6f6b275de231345c20d14ab812db62151b00",
     "block": 67581730,
     "blockTime": "2026-09-20T02:26:20Z",
     "chainId": 4663,
     "chainlink": {
      "address": "0xb265810950ba6c5c0ff821c9963014a56fd8bffb",
      "feed": "Robinhood SPCX / USD",
      "fresh": "age 98305s, of which 94880s in the closed session inferred for us_equities_24/5 (Sat 00:05:00Z to Sun 23:55:00Z every week): 3425s of open session against heartbeat 86400s + margin 3600s",
      "how": "read on chain at the pinned block, from the feed at this address",
      "price": "152.82485",
      "roundId": "18446744073709554894",
      "updatedAt": "2026-09-18T23:07:55Z",
      "verdict": "the fresh answer of the feed pinned to this address"
     },
     "contract": "0x4a0e65a3eccec6dbe60ae065f2e7bb85fae35eea",
     "gecko": {
      "divergenceBps": "-5.35",
      "how": "GeckoTerminal's token-level price, independent of the venue and the feed",
      "price": "152.9066536994",
      "session": "closed",
      "tier": "above-line",
      "verdict": "closed session: divergence -5.35 bps on $41466485.6008856 of 24h volume is a finding, not a veto",
      "volume24h": "41466485.6008856"
     },
     "identity": "listed in rhj_assets 442718b5843e…",
     "status": "tradeable",
     "venue": {
      "fetchedAt": "2026-09-20T02:28:04.684Z",
      "how": "Bankr /wallet/swap-quote at the intended size, read-only",
      "impactBps": "6",
      "price": "153.0370848481095"
     }
    },
    "execution": {
     "call": "—",
     "score": 0
    },
    "feed": "Robinhood SPCX / USD",
    "feedAddress": "0xb265810950ba6c5c0ff821c9963014a56fd8bffb",
    "integrity": {
     "call": "—",
     "score": 0
    },
    "macro": {
     "call": "—",
     "score": 0
    },
    "move": 0.0,
    "score": 0.0,
    "target": 10.29,
    "trend": {
     "call": "—",
     "score": 0
    },
    "why": "no seat mentioned it: kept"
   },
   {
    "asset": "PLTR",
    "current": 0.0,
    "evidence": {
     "beacon": "resolves to the issuer beacon 0xe10b6f6b275de231345c20d14ab812db62151b00",
     "block": 67581730,
     "blockTime": "2026-09-20T02:26:20Z",
     "chainId": 4663,
     "chainlink": {
      "address": "0x820abedff239034956b7a9d2f0a331f9f075eb4c",
      "feed": "Robinhood PLTR / USD",
      "fresh": "age 109686s, of which 94880s in the closed session inferred for us_equities_24/5 (Sat 00:05:00Z to Sun 23:55:00Z every week): 14806s of open session against heartbeat 86400s + margin 3600s",
      "how": "read on chain at the pinned block, from the feed at this address",
      "price": "177.6031",
      "roundId": "18446744073709553580",
      "updatedAt": "2026-09-18T19:58:14Z",
      "verdict": "the fresh answer of the feed pinned to this address"
     },
     "contract": "0x894e1ec2d74ffe5aef8dc8a9e84686accb964f2a",
     "gecko": {
      "divergenceBps": "170.8",
      "how": "GeckoTerminal's token-level price, independent of the venue and the feed",
      "price": "174.6206548039",
      "session": "closed",
      "tier": "above-line",
      "verdict": "closed session: divergence 170.8 bps on $2351431.61915233 of 24h volume is a finding, not a veto",
      "volume24h": "2351431.61915233"
     },
     "identity": "listed in rhj_assets 442718b5843e…",
     "status": "tradeable",
     "venue": {
      "fetchedAt": "2026-09-20T02:28:10.755Z",
      "how": "Bankr /wallet/swap-quote at the intended size, read-only",
      "impactBps": "11",
      "price": "177.68465886366494"
     }
    },
    "execution": {
     "call": "CAUTION",
     "score": 0.5
    },
    "feed": "Robinhood PLTR / USD",
    "feedAddress": "0x820abedff239034956b7a9d2f0a331f9f075eb4c",
    "integrity": {
     "call": "PROCEED",
     "score": 0.0
    },
    "macro": {
     "call": "—",
     "score": 0
    },
    "move": 0.0,
    "score": 0.0,
    "target": 0.0,
    "trend": {
     "call": "—",
     "score": 0
    },
    "why": "caution with no direction call: kept"
   },
   {
    "asset": "USO",
    "current": 10.31,
    "evidence": {
     "beacon": "resolves to the issuer beacon 0xe10b6f6b275de231345c20d14ab812db62151b00",
     "block": 67581730,
     "blockTime": "2026-09-20T02:26:20Z",
     "chainId": 4663,
     "chainlink": {
      "address": "0x75a9c76ef439e2c7c2e5a34ab105ecfe3766431c",
      "feed": "Robinhood USO / USD",
      "fresh": "age 95748s, of which 94880s in the closed session inferred for us_equities_24/5 (Sat 00:05:00Z to Sun 23:55:00Z every week): 868s of open session against heartbeat 86400s + margin 3600s",
      "how": "read on chain at the pinned block, from the feed at this address",
      "price": "154.54265",
      "roundId": "18446744073709553123",
      "updatedAt": "2026-09-18T23:50:32Z",
      "verdict": "the fresh answer of the feed pinned to this address"
     },
     "contract": "0xa30fa36db767ad9ed3f7a60fc79526fb4d56d344",
     "gecko": {
      "divergenceBps": "52.88",
      "how": "GeckoTerminal's token-level price, independent of the venue and the feed",
      "price": "153.729869344",
      "session": "closed",
      "tier": "above-line",
      "verdict": "closed session: divergence 52.88 bps on $1322222.1281467 of 24h volume is a finding, not a veto",
      "volume24h": "1322222.1281467"
     },
     "identity": "listed in rhj_assets 442718b5843e…",
     "status": "tradeable",
     "venue": {
      "fetchedAt": "2026-09-20T02:28:13.701Z",
      "how": "Bankr /wallet/swap-quote at the intended size, read-only",
      "impactBps": "-5",
      "price": "155.03570070845487"
     }
    },
    "execution": {
     "call": "—",
     "score": 0
    },
    "feed": "Robinhood USO / USD",
    "feedAddress": "0x75a9c76ef439e2c7c2e5a34ab105ecfe3766431c",
    "integrity": {
     "call": "—",
     "score": 0
    },
    "macro": {
     "call": "BUY",
     "score": 0.5
    },
    "move": 7.21999950079403,
    "score": 0.5,
    "target": 22.81,
    "trend": {
     "call": "BUY",
     "score": 0.5
    },
    "why": "buy: raised by 0.125"
   },
   {
    "asset": "AAPL",
    "current": 15.43,
    "evidence": {
     "beacon": "resolves to the issuer beacon 0xe10b6f6b275de231345c20d14ab812db62151b00",
     "block": 67581730,
     "blockTime": "2026-09-20T02:26:20Z",
     "chainId": 4663,
     "chainlink": {
      "address": "0x6b22a786baa607d76728168703a39ea9c99f2cd0",
      "feed": "Robinhood AAPL / USD",
      "fresh": "age 126892s, of which 94880s in the closed session inferred for us_equities_24/5 (Sat 00:05:00Z to Sun 23:55:00Z every week): 32012s of open session against heartbeat 86400s + margin 3600s",
      "how": "read on chain at the pinned block, from the feed at this address",
      "price": "335.3847472",
      "roundId": "18446744073709552261",
      "updatedAt": "2026-09-18T15:11:28Z",
      "verdict": "the fresh answer of the feed pinned to this address"
     },
     "contract": "0xaf3d76f1834a1d425780943c99ea8a608f8a93f9",
     "gecko": {
      "divergenceBps": "11.76",
      "how": "GeckoTerminal's token-level price, independent of the venue and the feed",
      "price": "334.9910055111",
      "session": "closed",
      "tier": "above-line",
      "verdict": "closed session: divergence 11.76 bps on $4155466.8197435 of 24h volume is a finding, not a veto",
      "volume24h": "4155466.8197435"
     },
     "identity": "listed in rhj_assets 442718b5843e…",
     "status": "tradeable",
     "venue": {
      "fetchedAt": "2026-09-20T02:28:15.361Z",
      "how": "Bankr /wallet/swap-quote at the intended size, read-only",
      "impactBps": "8",
      "price": "336.04133058417244"
     }
    },
    "execution": {
     "call": "—",
     "score": 0
    },
    "feed": "Robinhood AAPL / USD",
    "feedAddress": "0x6b22a786baa607d76728168703a39ea9c99f2cd0",
    "integrity": {
     "call": "—",
     "score": 0
    },
    "macro": {
     "call": "—",
     "score": 0
    },
    "move": 5.51999976790854,
    "score": 0.5,
    "target": 25.0,
    "trend": {
     "call": "BUY",
     "score": 0.5
    },
    "why": "buy: raised by 0.0956933188465229404231725592, capped at the position limit"
   },
   {
    "asset": "META",
    "current": 0.0,
    "evidence": {
     "beacon": "resolves to the issuer beacon 0xe10b6f6b275de231345c20d14ab812db62151b00",
     "block": 67581730,
     "blockTime": "2026-09-20T02:26:20Z",
     "chainId": 4663,
     "chainlink": {
      "address": "0x7c38c00c30bee9378381e7b6135d7283356d71b1",
      "feed": "Robinhood META / USD",
      "fresh": "age 109964s, of which 94880s in the closed session inferred for us_equities_24/5 (Sat 00:05:00Z to Sun 23:55:00Z every week): 15084s of open session against heartbeat 86400s + margin 3600s",
      "how": "read on chain at the pinned block, from the feed at this address",
      "price": "666.7615",
      "roundId": "18446744073709552837",
      "updatedAt": "2026-09-18T19:53:36Z",
      "verdict": "the fresh answer of the feed pinned to this address"
     },
     "contract": "0xc0d6457c16cc70d6790dd43521c899c87ce02f35",
     "gecko": {
      "divergenceBps": "-80.64",
      "how": "GeckoTerminal's token-level price, independent of the venue and the feed",
      "price": "672.1818590738",
      "session": "closed",
      "tier": "above-line",
      "verdict": "closed session: divergence -80.64 bps on $5162204.8515142 of 24h volume is a finding, not a veto",
      "volume24h": "5162204.8515142"
     },
     "identity": "listed in rhj_assets 442718b5843e…",
     "status": "tradeable",
     "venue": {
      "fetchedAt": "2026-09-20T02:28:18.508Z",
      "how": "Bankr /wallet/swap-quote at the intended size, read-only",
      "impactBps": "8",
      "price": "672.460343051608"
     }
    },
    "execution": {
     "call": "—",
     "score": 0
    },
    "feed": "Robinhood META / USD",
    "feedAddress": "0x7c38c00c30bee9378381e7b6135d7283356d71b1",
    "integrity": {
     "call": "—",
     "score": 0
    },
    "macro": {
     "call": "—",
     "score": 0
    },
    "move": 7.21999950079403,
    "score": 0.5,
    "target": 12.5,
    "trend": {
     "call": "BUY",
     "score": 0.5
    },
    "why": "buy: raised by 0.125"
   },
   {
    "asset": "INTC",
    "current": 15.36,
    "evidence": {
     "beacon": "resolves to the issuer beacon 0xe10b6f6b275de231345c20d14ab812db62151b00",
     "block": 67581730,
     "blockTime": "2026-09-20T02:26:20Z",
     "chainId": 4663,
     "chainlink": {
      "address": "0x3f390c5c24628ac7c489515402235fead71d1913",
      "feed": "Robinhood INTC / USD",
      "fresh": "age 108919s, of which 94880s in the closed session inferred for us_equities_24/5 (Sat 00:05:00Z to Sun 23:55:00Z every week): 14039s of open session against heartbeat 86400s + margin 3600s",
      "how": "read on chain at the pinned block, from the feed at this address",
      "price": "109.05",
      "roundId": "18446744073709555596",
      "updatedAt": "2026-09-18T20:11:01Z",
      "verdict": "the fresh answer of the feed pinned to this address"
     },
     "contract": "0xc72b96e0e48ecd4dc75e1e45396e26300bc39681",
     "gecko": {
      "divergenceBps": "-164.45",
      "how": "GeckoTerminal's token-level price, independent of the venue and the feed",
      "price": "110.8731992234",
      "session": "closed",
      "tier": "above-line",
      "verdict": "closed session: divergence -164.45 bps on $2768264.40976589 of 24h volume is a finding, not a veto",
      "volume24h": "2768264.40976589"
     },
     "identity": "listed in rhj_assets 442718b5843e…",
     "status": "tradeable",
     "venue": {
      "fetchedAt": "2026-09-20T02:28:19.418Z",
      "how": "Bankr /wallet/swap-quote at the intended size, read-only",
      "impactBps": "11",
      "price": "110.92391337248277"
     }
    },
    "execution": {
     "call": "—",
     "score": 0
    },
    "feed": "Robinhood INTC / USD",
    "feedAddress": "0x3f390c5c24628ac7c489515402235fead71d1913",
    "integrity": {
     "call": "CAUTION",
     "score": 0.5
    },
    "macro": {
     "call": "—",
     "score": 0
    },
    "move": 3.60999925043562,
    "score": 0.25,
    "target": 21.61,
    "trend": {
     "call": "BUY",
     "score": 0.5
    },
    "why": "buy: raised by 0.0625"
   },
   {
    "asset": "NVDA",
    "current": 0.0,
    "evidence": {
     "beacon": "resolves to the issuer beacon 0xe10b6f6b275de231345c20d14ab812db62151b00",
     "block": 67581730,
     "blockTime": "2026-09-20T02:26:20Z",
     "chainId": 4663,
     "chainlink": {
      "address": "0x379ec4f7c378f34a1b47e4f3cbebcbac3e8e9f15",
      "feed": "Robinhood NVDA / USD",
      "fresh": "age 109848s, of which 94880s in the closed session inferred for us_equities_24/5 (Sat 00:05:00Z to Sun 23:55:00Z every week): 14968s of open session against heartbeat 86400s + margin 3600s",
      "how": "read on chain at the pinned block, from the feed at this address",
      "price": "222.44729849",
      "roundId": "18446744073709552677",
      "updatedAt": "2026-09-18T19:55:32Z",
      "verdict": "the fresh answer of the feed pinned to this address"
     },
     "contract": "0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec",
     "gecko": {
      "divergenceBps": "-0.99",
      "how": "GeckoTerminal's token-level price, independent of the venue and the feed",
      "price": "222.4692917325",
      "session": "closed",
      "tier": "above-line",
      "verdict": "closed session: divergence -0.99 bps on $55725071.1313778 of 24h volume is a finding, not a veto",
      "volume24h": "55725071.1313778"
     },
     "identity": "listed in rhj_assets 442718b5843e…",
     "status": "tradeable",
     "venue": {
      "fetchedAt": "2026-09-20T02:28:20.724Z",
      "how": "Bankr /wallet/swap-quote at the intended size, read-only",
      "impactBps": "3",
      "price": "222.88023295455173"
     }
    },
    "execution": {
     "call": "—",
     "score": 0
    },
    "feed": "Robinhood NVDA / USD",
    "feedAddress": "0x379ec4f7c378f34a1b47e4f3cbebcbac3e8e9f15",
    "integrity": {
     "call": "—",
     "score": 0
    },
    "macro": {
     "call": "HOLD",
     "score": 0.0
    },
    "move": 0.0,
    "score": 0.0,
    "target": 0.0,
    "trend": {
     "call": "—",
     "score": 0
    },
    "why": "hold: kept"
   },
   {
    "asset": "QQQ",
    "current": 0.0,
    "evidence": {
     "beacon": "resolves to the issuer beacon 0xe10b6f6b275de231345c20d14ab812db62151b00",
     "block": 67581730,
     "blockTime": "2026-09-20T02:26:20Z",
     "chainId": 4663,
     "chainlink": {
      "address": "0x80901d846d5d7b030f26b480776ee3b29374c2ae",
      "feed": "Robinhood QQQ / USD",
      "fresh": "age 110154s, of which 94880s in the closed session inferred for us_equities_24/5 (Sat 00:05:00Z to Sun 23:55:00Z every week): 15274s of open session against heartbeat 86400s + margin 3600s",
      "how": "read on chain at the pinned block, from the feed at this address",
      "price": "720.3651",
      "roundId": "18446744073709551975",
      "updatedAt": "2026-09-18T19:50:26Z",
      "verdict": "the fresh answer of the feed pinned to this address"
     },
     "contract": "0xd5f3879160bc7c32ebb4dc785f8a4f505888de68",
     "gecko": {
      "divergenceBps": "-39.3",
      "how": "GeckoTerminal's token-level price, independent of the venue and the feed",
      "price": "723.2067441908",
      "session": "closed",
      "tier": "above-line",
      "verdict": "closed session: divergence -39.3 bps on $1089517.43087106 of 24h volume is a finding, not a veto",
      "volume24h": "1089517.43087106"
     },
     "identity": "listed in rhj_assets 442718b5843e…",
     "status": "tradeable",
     "venue": {
      "fetchedAt": "2026-09-20T02:28:21.506Z",
      "how": "Bankr /wallet/swap-quote at the intended size, read-only",
      "impactBps": "5",
      "price": "723.9007490949778"
     }
    },
    "execution": {
     "call": "—",
     "score": 0
    },
    "feed": "Robinhood QQQ / USD",
    "feedAddress": "0x80901d846d5d7b030f26b480776ee3b29374c2ae",
    "integrity": {
     "call": "—",
     "score": 0
    },
    "macro": {
     "call": "HOLD",
     "score": 0.0
    },
    "move": 0.0,
    "score": 0.0,
    "target": 0.0,
    "trend": {
     "call": "—",
     "score": 0
    },
    "why": "hold: kept"
   },
   {
    "asset": "MSTR",
    "current": 0.0,
    "evidence": {
     "beacon": "resolves to the issuer beacon 0xe10b6f6b275de231345c20d14ab812db62151b00",
     "block": 67581730,
     "blockTime": "2026-09-20T02:26:20Z",
     "chainId": 4663,
     "chainlink": {
      "address": "0x396118bdfb181e6240e74d243f266b061c0edc3d",
      "feed": "Robinhood MSTR / USD",
      "fresh": "age 96294s, of which 94880s in the closed session inferred for us_equities_24/5 (Sat 00:05:00Z to Sun 23:55:00Z every week): 1414s of open session against heartbeat 86400s + margin 3600s",
      "how": "read on chain at the pinned block, from the feed at this address",
      "price": "152.643",
      "roundId": "18446744073709555623",
      "updatedAt": "2026-09-18T23:41:26Z",
      "verdict": "the fresh answer of the feed pinned to this address"
     },
     "contract": "0xec262a75e413fafd0df80480274532c79d42da09",
     "gecko": {
      "divergenceBps": "-223.53",
      "how": "GeckoTerminal's token-level price, independent of the venue and the feed",
      "price": "156.1329774406",
      "session": "closed",
      "tier": "above-line",
      "verdict": "closed session: divergence -223.53 bps on $3435117.5630383 of 24h volume is a finding, not a veto",
      "volume24h": "3435117.5630383"
     },
     "identity": "listed in rhj_assets 442718b5843e…",
     "status": "tradeable",
     "venue": {
      "fetchedAt": "2026-09-20T02:28:24.029Z",
      "how": "Bankr /wallet/swap-quote at the intended size, read-only",
      "impactBps": "-12",
      "price": "158.74324096435143"
     }
    },
    "execution": {
     "call": "CAUTION",
     "score": 0.5
    },
    "feed": "Robinhood MSTR / USD",
    "feedAddress": "0x396118bdfb181e6240e74d243f266b061c0edc3d",
    "integrity": {
     "call": "CAUTION",
     "score": 0.25
    },
    "macro": {
     "call": "BUY",
     "score": 0.5
    },
    "move": 3.60999925043562,
    "score": 0.25,
    "target": 6.25,
    "trend": {
     "call": "—",
     "score": 0
    },
    "why": "buy: raised by 0.0625"
   },
   {
    "asset": "MU",
    "current": 0.0,
    "evidence": {
     "beacon": "resolves to the issuer beacon 0xe10b6f6b275de231345c20d14ab812db62151b00",
     "block": 67581730,
     "blockTime": "2026-09-20T02:26:20Z",
     "chainId": 4663,
     "chainlink": {
      "address": "0x425eefdcf05ed6526c3ce61af99429a228a6d596",
      "feed": "Robinhood MU / USD",
      "fresh": "age 109846s, of which 94880s in the closed session inferred for us_equities_24/5 (Sat 00:05:00Z to Sun 23:55:00Z every week): 14966s of open session against heartbeat 86400s + margin 3600s",
      "how": "read on chain at the pinned block, from the feed at this address",
      "price": "1014.42589693",
      "roundId": "18446744073709556519",
      "updatedAt": "2026-09-18T19:55:34Z",
      "verdict": "the fresh answer of the feed pinned to this address"
     },
     "contract": "0xff080c8ce2e5feadaca0da81314ae59d232d4afd",
     "gecko": {
      "divergenceBps": "-3.94",
      "how": "GeckoTerminal's token-level price, independent of the venue and the feed",
      "price": "1014.8254268027",
      "session": "closed",
      "tier": "above-line",
      "verdict": "closed session: divergence -3.94 bps on $1277396.37112843 of 24h volume is a finding, not a veto",
      "volume24h": "1277396.37112843"
     },
     "identity": "listed in rhj_assets 442718b5843e…",
     "status": "tradeable",
     "venue": {
      "fetchedAt": "2026-09-20T02:28:24.853Z",
      "how": "Bankr /wallet/swap-quote at the intended size, read-only",
      "impactBps": "6",
      "price": "1015.1477189530937"
     }
    },
    "execution": {
     "call": "—",
     "score": 0
    },
    "feed": "Robinhood MU / USD",
    "feedAddress": "0x425eefdcf05ed6526c3ce61af99429a228a6d596",
    "integrity": {
     "call": "—",
     "score": 0
    },
    "macro": {
     "call": "—",
     "score": 0
    },
    "move": 7.21999950079403,
    "score": 0.5,
    "target": 12.5,
    "trend": {
     "call": "BUY",
     "score": 0.5
    },
    "why": "buy: raised by 0.125"
   }
  ],
  "step": null,
  "subtitle": "A deterministic rule turns signed calls into a proposed portfolio. Risk reviews it next.",
  "threshold": null,
  "title": "How opinions became weights.",
  "trendContribution": null,
  "warning": "quorum met: targets from the calls"
 },
 "generated_at": "2026-09-20T02:38:20+00:00",
 "overview": {
  "cash": 4.33456730221658,
  "holdings": [
   {
    "feedAddress": "0x6b22a786baa607d76728168703a39ea9c99f2cd0",
    "feedUpdated": "2026-09-18T15:11:28Z",
    "name": "Robinhood AAPL / USD",
    "pnl": 0.021389983549289716,
    "price": 335.3847472,
    "ticker": "AAPL",
    "value": 36.39138863912082,
    "weight": 18.2
   },
   {
    "feedAddress": "0xd5a1508ced74c084ebf3cbe853e2c968fb2a651c",
    "feedUpdated": "2026-09-18T16:19:12Z",
    "name": "Robinhood AMZN / USD",
    "pnl": -0.005899190805039852,
    "price": 253.863,
    "ticker": "AMZN",
    "value": 5.1340999192198,
    "weight": 2.57
   },
   {
    "feedAddress": "0x27c71df6a64fb476468edf256cf72c038bab5b67",
    "feedUpdated": "2026-09-18T20:18:46Z",
    "name": "Robinhood GME / USD",
    "pnl": 0.16060388425271896,
    "price": 22.55175,
    "ticker": "GME",
    "value": 36.50060185635588,
    "weight": 18.25
   },
   {
    "feedAddress": "0x3f390c5c24628ac7c489515402235fead71d1913",
    "feedUpdated": "2026-09-18T20:11:01Z",
    "name": "Robinhood INTC / USD",
    "pnl": -0.16657349716867773,
    "price": 109.05,
    "ticker": "INTC",
    "value": 34.293424640929935,
    "weight": 17.15
   },
   {
    "feedAddress": "0x7c38c00c30bee9378381e7b6135d7283356d71b1",
    "feedUpdated": "2026-09-18T19:53:36Z",
    "name": "Robinhood META / USD",
    "pnl": -0.040474648709446864,
    "price": 666.7615,
    "ticker": "META",
    "value": 7.179524852084583,
    "weight": 3.59
   },
   {
    "feedAddress": "0x425eefdcf05ed6526c3ce61af99429a228a6d596",
    "feedUpdated": "2026-09-18T19:55:34Z",
    "name": "Robinhood MU / USD",
    "pnl": 0.01558792132119626,
    "price": 1014.42589693,
    "ticker": "MU",
    "value": 7.235587422115226,
    "weight": 3.62
   },
   {
    "feedAddress": "0xb265810950ba6c5c0ff821c9963014a56fd8bffb",
    "feedUpdated": "2026-09-18T23:07:55Z",
    "name": "Robinhood SPCX / USD",
    "pnl": 0.03226989189706677,
    "price": 152.82485,
    "ticker": "SPCX",
    "value": 20.592269331764797,
    "weight": 10.3
   },
   {
    "feedAddress": "0x319724394d3a0e3669269846abe664cd621f9f6a",
    "feedUpdated": "2026-09-18T12:22:01Z",
    "name": "Robinhood SPY / USD",
    "pnl": -0.0710362548341352,
    "price": 761.55079369,
    "ticker": "SPY",
    "value": 20.488963185033594,
    "weight": 10.25
   },
   {
    "feedAddress": "0x75a9c76ef439e2c7c2e5a34ab105ecfe3766431c",
    "feedUpdated": "2026-09-18T23:50:32Z",
    "name": "Robinhood USO / USD",
    "pnl": 0.056074790398220734,
    "price": 154.54265,
    "ticker": "USO",
    "value": 27.83607373105998,
    "weight": 13.92
   }
  ],
  "latest": {
   "approved": 6,
   "headline": "6 orders approved. 1 refused.",
   "summary": "The plan as a whole is supported by consistent reports and clean pricing except for MSTR, which is vetoed individually; the rest stand on their own evidence.",
   "vetoed": 1
  },
  "nav": 199.9865008799012,
  "paperNote": "Paper fill. Tokenized-stock execution is location-gated: the venue answered 403 to a real AAPL order — “Tokenized stocks (AAPL) are not available in your region” — before broadcast and with no gas (F0.5.1). So an equity order is sized, quoted and gated for real, and filled on paper.",
  "positionCount": 9,
  "provenance": {
   "attested": "35 of 35 assets carry an identity and beacon verdict in this snapshot; `make selftest` attests all 235 configured addresses against the chain",
   "block": 67581730,
   "blockHash": "0x77b0b6e397ad51abc81b98be4880f19dffa0686aa5594e9d9aab748da926fbe6",
   "chain": "Robinhood Chain 4663 · block 67581730 · 2026-09-20T02:26:20Z",
   "decisionId": "41bde62b1f…",
   "priceSource": "Chainlink feeds read on chain 4663 at block 67581730",
   "signatureStatus": "Signature verified",
   "snapshotHash": "9ce2581b88bb4e02c4c7f39df0b621537bd0b8f302ea9568d1cfd5733a950456",
   "timestamp": "20 Sep 2026, 02:29 UTC"
  },
  "subtitle": "The paper portfolio — simulated equity holdings. Real money is in Books and Chain, and the two are never added.",
  "tableNote": "Every price is a Chainlink feed read on chain 4663 at block 67581730, the block this snapshot is pinned to. The feed behind each price is named beside its ticker.",
  "title": "A fund that shows its work."
 },
 "record": {
  "approved": 6,
  "endpoint": null,
  "endpointReason": "publishing records by immutable id is unbuilt (7.1)",
  "format": "Canonical JSON · the bytes the signature covers",
  "headline": "6 approved, 1 refused.",
  "id": "41bde62b1f…",
  "idFull": "41bde62b1f02d552cc94333afd8388de1933205fd476dc5bb120956a13b50589",
  "included": [
   "Every accepted analyst report, in full",
   "The proposal and how each weight was reached",
   "Every gate with its value and reason",
   "The risk agent's vote on each order, and overall",
   "The signature over the record's exact bytes"
  ],
  "payloadHash": "41bde62b1f02d552cc94333afd8388de1933205fd476dc5bb120956a13b50589",
  "payloadNote": "the decision id is the sha256 of the record's exact bytes",
  "preview": [
   {
    "description": "sha256 9ce2581b88bb4e02… at block 67581730",
    "title": "The snapshot it was decided on"
   },
   {
    "description": "every accepted report's exact text, with its sha256",
    "title": "4 analyst report(s), in full"
   },
   {
    "description": "7 orders, every gate's value and reason, and the agent's sentence on each",
    "title": "The plan, the gates and the risk verdict"
   }
  ],
  "price": null,
  "priceReason": "the live x402 endpoint asks 0.001 USDC and serves a Phase 0 probe response, not this record (7.2)",
  "quote": "The plan as a whole is supported by consistent reports and clean pricing except for MSTR, which is vetoed individually; the rest stand on their own evidence.",
  "signature": "f671f0e7822b773cafcc2262b5d7ff7c892559af8bf19c82d481b8b96f0913c8b3850343a2bea0b93839bc69fd060513dbdc72e710478a2e8cbc8cf1c5c9d307",
  "signedReports": 4,
  "signer": "1c23243531ff47be0caaf1ce2d73b0b1b705a54fa063f2d50f0bde9b42928c21",
  "signerLabel": "ed25519 public key, published in config/keys.json",
  "snapshot": "9ce2581b88bb4e02c4c7f39df0b621537bd0b8f302ea9568d1cfd5733a950456",
  "subtitle": "One signed decision, including the disagreement and the refusal.",
  "title": "Buy the reasoning. Verify the record.",
  "vetoed": 1
 },
 "risk": {
  "agent": {
   "agent": "unassigned",
   "brief": "risk.v2.md",
   "bundleTokens": 46795,
   "costUsd": 0.075556,
   "endpoint": "Bankr LLM gateway, llm.bankr.bot/v1",
   "inputTokens": 27678,
   "latencyMs": 25210,
   "model": null,
   "note": "one live call, billed, over the whole bundle: every report in full and the sized plan",
   "outputTokens": 2020,
   "seat": "risk"
  },
  "gateList": [
   {
    "reason": "4 seat(s) reported, at least the quorum of 3",
    "rule": "quorum",
    "value": true
   },
   {
    "reason": "$39.88999585560204 traded, within 10000 bps of the NAV ($200.03)",
    "rule": "turnover",
    "value": true
   },
   {
    "reason": "the snapshot was 208.974s old when judged, within 900s",
    "rule": "snapshot-age",
    "value": true
   },
   {
    "reason": "in force until 2026-09-26T21:54:28Z",
    "rule": "mandate-term",
    "value": true
   },
   {
    "reason": "about 46795 tokens, within the budget of 70000",
    "rule": "context-budget",
    "value": true
   }
  ],
  "gates": [
   "4 seat(s) reported, at least the quorum of 3",
   "$39.88999585560204 traded, within 10000 bps of the NAV ($200.03)",
   "the snapshot was 208.974s old when judged, within 900s",
   "in force until 2026-09-26T21:54:28Z",
   "about 46795 tokens, within the budget of 70000"
  ],
  "orders": [
   {
    "allowed": null,
    "amount": 5.48999908444017,
    "asset": "GME",
    "blockedBy": [],
    "context": "buy $5.49",
    "decidedBy": "every gate cleared and the risk agent approved",
    "flaggedBy": [],
    "gateList": [
     {
      "reason": "tradeable in the snapshot: every rule passed",
      "rule": "tradeable",
      "value": true
     },
     {
      "reason": "GME is allowed by the mandate",
      "rule": "mandate",
      "value": true
     },
     {
      "reason": "every leg it trades is allowed by the mandate",
      "rule": "mandate-legs",
      "value": true
     },
     {
      "reason": "$5.48999908444017 within the per-trade limit of $25",
      "rule": "order-size",
      "value": true
     },
     {
      "reason": "quoted at the size asked; age 4.6s within 60s; swapImpactBps 9 within 50, compared signed",
      "rule": "quote",
      "value": true
     },
     {
      "reason": "the position would be 0.182334 of the NAV, within 0.25",
      "rule": "position-weight",
      "value": true
     }
    ],
    "heading": "buy $5.49 of GME.",
    "id": "order-1",
    "limitReason": "",
    "modelVote": "approve",
    "paragraphs": [
     "Price-trend shows a clean month-long uptrend and no price-integrity concern was raised on GME; venue, mark and execution all line up cleanly."
    ],
    "proposed": null,
    "quote": {
     "ageMs": 4581,
     "detail": "a price at size, not a fill (F0.3.3, F0.5.1); to.formattedAmount is lossy and not read",
     "endpoint": "/wallet/swap-quote",
     "feeBps": "0",
     "impactBps": "9",
     "minBuy": "0.232271168050526919",
     "quoteId": "88c7087c-eed8-4149-8c09-729533e22a5f",
     "slippageBps": "500",
     "status": "ok",
     "system": "bankr-quote",
     "venuePrice": "22.501909142735474",
     "verdict": "quoted at the size asked; age 4.6s within 60s; swapImpactBps 9 within 50, compared signed"
    },
    "rule": "Gates cleared and risk approved",
    "side": "Buy",
    "status": "approved"
   },
   {
    "allowed": null,
    "amount": 7.21999950079403,
    "asset": "USO",
    "blockedBy": [],
    "context": "buy $7.22",
    "decidedBy": "every gate cleared and the risk agent approved",
    "flaggedBy": [],
    "gateList": [
     {
      "reason": "tradeable in the snapshot: every rule passed",
      "rule": "tradeable",
      "value": true
     },
     {
      "reason": "USO is allowed by the mandate",
      "rule": "mandate",
      "value": true
     },
     {
      "reason": "every leg it trades is allowed by the mandate",
      "rule": "mandate-legs",
      "value": true
     },
     {
      "reason": "$7.21999950079403 within the per-trade limit of $25",
      "rule": "order-size",
      "value": true
     },
     {
      "reason": "quoted at the size asked; age 4.0s within 60s; swapImpactBps 17 within 50, compared signed",
      "rule": "quote",
      "value": true
     },
     {
      "reason": "the position would be 0.139169 of the NAV, within 0.25",
      "rule": "position-weight",
      "value": true
     }
    ],
    "heading": "buy $7.22 of USO.",
    "id": "order-2",
    "limitReason": "",
    "modelVote": "approve",
    "paragraphs": [
     "Both macro and price-trend call buy on strong independent evidence (14.3% move against a flat SPY/QQQ), and price-integrity raised no concern for USO's mark."
    ],
    "proposed": null,
    "quote": {
     "ageMs": 3967,
     "detail": "a price at size, not a fill (F0.3.3, F0.5.1); to.formattedAmount is lossy and not read",
     "endpoint": "/wallet/swap-quote",
     "feeBps": "0",
     "impactBps": "17",
     "minBuy": "0.044302546147233875",
     "quoteId": "935c2d3b-c60c-444b-a3af-6ae85fdd402a",
     "slippageBps": "500",
     "status": "ok",
     "system": "bankr-quote",
     "venuePrice": "155.0537395011787",
     "verdict": "quoted at the size asked; age 4.0s within 60s; swapImpactBps 17 within 50, compared signed"
    },
    "rule": "Gates cleared and risk approved",
    "side": "Buy",
    "status": "approved"
   },
   {
    "allowed": null,
    "amount": 5.51999976790854,
    "asset": "AAPL",
    "blockedBy": [],
    "context": "buy $5.52",
    "decidedBy": "every gate cleared and the risk agent approved",
    "flaggedBy": [],
    "gateList": [
     {
      "reason": "tradeable in the snapshot: every rule passed",
      "rule": "tradeable",
      "value": true
     },
     {
      "reason": "AAPL is allowed by the mandate",
      "rule": "mandate",
      "value": true
     },
     {
      "reason": "every leg it trades is allowed by the mandate",
      "rule": "mandate-legs",
      "value": true
     },
     {
      "reason": "$5.51999976790854 within the per-trade limit of $25",
      "rule": "order-size",
      "value": true
     },
     {
      "reason": "quoted at the size asked; age 3.1s within 60s; swapImpactBps 12 within 50, compared signed",
      "rule": "quote",
      "value": true
     },
     {
      "reason": "the position would be 0.181902 of the NAV, within 0.25",
      "rule": "position-weight",
      "value": true
     }
    ],
    "heading": "buy $5.52 of AAPL.",
    "id": "order-3",
    "limitReason": "",
    "modelVote": "approve",
    "paragraphs": [
     "Price-trend shows a steady ~8.6% climb, and neither price-integrity nor execution-quality flagged any issue with AAPL's mark or venue price."
    ],
    "proposed": null,
    "quote": {
     "ageMs": 3143,
     "detail": "a price at size, not a fill (F0.3.3, F0.5.1); to.formattedAmount is lossy and not read",
     "endpoint": "/wallet/swap-quote",
     "feeBps": "0",
     "impactBps": "12",
     "minBuy": "0.015636485855451466",
     "quoteId": "fd892fde-bb45-4eb2-84ac-1ca514924b9c",
     "slippageBps": "500",
     "status": "ok",
     "system": "bankr-quote",
     "venuePrice": "335.96729213959",
     "verdict": "quoted at the size asked; age 3.1s within 60s; swapImpactBps 12 within 50, compared signed"
    },
    "rule": "Gates cleared and risk approved",
    "side": "Buy",
    "status": "approved"
   },
   {
    "allowed": null,
    "amount": 7.21999950079403,
    "asset": "META",
    "blockedBy": [],
    "context": "buy $7.22",
    "decidedBy": "every gate cleared and the risk agent approved",
    "flaggedBy": [],
    "gateList": [
     {
      "reason": "tradeable in the snapshot: every rule passed",
      "rule": "tradeable",
      "value": true
     },
     {
      "reason": "META is allowed by the mandate",
      "rule": "mandate",
      "value": true
     },
     {
      "reason": "every leg it trades is allowed by the mandate",
      "rule": "mandate-legs",
      "value": true
     },
     {
      "reason": "$7.21999950079403 within the per-trade limit of $25",
      "rule": "order-size",
      "value": true
     },
     {
      "reason": "quoted at the size asked; age 2.5s within 60s; swapImpactBps 11 within 50, compared signed",
      "rule": "quote",
      "value": true
     },
     {
      "reason": "the position would be 0.036095 of the NAV, within 0.25",
      "rule": "position-weight",
      "value": true
     }
    ],
    "heading": "buy $7.22 of META.",
    "id": "order-4",
    "limitReason": "",
    "modelVote": "approve",
    "paragraphs": [
     "Price-trend shows a sustained 21% climb with only a shallow pullback, and no price-integrity or execution caution was raised for META."
    ],
    "proposed": null,
    "quote": {
     "ageMs": 2468,
     "detail": "a price at size, not a fill (F0.3.3, F0.5.1); to.formattedAmount is lossy and not read",
     "endpoint": "/wallet/swap-quote",
     "feeBps": "0",
     "impactBps": "11",
     "minBuy": "0.010220775348578449",
     "quoteId": "7db35761-0548-4754-b5f8-a252e4bd2195",
     "slippageBps": "500",
     "status": "ok",
     "system": "bankr-quote",
     "venuePrice": "672.4335795341244",
     "verdict": "quoted at the size asked; age 2.5s within 60s; swapImpactBps 11 within 50, compared signed"
    },
    "rule": "Gates cleared and risk approved",
    "side": "Buy",
    "status": "approved"
   },
   {
    "allowed": null,
    "amount": 3.60999925043562,
    "asset": "INTC",
    "blockedBy": [],
    "context": "buy $3.61",
    "decidedBy": "every gate cleared and the risk agent approved",
    "flaggedBy": [],
    "gateList": [
     {
      "reason": "tradeable in the snapshot: every rule passed",
      "rule": "tradeable",
      "value": true
     },
     {
      "reason": "INTC is allowed by the mandate",
      "rule": "mandate",
      "value": true
     },
     {
      "reason": "every leg it trades is allowed by the mandate",
      "rule": "mandate-legs",
      "value": true
     },
     {
      "reason": "$3.60999925043562 within the per-trade limit of $25",
      "rule": "order-size",
      "value": true
     },
     {
      "reason": "quoted at the size asked; age 1.6s within 60s; swapImpactBps 18 within 50, compared signed",
      "rule": "quote",
      "value": true
     },
     {
      "reason": "the position would be 0.171695 of the NAV, within 0.25",
      "rule": "position-weight",
      "value": true
     }
    ],
    "heading": "buy $3.61 of INTC.",
    "id": "order-5",
    "limitReason": "",
    "modelVote": "approve",
    "paragraphs": [
     "Price-integrity flags the closed-session mark as the stale figure here (venue and GeckoTerminal agree near 110.9 vs a 109.05 mark), which means the venue fill is fair and any mark catch-up would work in the fund's favor, not against it."
    ],
    "proposed": null,
    "quote": {
     "ageMs": 1650,
     "detail": "a price at size, not a fill (F0.3.3, F0.5.1); to.formattedAmount is lossy and not read",
     "endpoint": "/wallet/swap-quote",
     "feeBps": "0",
     "impactBps": "18",
     "minBuy": "0.030951814502741948",
     "quoteId": "ed621fed-a7e0-40b3-ab0c-3e0b4d9a67e4",
     "slippageBps": "500",
     "status": "ok",
     "system": "bankr-quote",
     "venuePrice": "110.93099383937593",
     "verdict": "quoted at the size asked; age 1.6s within 60s; swapImpactBps 18 within 50, compared signed"
    },
    "rule": "Gates cleared and risk approved",
    "side": "Buy",
    "status": "approved"
   },
   {
    "allowed": null,
    "amount": 3.60999925043562,
    "asset": "MSTR",
    "blockedBy": [],
    "context": "buy $3.61",
    "decidedBy": "the risk agent",
    "flaggedBy": [],
    "gateList": [
     {
      "reason": "tradeable in the snapshot: every rule passed",
      "rule": "tradeable",
      "value": true
     },
     {
      "reason": "MSTR is allowed by the mandate",
      "rule": "mandate",
      "value": true
     },
     {
      "reason": "every leg it trades is allowed by the mandate",
      "rule": "mandate-legs",
      "value": true
     },
     {
      "reason": "$3.60999925043562 within the per-trade limit of $25",
      "rule": "order-size",
      "value": true
     },
     {
      "reason": "quoted at the size asked; age 0.7s within 60s; swapImpactBps 8 within 50, compared signed",
      "rule": "quote",
      "value": true
     },
     {
      "reason": "the position would be 0.018047 of the NAV, within 0.25",
      "rule": "position-weight",
      "value": true
     }
    ],
    "heading": "Do not buy $3.61 of MSTR.",
    "id": "order-6",
    "limitReason": "",
    "modelVote": "veto",
    "paragraphs": [
     "Price-integrity finds mark, venue and GeckoTerminal all diverge from each other by >150bps with no pair converging, and execution-quality separately flags a ~4% paid-vs-booked gap — there is no reliable reference price to size this buy against."
    ],
    "proposed": null,
    "quote": {
     "ageMs": 717,
     "detail": "a price at size, not a fill (F0.3.3, F0.5.1); to.formattedAmount is lossy and not read",
     "endpoint": "/wallet/swap-quote",
     "feeBps": "0",
     "impactBps": "8",
     "minBuy": "0.02169093306702834",
     "quoteId": "abfe96dd-89b0-484c-a513-48cfc29bc001",
     "slippageBps": "500",
     "status": "ok",
     "system": "bankr-quote",
     "venuePrice": "158.45128018966378",
     "verdict": "quoted at the size asked; age 0.7s within 60s; swapImpactBps 8 within 50, compared signed"
    },
    "rule": "risk",
    "side": "Buy",
    "status": "vetoed"
   },
   {
    "allowed": null,
    "amount": 7.21999950079403,
    "asset": "MU",
    "blockedBy": [],
    "context": "buy $7.22",
    "decidedBy": "every gate cleared and the risk agent approved",
    "flaggedBy": [],
    "gateList": [
     {
      "reason": "tradeable in the snapshot: every rule passed",
      "rule": "tradeable",
      "value": true
     },
     {
      "reason": "MU is allowed by the mandate",
      "rule": "mandate",
      "value": true
     },
     {
      "reason": "every leg it trades is allowed by the mandate",
      "rule": "mandate-legs",
      "value": true
     },
     {
      "reason": "$7.21999950079403 within the per-trade limit of $25",
      "rule": "order-size",
      "value": true
     },
     {
      "reason": "quoted at the size asked; age 0.0s within 60s; swapImpactBps 7 within 50, compared signed",
      "rule": "quote",
      "value": true
     },
     {
      "reason": "the position would be 0.036095 of the NAV, within 0.25",
      "rule": "position-weight",
      "value": true
     }
    ],
    "heading": "buy $7.22 of MU.",
    "id": "order-7",
    "limitReason": "",
    "modelVote": "approve",
    "paragraphs": [
     "Price-trend shows a clear rebound to the month's high, and no integrity or execution concern was raised for MU."
    ],
    "proposed": null,
    "quote": {
     "ageMs": 0,
     "detail": "a price at size, not a fill (F0.3.3, F0.5.1); to.formattedAmount is lossy and not read",
     "endpoint": "/wallet/swap-quote",
     "feeBps": "0",
     "impactBps": "7",
     "minBuy": "0.006772173458981473",
     "quoteId": "1ac416b9-4503-4c55-a1a2-81d8504d9c5d",
     "slippageBps": "500",
     "status": "ok",
     "system": "bankr-quote",
     "venuePrice": "1015.3044634949396",
     "verdict": "quoted at the size asked; age 0.0s within 60s; swapImpactBps 7 within 50, compared signed"
    },
    "rule": "Gates cleared and risk approved",
    "side": "Buy",
    "status": "approved"
   }
  ],
  "outcome": "6 approved · 1 vetoed · only approved orders reach the treasurer",
  "overall": "The plan as a whole is supported by consistent reports and clean pricing except for MSTR, which is vetoed individually; the rest stand on their own evidence.",
  "subtitle": "Risk reviewed every report. 6 of 7 orders survived.",
  "title": "The fund said no.",
  "wallet": null,
  "walletReason": "no per-agent wallet: the seats share one gateway key"
 },
 "source": {
  "cycle": "fixtures/live/cycles/20260920T022826Z",
  "decision": "fixtures/live/decisions/live-20260920T022620Z",
  "snapshot": "fixtures/live/snapshot-9ce2581b88bb4e02c4c7f39df0b621537bd0b8f302ea9568d1cfd5733a950456.json",
  "swaps": [
   "run2-leg2-usdg-eth",
   "run2-leg1-eth-usdg",
   "leg2-usdg-eth",
   "leg1-eth-usdg"
  ]
 },
 "swarm": {
  "agents": [
   {
    "calls": [
     {
      "asset": "AAPL",
      "call": "Buy",
      "confidence": "medium"
     },
     {
      "asset": "GME",
      "call": "Buy",
      "confidence": "high"
     },
     {
      "asset": "INTC",
      "call": "Buy",
      "confidence": "medium"
     },
     {
      "asset": "META",
      "call": "Buy",
      "confidence": "medium"
     },
     {
      "asset": "MU",
      "call": "Buy",
      "confidence": "medium"
     },
     {
      "asset": "USO",
      "call": "Buy",
      "confidence": "medium"
     }
    ],
    "confidence": "Medium",
    "confidenceReason": "confidence is recorded per call, not per seat",
    "cost": 0.434954,
    "id": "trend",
    "latency": 39.444,
    "paragraphs": [
     "REPORT price-trend unassigned 9ce2581b88bb4e02c4c7f39df0b621537bd0b8f302ea9568d1cfd5733a950456",
     "The block shows `block.closed_sessions` containing `us_equities_24/5`: every stock's mark is frozen at its last Robinhood round before the weekend close, while GeckoTerminal keeps trading (see the closed-session divergence findings on AMZN, INTC, MSTR, PLTR). That freeze does not affect the 30-day closes I read here — they are the feed's own daily prints, not live venue prices — so a trend read off the timeline still stands, but the latest \"round\" appended to each series is that same frozen weekend value, not a fresh close. I limit calls to `tradeable` names and skip range-bound or single-day-spike names (NVDA, PLTR, SPY, TSLA, CRCL, AMZN, QQQ) where the 30 closes show no clean direction.",
     "CALL AAPL 0xaf3d76f1834a1d425780943c99ea8a608f8a93f9 buy medium\nA steady month-long climb, roughly +8.6% from window start to mark, with only one shallow pullback in the second week.\n- $308.93973568 close on 2026-08-21 [timeline 2026-08-21]\n- $335.3847472 close on 2026-09-18, matching the mark [timeline 2026-09-18, mark.price_usd]\n- dip to $315.69360675 on 2026-09-09 before recovering [timeline 2026-09-09]\nWrong if: the next several closes fall back under $320.",
     "CALL GME 0x1b0e319c6a659f002271b69db8a7df2f911c153e buy high\nA clean, near-monotonic climb all month, +~24% from window start to the latest round, with no reversal in the last two weeks.\n- $18.225 close on 2026-08-21 [timeline 2026-08-21]\n- $22.55175 latest round on 2026-09-18 [timeline latest, mark.price_usd]\n- $21.115 on 2026-09-11 rising to $22.713 on 2026-09-17, an unbroken run [timeline 2026-09-11, timeline 2026-09-17]\nWrong if: closes drop back under $21 for more than a day or two.",
     "CALL INTC 0xc72b96e0e48ecd4dc75e1e45396e26300bc39681 buy medium\nA strong steady climb from the high-$80s to the low-$100s over the month, accelerating in the final week.\n- $89.95465 close on 2026-08-21 [timeline 2026-08-21]\n- $109.05 latest round on 2026-09-18, matching the mark [timeline latest, mark.price_usd]\n- $97.485 on 2026-09-14 up to $109.205 on 2026-09-17, a fast late push [timeline 2026-09-14, timeline 2026-09-17]\nWrong if: closes retreat back under $100 in the coming week.",
     "CALL META 0xc0d6457c16cc70d6790dd43521c899c87ce02f35 buy medium\nUp ~21% over the month with an orderly grind higher, though the last close pulled back from the month's peak.\n- $549.15 close on 2026-08-21 [timeline 2026-08-21]\n- $682.42815 peak close on 2026-09-17 [timeline 2026-09-17]\n- $666.7615 close on 2026-09-18, matching the mark, a ~2.3% pullback from the peak [timeline 2026-09-18, mark.price_usd]\nWrong if: the pullback deepens and closes fall under $650.",
     "CALL MU 0xff080c8ce2e5feadaca0da81314ae59d232d4afd buy medium\nA sharp rebound in the last four sessions after a mid-month dip, closing near the month's high.\n- $924.43916433 close on 2026-09-14, the month's low point after a pullback [timeline 2026-09-14]\n- $1014.42589693 close on 2026-09-18, matching the mark, a ~9.7% run in four sessions [timeline 2026-09-18, mark.price_usd]\n- $967.91741727 close on 2026-08-21, so the month's net gain is a modest ~4.8% versus the sharper recent leg [timeline 2026-08-21]\nWrong if: the rebound stalls and closes fall back under $960.",
     "CALL USO 0xa30fa36db767ad9ed3f7a60fc79526fb4d56d344 buy medium\nA clear uptrend all month, +~14%, holding a higher range through September despite some chop near the highs.\n- $135.255 close on 2026-08-21 [timeline 2026-08-21]\n- $154.54265 latest round on 2026-09-18, matching the mark [timeline latest, mark.price_usd]\n- $161.405 peak close on 2026-09-15, since eased back to the mid-$150s [timeline 2026-09-15]\nWrong if: closes break decisively under $145."
    ],
    "perspective": "Price Trend: Buy",
    "primaryCall": {
     "asset": "AAPL",
     "call": "Buy",
     "confidence": "medium"
    },
    "reportSha256": "730ee750d2f39502c4e92fe088732ebc6f24ec94f5d3b132e1175c6675ed9cfe",
    "seat": "Price Trend",
    "signature": null,
    "signatureReason": "reports are validated against the snapshot, not signed; only the record is signed",
    "status": "reported",
    "summary": "6 call(s) on this snapshot",
    "wallet": null,
    "walletReason": "no per-agent wallet: the seats share one gateway key"
   },
   {
    "calls": [
     {
      "asset": "QQQ",
      "call": "Hold",
      "confidence": "medium"
     },
     {
      "asset": "NVDA",
      "call": "Hold",
      "confidence": "medium"
     },
     {
      "asset": "MSTR",
      "call": "Buy",
      "confidence": "medium"
     },
     {
      "asset": "USO",
      "call": "Buy",
      "confidence": "medium"
     }
    ],
    "confidence": "Medium",
    "confidenceReason": "confidence is recorded per call, not per seat",
    "cost": 0.265182,
    "id": "macro",
    "latency": 77.115,
    "paragraphs": [
     "REPORT cross-asset-macro unassigned 9ce2581b88bb4e02c4c7f39df0b621537bd0b8f302ea9568d1cfd5733a950456",
     "The block sits inside the us_equities_24/5 closed session, so every stock mark here is Friday's last Chainlink round while GeckoTerminal and the venue keep pricing off-hours: findings like AMZN's -367.53bps and MSTR's -223.53bps divergence are a closed-market artifact, not new co-movement information, and I read the 30-day daily-close timelines rather than these stale marks. Over that window SPY and QQQ, the fund's only broad-market proxies, are essentially flat (SPY -0.60%, QQQ +0.92%) and move almost as one day to day. Against that flat backdrop several names posted return magnitudes an index-tracking factor cannot explain — MSTR +27.8%, USO +14.3%, INTC +21.2%, GME +23.8%, META +21.4% — while NVDA, though beating the index in total return, still shares SPY's daily direction most of the time. The market is not moving as one block; a large index-correlated core sits beside a set of names swinging on their own drivers.",
     "CALL QQQ 0xd5f3879160bc7c32ebb4dc785f8a4f505888de68 hold medium\nQQQ tracked SPY's daily direction on 15 of 19 days while both stayed flat over the month; adding QQQ on top of SPY doubles a single market-beta bet the book can already take.\n- SPY -0.60% (766.1254 -> 761.55079369) [SPY timeline 2026-08-21, SPY timeline 2026-09-18]\n- QQQ +0.92% (713.7894 -> 720.3651) [timeline 2026-08-21, timeline 2026-09-18]\n- 15 of 19 daily moves shared direction with SPY [timeline, SPY timeline]\nWrong if: QQQ's daily direction decouples from SPY's, agreeing on fewer than half the days going forward.",
     "CALL NVDA 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec hold medium\nNVDA matched SPY's daily direction about three days in four even as it beat the index's return; it rides the same broad factor the book already holds via SPY/QQQ rather than adding a distinct source of movement.\n- NVDA +3.6% (214.705 -> 222.44729849) [timeline 2026-08-21, timeline 2026-09-18]\n- SPY -0.60% over the same window [SPY timeline 2026-08-21, SPY timeline 2026-09-18]\n- 14 of 19 daily moves shared direction with SPY [timeline, SPY timeline]\nWrong if: NVDA's daily direction stops matching SPY's more than half the time.",
     "CALL MSTR 0xec262a75e413fafd0df80480274532c79d42da09 buy medium\nMSTR rallied 27.8% while SPY and QQQ were essentially flat, a divergence in size that a shared index factor cannot explain; it moves on a driver (crypto-linked) the SPY/QQQ-anchored book does not otherwise carry.\n- MSTR +27.8% (119.4185 -> 152.643) [timeline 2026-08-21, timeline 2026-09-18]\n- SPY -0.60% over the same window [SPY timeline 2026-08-21, SPY timeline 2026-09-18]\n- QQQ +0.92% over the same window [QQQ timeline 2026-08-21, QQQ timeline 2026-09-18]\nWrong if: MSTR's daily moves begin tracking SPY/QQQ closely, showing it has become another index-beta name.",
     "CALL USO 0xa30fa36db767ad9ed3f7a60fc79526fb4d56d344 buy medium\nUSO gained 14.3% while the equity indices were flat; a commodity moving on its own driver over this window is diversification the book cannot get from adding more equity names.\n- USO +14.3% (135.255 -> 154.54265) [timeline 2026-08-21, timeline 2026-09-18]\n- SPY -0.60% over the same window [SPY timeline 2026-08-21, SPY timeline 2026-09-18]\n- QQQ +0.92% over the same window [QQQ timeline 2026-08-21, QQQ timeline 2026-09-18]\nWrong if: USO's daily moves start correlating tightly with SPY/QQQ, trading as a risk-on proxy rather than its own driver."
    ],
    "perspective": "Cross Asset Macro: Hold",
    "primaryCall": {
     "asset": "QQQ",
     "call": "Hold",
     "confidence": "medium"
    },
    "reportSha256": "443f500d75a2e375eefc21c7fa10b4849f4fcf2369cff37e3bdd3939ec9a2dd2",
    "seat": "Cross Asset Macro",
    "signature": null,
    "signatureReason": "reports are validated against the snapshot, not signed; only the record is signed",
    "status": "reported",
    "summary": "4 call(s) on this snapshot",
    "wallet": null,
    "walletReason": "no per-agent wallet: the seats share one gateway key"
   },
   {
    "calls": [
     {
      "asset": "PLTR",
      "call": "Caution",
      "confidence": "medium"
     },
     {
      "asset": "MSTR",
      "call": "Caution",
      "confidence": "medium"
     }
    ],
    "confidence": "Medium",
    "confidenceReason": "confidence is recorded per call, not per seat",
    "cost": 0.20782,
    "id": "execution",
    "latency": 17.968,
    "paragraphs": [
     "REPORT execution-quality unassigned 9ce2581b88bb4e02c4c7f39df0b621537bd0b8f302ea9568d1cfd5733a950456",
     "The market is shut (block.closed_sessions lists us_equities_24/5), so every mark is frozen at its last pre-close round while the venue keeps quoting live against pool prices; the gap between venue fill price and mark booking price is therefore wider and noisier than an open session would show. Fee is zero everywhere (fee_bps=0), so cost at the quoted $25 size is driven entirely by swap impact and by mark-vs-venue drift. Across the 16 tradeable assets, most quotes are cheap and fresh: swap impact sits in the single digits (0–16 bps) and ages are all under 30s, well inside the 60s/50bps tradeability gates. Two names stand out for cost even though they pass the gate: ORCL-style large mark/venue gaps recur in PLTR and MSTR, both showing swings driven by the closed-session freeze rather than by impact itself. Only one tradeable asset, ORCL... wait, ORCL is not tradeable (below line); among the tradeable set, none breach the 50bps impact cap, but PLTR and MSTR show large mark-vs-venue paid-vs-booked gaps worth flagging as a cost-of-trading-now issue distinct from direction.",
     "CALL PLTR 0x894e1ec2d74ffe5aef8dc8a9e84686accb964f2a caution medium\nA buy fills at the venue price of 177.68 but books at the frozen mark of 177.6031, and GeckoTerminal already trades 170.8 bps above that mark while the session is closed — so the \"fair\" reference itself is stale versus where the venue is already pricing. Swap impact is a modest 11 bps and the quote is fresh, but the paid-vs-booked gap here is a real, quantifiable cost, not noise.\n- swap impact 11 bps, quote age 14.1s [quote.swap_impact_bps, quote.age_s]\n- venue price 177.68466 vs mark 177.6031 [quote.venue_price_usd, mark.price_usd]\n- GeckoTerminal divergence 170.8 bps in closed session [corroboration.divergence_bps]\nWrong if: the session reopens and the mark converges to within 50 bps of GeckoTerminal without the venue price moving.",
     "CALL MSTR 0xec262a75e413fafd0df80480274532c79d42da09 caution medium\nThe venue quotes a buy at 158.74 while the trade would book at a mark of 152.643, a paid-vs-booked gap of roughly 4% driven by the closed-session freeze (GeckoTerminal divergence -223.53 bps). Swap impact itself is negative (price improvement, -12 bps) and the quote is only 0.8s old, so the cost here is not impact or staleness of the quote — it is the size of the mark/venue split at the moment of booking.\n- venue price 158.74324 vs mark 152.643 [quote.venue_price_usd, mark.price_usd]\n- corroboration divergence -223.53 bps [corroboration.divergence_bps]\n- swap impact -12 bps, quote age 0.824s [quote.swap_impact_bps, quote.age_s]\nWrong if: the venue price and mark converge to within 100 bps once the market reopens.",
     "Every other tradeable name (AAPL, AMZN, CRCL, GME, GOOGL, INTC, META, MU, NVDA, QQQ, SPCX, SPY, TSLA, USO) shows swap impact under 15 bps, zero fee, and quote ages under 30 seconds — proceed-quality execution with nothing worth flagging at this size."
    ],
    "perspective": "Execution Quality: Caution",
    "primaryCall": {
     "asset": "PLTR",
     "call": "Caution",
     "confidence": "medium"
    },
    "reportSha256": "d95feb722c8cf77e85660602db2c9e8fb7a5949051068f00254a52ce1db1ee49",
    "seat": "Execution Quality",
    "signature": null,
    "signatureReason": "reports are validated against the snapshot, not signed; only the record is signed",
    "status": "reported",
    "summary": "2 call(s) on this snapshot",
    "wallet": null,
    "walletReason": "no per-agent wallet: the seats share one gateway key"
   },
   {
    "calls": [
     {
      "asset": "AMZN",
      "call": "Proceed",
      "confidence": "medium"
     },
     {
      "asset": "INTC",
      "call": "Caution",
      "confidence": "medium"
     },
     {
      "asset": "MSTR",
      "call": "Caution",
      "confidence": "low"
     },
     {
      "asset": "PLTR",
      "call": "Proceed",
      "confidence": "medium"
     }
    ],
    "confidence": "Medium",
    "confidenceReason": "confidence is recorded per call, not per seat",
    "cost": 0.240312,
    "id": "integrity",
    "latency": 51.39,
    "paragraphs": [
     "REPORT price-integrity unassigned 9ce2581b88bb4e02c4c7f39df0b621537bd0b8f302ea9568d1cfd5733a950456",
     "The block's `closed_sessions` shows us_equities_24/5 shut: every stock's Chainlink mark is frozen at its last pre-close round while GeckoTerminal and the venue keep trading. That means a mark-vs-GeckoTerminal gap alone is expected and not vetoed here — the question is which of the three prices, if any, has drifted from the other two. Four assets carry an explicit closed-session divergence finding (AMZN, INTC, MSTR, PLTR); I checked each against the venue quote, since GeckoTerminal and venue are independent of each other and of the frozen mark. Where venue and mark still agree, the mark holds up and GeckoTerminal is the stale/thin outlier. Where venue and GeckoTerminal agree instead, the frozen mark is the one that no longer holds up.",
     "CALL AMZN 0x12f190a9f9d7d37a250758b26824b97ce941bf54 proceed medium\nThe finding flags a large mark/GeckoTerminal gap, but the venue price sits within 36 bps of the mark, confirming the frozen mark rather than the pool price.\n- mark 253.863 vs venue 254.778, ~36 bps apart [mark.price_usd, quote.venue_price_usd]\n- GeckoTerminal 263.5491, -367.53 bps from mark [corroboration.price_usd, corroboration.divergence_bps]\n- GeckoTerminal vs venue diverge by roughly 344 bps, GeckoTerminal is the outlier [corroboration.price_usd, quote.venue_price_usd]\nWrong if: the venue price itself drifts toward GeckoTerminal's level once the market reopens, rather than the mark.",
     "CALL INTC 0xc72b96e0e48ecd4dc75e1e45396e26300bc39681 caution medium\nHere the venue and GeckoTerminal agree closely while the frozen mark sits well below both, so it is the mark, not GeckoTerminal, that looks stale.\n- mark 109.05 vs venue 110.92391337248277, ~172 bps apart [mark.price_usd, quote.venue_price_usd]\n- GeckoTerminal 110.8731992234, only ~5 bps from venue [corroboration.price_usd, quote.venue_price_usd]\n- mark is -164.45 bps from GeckoTerminal [corroboration.divergence_bps]\nWrong if: the mark's first post-reopen round confirms 109 rather than moving up toward 110.9.",
     "CALL MSTR 0xec262a75e413fafd0df80480274532c79d42da09 caution low\nNo two of the three prices agree here: mark, GeckoTerminal, and venue are all more than 150 bps apart from one another, so unlike AMZN/PLTR I cannot pin the miss on GeckoTerminal alone.\n- mark 152.643 vs GeckoTerminal 156.1329774406, -223.53 bps [mark.price_usd, corroboration.divergence_bps]\n- venue 158.74324096435143 vs GeckoTerminal, ~167 bps apart [quote.venue_price_usd, corroboration.price_usd]\n- venue vs mark, ~400 bps apart [quote.venue_price_usd, mark.price_usd]\nWrong if: any two of the three converge to within 100 bps once trading resumes, isolating a single bad print.",
     "CALL PLTR 0x894e1ec2d74ffe5aef8dc8a9e84686accb964f2a proceed medium\nThe mark/GeckoTerminal finding is again explained by a thin or lagging GeckoTerminal print: venue confirms the frozen mark to within 5 bps.\n- mark 177.6031 vs venue 177.68465886366494, ~5 bps apart [mark.price_usd, quote.venue_price_usd]\n- GeckoTerminal 174.6206548039, +170.8 bps from mark [corroboration.price_usd, corroboration.divergence_bps]\n- GeckoTerminal vs venue diverge by roughly 176 bps, GeckoTerminal is the outlier [corroboration.price_usd, quote.venue_price_usd]\nWrong if: the venue price converges toward GeckoTerminal's 174.6 rather than holding near the mark."
    ],
    "perspective": "Price Integrity: Proceed",
    "primaryCall": {
     "asset": "AMZN",
     "call": "Proceed",
     "confidence": "medium"
    },
    "reportSha256": "d6a06f5144d5550192d307e1f32cb79fb8c3c0d89d5dbd4b1d87f4c3750030c4",
    "seat": "Price Integrity",
    "signature": null,
    "signatureReason": "reports are validated against the snapshot, not signed; only the record is signed",
    "status": "reported",
    "summary": "4 call(s) on this snapshot",
    "wallet": null,
    "walletReason": "no per-agent wallet: the seats share one gateway key"
   }
  ],
  "costIsEstimate": true,
  "parallelReason": "build and wall-clock timings are printed, not written to an artifact",
  "parallelTime": null,
  "quorum": "4 seat(s) reported, at least the quorum of 3",
  "reportCost": 1.148268,
  "signedReports": 4,
  "snapshot": {
   "block": 67581730,
   "chainId": 4663,
   "elapsed": null,
   "elapsedReason": "build and wall-clock timings are printed, not written to an artifact",
   "hash": "9ce2581b88bb4e02c4c7f39df0b621537bd0b8f302ea9568d1cfd5733a950456",
   "source": "every mark in it is a Chainlink feed read on chain 4663 at this block, and every asset carries an identity and beacon verdict from the same read",
   "time": "2026-09-20T02:26:20Z"
  },
  "stages": [
   "Freeze snapshot",
   "Analysts",
   "Aggregate",
   "Risk",
   "Execute"
  ],
  "subtitle": "Independent reports on the same market snapshot.",
  "title": "Four analysts. One frozen moment.",
  "weights": "SPY 10.24% · AMZN 2.57% · GME 25.0% · SPCX 10.29% · USO 22.81% · AAPL 25.0% · META 12.5% · INTC 21.61% · MSTR 6.25% · MU 12.5%"
 }
};
