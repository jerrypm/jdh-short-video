**Gemini Nano local feasibility spike**

This experiment belongs to Task 01 only. It uses Chrome's on-device LanguageModel API.
There is no cloud inference implementation, API key, alternate provider, production
project access, extension installation, or change to the shipped Mac application.

Run from the project root:

```sh
python3 experiments/nano-local-spike/server.py
```

Open the printed loopback URL in your permitted personal Chrome profile. Check
capabilities first. Prepare the model only if Chrome says a download is needed.
Then run the inference and cancellation checks. Video playback is optional and
uses the repository's existing rendered QA fixture.

The page checks actual English and Indonesian capabilities independently. It
never declares Indonesian text to be English to bypass capability checks.
Unsupported languages remain unavailable.

The cold sample is the first prompt in a new session, not a cold browser process.
The warm sample reuses that session. Both outputs must pass JSON structure and
semantic validation. Timing is measured in the browser, not by automation latency.

**Backend connection experiment**

Click “Hubungkan companion lokal”. The server prints a temporary connection
file path. That file contains an ephemeral token and has owner-only permissions.
Pass its actual path to the native backend-side client:

```sh
python3 experiments/nano-local-spike/client.py /path/printed/by/server/connection.json
```

The prototype supports only a fixed public ideas fixture. The Python client
enqueues a job locally; the Chrome page claims it, calls Nano, validates the
result, and returns it to the local broker. It does not accept arbitrary commands
or filesystem paths. The companion must remain open.

To test disconnection, close the companion while a request runs. The broker
expires the lease after six seconds without heartbeat and reports a failure.
Open the page again, reconnect, and submit a new request to check recovery.
This is a loopback tab prototype, not Chrome Native Messaging or a production
AIProvider integrated into the Mac editor.

**Verification**

```sh
node --test experiments/nano-local-spike/validation.test.mjs
node --check experiments/nano-local-spike/spike.js
python3 experiments/nano-local-spike/security_smoke.py
```

The security smoke check expects the default server port and no active report
write. It validates host/origin/token rejection, forbidden paths, malformed
payloads, and the operation allowlist without changing the report.

Reports are saved under the project's docs/qa directory. The browser report is
the latest page session; preserve a copy before starting another session if you
need previous results. Server shutdown removes the temporary connection file.

**Scope limits**

The page enforces same-origin requests with a restrictive CSP, and the broker
binds only to 127.0.0.1. These controls do not constitute an OS-wide offline audit
of Chrome. No browser flags, security policies, network interfaces, or work
profiles are changed.

The companion heartbeat is intentionally a feasibility mechanism. Background
tab throttling, sleep/wake, full browser restart, long-running lifecycle, and
packaged app integration need production validation in a later task.
