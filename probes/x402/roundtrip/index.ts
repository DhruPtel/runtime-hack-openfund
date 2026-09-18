/**
 * Probe 0.7 — a handler that does no work, on purpose.
 *
 * Unit 0.7 measures the x402 platform's own round-trip overhead: the 402
 * challenge, the payment, the settlement, and the cold start. Any work this
 * function does is added to every one of those numbers and cannot be separated
 * out afterwards, so the measurement would be of our code rather than of the
 * platform. No I/O, no clock read — deliberately without the
 * `new Date().toISOString()` the CLI's scaffold includes, because a clock read
 * is work.
 *
 * **It must return a `Response`.** The first version returned a plain object, on
 * the strength of the quick-start's claim that "Bankr auto-wraps" one. It does
 * not, on this runtime path: the handler ran and threw `fetch() did not return a
 * Response` (`research/findings.md` F0.7d.1), the request 500'd, and
 * settle-after-response meant nothing was charged. That was the entire cause of
 * 0.7's failed payment — not the deploy config, which F0.7d.3 shows was fine.
 * Follow the platform's scaffold, not its prose.
 *
 * Revisions 3 and 4 of this file echoed request headers to settle the
 * `x-402-payer` question (F0.7d.7) and were replaced by this one, so that what
 * is deployed matches the handler the timings in F0.7d.5 were taken against.
 *
 * Deliberately NOT the real handler. It sells nothing, signs nothing, and reads
 * no decision record.
 */
export default async function handler(_req: Request): Promise<Response> {
  return Response.json({ ok: true, probe: "0.7", work: "none" });
}
