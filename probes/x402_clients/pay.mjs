// Probe 0.7e, the one payment: the unmodified @x402/fetch 2.26.0, configured as
// its README shows a buyer, pays our endpoint once. v2.mjs already drove the
// same client to signing offline; this is the only step that can show whether
// Bankr's server accepts and settles what a standard v2 client sends.
//
// **Spends $0.001 USDC, self-paid, so it nets to zero (F0.7d.6).** Without
// --confirm it prints the plan and signs nothing.
//
// The signer. The only funded wallet is the fund's own Bankr-custodied EOA, so
// signTypedData is answered by Bankr's POST /wallet/sign through the installed,
// logged-in CLI; no credential enters this process. The client code, the
// payload it builds and the header it sends are the published library's, not
// ours — what differs from a non-Bankr buyer is who holds the key, and the
// server sees only the payload and an ECDSA signature from an EOA (eth_getCode
// on Base is 0x). The signer refuses anything but this one authorization,
// signs at most once, and checks the signature locally before returning it.
//
// Settlement is verified on chain, never from the 200 (F0.7b.4): the router's
// PaymentSettled event with us as owner, and USDC's AuthorizationUsed event
// carrying the exact nonce this client signed.
//
//   node probes/x402_clients/pay.mjs [--confirm]

import { execFileSync } from "node:child_process";
import { wrapFetchWithPaymentFromConfig } from "@x402/fetch";
import { ExactEvmScheme } from "@x402/evm";
import { getAddress, keccak256, toBytes, recoverTypedDataAddress } from "viem";
import { ENDPOINT, FUND_WALLET, fetchChallenge, record, decodeB64Json } from "./lib.mjs";

const CONFIRM = process.argv.includes("--confirm");
const BASE_RPC = "https://mainnet.base.org";
const USDC = getAddress("0x833589fcd6edb6e08f4c7c32d4f71b54bda02913");
const ROUTER = getAddress("0x8AEE621035D93Deb3C0C1177fac252dC2dd501a0");
const FUND = getAddress(FUND_WALLET);
const PRICE_ATOMIC = 1000n;
const TOPIC_SETTLED = keccak256(toBytes(
  "PaymentSettled(address,address,address,uint256,uint256,uint256,uint16)"));
const TOPIC_AUTH_USED = keccak256(toBytes("AuthorizationUsed(address,bytes32)"));
const pad = (a) => "0x" + a.slice(2).toLowerCase().padStart(64, "0");

async function rpc(method, params) {
  const res = await fetch(BASE_RPC, {
    method: "POST",
    headers: { "content-type": "application/json", "user-agent": "openfund-probe/0.7e" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
  });
  const j = await res.json();
  if (j.error) throw new Error(`${method}: ${JSON.stringify(j.error)}`);
  return j.result;
}
const usdcBalance = async () => BigInt(await rpc("eth_call",
  [{ to: USDC, data: "0x70a08231" + pad(FUND).slice(2) }, "latest"]));
const blockNumber = async () => Number(await rpc("eth_blockNumber", []));

// ── the signer ───────────────────────────────────────────────────────────
let signatures = 0;
const signLog = [];
const bankrSigner = {
  address: FUND,
  async signTypedData({ domain, types, primaryType, message }) {
    const refuse = (why) => { throw new Error(`signer refused: ${why}`); };
    if (primaryType !== "TransferWithAuthorization") refuse(primaryType);
    if (Number(domain.chainId) !== 8453) refuse(`chainId ${domain.chainId}`);
    if (getAddress(domain.verifyingContract) !== USDC) refuse("asset");
    if (getAddress(message.from) !== FUND) refuse("from");
    if (getAddress(message.to) !== ROUTER) refuse("to");
    if (BigInt(message.value) !== PRICE_ATOMIC) refuse(`value ${message.value}`);
    if (signatures++ > 0) refuse("already signed once");

    const typedData = JSON.stringify({ domain, types, primaryType, message },
      (_, v) => (typeof v === "bigint" ? v.toString() : v));
    const started = Date.now();
    const out = execFileSync("bankr",
      ["wallet", "sign", "--type", "eth_signTypedData_v4", "--typed-data", typedData],
      { encoding: "utf8", env: { ...process.env, BANKR_NOT_INTERACTIVE: "1", NO_COLOR: "1", FORCE_COLOR: "0" } })
      .replace(/\x1b\[[0-9;]*m/g, "");
    const signature = out.match(/Signature:?\s+(0x[0-9a-fA-F]+)/)?.[1];
    const signer = out.match(/Signer:?\s+(0x[0-9a-fA-F]{40})/)?.[1];
    if (!signature) refuse(`no signature in CLI output: ${out.trim().split("\n").pop()}`);
    const recovered = await recoverTypedDataAddress({ domain, types, primaryType, message, signature });
    signLog.push({ ms: Date.now() - started, signer, recovered, nonce: message.nonce });
    if (recovered !== FUND) refuse(`signature recovers to ${recovered}, not the fund`);
    return signature;
  },
};

// ── the fetch underneath the client: real network, one paid request at most ──
const wire = [];
let paidRequests = 0;
async function guardedFetch(input, init) {
  const req = new Request(input, init);
  const pay = ["payment-signature", "x-payment"].find((h) => req.headers.has(h));
  if (pay && paidRequests++ > 0) throw new Error("guard: refused a second paid request");
  const started = Date.now();
  const res = await fetch(req);
  wire.push({
    paid: Boolean(pay),
    payment_header: pay ?? null,
    payload: pay ? decodeB64Json(req.headers.get(pay)) : null,
    status: res.status,
    ms: Date.now() - started,
    response_headers: Object.fromEntries(res.headers.entries()),
  });
  return res;
}

// ── plan ─────────────────────────────────────────────────────────────────
const challenge = await fetchChallenge();
const req = challenge.body.accepts[0];
const planOk = challenge.status === 402 && req.network === "eip155:8453" &&
  getAddress(req.asset) === USDC && getAddress(req.payTo) === ROUTER &&
  BigInt(req.amount) === PRICE_ATOMIC;
const before = { usdc: await usdcBalance(), block: await blockNumber() };

console.log(`endpoint  ${ENDPOINT}`);
console.log(`price     ${req.amount} atomic USDC on ${req.network}, payTo ${req.payTo}`);
console.log(`payer     ${FUND} (self-payment; nets to zero)`);
console.log(`client    @x402/fetch 2.26.0 + @x402/evm ExactEvmScheme, unmodified`);
console.log(`USDC      ${before.usdc} atomic at Base block ${before.block}`);
if (!planOk) throw new Error("live challenge no longer matches the authorised payment; not paying");
if (before.usdc < PRICE_ATOMIC) throw new Error("insufficient USDC; not paying");
if (!CONFIRM) {
  console.log("\ndry run: nothing signed, nothing sent. Re-run with --confirm to pay once.");
  process.exit(0);
}

// ── the payment ──────────────────────────────────────────────────────────
const fetchWithPayment = wrapFetchWithPaymentFromConfig(guardedFetch, {
  schemes: [{ network: "eip155:8453", client: new ExactEvmScheme(bankrSigner) }],
});
const started = Date.now();
let status = null, body = null, error = null;
try {
  const res = await fetchWithPayment(ENDPOINT, { method: "GET" });
  status = res.status;
  body = await res.text();
} catch (e) {
  error = String(e.message);
}
const totalMs = Date.now() - started;
const paid = wire.find((w) => w.paid);
const paymentResponse = paid?.response_headers["payment-response"] ??
  paid?.response_headers["x-payment-response"];
const nonce = paid?.payload?.payload?.authorization?.nonce ?? null;

// ── settlement, from the chain ───────────────────────────────────────────
let settled = null, authUsed = null;
if (paid) {
  for (let i = 0; i < 30 && !(settled && authUsed); i++) {
    await new Promise((r) => setTimeout(r, 3000));
    const logs = await rpc("eth_getLogs", [{
      fromBlock: "0x" + before.block.toString(16), toBlock: "latest", address: ROUTER,
      topics: [TOPIC_SETTLED, null, pad(FUND), pad(FUND)] }]);
    for (const log of logs) {
      const receipt = await rpc("eth_getTransactionReceipt", [log.transactionHash]);
      const used = receipt.logs.find((l) => l.address.toLowerCase() === USDC.toLowerCase() &&
        l.topics[0] === TOPIC_AUTH_USED && l.topics[2] === nonce);
      if (used) {
        const d = log.data.slice(2);
        settled = {
          tx: log.transactionHash, block: Number(log.blockNumber),
          totalAmount: BigInt("0x" + d.slice(0, 64)).toString(),
          ownerAmount: BigInt("0x" + d.slice(64, 128)).toString(),
          bankrFee: BigInt("0x" + d.slice(128, 192)).toString(),
          feeBps: Number(BigInt("0x" + d.slice(192, 256))),
        };
        authUsed = { authorizer: "0x" + used.topics[1].slice(26), nonce: used.topics[2] };
      }
    }
  }
}
const after = { usdc: await usdcBalance(), block: await blockNumber() };

const result = {
  confirmed: true,
  client: { "@x402/fetch": "2.26.0", "@x402/evm": "2.26.0" },
  endpoint: ENDPOINT,
  status, body, error, total_ms: totalMs,
  requests: wire.map(({ payload, ...w }) => w),
  paid_requests: paidRequests,
  payment_header: paid?.payment_header ?? null,
  payment_payload: paid?.payload ?? null,
  payment_response: paymentResponse ? decodeB64Json(paymentResponse) : null,
  signing: signLog,
  settlement: settled,
  authorization_used: authUsed,
  usdc: { before: before.usdc.toString(), after: after.usdc.toString(),
    delta: (after.usdc - before.usdc).toString() },
  blocks: { before: before.block, after: after.block },
};
record("pay", result);

console.log(`\nresult    ${status ?? "no response"} in ${totalMs} ms${error ? ` — ${error}` : ""}`);
if (body) console.log(`body      ${body}`);
console.log(`paid requests sent: ${paidRequests} (header ${result.payment_header})`);
if (result.payment_response) console.log(`PAYMENT-RESPONSE ${JSON.stringify(result.payment_response)}`);
if (signLog.length) console.log(`signing   ${signLog[0].ms} ms via /wallet/sign, recovers to fund: ${signLog[0].recovered === FUND}`);
console.log(settled
  ? `settled   ${settled.tx} block ${settled.block}; total ${settled.totalAmount} owner ${settled.ownerAmount} fee ${settled.bankrFee} (${settled.feeBps} bps)`
  : "settled   no PaymentSettled with our nonce found within ~90 s");
if (authUsed) console.log(`nonce     AuthorizationUsed ${authUsed.nonce} by ${authUsed.authorizer} — the one this client signed`);
console.log(`USDC      ${result.usdc.before} → ${result.usdc.after} (delta ${result.usdc.delta})`);
