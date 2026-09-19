/**
 * Unit 2.0 — a preload for the installed Bankr CLI's `login siwe`, so the real
 * CLI runs the login while the probe keeps two promises.
 *
 * Loaded with `node --import`, before the CLI parses its arguments:
 *
 *   1. The SIWE private key never appears on a command line. The CLI takes it
 *      only as `--private-key <key>`, which would put it in the process list and
 *      shell history. This reads it from OPENFUND_SIWE_KEY_FILE and splices it
 *      into `process.argv` in-process, after the `siwe` token. The kernel's copy
 *      of the command line (`/proc/<pid>/cmdline`) never holds it.
 *
 *   2. The login's own answer is kept. The CLI prints one field of the
 *      `/cli/siwe/verify` response ("Mode"); the key's other flags, as the API
 *      reports them, would be lost. This wraps `fetch` and writes the request
 *      and response of every `/cli/siwe/*` call to OPENFUND_SIWE_RECORD, with the
 *      new API key replaced by a mask before anything is written.
 *
 * It signs nothing and sends nothing the CLI would not. Throwaway, like every
 * probe. See research/findings.md §2.0.
 */
import { readFileSync, writeFileSync } from "node:fs";

const keyFile = process.env.OPENFUND_SIWE_KEY_FILE;
const recordPath = process.env.OPENFUND_SIWE_RECORD;
if (!keyFile || !recordPath) {
  throw new Error("OPENFUND_SIWE_KEY_FILE and OPENFUND_SIWE_RECORD must both be set");
}

const at = process.argv.indexOf("siwe");
if (at < 0) throw new Error("hook.mjs expects a `login siwe` command line");
process.argv.splice(at + 1, 0, "--private-key", readFileSync(keyFile, "utf8").trim());

const record = [];
const realFetch = globalThis.fetch;

function masked(text, secrets) {
  let out = text;
  for (const secret of secrets) {
    if (secret) out = out.split(secret).join("[AGENT_API_KEY]");
  }
  return out;
}

globalThis.fetch = async (input, init = {}) => {
  const url = typeof input === "string" ? input : input.url;
  const response = await realFetch(input, init);
  if (!url.includes("/cli/siwe/")) return response;

  const text = await response.clone().text();
  let apiKey;
  try {
    apiKey = JSON.parse(text).apiKey;
  } catch {
    apiKey = undefined;
  }
  record.push({
    url,
    method: init.method ?? "GET",
    request_body: init.body ? masked(String(init.body), [apiKey]) : null,
    status: response.status,
    response_body: masked(text, [apiKey]),
    at: new Date().toISOString(),
  });
  writeFileSync(recordPath, JSON.stringify(record, null, 2) + "\n", { mode: 0o600 });
  return response;
};
