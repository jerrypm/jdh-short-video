# Gemini Nano local companion

Version 0.2.2 connects the native Mac editor to a Chrome companion tab. Nano runs through Chrome's local `LanguageModel` API; WKWebView does not host the model. No cloud provider, API key, embedded Chromium, browser extension, or Native Messaging registration is used. This follows the companion-tab route proven in Task 01. The original extension/Native Messaging design remains unimplemented.

## Connect

1. Open the Mac app → **Setup & pengaturan** → **Buat tautan companion**.
2. Copy the link and open it in your personal Chrome profile. It expires after three minutes and can be used once.
3. If required, select **Siapkan model lokal** in the companion. Chrome owns eligibility, the initial download, and model storage. Nano is not bundled in the app or DMG.
4. Keep Chrome and that tab open. Return to an English project and select **Buat 3 hook** or **Buat draf naskah**.
5. Review, then apply explicitly. Only the main script changes; scenes stay intact. Undo restores the script. A proposal cannot be applied after the project changes.

English text is enabled. Task 01 measured English available and Indonesian unavailable on this Mac; the companion rechecks both explicitly. Manual editing, imported audio, Kokoro, and rendering remain usable without Nano. Image/audio inference is not wired into Task 02.

If Chrome reports `ERR_BLOCKED_BY_CLIENT`, inspect the policy or extension causing the block in the personal profile. The app does not bypass browser security or change browser settings. Do not use a work profile. This error blocked the integrated build's live Nano check in Task 02; fixture tests do not resolve that verification gap.

## Lifecycle and limits

- The existing sidecar uses a random loopback port. Pairing lives only for that app session. The single-use code travels in the URL fragment and is removed after parsing; it never appears in an HTTP request URL.
- The companion token is stored in tab-scoped `sessionStorage`; the broker retains only its hash. New pairing or **Putuskan koneksi** revokes the previous companion. Restarting the app requires a new link.
- Reloading the tab creates a new document ID; in-flight work fails and is never replayed. Closing the tab or Chrome makes AI unavailable after the connection lease. Submit a fresh request after reconnecting.
- One active request; up to 32 recent records; 120-second server deadline; ten-second lease after last contact. Held polls return within five seconds, avoiding dependence on throttled background timers. Inference aborts at 115 seconds; the editor's outer deadline is 125 seconds.
- The request UUID exists before submission: cancel can prevent a late POST from starting work. Cancel/reload/disconnect/timeout reject late results. Each inference session is destroyed in `finally`. Page closure aborts controllers; app shutdown revokes pairing.
- Source text is cleared on terminal status. Terminal records/results expire from memory after ten minutes, checked on broker activity. Unapplied results are not saved in project files. Source text and credentials are not intentionally logged.

## Security and data flow

`AIProvider` → editor API → in-memory broker → paired Chrome document → local Nano → schema/broker/frontend validation → review → existing undo/autosave.

Editor APIs retain exact Host/Origin, same-site session cookie and CSRF protection. Companion mutations require exact same-origin and a separate credential; that credential alone grants no project API access. Assets are allowlisted and use a self-only CSP. No CORS or arbitrary command/path/model operation is exposed. Only hooks/draft are accepted: 64 KiB messages, 12,000-character input, 3,000 characters per suggestion. Context usage is checked when Chrome exposes it. Validation rejects unexpected counts, duplicates and blank/oversized output.

These guards are not a boundary against malicious software running as the same OS user. Valid JSON also does not guarantee factual correctness; review remains necessary.

## Verification

- [Task 01](gemini-nano-task-01-results.md): real English Nano inference and prototype round trip/cancel/reconnect passed.
- [Task 02](gemini-nano-task-02-results.md): native integration and isolated tests, with an explicit live-browser limitation.
- `script/qa_nano_fixture.py` returns labelled fake responses for UI QA. It refuses non-QA storage. It is not a runtime fallback or evidence of inference.

API reference: [Chrome Prompt API](https://developer.chrome.com/docs/ai/prompt-api).
