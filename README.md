# JDH Shorts Studio

**macOS desktop app** for vertical shorts, based on the supplied Claude design. Version 0.2 adds a native AppKit/SwiftUI window, an embedded WebKit editor, native file dialogs, and a self-contained Python/Kokoro/FFmpeg runtime. Double-click the app; no Terminal, browser, Node, Python, or Homebrew is needed to run the built bundle. The full editor roadmap remains in progress.

## Open the Mac app

Double-click `dist/JDH Shorts Studio.app`. The current local build requires **Apple Silicon and macOS 26+** (the bundled Homebrew FFmpeg build's minimum OS) and is approximately 1.2 GB including Kokoro. It is ad-hoc signed for local use; it is not a Developer ID notarized release.

The native app stores projects in `~/Library/Application Support/JDH Shorts Studio/Projects`. File → Show Project Folder reveals them. Its private loopback service starts automatically on an unused port and stops with the app. The supplied QA ZIP was imported through the native file dialog to verify migration. The original web data remains in `data/`.

To rebuild and launch:

```sh
./script/build_and_run.sh --verify
```

See [macOS build and runtime notes](docs/macos-app.md). Version 0.2.2 adds a paired Chrome companion for local Gemini Nano English script assistance. Chrome and its companion tab must stay open for AI; manual scripts, imported audio, Kokoro and rendering remain independent. See [setup and verification limits](docs/chrome-ai.md).

Version 0.2.3 adds **Memori konten** on the home page. Select which projects to remember, set a channel profile, correct labels, record idea feedback and inspect bounded local context. Nothing is included automatically; export never implies publication. See [content memory](docs/content-memory.md) and [Task 03 results](docs/gemini-nano-task-03-results.md).

Version 0.2.4 adds **Ide hari ini**: three local-Nano proposal cards, daily/manual mode, dated persistent cache, save/skip feedback, and editor/render deferral. Empty history uses onboarding preferences or a labelled manual guide. See [daily ideas](docs/daily-ideas.md) and [Task 04 results](docs/gemini-nano-task-04-results.md); live Nano verification remains pending.

Version 0.2.5 adds **Susun draft / Draft dari ide**: local-Nano script/storyboard proposals, per-scene review and edits, partial append/replace, measured-audio safeguards, revision-checked atomic apply, and Undo. See [storyboard workflow](docs/storyboard-proposals.md) and [Task 05 results](docs/gemini-nano-task-05-results.md).

Version 0.2.6 adds **Timing & caption**: measured local audio duration and silence, reviewable scene-length changes, balanced caption lines and readability warnings, partial apply and Undo/Redo. Export encodes AAC only after concatenation to avoid accumulating per-scene audio delay. No new model or cloud provider is added. See [timing workflow](docs/pacing-and-captions.md) and [Task 06 results](docs/gemini-nano-task-06-results.md).

Version 0.2.7 adds **Animasi & callout**: gentle zoom/pan, caption fade/slide, editable callouts, focal controls and a project-wide no-motion option. Motion is validated data shared by the editor, reviewed Nano storyboard proposals and local FFmpeg export. Old projects remain static. See [motion presets](docs/motion-presets.md) and [Task 07 results](docs/gemini-nano-task-07-results.md).

Version 0.2.8 adds **Pemeriksaan Shorts & paket unggah**: measured media/audio/caption checks, separate text-only local-Nano editorial suggestions, reviewed corrections and editable upload metadata. Export verifies the actual MP4 and provides an upload ZIP for manual publishing. See [quality and upload workflow](docs/shorts-quality-and-upload.md) and [Task 08 results](docs/gemini-nano-task-08-results.md). Native review/apply/Undo/Redo/export QA passed; integrated real Nano inference remains unverified.

Version **0.2.9 build 11** provides the personal **Apple Silicon DMG** at `dist/JDH-Shorts-Studio-0.2.9-arm64.dmg`, with SHA-256 and companion setup notes. It fixes the companion's editorial operation guard and passes 185 tests plus 72 workflow checks on a copy installed from the DMG. It remains ad-hoc signed and not notarized; Gatekeeper rejects it without a user-approved exception. See [Task 09 results and remaining validation limits](docs/gemini-nano-task-09-results.md): real integrated Nano, native UI on this locked session, and the destination Mac mini remain unverified.

Version **0.2.10 build 12** adds **Performa video**: reviewed manual/CSV measurements, duplicate detection, explicit corrections, video-wide anomaly exclusion, cautious comparable-window summaries, and cited evidence for local Nano ideas. See [workflow and CSV contract](docs/video-performance.md) and [Task 10 results](docs/gemini-nano-task-10-results.md): 214 tests, 18 packaged-runtime checks, and native manual/CSV review and exclusion QA passed. Real integrated Nano is still blocked by Chrome. The 0.2.9 DMG remains the Task 09 artifact; this milestone updates the `.app`.

Version **0.2.11 build 13** adds **Sumber riset** and a separate, manual research-ideas mode: reviewed notes or explicitly fetched public HTTPS previews, dated source metadata, duplicate/conflict/expiry handling, and exact-source quotations on idea cards. Nano remains local. See [research workflow and limits](docs/research-sources.md) and [Task 11 results](docs/gemini-nano-task-11-results.md). This is the final planned feature task; native UI/live Nano verification and an updated installer remain separate release checks. The existing DMG is still 0.2.9.

## Optional web development server

```sh
cd /Users/jeripurnamamaulid/Projects/01_PRODUCT-Claude/jdh-shorts-studio
./scripts/start.sh
```

Open **http://127.0.0.1:8741**. Stop with Ctrl+C. The current checkout already has a Python environment, dependencies, a built frontend, and downloaded Kokoro assets. The project named **QA — One Idea, One Short** is clearly labelled test material created during verification.

For a fresh checkout: install Node.js 22+, `uv`, and FFmpeg (`brew install node uv ffmpeg`), then run:

```sh
./scripts/setup.sh
./scripts/setup-kokoro.sh # optional; downloads local English TTS dependencies/model
./scripts/start.sh
```

Setup requires the internet. Rendering and Kokoro inference use local files after setup. Python 3.13 / Apple Silicon is the tested configuration. Kokoro runs on CPU. Do not run multiple server instances against the same data directory.

## Workflow

1. Create a short and choose English or Indonesian. Write a script and split it into scenes; initial duration is a word-proportion estimate.
2. Import owned images, videos, or audio. Click media to attach it to the selected scene, or drag it onto a scene. Files are copied into the project.
3. For English, generate Kokoro narration per scene, listen, and apply. For Indonesian, import recorded narration. Applying narration extends a scene if necessary; adjust extra silence manually.
4. Set framing, source trim, duration, volumes, caption text/style and optional **Animasi & callout** in the inspector. **Gerak seluruh proyek → Tanpa gerak** disables animation while keeping text visible. Use Space, arrows, Shift+arrows, S, and Cmd/Ctrl+Z in the editor. Splitting a scene containing narration is deliberately blocked until accurate audio splitting is implemented.
5. Open **Ekspor**, select draft (360×640) or final (1080×1920), and **Periksa Shorts**. Review measured findings, optionally request local-Nano editorial feedback, and edit metadata or proposed corrections. Review/apply changes, then recheck before export. Download the MP4, WAV, SRT, portable source project, or upload ZIP with metadata/report. Upload to YouTube manually.

## Local storage and privacy

The optional web server stores data in `./data`; the Mac app uses Application Support. Neither uses your Movies directory by default. Set `JDH_DATA_DIR` before launch to choose another location; model location can be set with `JDH_KOKORO_DIR`. The server binds only to 127.0.0.1 and validates Host, Origin, session cookie, and CSRF token. No application analytics, cloud generation, API keys, accounts, or media upload services are integrated. This protects against ordinary cross-site browser requests; it is not authentication against other local programs running as your user.

Project manifests have schema version 1, atomic replacement, a previous-version backup, and optimistic revision checks. On conflict, preserve your changes before reloading. ZIP import creates a new project and verifies every media file. Cache and finished export directories currently require manual management while the server is stopped.

## Development

- `macos/Sources/JDHShortsStudio`: native window, lifecycle, file panels, download handling and private sidecar supervision.
- `script/`: app packaging, build/run entrypoint and bundled runtime verification.
- `web/src/components`: React editor, script builder, timeline, preview, setup and export.
- `web/src/lib`: frame clock, state/history/autosave, same-origin API and Chrome AI adapter.
- `backend`: FastAPI, validation, repository, media probe, captions, job worker, Kokoro, FFmpeg renderer.
- `web/src/vendor/opencut`: a small, attributed subset of OpenCut Classic utilities. **This is not yet a complete OpenCut editor fork.** See the audit below.

```sh
uv pip install --python .venv/bin/python -r backend/requirements-dev.txt
.venv/bin/python -m pytest backend/tests -q
.venv/bin/ruff check backend scripts --select F
(cd web && npm test && npm run typecheck && npm run build)
```

Rebuild `web` after frontend edits; the Python server serves `web/out`. Restart the server after Python edits. The standalone Next development server has no API proxy and is not the supported integrated workflow yet. Frontend packages are locked in `package-lock.json`; backend and Kokoro have separate lock files. Keep generated `data`, `.venv`, and `web/out` out of source control.

## Current limits

- Task 01 verified real Gemini Nano English inference through a local companion prototype. Task 02 adds native editor integration; its live Chrome check was blocked by `ERR_BLOCKED_BY_CLIENT`. Protocol and native UI fixture checks passed, but real Nano on the integrated build remains pending. No cloud fallback is present.
- Kokoro English was verified with real audio and outbound Python sockets denied. This is not an OS-wide offline audit of every browser process.
- Caption cues are scene-level, with measured two-line wrapping, manual corrections and readability warnings. No automatic speech alignment or karaoke words yet.
- Scenes use hard cuts, static framing or bounded zoom/pan, and caption/callout entrances. Cross-scene fades, transition handles, narration splitting, arbitrary track arrangement, and a full OpenCut integration remain future work.
- Job cancellation stops FFmpeg. Kokoro cancellation is cooperative between inference chunks, so a running chunk must finish first.
- Browser preview is for editing. Export uses native FFmpeg and is validated by ffprobe and a full decode; exact playback synchronization and every codec/device combination still require broader QA.
- Desktop is the target. Narrow-screen drawers are provided, but phone editing is not a release target.

Read [design handoff](docs/design-handoff.md), [architecture](docs/architecture.md), [upstream audit](docs/upstream-audit.md), [verification](docs/verification.md), [Chrome AI setup](docs/chrome-ai.md), and [third-party notices](THIRD_PARTY_NOTICES.md).
# jdh-short-video
