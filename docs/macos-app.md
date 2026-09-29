# macOS desktop app — v0.2

### 0.2.12 scene card controls

Every scene card in the editor now has visible **Edit** and **Hapus** buttons, including empty scenes. Edit opens a form for the scene name, narration, caption, duration and existing visual media. Save applies the form as one undoable change; Cancel leaves the scene unchanged. Changed narration reminds the user to regenerate its voice.

Deleting a card removes that scene from the timeline, pauses playback and selects an adjacent scene. Media files remain available, and Undo restores the scene with its audio and settings. The updated local app is build 14; the existing DMG is unchanged.

### 0.2.9 personal DMG

The latest installer is `dist/JDH-Shorts-Studio-0.2.9-arm64.dmg`, with a SHA-256 sidecar and installation/Chrome companion notes inside. It fixes the editorial companion operation guard and verifies the app copied out of the DMG with native dependency, offline Kokoro, migration, cancellation, timing and proposal workflow checks. See [Task 09 results](gemini-nano-task-09-results.md) for measured evidence and open native UI/Nano/Mac mini validation limits. It is ad-hoc signed, not notarized; no installed app was replaced.

### 0.2.3 local content memory

The home page now offers an opt-in content catalogue and channel profile, source/user provenance, reference controls, idea feedback and bounded local retrieval. The catalogue uses the bundled Python SQLite runtime under `Projects/_memory`, separate from project manifests. No inference runs in Task 03. See [content memory](content-memory.md) and [Task 03 verification](gemini-nano-task-03-results.md), including the native UI check blocked by the locked Mac.

### 0.2.2 local Nano integration

Setup pairs a personal Chrome companion tab with the Mac editor for English hooks/drafts, availability, cancellation, bounded requests and review before apply. Nano stays in Chrome and is not bundled. See [setup](chrome-ai.md) and [Task 02 verification](gemini-nano-task-02-results.md). Task 02 updates the staged `.app`; it does not rebuild the DMG or replace the installed app.

### 0.2.1 playback fix

Timeline preview now issues media playback/seek commands on transport changes instead of on every animation frame. Narration stops naturally at EOF, the next scene's narration preloads, and music uses the media element's native loop. A short narration still leaves silence until the next scene; project timings are not automatically shortened. Regression coverage includes delayed readiness, pause/seek/resume, EOF, final-syllable playback, loop boundaries, disposal and playback errors. Quit keeps AppKit's normal run loop active while awaiting the editor save, then requests termination again after it completes.

## Artifact

`dist/JDH Shorts Studio.app` is a self-contained Apple Silicon application. It launches a native AppKit window hosting a SwiftUI loading/error view and a WKWebView editor. It is an app bundle with its own Dock icon and menus; the editor UI remains React embedded inside the window rather than being rewritten as native SwiftUI controls.

Python 3.13, its installed dependencies, Kokoro weights/voices/spaCy model, caption fonts, FFmpeg, ffprobe, and FFmpeg's non-system libraries are included. The app does not launch a browser or require a source checkout at runtime. The current bundle is about 1.2 GB. No private project data is bundled.

This local build requires macOS **26.0 or later**, because the installed FFmpeg binary has `LC_BUILD_VERSION minos 26.0`. The Swift shell itself targets macOS 14. Supporting macOS 14/15 means rebuilding and validating the renderer and all native dependencies for that minimum, then updating the bundle minimum; changing only Info.plist would be incorrect.

## Runtime and storage

- Projects: `~/Library/Application Support/JDH Shorts Studio/Projects`.
- Diagnostics: `desktop.log` plus `desktop.previous.log` in the same support directory. Script/media content is not intentionally logged.
- The app spawns its bundled Python with an explicit isolated environment and a tools-only PATH plus system paths. Existing project Python and Homebrew paths are not included.
- The child binds `127.0.0.1` on an OS-assigned unused port before importing FastAPI. A per-launch random token protects the native health endpoint. Frontend requests still use same-origin cookie + CSRF protection.
- On Quit/close, the host waits for autosave. It warns if an export/TTS/AI job is active. Closing stdin requests worker cancellation, revokes companion pairing, and triggers graceful shutdown. The child also watches parent loss and has a bounded shutdown deadline.
- eSpeak phoneme files have a shallow resource location to avoid its native path-resolution failure inside deeply nested site-packages in an app bundle.
- WKWebView uses an ephemeral web data store; actual projects are backend files. Main-frame navigation stays on the app's own origin. User-clicked HTTPS reference links open externally. No arbitrary filesystem/command execution bridge is exposed to web content.
- Uploads use NSOpenPanel. Downloads use NSSavePanel and a temporary sibling file; an existing destination is replaced only after download completes. Cmd+S flushes autosave; native Edit menus route project undo/redo and normal text editing.

## Build

Use `./script/build_and_run.sh`, or `--verify`, `--build`, `--qa`, `--logs`, `--telemetry`, `--debug`. `--qa` launches with isolated temporary storage and a QA window title. Rebuild needs Xcode/Swift tools, Node/npm, the prepared project Python environment, models, and installed FFmpeg. Runtime users need none of these. `.codex/environments/environment.toml` provides the Run action when this directory is opened as a Codex project.

The script requests a graceful quit of this app only, builds the static UI and Swift executable, stages resources, relocates renderer libraries, checks bundled Python imports, and signs/verifies the bundle ad hoc. Large runtime/model copies are cached between local builds. For dependency changes, quit the app and remove the generated `dist/` directory before a clean rebuild. Do not modify a live bundle in place.

`script/verify_desktop_runtime.py` checks the built app's sidecar from a separate temporary working directory with an isolated data folder and a PATH without Homebrew. It covers session protection, static frontend, real Kokoro generation, native rendering, downloading outputs and EOF shutdown.

## Personal DMG installer

Run `./script/create_dmg.sh` after building the application. It packages the existing bundle into `dist/JDH-Shorts-Studio-<version>-arm64.dmg`, with an Applications shortcut and installation/companion notes. It verifies the compressed image and app signature, mounts the DMG read-only, copies the app to a temporary installation directory, runs real Kokoro/FFmpeg plus release workflow checks from that relocated copy, then writes a SHA-256 checksum beside the completed installer. It does not stop or change the installed application. Compression uses LZFSE, supported by the required macOS version. If verification fails, the intermediate `.building.dmg` is preserved for diagnosis. Set `JDH_KEEP_INSTALL_CHECK=1` to retain the printed temporary copy for additional UI QA, then remove that test copy after quitting it.

On an Apple Silicon Mac mini with macOS 26+, open the DMG, drag the app into Applications, eject the image, then launch the installed app. This personal build is not notarized; if macOS blocks the developer, follow [Apple's per-app Open Anyway instructions](https://support.apple.com/en-us/102445). Do not disable Gatekeeper globally. Existing projects are not included: export a project's ZIP on the original Mac and import it on the destination Mac.

To recheck a mounted or relocated copy independently, run `script/verify_desktop_runtime.py --app '/path/JDH Shorts Studio.app' --report /private/tmp/jdh-runtime-check.json` with the development Python environment.

## Distribution boundaries

The bundle is intended for this Mac/local testing. It is not notarized, Developer ID signed, hardened-runtime audited, or App Store sandboxed. Moving it to another Mac requires those distribution decisions and a full third-party redistribution review, including the actual FFmpeg build, native libraries and model licenses. `Contents/Resources/ffmpeg-libraries.json` records copied renderer libraries and their original SHA-256 hashes. Preserve the license files and model cards included with dependencies.

Gemini Nano does not run inside WKWebView. The native editor reaches it through the paired Chrome companion tab, which must stay open. No cloud replacement is used. Existing editing, Kokoro and rendering work locally without Chrome.

Bounded pan/zoom and text entrances are available from Task 07. Full OpenCut integration, cross-scene transitions and word-level speech alignment remain outside this release; packaging does not imply those are complete.
