# Local storyboard proposals

Version 0.2.5 adds a reviewed path from **Ide hari ini** to a script and scene plan using the existing **Gemini Nano local Chrome companion**. This is Task 05; animation rendering, word timing and Shorts checks remain later tasks.

## Workflow

1. Select **Susun draft** on a daily/saved idea and choose an existing English project. Alternatively, open an English project and choose **Draft dari ide**. If no English project exists, create one using **Short baru** first.
2. Select the idea, ensure the local companion is ready, then **Susun proposal**. Generation never changes the project. English is the only enabled generation language; there is no cloud or alternate-model fallback.
3. Review the hook, source summaries and each scene. Edit narration, caption, estimated frames, visual selection, required media and static framing intent. The hook must start the first narration exactly. Uncheck scenes you do not want to apply.
4. Choose **Tambahkan** (default) or **Ganti seluruh scene dan naskah**. Replacement removes old scene/audio associations, while retaining media files and all other project settings.
5. Choose **Periksa perubahan**. Review scene counts, removed scenes, total frames, missing media and measured-audio adjustments. Editing any proposal field invalidates this summary.
6. Confirm the review checkbox and choose **Terapkan pilihan**. The project is saved atomically. **Undo** in the editor restores the previous script/scenes through the normal revision-checked save; **Redo** remains available in the current editor session.

Missing visuals are permitted in a draft and explicitly shown. Export retains the existing preflight that requires usable media. Applied scene planning notes remain visible in **Naskah & scene**; they document the reviewed proposal and are not automatically re-analyzed after later manual edits.

## Contract and provenance

A proposal envelope is created by the server with project ID, base project revision, catalogue revision, request UUID, source project IDs/revisions and a 15-minute expiry. The model supplies only hook and 1–8 scene proposals. It never supplies the project identity or revision guards.

Each scene has a name, narration, short caption, integer `estimated_frames` at 30 fps, visual need, optional registered visual/audio IDs, explicit available/missing status, source IDs and static framing intent. Only `effect: static` is accepted; scenes use the existing cut renderer. Free text about movement is a planning note, never an executable effect, shell command, file path or FFmpeg filter.

The model context contains the selected idea, opted-in source summaries, channel profile, target duration, and up to 20 registered assets that still exist. Assets are described by ID, name, kind and measured frames, not paths or media bytes. Known full narration transcripts are included only for existing untrimmed scene audio whose saved transcript equals its narration. Entire optional asset entries are removed when necessary to keep input under 12,000 characters. Cited sources that cannot fit are rejected instead of silently omitted.

Source/schema validation does not prove factual accuracy. The UI exposes source summaries and asks the user to review facts and personal claims. No performance/trend/research claim is automatically verified. Source excerpts are explicitly marked as user summaries or project excerpts.

## Timing and validation

- Estimated duration must be a strict integer, 9–1,800 frames per scene, with proposal and resulting project totals no more than 5,400 frames. The existing 60-scene and 12,000-character script limits still apply after append/replace.
- Existing narration audio is reusable only when its known transcript exactly matches the proposed narration. A changed narration requires detaching that audio and generating/importing a replacement after apply.
- Scene duration is at least the full measured audio asset duration, with `audio_in=0`; no speech is truncated to meet an estimate or target. Audio longer than the per-scene limit is rejected for manual handling.
- A selected video must cover the resulting scene, including any audio extension. A too-short video is rejected instead of shortening the narration. Images have no such duration bound.
- Unknown source/asset IDs, wrong media types, inconsistent availability, unsupported effects and extra executable fields are rejected. The proposal is revalidated both before the summary and during apply.

## Persistence, concurrency and lifecycle

Existing project schema v1 remains readable. An optional `planning` field on scenes stores the applied proposal's visual need, framing intent, original estimate and source revisions. Old scenes default to no planning notes. Use build 0.2.5 or later for projects saved with this new field; older strict-schema builds may reject it. Existing media, caption style, music, volume, atomic save, prior-version backup and audio preview clocks are preserved.

Proposals are ephemeral, bounded to 12 per sidecar and 15 minutes. The UI cancels inference on close/unmount and supports cancel-before-submit with a known request UUID. Render/TTS preempts storyboard inference. Opening a storyboard review pauses the current preview; automatic daily ideas remain deferred while the editor is active.

Any project revision or catalogue revision change after generation requires a new proposal. Excluding/forgetting sources or removing media likewise blocks review/apply. Local edits are checked against the captured client state, and the saved project is compared semantically after flushing autosave so an external edit cannot silently become the wrong Undo predecessor.

Apply runs under the repository lock and reuses its atomic manifest write and previous-version backup. Exact duplicate apply retries return the already-saved revision during the proposal session; changed payloads or a later project revision are rejected. A process restart discards proposals and replay receipts, never replays an apply. If a response was lost around shutdown, reopen the project to inspect the persisted result. Undo history is the existing in-memory editor history; the disk backup preserves the prior project version independently.

API mutations retain exact-origin/session/CSRF enforcement and a 64 KiB body bound. The raw generic AI endpoint cannot enqueue uncurated storyboard requests. All verification fixtures use separate temporary data and explicitly labelled output.

See [Task 05 results](gemini-nano-task-05-results.md) and [bundled runtime evidence](qa/storyboard-runtime.json).
