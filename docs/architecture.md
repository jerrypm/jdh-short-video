# Architecture and boundaries

## Request flow

A Next.js static export and FastAPI API share one loopback origin. React holds an editable, frame-based project; `useProject` serializes autosave operations and tracks the server revision separately from undo history. Heavy work takes a saved manifest snapshot and is processed by one background worker. Import copies and probes assets, then the UI adopts the resulting manifest while editing is temporarily disabled.

Kokoro outputs are staged under a job. Generation does not write project state. Applying a result is a separate guarded transaction: the project revision and exact scene narration must still match. This prevents a background generation task from silently replacing edited text. Applying is undoable in the current editor session; importing media resets the session history.

## Project schema v1

The manifest uses integer 30 fps frames for scene duration, source offset and narration offset. Scene ordering defines contiguous timing. Limits: 60 scenes, 60 seconds per scene, 180 seconds total, 200 assets, 512 MB per imported file/package. Visuals and narration reference importer-owned asset IDs, not arbitrary paths. Metadata and waveforms are read from actual files. Empty scenes are useful while editing but block export.

## Rendering

FFmpeg builds per-scene H.264 segments, applying fit/fill, static scale/position, source trim, optional source audio and narration. A single 1080×1920 caption raster is shared by browser preview and export, then scaled for draft output. Segments are concatenated; optional music loops beneath the result. The renderer writes narration-only WAV, scene-level SRT and a ZIP manifest/media bundle. It checks dimensions, codecs, duration and full decoding before making outputs downloadable.

No shell interpolation is used for FFmpeg. The worker receives argument arrays, confines media protocols to file/pipe, has a 15-minute process watchdog, and terminates the process group on cancellation. Failed or cancelled job output is cleaned up; interrupted jobs are reported failed after restart. One heavy job is accepted at a time.

## Security and persistence

Loopback binding, exact Host/Origin validation, SameSite strict HttpOnly session cookie, CSRF for writes, no CORS, no external media proxy. Media paths are validated under the project root; ZIP extraction enumerates only exact manifest entries and re-probes files. Manifests use fsync + atomic replace, one backup, and optimistic revision checks. This does not promise filesystem protection from malicious programs already running as the same OS user.

Development storage defaults to the project `data` directory. The native app stores projects in Application Support and supervises its bundled sidecar. `--isolated-qa` uses a separate temporary directory.

## Local Nano provider

WKWebView calls a bounded, authenticated AI broker in the sidecar. A paired Chrome document obtains allowlisted script requests and runs the local Prompt API. Suggestions require explicit review; accepted text uses existing undo and optimistic autosave. No AI output is interpreted as code, a command, or a path. See [pairing and lifecycle](chrome-ai.md). The companion tab is the chosen transport; no extension or Native Messaging host is installed.

## Opt-in content memory

The separate `_memory/catalog.sqlite3` stores a versioned JSON catalogue, user profile and selected project references in SQLite transactions. Project schema v1 and media ownership remain unchanged. Catalogue reads/retrieval refresh observed metadata for selected references; optimistic revisions guard user edits. Confirmed labels and AI proposals have separate provenance. Export receipts never imply publication. Forgetting removes the reference and its feedback, leaving the project intact. Retrieval returns bounded text and asset IDs with relevance/recency/diversity selection; it never calls a model. See [storage, recovery and retrieval contract](content-memory.md).
