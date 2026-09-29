# Local daily ideas

Version 0.2.4 adds **Ide hari ini** to the project home page. The three proposal types are a series continuation (or a new series without history), a new angle, and a relevant experiment. Each includes a hook, concept, rationale, difference, estimated duration, media needs, and validated source project IDs.

## Use and boundaries

Choose references in **Memori konten**, or enter a topic/audience under **Preferensi ide** if the catalogue is empty. Save preferences explicitly. English generation uses the paired **Gemini Nano local Chrome companion** from Setup. Indonesian currently shows a clearly labelled manual guide; no substitute model is called. Downloading the Nano model still requires a direct gesture in the companion. This feature never downloads a model on launch.

The home page loads saved cards before considering inference. Daily mode attempts generation at most once per local day/timezone while the home page is visible, with at least 15 minutes between automatic requests. Manual mode only generates after **Ide baru**. Manual requests have a 30-second cooldown; failed and cancelled requests count toward the daily limit. An unavailable/busy provider, empty onboarding, or active editor/render does not consume an attempt. Changing context after today's attempt requires **Ide baru**, preventing regeneration loops.

**Simpan** and **Lewati** record optional reasons; **Urungkan** removes the decision. Save again to update a reason. Saved ideas remain accessible after a new batch; this task does not turn them into projects or storyboards. Results are proposals to review, not researched facts, verified trends or predicted channel performance.

## Cache and persistence

Cache keys include local date, IANA timezone, channel profile, language/preferences, catalogue revision and feedback revision. Dates are computed by the backend clock in the timezone reported by the app. Same-day reopening/restarting uses the persistent cache. A changed key marks safe older cards as dated, stale suggestions. A language change only shows batches matching that language.

SQLite schema `user_version=2` adds one `daily_ideas` table to the existing `_memory/catalog.sqlite3`. Migration from version 1 is additive and transactional. The catalogue JSON itself stays schema v1, and no project manifest or media is migrated. The idea document is versioned independently, with a 2 MiB read bound: 14 batches, up to 30 saved ideas, 60 skipped decisions and 60 recent request receipts. Recent feedback is provided as context to the model, not training data.

Excluding, forgetting, recategorizing or changing a source revision removes dependent cached batches and saved/skipped snapshots in the same catalogue transaction. Active requests using an invalidated source are cancelled. Conservative invalidation tracks all references supplied to the model, not just the IDs it cited. Returning a source to the catalogue does not resurrect deleted cards. Profile/label changes invalidate freshness without deleting otherwise valid old proposals.

The server curates a maximum 5,000-character retrieval envelope and bounded preferences/feedback for the existing 12,000-character Nano input limit. Unselected projects, media bytes, file paths and accounts are not sent. Raw inference inputs are not persisted in the idea cache. The companion sends structured JSON through the existing loopback authenticated broker. Both the output schema and referenced IDs are checked before caching; malformed or late results are rejected. Shape/source validation does not establish factual correctness of generated prose.

## Lifecycle and editor priority

One broker request can be active at a time. A client-generated request UUID provides idempotency and cancel-before-submit protection. The home page polls status without overlapping polls; mutations invalidate older poll responses. Leaving home, hiding it, opening a new-project form, entering the editor or starting render/TTS cancels pending idea work. Editor activity leases expire after 15 seconds and renew every 5 seconds, preventing a crashed view from blocking future ideas indefinitely. Preview remains confined to the editor and its existing media-clock implementation is unchanged.

Pending requests are never resumed automatically across sidecar restarts. Completed output is persisted when the home status is reconciled. If the app exits before that reconciliation, a new manual request may be needed; the previous completed cache remains intact. Provider failures expose a message and keep the last valid dated cache, or a labelled manual guide when no cache exists.

Invalid/unsupported database documents fail visibly without resetting stored data. A damaged idea document does not prevent rendering; the active idea job is cancelled in memory before media work starts. API writes retain exact-origin/session/CSRF checks and a 64 KiB body bound. Data remains on the local device, without application-level encryption.

## Verification

Backend tests cover cache/restart/day/timezone, preferences, feedback, opt-out invalidation, malformed results, cancellation, cooldowns, parallel requests, editor/render deferral, migration, and security boundaries. The packaged runtime check uses two real bundled Python processes and a real imported PNG. Its companion output is explicitly labelled **QA FIXTURE**, not real Nano inference.

See [Task 04 results](gemini-nano-task-04-results.md) and [runtime evidence](qa/daily-ideas-runtime.json) for current verification limits.
