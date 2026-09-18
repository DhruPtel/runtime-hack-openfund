// Probe 0.7e, step 2: can a thin adapter, sitting between the unmodified
// x402-fetch@1.2.0 and the network, make it pay a v2 challenge? Two depths:
//
//   inbound   rewrite the 402 into a clean v1 challenge (network "base",
//             x402Version 1) and let x402-fetch send its own v1 X-PAYMENT;
//   envelope  additionally re-wrap that X-PAYMENT as a v2 PAYMENT-SIGNATURE
//             carrying the original requirement as `accepted`.
//
// Reading x402@1.2.0 first (schemes/exact/evm/sign.ts): the EIP-712 signature
// covers the authorization {from, to, value, validAfter, validBefore, nonce}
// under the domain {name, version, chainId, verifyingContract}. Neither
// x402Version nor the network string is signed; the network enters only as
// chainId, and "base" and "eip155:8453" both resolve to 8453. So the rewrite
// cannot invalidate the signature, and this probe checks that by recovering it.
// Offline after one free unpaid GET; nothing pays.
//
//   node probes/x402_clients/adapter.mjs

import { wrapFetchWithPayment, createSigner } from "x402-fetch";
import { ChainIdToNetwork } from "x402/types";
import {
  ENDPOINT, fetchChallenge, offlineFetch, throwawayKey, record, decodeB64Json,
  recoverAuthorization, usdcDomain, PaidRequestRefused,
} from "./lib.mjs";

const toV1Network = (n) =>
  n.startsWith("eip155:") ? ChainIdToNetwork[Number(n.slice(7))] ?? n : n;

// The adapter a buyer would have to install. Inbound: a v2 challenge in, a v1
// challenge out. Outbound (optional): a v1 X-PAYMENT in, a v2 PAYMENT-SIGNATURE out.
function adapt(fetch, { envelope }) {
  let original = null;
  return async (input, init) => {
    const xPayment = new Headers(init?.headers ?? {}).get("x-payment");
    if (envelope && xPayment && original) {
      const v1 = decodeB64Json(xPayment);
      const v2 = { x402Version: 2, payload: v1.payload, accepted: original };
      const headers = { ...init.headers };
      delete headers["X-PAYMENT"];
      headers["PAYMENT-SIGNATURE"] = Buffer.from(JSON.stringify(v2)).toString("base64");
      return fetch(input, { ...init, headers });
    }
    const res = await fetch(input, init);
    if (res.status !== 402) return res;
    const body = await res.json();
    original = body.accepts[0];
    const v1 = {
      ...body,
      x402Version: 1,
      accepts: body.accepts.map((a) => ({
        ...a,
        network: toV1Network(a.network),
        maxAmountRequired: a.maxAmountRequired ?? a.amount,
      })),
    };
    return new Response(JSON.stringify(v1), { status: 402, headers: res.headers });
  };
}

const challenge = await fetchChallenge();
const requirement = challenge.body.accepts[0];
const chainId = Number(requirement.network.slice("eip155:".length));

const runs = {};
for (const envelope of [false, true]) {
  const name = envelope ? "envelope" : "inbound";
  const { key, address } = throwawayKey();
  const off = offlineFetch(challenge);
  const paidFetch = wrapFetchWithPayment(
    adapt(off.fetch, { envelope }), await createSigner("base", key), 1000n);
  let stage, error = null;
  try {
    await paidFetch(ENDPOINT);
    stage = "returned_without_paying";
  } catch (e) {
    stage = e instanceof PaidRequestRefused ? "reached_signing" : "threw_before_signing";
    if (stage !== "reached_signing") error = String(e.message).split("\n")[0];
  }
  const sent = off.capture.paid[0];
  const headerName = sent ? Object.keys(sent)[0] : null;
  const payload = sent ? decodeB64Json(sent[headerName]) : null;
  const recovered = payload
    ? await recoverAuthorization(payload.payload, usdcDomain(requirement, chainId))
    : null;
  runs[name] = {
    stage,
    error,
    header_name: headerName,
    payload,
    signer: address,
    recovered_under_chainId: chainId,
    recovered,
    signature_valid_for_live_domain: recovered === address,
    authorization_matches_live_requirement: payload
      ? payload.payload.authorization.to.toLowerCase() === requirement.payTo.toLowerCase() &&
        payload.payload.authorization.value === requirement.amount
      : null,
  };
}

record("adapter", { endpoint: ENDPOINT, runs });

for (const [k, v] of Object.entries(runs)) {
  const p = v.payload;
  console.log(`${k.padEnd(9)} ${v.stage}${v.error ? ` — ${v.error}` : ""}`);
  if (!p) continue;
  console.log(`          header ${v.header_name}  x402Version ${p.x402Version}` +
    `  network ${p.network ?? p.accepted?.network}  keys [${Object.keys(p).join(", ")}]`);
  console.log(`          signature recovers to the signer under chainId ${chainId}: ` +
    `${v.signature_valid_for_live_domain}; to/value match the live requirement: ` +
    `${v.authorization_matches_live_requirement}`);
}
