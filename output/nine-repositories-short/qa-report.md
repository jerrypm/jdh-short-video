# QA report — nine-repositories short

Everything below was measured on the actual files. The raw evidence is in `qa-final.json`,
`qa-draft.json`, `final/final-verification.json`, `final/quality-report.json`,
`quality-final-before.json`, `loudness-level.json`, `pacing-report.json`, `visual-report.json`,
`source/crops.json` and `review/`. Run `qa_check.py <file> <label>` to reproduce.

## 1. What could not be checked, stated first

**This machine cannot see or hear the media.** There is no human viewing or listening step in this
run: I have no vision or audio playback here, and I deliberately did not use computer use, GUI
automation, browser automation, screenshots of the desktop, or a browser session.

So "inspection" throughout this report means **programmatic inspection of the decoded pixels and
PCM**: container facts, full decode, loudness and true-peak measurement, silence detection, per-scene
frame-to-card matching, caption-band comparison against the renderer's own caption image, and
colour/blank-frame statistics. Nothing here is a substitute for watching the video on a phone and
listening to it. Concretely, the following remain **unverified**:

- whether the narration sounds natural, or whether any word is mispronounced;
- whether the music-free mix is pleasant, beyond its measured loudness and peaks;
- aesthetic judgement (typography, spacing, colour, pace) — I measured it, I did not look at it;
- exact playback synchronisation on a real device, and how the Shorts UI overlaps the frame in the
  live app (I only verified against the documented control/overlay zones);
- YouTube's own transcoding, Shorts classification and processing, because nothing was uploaded.

## 2. Encoded file

| Property | Measured |
| --- | --- |
| File | `final.mp4` (8,370,884 bytes) |
| Frame size | 1080 × 1920 |
| Frame rate | 30.0 fps (`avg_frame_rate` 30/1) |
| Frames | 1934, matching the project timeline exactly |
| Duration | 64.467 s (container), 64.469 s of audio |
| Video codec | h264 (yuv420p, CRF 18, `+faststart`) |
| Audio codec | aac, 48 000 Hz, stereo |
| Full decode | `ffmpeg -xerror -i final.mp4 -f null -` completed with **no error on any frame** |
| JDH export check | `verified_file: true`, `full_decode_passed: true`, `near_full_scale_samples: 0`, `at_full_scale_samples: 0`, `long_silences: []` |

## 3. Audio

| Property | Measured |
| --- | --- |
| Integrated loudness (EBU R128) | **−16.0 LUFS** (target −16) |
| Loudness range | 2.5 LU (speech only, no music) |
| True peak | **−3.2 dBFS** (ceiling ≤ −1.0 dBTP met; no clipping) |
| Sample peak in the renderer's own check | −3.163 dBFS |
| Clipped / full-scale samples | 0 near-full-scale, 0 at full scale (10 ms windows) |
| Silence longer than 1.5 s (JDH check, −40 dBFS) | none |
| Silence longer than 0.9 s (independent check, RMS < 0.002) | none |
| Silence immediately before each of the 12 cuts | 0.59 – 0.67 s |
| Silence immediately after each cut (until the next line starts) | 0.05 – 0.07 s |

How the loudness was reached, honestly: the Kokoro takes measured **−27.1 LUFS / −5.25 dBTP** as a
set. A single uniform gain to reach −16 LUFS would have needed **+11.1 dB**, which would have pushed
the true peak **6 dB over the ceiling**, so that is not a valid option. Instead each take was levelled
once with FFmpeg `loudnorm` (I = −16, TP = −1.5, LRA = 11), which landed at −17.1 LUFS / −4.48 dBTP,
and then one **shared trim of +1.1 dB** was applied to every take so the relative level between
scenes stayed exactly as generated (it did: per-scene integrated loudness now spans −15.3 to
−16.9 LUFS against −25.8 to −27.8 before, i.e. tighter than the source). The final measurement above
is taken from the encoded AAC stream, not from the intermediate WAV.

Repeated audio: each of the 13 narration takes is a distinct Kokoro generation of a distinct
sentence; no take is reused in two scenes (the project's scene-to-audio map in
`production-state.json` shows 13 distinct trimmed assets), and no audio is looped.

## 4. Per-scene timing, from the exported project

Narration audio is the measured length of the take used; the scene duration adds the deliberate
0.5 s pause (0.67 s for the closing card). "Trim" is the near-silence removed from each end of the
raw take after measuring it.

| # | Scene | Scene s | Narration s | Trim lead / tail s | Caption cps | Motion | Article page |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Hook | 4.93 | 4.43 | 0.34 / 0.31 | 7.7 | zoom_in | 1 |
| 2 | ECC | 4.53 | 4.03 | 0.36 / 0.39 | 8.6 | zoom_out | 2 |
| 3 | CLI-Anything | 5.57 | 5.07 | 0.34 / 0.39 | 10.8 | pan_right | 3 |
| 4 | Screenshot-to-code | 5.80 | 5.30 | 0.32 / 0.35 | 10.2 | zoom_in | 5 |
| 5 | ScrapeGraphAI | 5.47 | 4.97 | 0.32 / 0.37 | 8.2 | zoom_out | 6 |
| 6 | Google Skills | 5.13 | 4.63 | 0.34 / 0.39 | 12.9 | pan_left | 9 |
| 7 | DeepSeek Harness | 5.67 | 5.17 | 0.34 / 0.39 | 9.0 | zoom_in | 9 |
| 8 | Humanizer | 5.73 | 5.23 | 0.34 / 0.47 | 8.7 | zoom_out | 11 |
| 9 | Stop Slop | 4.80 | 4.30 | 0.32 / 0.33 | 12.9 | zoom_in | 12 |
| 10 | OmniRoute | 5.40 | 4.90 | 0.38 / 0.71 | 9.1 | zoom_out | 13 |
| 11 | The pattern | 4.43 | 3.93 | 0.32 / 0.33 | 13.3 | pan_right | 13 |
| 12 | Read the README | 4.53 | 4.03 | 0.34 / 0.37 | 11.5 | zoom_in | — |
| 13 | Subscribe | 2.47 | 1.80 | 0.32 / 0.45 | 10.9 | zoom_out | — |

Total: **1934 frames = 64.47 s**, inside the 60–75 s brief; narration itself is 57.8 s, so about
6.7 s of the video is deliberate pause/breath.

The script was tightened once, after measurement: the first pass measured **83.7 s** and was over
budget, so every line was rewritten shorter (for example "ECC packages skills, agents, and hooks for
coding workflows. Start with a small profile." → "ECC packages skills, agents, and hooks. Start
small."), the project was re-scripted through the API and the narration regenerated. The second
measurement was 72.2 s; trimming the takes' own near-silence (below) brought it to 64.5 s. No speech
rate was raised to hit the target: the voice stayed `am_michael` at speed 0.96.

A pacing defect was found and fixed in this step: taken at face value, each Kokoro take carries
0.32–0.38 s of near-silence at the start and 0.31–0.71 s at the end, so scene durations built from
raw take length left a **~1.3 s hole at every cut** (measured on the first draft). The takes are now
trimmed to measured speech plus 0.06 s lead and 0.15 s tail, and the scene keeps a deliberate 0.5 s
pause, leaving 0.59–0.67 s of silence before each cut. The paragraph above is the honest record that
the first draft was worse than the final.

## 5. Captions

| Check | Result |
| --- | --- |
| Cues | 13, one per scene; `captions.srt` is byte-identical to an independent recomputation from the scene plan and the project's caption style |
| Fit | every caption fits two lines at size 40 in the renderer's own layout check; the check's `errors` list is empty and JDH's Shorts check reported `findings: []` |
| Reading speed | 7.7 – 13.3 characters/second, below the 20 cps warning threshold |
| Burned in | each scene's caption band was compared with the image the renderer draws for that scene's text: masked MAE **5.90 – 6.94** grey levels, against **112.9 – 173.8** for a deliberate wrong-text control (the next scene's caption). Every caption is therefore present and is the expected text |
| CTA | the closing caption is exactly `Subscribe for more content.` (MAE 6.29, control 112.6) |
| Alignment | **scene-level only.** No word-level alignment is implemented in this pipeline, and no word-level timing is claimed |

## 6. Layout safety and motion

Measured on the rendered pixels of all 13 scene frames:

- **Right band (x ≥ 945 of 1080): 0 non-background pixels** in every scene. This is the zone where
  the Shorts action buttons sit. An earlier caption size (46) failed this check — the widest caption
  bar reached x = 962 — which is why the caption style was changed to size 40 after measuring.
- **Bottom band (y ≥ 1620 of 1920): 0 non-background pixels.** Nothing competes with the Shorts
  title/channel overlay.
- The red accent appears in every scene frame (6 154 – 18 653 pixels within tolerance of the
  reference red), and no frame is blank or washed out (grey standard deviation 38.2 – 47.8).
- Motion is bounded and data-driven: `zoom_in`/`zoom_out` at amount 0.035, `pan_left`/`pan_right`
  horizontal pans, and a 6-frame caption fade. There are no flashing transitions; cuts are hard cuts
  (cross-scene transitions are not implemented in JDH). No `Callout` object is used, so the
  framework's lime callout colour never appears; the palette is warm off-white, dark type and red.

## 7. Scene and cut integrity

- 26 sampled frames (8 frames into each scene and the midpoint of each scene) were matched against
  the 13 source cards with a small offset/zoom search. **26 / 26 matched their own card, 0
  mismatches.** The narrowest winning margin is 1.4 grey levels on the upper band (frame 1121,
  Humanizer); all other margins are 2.5–6.0. The margin is reported rather than hidden because a
  small margin means the test is weakly discriminating for that frame, not that the frame is wrong:
  a follow-up comparison of the same frame over the whole frame area also ranks Humanizer first
  (13.24 against 13.97 for the runner-up), and that frame's caption matches the Humanizer caption at
  MAE 6.1 against 119 for the control.
- The frame count equals the sum of scene durations exactly, so there are no dropped or duplicated
  frames and no gap between scenes.
- The closing frame was extracted and checked (it is in the contact sheet, and its caption matched
  the CTA text).

## 8. Contact sheet

`contact-sheet.png` — one mid-scene frame from each of the 13 scenes plus the final frame, labelled
01–13 and "closing frame". This is the review artifact for a human viewer; I could not look at it
myself.

## 9. Draft vs final

| | Draft | Final |
| --- | --- | --- |
| Frame size | 360 × 640 | 1080 × 1920 |
| Frames / duration | 1934 / 64.47 s | 1934 / 64.47 s |
| Full decode | passed | passed |
| Loudness / true peak | −16.0 LUFS / −3.2 dBFS | −16.0 LUFS / −3.2 dBFS |
| Gaps > 0.9 s | none | none |
| Card matching | 26/26, min margin 5.97 | 26/26, min margin 1.4 |
| Caption MAE vs control | 18.0–21.9 vs 84–127 | 5.9–6.9 vs 113–174 |

The draft was rendered and checked before the final, as required. No layout or audio defect was found
in the draft that needed a re-render; the one real defect found earlier (the ~1.3 s cut holes) was
fixed before the draft that is reported here, and the caption-size change came out of the pixel-level
right-margin check, not out of the draft video.

## 10. Project package

`project.zip` (14,460,735 bytes): 63 entries, 62 media assets (**13 images, 49 audio; 0 video**), all
referenced media included, ZIP integrity check passed, manifest at schema version 1, revision 70,
13 scenes. Import it with **Impor paket proyek** in JDH Shorts Studio to continue editing; the media
files are the exact cards and takes used for this render, including the original Kokoro takes
alongside the levelled and trimmed versions.

## 11. Reproduce

```sh
cd /Users/jeripurnamamaulid/Projects/01_PRODUCT-Claude/jdh-shorts-studio/output/nine-repositories-short
../../.venv/bin/python source/extract_source.py     # article crops + assertions
../../.venv/bin/python build_assets.py              # cards + scene plan
../../.venv/bin/python produce.py prepare|level|pace|captions|draft|final
../../.venv/bin/python qa_check.py final/final.mp4 final
../../.venv/bin/python finalize.py
```

The server used for every API step is a task-owned instance
(`JDH_DATA_DIR=…/nine-repositories-short/jdh-data`, `JDH_PORT=56125`,
`JDH_KOKORO_DIR=…/jdh-shorts-studio/data/models/kokoro`). The Heartwoodfall project and every
pre-existing asset were never opened for writing; no second server ran against any other data
directory.
