# BankrBot/x402-cli-example — read-only research report

Date: 2026-09-17
Target: `https://github.com/BankrBot/x402-cli-example` @ `00f101e` (clone is at the
working-directory root `/home/dhrupatstudio/BNKR_play/repo_research/x402`, **not** in a
`./x402-cli-example` subdirectory).

## Evidence conventions

Two classes of citation are used, and they are never mixed:

- **In-repo** — plain paths: `src/index.ts:174`. This is the repository you asked me to read.
- **[npm]** — packages I downloaded into the session scratchpad because the repo itself
  contains no payment code at all. Cited as `[npm] <pkg>@<ver> <path>:<line>`. These are
  public, unminified, unpacked from `npm pack`. Nothing was installed into the repo; the
  repo is untouched apart from this file.

The three scratchpad packages:

| package | version | why |
|---|---|---|
| `@bankr/sdk` | `0.1.0-alpha.8` | exact version pinned at `package.json:11` |
| `x402-fetch` | `1.2.0` | the SDK's payment dependency |
| `x402` | `1.2.0` | `x402-fetch`'s core (schemas, signing, selector) |

**Headline caveat: the repository contains zero lines of x402 protocol code.** A grep for
every payment term across all six files returns only prose in `README.md`, a keyword in
`package.json`, and one comment (`src/index.ts:65`). Every question you asked in sections
2–9 is answered from the SDK chain, not from the repo. Where I could not read something,
it is marked **not present** rather than guessed, and every inference is labelled
**[INFERRED]**.

---

## 1. ORIENTATION

An interactive terminal REPL that sends natural-language prompts to the Bankr AI agent and
prints the reply. Each prompt costs $0.10 USDC on Base, paid automatically via x402.

**Entry point:** `package.json:8` → `bun run src/index.ts`; `main()` defined at
`src/index.ts:69`, invoked at `src/index.ts:256`.

**Directory map** — the entire repository is six files:

```
.env-example      4 lines
.gitignore       17
README.md        82
package.json     39
tsconfig.json    17
src/index.ts    260
                419 total
```

Git history is three commits, all files added in the first (`cf72162`); only `README.md`
and `package.json` were ever modified. No branches beyond `main`, no deleted files.

Of the 260 lines in `src/index.ts`, roughly 120 are process-lifecycle scaffolding
(`src/index.ts:73-137`: unhandled-rejection, uncaught-exception, `beforeExit`, SIGINT/SIGTERM
handlers and a 1-second `setInterval` keep-alive at `src/index.ts:95-97`). The actual
application logic is about 60 lines.

**Dead code worth knowing about**, because it makes the repo look like it does more than it
does:

- `src/index.ts:47-52` builds a viem `walletClient` on Base. It is never referenced again —
  grep for `walletClient` in the repo returns only its declaration. The comment "for tx
  execution" describes a feature that does not exist: transaction execution is explicitly
  skipped at `src/index.ts:209-213`.
- `src/index.ts:20` and `src/index.ts:47` call `privateKeyToAccount` on the same key twice.
- The viem imports at `src/index.ts:6-8` exist only to serve that dead client.

So: **`viem` appears in this repo's imports but plays no part in payment.** The signing
happens inside the SDK, which has its own viem.

---

## 2. THE PAYMENT FLOW, STEP BY STEP

The repo's entire contribution is two calls:

```ts
const client = new BankrClient({ privateKey, walletAddress });   // src/index.ts:32-35
const result = await client.promptAndWait({ prompt: input });    // src/index.ts:174
```

Everything below `src/index.ts:174` is the SDK chain.

### Step 0 — client construction

`[npm] @bankr/sdk dist/client.js:6-41`. Notable:

- `baseUrl` defaults to **`https://api-staging.bankr.bot`** (`client.js:7`). The CLI never
  overrides it (`src/index.ts:32-35`), so this example points at **staging**, while the SDK
  README's own example uses `https://api.bankr.bot`. Flagging because it is easy to copy the
  wrong default.
- `timeout` defaults to `10 * 60 * 1000` — ten minutes (`client.js:8`).
- `network` is hardcoded to `"base"` with a comment saying not to change it (`client.js:11-12`).
- The payment-capable fetch is built once (`client.js:36`):

```js
this.wrappedFetch = wrapFetchWithPayment(fetch, this.walletClient, BigInt(1 * 10 ** 6));
```

### Step 1 — the unpaid request

`[npm] @bankr/sdk dist/client.js:73-78`:

```js
const response = await fetchFunction(`${this.baseUrl}/v2/prompt`, {
  method: "POST",
  headers,                       // Content-Type: application/json, wallet-address: 0x…
  body: JSON.stringify(requestBody),
  signal: AbortSignal.timeout(this.timeout),
});
```

The first hop is a plain unpaid POST (`[npm] x402-fetch dist/cjs/index.js:35`). If the status
is anything other than 402 it is returned untouched (`x402-fetch index.js:36-38`) — note this
means a 200 costs nothing and no payment is attempted.

**What comes back on 402:** a JSON body `{ x402Version, accepts }` (`x402-fetch index.js:39`).
The challenge is read from the **body**, not from a header. This is a real divergence from the
`payments.sh` preflight you described, which base64-decodes a payment-required *header* — I
can only see the body path here; a header-borne challenge would be ignored by this client.
The SDK's type for the body is `X402ErrorResponse { x402Version, error, accepts }`
(`[npm] @bankr/sdk dist/types.d.ts:301-305`).

### Step 2 — parsing the challenge

`[npm] x402-fetch dist/cjs/index.js:39-40`:

```js
const { x402Version, accepts } = await response.json();
const parsedPaymentRequirements = accepts.map((x) => PaymentRequirementsSchema.parse(x));
```

Fields read, per the zod schema at `[npm] x402 dist/cjs/types/index.js:1273-1285`:

| field | type | used for |
|---|---|---|
| `scheme` | enum | selector filter; must be `"exact"` |
| `network` | closed enum (see §7) | selector filter, chainId derivation |
| `maxAmountRequired` | integer string | the cap check, and the signed `value` |
| `resource` | url | **parsed, never used** |
| `description` | string | **parsed, never used** |
| `mimeType` | string | **parsed, never used** |
| `outputSchema` | record, optional | **parsed, never used** |
| `payTo` | address | signed as the `to` of the transfer |
| `maxTimeoutSeconds` | int | becomes `validBefore` |
| `asset` | address | EIP-712 `verifyingContract`; USDC preference |
| `extra` | record, optional | EIP-712 domain `name` and `version` |

Selection among multiple `accepts` entries — `[npm] x402 dist/cjs/client/index.js:706-722`:
filter by scheme and by the wallet's network, then **prefer** the entry whose `asset` equals
the canonical USDC address for that chain, else the first surviving entry, else
`paymentRequirements[0]`. That last fallback is important and is discussed in §3.

### Step 3 — constructing and signing the payment

`[npm] x402 dist/cjs/client/index.js:525-549` (`preparePaymentHeader`):

```js
const nonce = createNonce();
const validAfter  = BigInt(Math.floor(Date.now() / 1e3) - 600).toString();       // now − 10 min
const validBefore = BigInt(Math.floor(Date.now() / 1e3 + paymentRequirements.maxTimeoutSeconds)).toString();
```

with `to: paymentRequirements.payTo`, `value: paymentRequirements.maxAmountRequired`,
`from:` the wallet address. `createNonce()` is 32 random bytes from webcrypto
(`client/index.js:489-493`).

Signing — `[npm] x402 dist/cjs/client/index.js:453-488`:

- **Scheme:** EIP-3009 `TransferWithAuthorization`, typed at `client/index.js:105-114`.
- **Library:** viem `signTypedData`, via the wallet client the SDK built.
- **Key:** the raw `PRIVATE_KEY` from `.env`, turned into an account at
  `[npm] @bankr/sdk dist/client.js:29`.
- **Chain:** `chainId` is derived from the *challenge's* `network` field, not from the
  wallet's chain (`client/index.js:454`).
- **Domain:** `{ name: extra?.name, version: extra?.version, chainId, verifyingContract: asset }`
  (`client/index.js:455-464`). The domain `name` and `version` are taken **verbatim from the
  server's `extra` blob**.

This is a **gasless signature, not a transaction.** The client signs an authorization; the
facilitator submits it onchain and pays the gas. That is why the client needs USDC but no ETH.

### Step 4 — the retry with payment attached

`[npm] x402-fetch dist/cjs/index.js:56-69`:

```js
if (init && init.__is402Retry) {
  throw new Error("Payment already attempted");
}
const newInit = {
  ...init,
  headers: {
    ...(init?.headers) || {},
    "X-PAYMENT": paymentHeader,
    "Access-Control-Expose-Headers": "X-PAYMENT-RESPONSE"
  },
  __is402Retry: true
};
const secondResponse = await fetch(input, newInit);
return secondResponse;
```

**Header:** `X-PAYMENT`. **Encoding:** base64 of the JSON payment payload
(`encodePayment`, `[npm] x402 dist/cjs/schemes/index.js:1373-1389`, using `btoa`/Buffer at
`[npm] x402 dist/cjs/shared/index.js:60-65`). The payload shape is
`{ x402Version, scheme, network, payload: { signature, authorization: {from,to,value,validAfter,validBefore,nonce} } }`
(`[npm] x402 dist/cjs/types/index.js:1286-1306`).

### Step 5 — what the client does with the response

`wrapFetchWithPayment` returns `secondResponse` **raw and uninspected**
(`x402-fetch index.js:69`). It does not look at `X-PAYMENT-RESPONSE` — it asks the server to
expose that header (`index.js:64`) and then never reads it. `decodeXPaymentResponse` *is*
exported by the same module (`index.js:24`) but the Bankr SDK never imports it.

Back in the SDK (`[npm] @bankr/sdk dist/client.js:81-91`): a still-402 response throws
`Payment required: …`; any other non-OK throws; otherwise `response.json()` yields
`PromptResponse { success, jobId, status, message, price? }`
(`[npm] @bankr/sdk dist/types.d.ts:8-17`).

Then — and this is the architecturally interesting part — `promptAndWait`
(`client.js:139-147`) hands off to `pollJob` (`client.js:114-135`), which calls
`getJobStatus` every 2s up to 150 times. **Those status reads use plain `fetch`, not
`wrappedFetch`** (`client.js:102`), so polling is free. Auth for the free reads is a wallet
signature over a fixed message string (`client.js:93-110`):

```js
const message = `Get job status for ${jobId}`;
const signature = await this.walletClient.signMessage({ account, message });
// headers: wallet-address, x-signature, x-message
```

(`hashMessage` is computed at `client.js:96` and never used — dead.)

Finally the CLI prints `result.response` (`src/index.ts:183-187`), regex-scrapes image URLs
(`src/index.ts:190-196`), and prints but explicitly refuses to execute any returned
transactions (`src/index.ts:203-214`).

---

## 3. VALIDATION BEFORE PAYING

**The repository performs no validation whatsoever — it has no access to the challenge.**
The CLI calls `promptAndWait` (`src/index.ts:174`) and the next thing it sees is a result or
an exception. It never sees `accepts`, never sees an amount, never prompts the user.

Inside the SDK chain, here is the complete list. It is short.

| # | Check | Where | Verdict |
|---|---|---|---|
| 1 | Structural shape of each `accepts` entry (zod) | `[npm] x402-fetch index.js:40` | present |
| 2 | `scheme === "exact"` | `[npm] x402-fetch index.js:45` → `x402 client/index.js:707` | present, **with fallthrough** |
| 3 | `network` matches wallet chain | `[npm] x402-fetch index.js:41` → `x402 client/index.js:708-710` | present, **with fallthrough** |
| 4 | `maxAmountRequired <= maxValue` | `[npm] x402-fetch index.js:47-49` | **the only real spend check** |
| 5 | Asset is canonical USDC | `[npm] x402 client/index.js:713-718` | **preference only, not a requirement** |

And here is what is **not** checked, plainly:

- **`payTo` is never validated.** No allowlist, no comparison to anything. Whoever the
  challenge names as payee gets signed into the authorization
  (`[npm] x402 client/index.js:542`).
- **`maxTimeoutSeconds` is never bounded.** It is fed straight into `validBefore`
  (`[npm] x402 client/index.js:531`). A server returning a large value gets a long-lived
  signed authorization against the payer's USDC.
- **`x402Version` is never validated** on the outbound path. It is destructured
  (`x402-fetch index.js:39`) and passed into the payload (`index.js:51`) unchecked. The schema
  that *would* validate it (`x402 types/index.js:1302`) is applied to inbound payloads on the
  server side, not here.
- **`resource` is never compared to the URL actually being fetched.** A challenge may name a
  different resource than the one requested; nothing notices.
- **`extra.name` / `extra.version`** — server-controlled strings placed directly into the
  EIP-712 domain (`x402 client/index.js:455-456, 460-461`) with no validation.
- **No user confirmation.** Nothing in this stack shows a human the amount before signing.

Two fallthroughs deserve emphasis, because they weaken checks 2 and 3 into near-nothing.
`selectPaymentRequirements` ends (`[npm] x402 dist/cjs/client/index.js:713-722`):

```js
if (usdcRequirements.length > 0)                 return usdcRequirements[0];
if (broadlyAcceptedPaymentRequirements.length>0) return broadlyAcceptedPaymentRequirements[0];
return paymentRequirements[0];
```

If nothing matches the scheme/network filter, it returns `accepts[0]` — **an entry that passed
no filter at all.** Since `signPaymentHeader` only requires that the network be in
`SupportedEVMNetworks` (`client/index.js:725`), a challenge offering, say, only Polygon to a
Base-configured wallet would fall through and be signed for chainId 137. **[INFERRED]** — I
read the code path but did not execute it.

**Direct answer to your question: this client substantially trusts the challenge.** Compared
to your `quotient/scripts/payments.sh` preflight, which validates x402Version, scheme,
network+asset, payTo, maxTimeoutSeconds *and* amount, this client validates only the amount
cap plus a soft scheme/network preference. **`payments.sh` is strictly stronger. Keep it.**

---

## 4. SPEND CONTROLS

**One control exists: a per-call cap.** `[npm] x402-fetch dist/cjs/index.js:47-49`:

```js
if (BigInt(selectedPaymentRequirements.maxAmountRequired) > maxValue) {
  throw new Error("Payment amount exceeds maximum allowed");
}
```

- **Default** (library): `BigInt(0.1 * 10 ** 6)` = 100000 = **$0.10** (`x402-fetch index.js:32`).
- **As set by Bankr:** `BigInt(1 * 10 ** 6)` = **1 USDC** (`[npm] @bankr/sdk dist/client.js:36`).

Note the comment on that line: `// Set a higher maxValue to allow larger payments (e.g., 10
USDC worth)`. **The comment says 10 USDC; the code passes 1 USDC.** Either the comment is stale
or the constant is wrong; either way, do not read the comment as the limit.

- **Not configurable through the SDK.** `BankrClientConfig`
  (`[npm] @bankr/sdk dist/types.d.ts:306-312`) exposes `baseUrl`, `timeout`, `walletAddress`,
  `privateKey`, `network` — there is no cap field. The 1 USDC value is hardcoded. A consumer of
  `@bankr/sdk` cannot lower or raise it.
- **Cumulative cap: none.** Per-call only. Nothing counts spend across calls, per hour, or per
  day. Twenty prompts is twenty independent $0.10 payments with twenty independent cap checks,
  each of which passes.
- **On exceeded:** a thrown `Error`, before any signing. It surfaces in the CLI at
  `src/index.ts:216-225` as red text. Fails closed — good.
- **Dry-run / preview: not present.** Nothing anywhere fetches the challenge to display it
  without paying. The `PromptResponse.price` field
  (`[npm] @bankr/sdk dist/types.d.ts:13-16`) arrives *after* payment, so it is a receipt, not a
  quote.

---

## 5. THE SDK SURFACE

The repo imports (`src/index.ts:1-8`): `dotenv`, `@bankr/sdk`, `ora`, `chalk`,
`readline/promises`, `viem` (dead, §1).

It calls exactly two SDK things:

```ts
new BankrClient({ privateKey, walletAddress })   // src/index.ts:32-35
await client.promptAndWait({ prompt: input })    // src/index.ts:174
```

**In → `promptAndWait`:** `PromptOptions & Omit<PollOptions,"jobId">` =
`{ prompt, walletAddress?, xmtp?, interval?, maxAttempts?, timeout? }`
(`[npm] @bankr/sdk dist/types.d.ts:313-323`, `dist/client.d.ts:29`). The CLI passes only
`prompt`, so all polling defaults apply.

**Out:** `JobStatus` (`[npm] @bankr/sdk dist/types.d.ts:285-300`) —
`{ success, jobId, status: "pending"|"processing"|"completed"|"failed"|"cancelled", prompt,
createdAt, processingTime?, response?, error?, startedAt?, completedAt?, transactions?,
richData?, cancellable? }`. The CLI reads `.response` and `.transactions`
(`src/index.ts:183, 203`).

Full public surface, unused by this repo but available
(`[npm] @bankr/sdk dist/client.d.ts:20-34`): `prompt()`, `getJobStatus()`, `pollJob()`,
`promptAndWait()`, `cancelJob()`, `getWalletAddress()`.

**The SDK is not closed-source in any meaningful sense.** `@bankr/sdk@0.1.0-alpha.8` ships
plain, unminified ESM in `dist/` (180 lines in `client.js`) with `.d.ts` files. The `.js.map`
files are all zero bytes, so there is no original TypeScript, but the shipped JS is entirely
readable — which is how this report answers §2–§4. **You can read inside it.** That corrects
the assumption in your brief.

The chain below it: `@bankr/sdk` → `x402-fetch@1.2.0` → `x402@1.2.0` (x402 Foundation,
Apache-2.0, `https://github.com/x402-foundation/x402`). Both are open source and readable.

**Fragility flag:** `[npm] @bankr/sdk package.json:29` declares `"x402-fetch": "^latest"`.
That is not a valid semver range. The payment library — the thing that signs — is effectively
unpinned. Do not copy this.

---

## 6. KEYS AND AUTH

**A raw private key, and nothing else. No Bankr API key.**

- `.env-example:2` — `PRIVATE_KEY=0xYourPrivateKeyHere # Payment wallet private key for x402
  USDC payments`.
- Loaded via `dotenv` at `src/index.ts:11`, read at `src/index.ts:19`, hard exit if absent
  (`src/index.ts:14-17`).
- Passed whole into `BankrClient` (`src/index.ts:33`) and into `privateKeyToAccount`
  (`src/index.ts:20, 47`).
- The SDK throws if it is missing — twice (`[npm] @bankr/sdk dist/client.js:19` and `:39`).
- **Storage:** plaintext `.env` on disk, gitignored (`.gitignore:5-6`). No keystore, no KMS,
  no encryption, no hardware signer path. The SDK README states the SDK is for server
  environments, not browsers.
- **No API key.** The SDK README is explicit: *"No API Key Required: The v2/prompt endpoint
  uses standard x402 payment protocol, so no API key is needed."* The `ApiKeyResponse` type at
  `[npm] @bankr/sdk dist/types.d.ts:1-7` is vestigial — nothing constructs it.

**Two distinct wallets, worth internalising for our design** (`.env-example:2-3`, and the SDK
README's own note): the **payment wallet** (from `PRIVATE_KEY`) spends the $0.10; the
**context wallet** (`WALLET_ADDRESS`, defaulting to the derived address at `src/index.ts:21`)
is the identity the agent reasons about and sends proceeds to. They can differ. The context
wallet travels as a body field and a `wallet-address` header
(`[npm] @bankr/sdk dist/client.js:57-69`) — it is **asserted, not proven**, on the prompt call.
Job reads, by contrast, *are* signature-authenticated (`client.js:98-107`).

**Funds: self-custodied. Bankr does not custody the payment.** The payer's own wallet must
hold USDC on Base (`README.md:15`, SDK README: *"Ensure you have USDC tokens in your wallet"*).
But note the client never submits a transaction — it signs an EIP-3009 authorization
(§2 step 3) which a facilitator settles. **So the payer needs USDC but does not need ETH for
gas.** That is a meaningful operational simplification for a swarm of paying agents.

---

## 7. ASSETS AND CHAINS

**Base + USDC only, and it is hardcoded in three places.**

- `[npm] @bankr/sdk dist/client.js:12` — `this.network = "base";` with the comment *"Network is
  payment network, not the chain the user is on. Shouldn't set this to anything other than
  base."*
- `[npm] @bankr/sdk dist/client.js:45-47` — `getChainForNetwork(network) { return base; }`.
  It **ignores its argument entirely** and returns viem's `base`.
- `[npm] @bankr/sdk dist/types.d.ts:311` — `network?: "base"` is a single-member type union.
- `src/index.ts:8, 50` — the (dead) CLI client is also Base.
- RPC: `http()` with no URL (`client.js:25, 32`) → viem's default public Base endpoint. No
  configurable RPC, no fallback.

USDC on Base = `0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913`
(`[npm] x402 dist/cjs/client/index.js:41-43`, chain `8453`). Price $0.10 = `100000` base units
(`README.md:72`, SDK README).

### USDG on chain 4663 — a definitive no

The underlying `x402@1.2.0` supports 15 EVM networks and 2 SVM networks
(`[npm] x402 dist/cjs/types/index.js:71-127`): abstract, abstract-testnet, base-sepolia, base,
avalanche-fuji, avalanche, iotex, sei, sei-testnet, polygon, polygon-amoy, peaq, story,
educhain, skale-base-sepolia, plus solana and solana-devnet.

**Chain 4663 does not appear. Nor does any Robinhood Chain entry. Nor USDG** — the asset config
at `[npm] x402 dist/cjs/client/index.js:33-100` lists USDC/bridged-USDC addresses only.

This is not merely "unsupported" — it is **actively rejected**. `NetworkSchema` is a closed
zod enum (`types/index.js:71-89`), and every `accepts` entry is parsed through it at
`[npm] x402-fetch dist/cjs/index.js:40`. A challenge advertising `network: "robinhood"` or any
chain-4663 identifier would **throw a zod error before any selection or signing occurs**.

**Consequence for us:** if our fund's endpoint prices in USDG on 4663, no `x402-fetch`-based
client — including every Bankr SDK consumer — can pay it without a patched or forked `x402`
core that adds the network to the enum, the chain-id map, and the asset config. Conversely,
if we want to be payable by the existing ecosystem today, we must price in USDC on one of the
17 listed networks. This is the single most consequential finding in this report for our
architecture.

---

## 8. FAILURE HANDLING

| Scenario | Behaviour | Evidence |
|---|---|---|
| **402 loop** | Bounded at exactly two fetches. The retry carries `__is402Retry: true`; a second 402 path throws `Payment already attempted`. A still-402 second response is returned raw, then the SDK throws `Payment required: …`. No infinite loop. | `[npm] x402-fetch index.js:56-58, 68-69`; `[npm] @bankr/sdk client.js:81-84` |
| **Insufficient funds** | Not detected client-side. No balance check before signing. The facilitator reports `insufficient_funds` (one of the protocol `ErrorReasons`), surfacing as a second 402 → generic `Payment required` throw. | `[npm] x402 types/index.js:1225-1226`; `[npm] @bankr/sdk client.js:83` |
| **Expired challenge** | No client-side clock or freshness check. `validAfter` is backdated 10 minutes for clock skew; `validBefore` is whatever `maxTimeoutSeconds` says. Expiry is enforced onchain/by the facilitator, not here. | `[npm] x402 client/index.js:526-532` |
| **Settlement failure** | **Invisible to the client.** `X-PAYMENT-RESPONSE` is requested but never decoded; `decodeXPaymentResponse` is exported and never called. The client cannot distinguish "settled" from "not settled". | `[npm] x402-fetch index.js:64, 24, 69` |
| **Timeout** | POST aborts at 10 min (`AbortSignal.timeout`). Polling: 2s interval, 150 attempts, 300s wall clock, each bound throwing its own error. | `[npm] @bankr/sdk client.js:8, 77, 114-135` |
| **Retry logic** | **None for the paid POST.** Zero retries, no backoff. `pollJob` retries only the *free* status reads. The CLI catches, prints red, and returns to the prompt — it does not retry. | `[npm] @bankr/sdk client.js:121-133`; `src/index.ts:216-233` |

### Can a retry double-pay? Yes.

The library's own guard is narrow and slightly misplaced: `__is402Retry` is checked at
`[npm] x402-fetch index.js:56` — **after** `createPaymentHeader` has already run at line 50.
The wasted signature is harmless in itself (an unsubmitted authorization does not move funds),
but it shows the guard is an afterthought. It also only protects within a single
`wrappedFetch` call.

The real exposure is the **lost-response window**. Each attempt mints a fresh random nonce
(`[npm] x402 client/index.js:489-493`), so every authorization is a distinct, independently
settleable payment. If the server receives and settles the payment but the response is lost —
abort at the 10-minute deadline, dropped connection, process crash between line 68 and line 69
of `x402-fetch` — the client throws. **The money is gone and the client holds no record of it.**
If the caller (a human at `src/index.ts:236-247`, or an agent in our design) simply re-submits
the prompt, a new nonce is signed and **paid again for the same logical work**.

Nothing in this stack mitigates that: no persisted nonce log, no client-side receipt, no
reconciliation against `X-PAYMENT-RESPONSE`, no idempotency key (§Q3). For a swarm making
unattended paid calls on a retry loop, this is the failure mode to engineer against first.

---

## 9. DISCOVERY

**Hardcoded. No discovery of any kind.**

The only endpoint is `` `${this.baseUrl}/v2/prompt` `` (`[npm] @bankr/sdk dist/client.js:73`),
with `baseUrl` from config or the staging default (`client.js:7`). Job endpoints are likewise
templated (`client.js:102, 156`). There is no search, no registry lookup, no marketplace call
anywhere in the repo or the SDK.

The underlying `x402` core *defines* a discovery protocol that nothing in this path uses
(**[INFERRED]** that Bankr does not use it — I found no call site, only the type definitions):

```js
// [npm] x402 dist/cjs/types/index.js:1327-1334
var DiscoveredResourceSchema = z.object({
  resource: z.string(),
  type: z.enum(["http"]),
  x402Version: z.number().refine((val) => x402Versions.includes(val)),
  accepts: z.array(PaymentRequirementsSchema),
  lastUpdated: z.date(),
  metadata: z.record(z.any()).optional()
});
```

with a paginated list request/response at `types/index.js:1355-1368`
(`{ type?, limit?, offset? }` → `{ x402Version, items[], pagination:{limit,offset,total} }`).

**So a listing is: a URL, plus the full `accepts` array — the same payment requirements the
endpoint would return in its 402.** That is the shape our fund's endpoint would need to expose
if we ever want it found programmatically. Which registry serves this is not determinable from
these packages.

---

## 10. VERDICT

### Patterns worth stealing

1. **Pay-then-poll: the paid call returns a job ID, not the work.** `prompt()` pays and returns
   `{ jobId }` immediately (`[npm] @bankr/sdk dist/client.js:91`, `dist/types.d.ts:8-17`);
   `pollJob` then reads status on a **free, unpaid** `fetch` (`client.js:102`). This decouples
   payment latency from compute latency entirely, and it is the direct answer to your swarm
   question (§Q1). Steal this.
2. **Signature-authenticated free reads.** Sign a deterministic message
   (`` `Get job status for ${jobId}` ``) and send `wallet-address` / `x-signature` / `x-message`
   (`client.js:93-107`). Cheap, keyless, no session state — the result is bound to the wallet
   that paid without needing an API key.
3. **Fail-closed cap check before signing.** `[npm] x402-fetch index.js:47-49` throws before any
   key material is used. The right shape; the wrong *placement* (a library default, not a
   caller policy) — see below.
4. **Gasless EIP-3009 authorization rather than a transaction** (`[npm] x402 client/index.js:453-488`).
   Payers need only the token, never the gas asset. Materially simplifies funding N agent wallets.
5. **Two-wallet split** — payment wallet vs. context wallet (`.env-example:2-3`,
   `src/index.ts:21`). Lets a low-balance hot key do the spending while the portfolio address
   stays separate. Directly applicable to our treasurer/analyst split.

### Fragile — do not copy

1. **Trusting the challenge.** No `payTo` allowlist, no `maxTimeoutSeconds` bound, no
   `x402Version` check, no `resource`/URL match, asset merely *preferred* (§3). Our agents must
   not inherit this.
2. **`selectPaymentRequirements`'s final `return paymentRequirements[0]`**
   (`[npm] x402 client/index.js:721`) — returns an entry that satisfied no filter, defeating the
   scheme and network checks.
3. **Unbounded `maxTimeoutSeconds` → `validBefore`** (`client/index.js:531`): a server-chosen
   value determines how long a signed claim on our USDC stays live.
4. **The 1 USDC cap is hardcoded and misdocumented** — `BigInt(1 * 10 ** 6)` under a comment
   claiming 10 USDC (`[npm] @bankr/sdk dist/client.js:36`), with no config field to change it
   (`dist/types.d.ts:306-312`). Per-call only; **no cumulative budget** (§4).
5. **`"x402-fetch": "^latest"`** (`[npm] @bankr/sdk package.json:29`) — an invalid, unpinned
   range on the library that signs payments.
6. **Settlement result discarded** — `X-PAYMENT-RESPONSE` requested, never read
   (`[npm] x402-fetch index.js:64, 69`). No receipt, no reconciliation. Our accountability
   swarm needs exactly this data; we would have to capture it ourselves.
7. **Raw private key in a plaintext `.env`** (`.env-example:2`), with the process holding a
   spend-capable key for its whole lifetime.
8. **Staging default** — `https://api-staging.bankr.bot` (`client.js:7`), not overridden by the
   example.
9. **Repo-level:** ~120 lines of process-lifecycle hackery including a 1s keep-alive interval
   (`src/index.ts:95-97`) and a `beforeExit` handler that logs *"This should not happen"*
   (`src/index.ts:100-108`); a `walletClient` built and never used (`src/index.ts:47-52`).
   This is demo scaffolding, not a template.

### Minimum code for an agent to pay another agent's x402 endpoint

Reading `[npm] x402-fetch dist/cjs/index.js:32-70`, the whole protocol is ~35 lines. Concretely:

1. **Fetch the URL normally.** If the status is not 402, you are done — no payment (`index.js:35-38`).
2. **Parse the 402 JSON body** into `{ x402Version, accepts }` (`index.js:39`). Body, not header.
3. **Validate each `accepts` entry structurally** against `PaymentRequirementsSchema`
   (`index.js:40`).
4. **Select one** — filter on `scheme === "exact"` and on your wallet's network; require, don't
   merely prefer, the asset (`x402 client/index.js:706-722`).
5. **Apply your own policy gate before anything else** — amount ≤ per-call cap **and** ≤
   remaining cumulative budget; `payTo` ∈ allowlist; `asset`/`network` ∈ allowlist;
   `maxTimeoutSeconds` ≤ your bound; `resource` matches the URL you requested; `x402Version`
   is one you support. Steps 5 is where `payments.sh` already lives, and where `x402-fetch`
   does only the amount half.
6. **Build the authorization**: random 32-byte `nonce`, `validAfter = now − 600`,
   `validBefore = now + maxTimeoutSeconds` (clamped by your bound), `to = payTo`,
   `value = maxAmountRequired`, `from = your address` (`x402 client/index.js:525-549`).
7. **Sign EIP-712 `TransferWithAuthorization`** with domain
   `{ name: extra.name, version: extra.version, chainId, verifyingContract: asset }`
   (`x402 client/index.js:453-474`). One `signTypedData` call. No transaction, no gas.
8. **Record the nonce and the intended payment durably, before sending** — this step is absent
   from the reference implementation and is what makes double-payment recoverable (§8).
9. **Re-issue the request** with `X-PAYMENT: base64(JSON.stringify(payload))`
   (`index.js:59-67`; encoding at `x402 schemes/index.js:1373-1389`).
10. **Decode `X-PAYMENT-RESPONSE`** to confirm settlement and capture the receipt — exported as
    `decodeXPaymentResponse` (`index.js:24`) and unused by this stack. Mark your recorded nonce
    settled.

Steps 1–4, 6, 7 and 9 are `x402-fetch` verbatim. Steps 5, 8 and 10 are what we must add.
Dependencies: `viem` (or any EIP-712 signer) plus `x402`/`x402-fetch`, or a few dozen lines of
our own if we would rather not inherit `^latest`.

### Does anything contradict your priors?

- **On the server side — no contradiction, but no confirmation either.** This repo is
  client-only. There is no `bankr.x402.json`, no handler, no `bankr x402 deploy`, nothing
  server-side anywhere in the six files. Your model of the server stands unchallenged and
  untested by this evidence. **Not present.**
- **On `payments.sh` — confirmed and strengthened.** Your preflight validates strictly more than
  this client does: it checks `x402Version`, `payTo` and `maxTimeoutSeconds`, none of which
  `x402-fetch` checks at all, and it requires network+asset where `x402-fetch` only prefers the
  asset. Two refinements: (a) the challenge here arrives in the **402 response body**, not a
  base64 header — if `payments.sh` decodes a header, confirm which shape our counterparties
  actually emit, since this client would ignore a header-only challenge; (b) `payments.sh`'s
  free-preflight-then-pay costs an extra round trip that `x402-fetch` avoids by reusing the
  first unpaid response — we can have the same validation with one fewer request.
- **One correction to your brief:** you assumed the SDK is closed and unreadable. **It is not.**
  `@bankr/sdk@0.1.0-alpha.8` publishes readable unminified JS (180 lines), and everything below
  it is Apache-2.0 open source. Sections 2–4 and 7–8 above are read, not inferred.

---

## TARGETED QUESTIONS

### Q1 — Timing signals: can a swarm cycle run inside an x402 handler?

**No measured end-to-end figure exists in the repo or the SDK.** No benchmark, no log of a real
call. The available signals are all *budgets*, not measurements:

| Signal | Value | Evidence |
|---|---|---|
| SDK request timeout (the paid POST) | 10 min | `[npm] @bankr/sdk dist/client.js:8, 77` |
| Poll interval | 2s | `client.js:115` |
| Max poll attempts | 150 | `client.js:116` |
| Poll wall-clock timeout | 300s (5 min) | `client.js:117` |
| `processingTime` in a README example | `5000` (5s) — illustrative comment, not a measurement | SDK README |
| `maxTimeoutSeconds` | server-declared, per challenge | `[npm] x402 types/index.js:1282` |

One clarification that matters: `maxTimeoutSeconds` is **not** a handler runtime budget. It
governs the validity window of the payment authorization (`validBefore`,
`[npm] x402 client/index.js:531`) — how long the facilitator has to settle, not how long our
code may run.

**The architectural answer is nonetheless clear, and it comes from Bankr's own design rather
than from a timing number: Bankr does not run the long work inside the paid handler.** The paid
POST returns a `jobId` in milliseconds (`[npm] @bankr/sdk dist/client.js:91`); the actual agent
work proceeds asynchronously and is retrieved by free, separately-authenticated polling
(`client.js:93-135`). The `JobStatus` lifecycle — `pending → processing → completed|failed`
(`dist/types.d.ts:288`) — exists precisely because the work outlives the request.

For us: **serve a cached result, or return a job handle.** Do not run a swarm cycle inside the
x402 handler. Bankr, whose workload is far lighter than an N-analyst swarm, already declined to.
If we want the decision record paid-for and fresh, the two viable shapes are (a) sell the most
recent completed decision record from cache, or (b) sell a job handle and let the buyer poll —
Bankr's exact pattern, and it reuses their signature-auth trick for the free reads.

### Q2 — Does the repo show how the handler identifies the payer (`x-402-payer`)?

**Not present.** The repo is purely a client; there is no server code, and grep finds no
`x-402-payer` anywhere in the repo or in any of the three packages.

What the protocol libraries *do* show about payer identity:

- The payer's address travels inside the `X-PAYMENT` payload as
  `payload.authorization.from` (`[npm] x402 dist/cjs/types/index.js:1287`), signed as part of
  the EIP-712 message (`client/index.js:467`).
- Server-side verification and settlement extract it from exactly there and return it as a
  `payer` field — e.g. `payer: exactEvmPayload.authorization.from`
  (`[npm] x402 dist/cjs/schemes/index.js:1477, 1493, 1524, 1592`), typed as an optional `payer`
  on the verify/settle responses (`types/index.js:1344-1352` region,
  `schemes/index.js:1178, 1183`).
- The error/challenge response schema also carries an optional `payer`
  (`types/index.js:1311`).

So in the open protocol, **payer identity is a field in the decoded payment payload, and it is
cryptographically bound to the signature — not a header the caller asserts.** Whether Bankr's
x402 Cloud additionally surfaces it to handlers as an `x-402-payer` request header is
**[INFERRED as plausible but unverifiable from these sources]** — that would be a platform
convenience layered on top, and no file I read mentions it. Worth confirming against the
platform docs before we depend on the header name.

This does mean payer identity is available and trustworthy, which our x402 endpoint needs for
per-buyer accounting in the accountability swarm.

### Q3 — Idempotency: can the same logical request be paid for twice?

**Yes, and nothing in this stack prevents it.**

- **No idempotency key exists.** The request body is `{ prompt, walletAddress?, xmtp? }`
  (`[npm] @bankr/sdk dist/client.js:54-62`) — no client-generated request ID. `PromptOptions`
  (`dist/types.d.ts:313-317`) has no field for one.
- **Every attempt is a fresh nonce.** `createNonce()` draws 32 random bytes per payment
  (`[npm] x402 client/index.js:489-493`), so two attempts at the same prompt are two
  cryptographically distinct, independently settleable authorizations. The EIP-3009 nonce
  prevents *replay of one authorization*; it does nothing about *two authorizations for the
  same work*.
- **The only guard is per-call and in-memory:** `__is402Retry`
  (`[npm] x402-fetch index.js:56-58`), scoped to a single `wrappedFetch` invocation. A new call
  — a user re-typing the prompt at `src/index.ts:236-247`, or an agent's retry loop — starts
  clean.
- **No receipt is retained.** The settlement response is never decoded (§8), so the client holds
  no evidence that a given prompt was already paid for, and cannot deduplicate even in principle.
- **`jobId` arrives too late to help** — it is minted server-side *after* payment
  (`client.js:91`), so it cannot serve as a pre-payment idempotency token.

**For our design:** if our endpoint sells a decision record, assume buyers will occasionally pay
twice for the same record, and assume our own agents will occasionally double-pay a
counterparty after a lost response. Both directions need explicit handling — a client-side
nonce/intent log written *before* signing (step 8 in §10), and a server-side dedupe key we
accept and honour. Neither comes for free from x402.
