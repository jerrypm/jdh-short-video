# Verification — 2026-09-21

## Completed checks

- Production Next.js static build and TypeScript checks passed.
- Four frontend logic tests passed: split clock/source offsets, narration split guard, upstream snapping, and manual storyboard semantics.
- Eight backend tests passed: session/Origin/CSRF, revision conflict/backup, invalid media/path escape, caption overflow, real FFmpeg export and portable ZIP roundtrip, restart recovery, process cancellation/partial output cleanup, and explicit TTS application with stale-script/revision rejection.
- Ruff undefined/unused-import checks passed; Python and frontend source formatted.
- Real Kokoro English audio generated for all three scenes from the UI. Review and apply completed successfully. Source WAV durations are measured, not placeholder audio. Synthetic tone is an unused imported QA asset, not a substitute for speech.
- `scripts/verify_kokoro_offline.py` generated a 121-frame/approximately 4-second speech sample with Python socket connections denied. Model and spaCy resources were installed beforehand. This verifies that inference path, not all browser/OS networking.
- Created a project through the browser, entered a three-paragraph script, built scenes, edited captions, imported owned test files, attached visuals, generated/applied speech, and exported final from the UI. Autosaved project survived server restarts and browser reopening.
- Final render job `51716bc881e84291a8d12bf13bf72db2`: **900 video frames, H.264, 1080×1920, 30/1 fps, AAC**. Container duration 30.021333 seconds includes AAC framing. FFmpeg full decode passed. Outputs include MP4, narration WAV, scene-level SRT, project JSON and ZIP.
- Export frames 0, 269, 270, 659, 660 and 899 were extracted and visually inspected: scene changes occur at the intended 9- and 22-second boundaries, captions are present and not clipped. See `qa/render-contact-sheet.png` and `qa/final-probe.json`.
- Reference and implementation screenshots compared at the design's desktop sizes. The palette, typography, panel hierarchy, portrait stage and four-track timeline are carried over. Fictional prototype navigation/progress and unimplemented effect controls are omitted.
- Editor playback advanced from 0 through scene 2 to 21 seconds; rendered media and caption images loaded. 1280×800 DOM measurements showed no document overflow. Further breakpoint observations are listed below when completed.

## Browser limitation found

The connected personal Chrome session could read the supplied Claude designs, but its client blocked localhost navigation. Local UI testing used Codex's in-app browser. While interacting with the final MP4's native play control, that tab crashed; the same saved project reopened successfully in a new tab. This is an unresolved browser playback issue, not a passing playback test. The file itself passes native FFmpeg decoding. Export UI now requests metadata preload and reports ordinary media errors, but these do not prove a renderer crash is fixed. Verify final MP4 playback and Gemini Nano in the target Chrome profile before a release.

## Still pending for the full original prompt

Full OpenCut fork/integration and comparative audit; real Gemini Nano inference on eligible Chrome; image pan/zoom and fades; narration splitting and speech-aligned captions; exhaustive codec/rotation/VFR and preview parity tests; packaged distribution and model-license inventory; OS-wide airplane-mode verification; cache/export cleanup UI; crash recovery beyond the covered cases. This milestone must not be advertised as a production-complete editor.

The QA project is `data/bb463be8d0ff44cd913f7ab6cec4275d`. Its generated images explicitly identify themselves as test media. No personal files or work-account content were used as test assets.

## Final layout pass

The 390×844 fallback layout also reported document width 390 and height 844 with no document overflow, and its screenshot was visually inspected. The left panel and inspector collapse; timeline clipping stays inside its horizontal scroll area. Narration clips now use actual audio duration, leaving visible gaps for silence, and waveform height is normalized from measured samples. This is a narrow-layout smoke check, not full mobile support.

## macOS application milestone — v0.2

- Release Swift build, static frontend build, four frontend tests and nine backend tests passed. The added backend check covers the private desktop health endpoint. Ad-hoc bundle signature passed `codesign --verify --deep --strict`.
- `script/verify_desktop_runtime.py` launched the **bundled** Python in a temporary working directory, with a PATH excluding Homebrew and an isolated project directory. Bootstrap, frontend, token protection, real Kokoro speech, FFmpeg draft rendering/full decoding, downloads and EOF shutdown passed. Evidence: `qa/macos-runtime-check.json`.
- Native AppKit launch and menus worked. Imported the existing QA ZIP through NSOpenPanel; the imported project survived Cmd+S, Cmd+Q and relaunch. The original web project was not moved or modified.
- Exported the imported three-scene, 30-second project from the native window. Job `0a009e688c01483a8fbc4184db0ea103` completed at 360×640. WKWebView playback advanced to 16 seconds in scene 2 and paused at 23 seconds in scene 3, without the earlier in-app-browser crash. This is a passing native draft-playback smoke test, not proof for every codec or final-resolution playback.
- Saved the MP4 through NSSavePanel to `qa/macos-output.mp4`. The downloaded file exists and was inspected with the bundled ffprobe. Native screenshots: `qa/macos-editor.png` and `qa/macos-playback.png`.
- The 1.2 GB bundle contains its runtime, models and renderer, but is a local Apple Silicon/macOS 26+ build, not a notarized release. Gemini Nano remains unavailable in WKWebView. Distribution/license review and the incomplete editor features listed above remain open.
