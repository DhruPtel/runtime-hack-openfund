// Shared plumbing for probe 0.7e. Nothing here pays, and nothing here holds a
// credential: the offline runs sign with a throwaway key generated per process
// that is never printed, never persisted and never funded.

import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { generatePrivateKey, privateKeyToAccount } from "viem/accounts";
import { recoverTypedDataAddress, getAddress } from "viem";

export const ENDPOINT =
  "https://x402.bankr.bot/0x93faecde3c88a713e1edddf417c02c326889a3da/roundtrip";
export const FUND_WALLET = "0x93faecde3c88a713e1edddf417c02c326889a3da";
export const UA = "openfund-probe/0.7e";

const HERE = dirname(fileURLToPath(import.meta.url));
const OUT = join(HERE, "..", "out", "x402_clients.json");

export function record(section, value) {
  mkdirSync(dirname(OUT), { recursive: true });
  const all = existsSync(OUT) ? JSON.parse(readFileSync(OUT, "utf8")) : {};
  all[section] = { at: new Date().toISOString(), ...value };
  writeFileSync(OUT, JSON.stringify(all, null, 2) + "\n");
}

export function decodeB64Json(s) {
  return JSON.parse(Buffer.from(s, "base64").toString("utf8"));
}

// One unpaid GET against the live endpoint. Free: a 402 is never charged.
export async function fetchChallenge() {
  const started = Date.now();
  const res = await fetch(ENDPOINT, { headers: { "user-agent": UA } });
  const bodyText = await res.text();
  const headers = Object.fromEntries(res.headers.entries());
  return {
    status: res.status,
    ms: Date.now() - started,
    headers,
    bodyText,
    body: JSON.parse(bodyText),
    headerDecoded: headers["payment-required"]
      ? decodeB64Json(headers["payment-required"])
      : null,
  };
}

const PAYMENT_HEADERS = ["payment-signature", "x-payment"];

function headersOf(input, init) {
  const h = new Headers(input instanceof Request ? input.headers : undefined);
  for (const [k, v] of Object.entries(init?.headers ?? {})) h.set(k, v);
  return h;
}

// A fetch that never reaches the network. The unpaid request is answered with
// the live 402 captured by fetchChallenge(), byte for byte; the paid request is
// captured and refused, so a client can be driven to the point of signing and
// no further. `capture.paid` holds every payment header a client tried to send.
export function offlineFetch(challenge, rewrite = (body) => body) {
  const capture = { requests: 0, paid: [] };
  const fn = async (input, init) => {
    capture.requests += 1;
    const h = headersOf(input, init);
    const sent = PAYMENT_HEADERS.filter((n) => h.has(n));
    if (sent.length) {
      capture.paid.push(Object.fromEntries(sent.map((n) => [n, h.get(n)])));
      throw new PaidRequestRefused(sent);
    }
    return new Response(JSON.stringify(rewrite(structuredClone(challenge.body))), {
      status: challenge.status,
      headers: challenge.headers,
    });
  };
  return { fetch: fn, capture };
}

export class PaidRequestRefused extends Error {
  constructor(sent) {
    super(`offline: refused to send a request carrying ${sent.join(", ")}`);
    this.name = "PaidRequestRefused";
  }
}

// A key that exists for one process and holds nothing. Callers pass `key` to a
// client's own signer constructor and log only `address`.
export function throwawayKey() {
  const key = generatePrivateKey();
  return { key, address: privateKeyToAccount(key).address };
}

const AUTHORIZATION_TYPES = {
  TransferWithAuthorization: [
    { name: "from", type: "address" },
    { name: "to", type: "address" },
    { name: "value", type: "uint256" },
    { name: "validAfter", type: "uint256" },
    { name: "validBefore", type: "uint256" },
    { name: "nonce", type: "bytes32" },
  ],
};

// Recover the signer of an EIP-3009 authorization under a stated domain. If it
// recovers to the key that signed, the signature was made over exactly this
// domain: that is how we learn which chainId a client actually signed for,
// without trusting the network string it wrote into the header.
export async function recoverAuthorization({ authorization, signature }, domain) {
  return recoverTypedDataAddress({
    domain: { ...domain, verifyingContract: getAddress(domain.verifyingContract) },
    types: AUTHORIZATION_TYPES,
    primaryType: "TransferWithAuthorization",
    message: {
      from: getAddress(authorization.from),
      to: getAddress(authorization.to),
      value: BigInt(authorization.value),
      validAfter: BigInt(authorization.validAfter),
      validBefore: BigInt(authorization.validBefore),
      nonce: authorization.nonce,
    },
    signature,
  });
}

export function usdcDomain(requirement, chainId) {
  return {
    name: requirement.extra.name,
    version: requirement.extra.version,
    chainId,
    verifyingContract: requirement.asset,
  };
}
