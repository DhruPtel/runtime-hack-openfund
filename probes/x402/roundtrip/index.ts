/**
 * Probe 0.7 — a handler that does no work, on purpose.
 *
 * Unit 0.7 measures the x402 platform's own round-trip overhead: the 402
 * challenge, the payment, the settlement, and the cold start. Any work this
 * function does is added to every one of those numbers and cannot be separated
 * out afterwards, so the measurement would be of our code rather than of the
 * platform.
 *
 * So: no I/O, no await, no allocation that depends on the request, no clock
 * read. It returns the same frozen literal to every caller. If a paid call
 * takes seconds, this file is not the reason — which is the whole point, and is
 * what makes the number evidence for or against the cached-record design in
 * `planning/PHASE-0-1.md` 1.4 / 7.x.
 *
 * Deliberately NOT the real handler. It sells nothing, signs nothing, and reads
 * no decision record.
 */
export default function handler(_req: Request) {
  return { ok: true, probe: "0.7", work: "none" };
}
