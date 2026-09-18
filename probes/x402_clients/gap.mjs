// Probe 0.7e, step 1: the gap between our live 402 and x402@1.2.0, measured
// with the library's own schemas rather than read off its source. Then drive
// the unmodified x402-fetch against a replay of that 402, changing one field at
// a time, to learn which differences actually stop a client and which the
// client never looks at. Offline after the one free unpaid GET; nothing pays.
//
//   node probes/x402_clients/gap.mjs

import { PaymentRequirementsSchema, x402ResponseSchema } from "x402/types";
import { wrapFetchWithPayment, createSigner } from "x402-fetch";
import {
  ENDPOINT, fetchChallenge, offlineFetch, throwawayKey, record, decodeB64Json,
  PaidRequestRefused,
} from "./lib.mjs";

function check(shape, obj) {
  const out = {};
  for (const [name, schema] of Object.entries(shape)) {
    const r = schema.safeParse(obj[name]);
    out[name] = {
      present: name in obj,
      value: obj[name],
      v1: r.success ? "ok" : r.error.issues.map((i) => i.message).join("; "),
    };
  }
  const unknown = Object.keys(obj).filter((k) => !(k in shape));
  return { fields: out, unknown_to_v1: unknown };
}

function describe(err) {
  if (err?.name === "ZodError") {
    return err.issues.map((i) => `${i.path.join(".") || "(root)"}: ${i.message}`).join("; ");
  }
  return String(err?.message ?? err).split("\n")[0];
}

const challenge = await fetchChallenge();
if (challenge.status !== 402) throw new Error(`expected 402, got ${challenge.status}`);

const requirement = challenge.body.accepts[0];
const schemaDiff = {
  header_equals_body:
    JSON.stringify(challenge.headerDecoded) === JSON.stringify(challenge.body),
  challenge_headers: Object.keys(challenge.headers),
  top_level: check(x402ResponseSchema.shape, challenge.body),
  requirement: check(PaymentRequirementsSchema.shape, requirement),
};

const toBase = (b) => ({ ...b, accepts: b.accepts.map((a) => ({ ...a, network: "base" })) });
const toV1 = (b) => ({ ...b, x402Version: 1 });
const variants = {
  unmodified: (b) => b,
  network_rewritten_only: toBase,
  version_rewritten_only: toV1,
};

const runs = {};
for (const [name, rewrite] of Object.entries(variants)) {
  const { key, address } = throwawayKey();
  const off = offlineFetch(challenge, rewrite);
  // createSigner is async in x402@1.2.0; an unawaited Promise fails the
  // library's wallet check and reads exactly like a protocol rejection.
  const paidFetch = wrapFetchWithPayment(off.fetch, await createSigner("base", key), 1000n);
  let stage, error = null;
  try {
    await paidFetch(ENDPOINT);
    stage = "returned_without_paying";
  } catch (e) {
    stage = e instanceof PaidRequestRefused ? "reached_signing" : "threw_before_signing";
    if (stage !== "reached_signing") error = describe(e);
  }
  const sent = off.capture.paid[0];
  runs[name] = {
    stage,
    error,
    signer: address,
    header_name: sent ? Object.keys(sent)[0] : null,
    payload: sent ? decodeB64Json(Object.values(sent)[0]) : null,
  };
}

record("gap", { endpoint: ENDPOINT, challenge_ms: challenge.ms, schemaDiff, runs });

console.log(`402 in ${challenge.ms} ms; payment-required header equals body: ${schemaDiff.header_equals_body}`);
console.log("\nrequirement vs x402@1.2.0 PaymentRequirementsSchema");
for (const [k, v] of Object.entries(schemaDiff.requirement.fields)) {
  console.log(`  ${k.padEnd(18)} ${v.present ? "present" : "absent "}  ${v.v1}`);
}
console.log(`  unknown to v1: ${schemaDiff.requirement.unknown_to_v1.join(", ") || "none"}`);
console.log("\ntop level vs x402@1.2.0 x402ResponseSchema");
for (const [k, v] of Object.entries(schemaDiff.top_level.fields)) {
  console.log(`  ${k.padEnd(18)} ${v.present ? "present" : "absent "}  ${v.v1}`);
}
console.log(`  unknown to v1: ${schemaDiff.top_level.unknown_to_v1.join(", ") || "none"}`);
console.log("\nunmodified x402-fetch@1.2.0 against the replayed 402");
for (const [k, v] of Object.entries(runs)) {
  const p = v.payload;
  console.log(`  ${k.padEnd(24)} ${v.stage}${v.error ? `  — ${v.error}` : ""}` +
    (p ? `  → ${v.header_name} {x402Version:${p.x402Version}, network:${p.network}}` : ""));
}
