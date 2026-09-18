// Probe 0.7e, step 4 (offline half): the v2 client line, published under the
// @x402 scope by the same maintainers as x402 and x402-fetch, and never
// examined by F0.7.3. Configured exactly as the @x402/fetch README's Quick
// Start shows a buyer, unmodified, against a replay of our live 402. Stops at
// signing; nothing pays. The paid half is pay.mjs.
//
//   node probes/x402_clients/v2.mjs

import { wrapFetchWithPaymentFromConfig } from "@x402/fetch";
import { ExactEvmScheme } from "@x402/evm";
import { privateKeyToAccount } from "viem/accounts";
import {
  ENDPOINT, fetchChallenge, offlineFetch, throwawayKey, record, decodeB64Json,
  recoverAuthorization, usdcDomain, PaidRequestRefused,
} from "./lib.mjs";

const challenge = await fetchChallenge();
const requirement = challenge.body.accepts[0];
const chainId = Number(requirement.network.slice("eip155:".length));

const { key, address } = throwawayKey();
const off = offlineFetch(challenge);
const fetchWithPayment = wrapFetchWithPaymentFromConfig(off.fetch, {
  schemes: [{ network: "eip155:8453", client: new ExactEvmScheme(privateKeyToAccount(key)) }],
});

let stage, error = null;
try {
  await fetchWithPayment(ENDPOINT, { method: "GET" });
  stage = "returned_without_paying";
} catch (e) {
  const refused = e instanceof PaidRequestRefused || e?.cause instanceof PaidRequestRefused ||
    String(e?.message).includes("offline: refused");
  stage = refused ? "reached_signing" : "threw_before_signing";
  if (!refused) error = String(e.message).split("\n")[0];
}

const sent = off.capture.paid[0];
const headerName = sent ? Object.keys(sent)[0] : null;
const payload = sent ? decodeB64Json(sent[headerName]) : null;
const recovered = payload
  ? await recoverAuthorization(payload.payload, usdcDomain(requirement, chainId))
  : null;

const result = {
  endpoint: ENDPOINT,
  stage,
  error,
  requests_attempted: off.capture.requests,
  header_name: headerName,
  payload,
  payload_keys: payload ? Object.keys(payload) : null,
  accepted_equals_live_requirement: payload
    ? JSON.stringify(payload.accepted) === JSON.stringify(requirement)
    : null,
  signer: address,
  recovered,
  signature_valid_for_live_domain: recovered === address,
};
record("v2_offline", result);

console.log(`@x402/fetch 2.26.0: ${stage}${error ? ` — ${error}` : ""}`);
if (payload) {
  console.log(`  header ${headerName}  x402Version ${payload.x402Version}  keys [${result.payload_keys.join(", ")}]`);
  console.log(`  accepted is the live requirement verbatim: ${result.accepted_equals_live_requirement}`);
  console.log(`  top-level resource sent: ${"resource" in payload}`);
  console.log(`  signature recovers to the signer under chainId ${chainId}: ${result.signature_valid_for_live_domain}`);
  console.log(`  authorization: validAfter ${payload.payload.authorization.validAfter}, value ${payload.payload.authorization.value}, to ${payload.payload.authorization.to}`);
}
