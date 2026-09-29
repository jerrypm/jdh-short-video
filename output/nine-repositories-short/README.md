# Nine Repositories Worth a Look — finished Short

Task run on **28 September 2026** in JDH Shorts Studio. One English vertical Short about Jerry PM's
Stackademic roundup *9 Cool Repositories I Found on the Internet This Week* (6 September 2026),
produced end to end through scripts and local tools: no computer use, no GUI automation, no browser
automation, no desktop screenshots, no cloud speech, no cloud image generation, no voice cloning.

**Nothing was published.** The private upload is blocked by a missing prerequisite — see
`youtube-setup.md`.

## Deliverables

| File | What it is |
| --- | --- |
| `final.mp4` | Finished video, 1080 × 1920, 30 fps, 64.47 s, H.264 + AAC |
| `narration.wav` | Narration track of the exported timeline (48 kHz stereo PCM, 64.47 s) |
| `captions.srt` | 13 caption cues, scene-level, identical to the cues burned into the video |
| `project.zip` | Editable JDH project, 62 media assets (13 cards + every Kokoro take, levelled and trimmed) |
| `script.md` | English script: spoken line, on-screen caption and duration per scene |
| `storyboard.json` | Machine-readable scene plan with measured timings, crops and motion |
| `upload-metadata.json` | Title, description, tags, sources, disclosure, private-upload intent, measured verification |
| `sources.md` | Article page references, the article-URL verification chain, official repository checks and unresolved claims |
| `qa-report.md` | Every check that was performed, the measured numbers, and what could not be verified |
| `contact-sheet.png` | All 13 scenes plus the closing frame, for human review |
| `youtube-setup.md` | The actual upload blocker and the exact one-time setup required |
| `upload_youtube.py` | Prepared, unexecuted resumable private-upload script (channel-verified, checkpointed) |

Supporting evidence: `qa-final.json`, `qa-draft.json`, `visual-report.json`, `pacing-report.json`,
`loudness-level.json`, `quality-final-before.json`, `final/final-verification.json`,
`final/final-quality-report.json`, `source/crops.json`, `review/`.

## Measured result

- **1080 × 1920, 30 fps, 1934 frames, 64.47 s**, H.264 (yuv420p, CRF 18, faststart) + AAC 48 kHz stereo.
- Full decode of every frame passed; no clipped samples; the longest silent run anywhere is the
  0.67 s deliberate pause before a cut (0.59–0.67 s before every cut, ≤ 0.07 s after each cut, which
  is where the next scene's first word lands).
- Integrated loudness **−16.0 LUFS**, loudness range 2.5 LU, true peak **−3.2 dBFS**.
- Captions verified against the renderer's own caption image (MAE 5.9–6.9 against 113–174 for a
  wrong-text control); every caption fits two lines at 7.7–13.3 characters/second.
- The Shorts control zone (x ≥ 945) and the bottom overlay zone (y ≥ 1620) contain **0** non-background
  pixels in all 13 scenes.
- 26 sampled frames all matched their own card; 13 distinct narration takes, one per scene.

Full detail, including the limitation that the media could not be watched or listened to on this
machine, is in `qa-report.md`.

## Content notes

- All nine repositories appear in the article's order, one point each, with the official URL in the
  description and the display name and a short benefit on each card.
- Visuals are original typography cards (warm off-white, dark type, red numerals, `1/9`–`9/9`
  counter, subtle JRDEVHUB branding) plus crops of the author's own PDF: the article heading, each
  repository's section heading and slug, the `npx skills add google/skills` box, and the closing
  "The pattern, stated plainly" block. These are excerpts, not live demonstrations.
- Star counts, provider counts, token-saving percentages and similar changing numbers are omitted
  everywhere; the article's "developer preview" wording for DeepSeek Harness is kept as such.
- Script authored by the assistant from the PDF; speech generated locally with **Kokoro
  `am_michael` at 0.96**; levelled locally with FFmpeg. No background music.

## Resume or re-render without duplicating work

Checkpoint: `production-state.json` (project id, media ids, revisions, job ids, loudness
measurements). The project lives in this task's own data directory, **not** in the app's library:

```sh
cd /Users/jeripurnamamaulid/Projects/01_PRODUCT-Claude/jdh-shorts-studio
JDH_DATA_DIR=$PWD/output/nine-repositories-short/jdh-data \
JDH_KOKORO_DIR=$PWD/data/models/kokoro \
JDH_PORT=56125 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 56125
```

Then, from this folder: `../../.venv/bin/python produce.py draft|final|…` (modes: `prepare`,
`rescript`, `level`, `pace`, `captions`, `draft`, `final`). Every mode is idempotent: it reuses the
recorded project, media ids and job ids and never creates a second project. `final/final.mp4`,
`final/narration.wav`, `final/captions.srt` and `final/project.zip` are the artefacts copied to this
folder's root.

The server was never pointed at the app's data directory, and the Heartwoodfall project
(`645965dbc6934456869044b6741b21cc`) and every pre-existing asset were left untouched. To keep editing
this Short inside the app rather than this folder, import `project.zip` with **Impor paket proyek**.

## Boundaries honoured

- No repository from the article was installed, cloned or executed, and no command shown in an
  article crop was run.
- No JDH application feature was changed and no DMG was rebuilt; only the documented local HTTP API
  was used, against this task's own data directory.
- No paid service, cloud TTS, cloud media generation or voice cloning was used. Gemini Nano was not
  used and no claim is made about it running offline.
- No credentials were read or used, and no OAuth scope was requested. The upload script refuses to
  run without an explicit client-secret file and stops if the authorized channel is not
  `UCRig_f5P4QyB_kilUs2PN8Q`.
