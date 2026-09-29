# Local content memory

Version 0.2.3 adds **Memori konten** to the project home page. This is the opt-in catalogue for later idea assistance, not an automatic daily-idea feature. It makes no model calls, opens no accounts, and reads no videos or audio for analysis.

## Use

1. Open **Memori konten → Pilih proyek** and select the projects to remember. Nothing is selected by default; at most 30 can be added in one action.
2. Review the category and **Sertakan dalam konteks ide**. QA/test/demo/fixture name prefixes and duplicate content fingerprints start excluded. These are simple rules, not AI classifications; correct the category if needed.
3. Fill in themes, audience, series, format, summary and hook, then **Simpan referensi**. Empty summary/hook fields use clearly attributed project excerpts during retrieval.
4. Mark **Sudah saya publikasikan** only when you have published it. A completed local render is labelled exported and never sets this checkbox.
5. Add optional idea feedback (saved/skipped/used and a reason), and set the channel profile separately.
6. Use **Cari konteks** to inspect the bounded reference selection. This does not start Nano.

Forms save explicitly. Save or cancel a draft before changing sections; unrelated feedback actions cannot overwrite unfinished label edits. **Muat ulang** refreshes source metadata and resolves a stale view after a revision conflict.

Excluding a reference keeps its labels for later use. **Hapus referensi** removes the catalogue entry, its labels and feedback. The source project and media are unchanged. Re-adding the project starts a fresh reference. There is no saved retrieval cache in Task 03; forgetting increments catalogue revision and the next retrieval excludes that source.

## Ownership and provenance

- `observed`: source project ID/revision, language, name, timestamp, timeline frames, target duration, registered asset IDs, bounded script/opening excerpts, duplicate fingerprint, and completed render receipt ID/revision. Timeline duration is not a measured final-video duration. A target remains separately labelled as a target.
- `confirmed`: labels entered by the user. Channel profile, inclusion/category, publication confirmation, and feedback also come from the user.
- `suggested`: separately typed, unconfirmed local-Nano proposal reserved for later tasks. Task 03 neither creates nor accepts AI label proposals over its API. Retrieval never treats this field as confirmed; a source revision change clears a stale proposal.

Observed values are server-owned; reference update requests cannot replace them. Source revisions are checked before saving labels. The project schema stays v1 and needs no migration. Old manifests receive their existing model defaults. Missing/unreadable source projects are marked unavailable and excluded from retrieval; stored labels can still be removed.

Render status is read from completed local `_jobs/*/job.json` receipts. A receipt is historical evidence and may describe an older revision. Once captured, that evidence is retained even if render output is later cleaned up. Imported project packages do not imply that the imported copy was exported or published locally. No performance claim is inferred from export counts, feedback or frequency.

## Persistent storage and recovery

The catalogue is a separate `_memory/catalog.sqlite3` below the existing project root. On Mac this is `~/Library/Application Support/JDH Shorts Studio/Projects/_memory/catalog.sqlite3`. The standard-library SQLite runtime is bundled and checked by packaging; no database service or extra package is required.

SQLite stores one bounded JSON document with schema version 1, catalogue revision, profile and references. `PRAGMA user_version` was 1 in Task 03; version 0.2.4 migrates it transactionally to 2 by adding the daily-idea table. The catalogue JSON remains schema v1. Mutations use `BEGIN IMMEDIATE`, full synchronous commits, and optimistic catalogue revision checks. Project reads and catalogue changes share the repository lock inside the single supported sidecar process. A failed write rolls back, and SQLite recovers interrupted uncommitted writes from its rollback journal. No stale backup is restored after a successful deletion.

Invalid documents, corrupt databases and unknown versions fail explicitly; they are never replaced by an empty catalogue. The catalogue file is retained for recovery. Project files remain accessible independently. Existing project atomic saves, optimistic revision checks, undo and previous-version backups are unchanged. This is transactional recovery, not a separate archival backup system.

The catalogue caps references at 500, feedback at 20 items per reference, and its encoded document at 12 MiB. API writes accept at most 64 KiB including chunked bodies and retain the existing session/origin/CSRF guards. Database/journal paths are confined below the project root. The file is local, not encrypted by the application, and does not protect against other programs running as the same OS user.

## Retrieval contract

`POST /api/memory/retrieve` accepts query, preferred theme/series, optional exact language and age filters, result limit (1–8; default 5) and context budget (1,000–12,000 characters; default 6,000).

Retrieval refreshes only selected references, rejects missing/excluded/QA/duplicate entries, filters language and age, then ranks simple keyword/theme/series matches with recency. Greedy selection penalizes repeated confirmed themes and series. Identical content fingerprints are returned once even if both entries were manually set to content. Fingerprints use normalized script, scene settings and asset IDs; they do not perform perceptual video matching. Unrelated references can fill remaining places because keywords/theme/series are preferences, not strict filters.

The JSON context includes catalogue revision, user profile, source project/revision IDs, bounded summaries/hooks, their origin, confirmed labels, duration, up to 12 asset IDs plus asset count, status provenance, and up to three recent feedback items per reference. It excludes media bytes, paths and full project manifests. The whole compact JSON envelope must fit the requested character budget; complete entries that cannot fit are skipped. If the profile alone is too large, retrieval asks for a larger budget. An empty result is valid.

Task 04 uses the returned catalogue revision in its cache key and rechecks source revisions before showing cached proposals. Excluding or forgetting a source also removes dependent cached ideas and saved feedback in the same transaction; see [daily ideas](daily-ideas.md). Gemini Nano remains the only inference provider; the Task 02 live-browser verification limitation remains open.

## Verification

See [Task 03 results](gemini-nano-task-03-results.md) and [packaged runtime evidence](qa/content-memory-runtime.json). Tests use temporary roots. `script/verify_content_memory_runtime.py` launches the actual bundled Python sidecar twice against one disposable folder and verifies persistence, source refresh, selection and deletion with a real imported PNG.
