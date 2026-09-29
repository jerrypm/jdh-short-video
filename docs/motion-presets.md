# Motion presets v1

Task 07, app 0.2.7 build 9. The editor and renderer use bounded preset data. AI remains the paired **local Gemini Nano** companion; motion itself requires no model, network connection or new dependency.

## Editor workflow

Select a scene, open **Animasi & callout** in the inspector, then choose a visual preset. Adjust intensity (0–12%, default 6%), focus X/Y and easing. Frame numbers are local to the scene at 30 fps. A blank end frame follows the last scene frame; shortening the scene clips the effective range without rewriting the saved intention. The UI displays the effective range.

**Animasi caption** supports no motion, fade in, or slide up with a fade. **Tampilkan callout** adds an editable label, box position/width/font size and pointer target. Caption and callout animation timings are independent. **Gerak seluruh proyek → Tanpa gerak** preserves the saved presets but displays static visuals and fully visible text. Normal autosave and Undo/Redo apply.

The same controls appear in storyboard review. Changing a reviewed proposal invalidates its review until checked again. Nothing is automatically applied to an existing project. Nano may choose only validated presets/parameters; it cannot supply renderer commands, filter graphs, file paths or cross-scene transitions.

## Data contract

`Scene.motion` has `version: 1`, `visual`, `caption` and nullable `callout`. Missing fields on old project manifests acquire defaults: visual/text `none`, no callout. `Project.motion_mode` defaults to `gentle`; `none` overrides all animation. Project schema remains 1 because these are additive fields with defaults. Revision checks, atomic replacement and previous-version backups remain in effect.

| Field | Values / bounds |
| --- | --- |
| Visual preset | `none`, `zoom_in`, `zoom_out`, `pan_left`, `pan_right`, `pan_up`, `pan_down` |
| Amount / focus | Amount 0–0.12; focus X/Y 0–1 |
| Visual easing | `linear`, `smoothstep` |
| Text preset / easing | `none`, `fade`, `slide_up`; linear |
| Frame range | Start integer 0–1798; end integer 1–1799 or null; explicit end must exceed start |
| Callout | 1–120 literal characters; maximum two measured lines; box width 160–800, font 24–48 |
| Callout position | X 65–855 and X+width ≤1015; Y 135–1450; target X 65–1015, Y 135–1612 |
| Slide callout bounds | Box Y ≤1400 and target Y ≤1564 reserve the 48 px entrance; the UI moves lower positions into range when selecting slide |

Unknown fields, non-finite numbers, wrong types, unsupported versions and out-of-range parameters are rejected by the backend. Callout text is rendered as literal text with the bundled font, never interpreted as code. The old storyboard `effect: static` field stays for compatibility; `motion` now carries animation and scene joins remain cuts.

## Preview/export coordinates and timing

All positions use a canonical 1080×1920 canvas. Source Fit/Fill, scale, offset and clipping are composed first; visual motion transforms that entire canvas, including Fit letterboxing. Captions and callouts stay above that moving visual layer. Pan names describe camera travel; the image moves in the opposite direction. Manual focus controls the crop anchor, with pan travel clamped to the canvas.

For duration D, the final local frame is D−1. The effective start/end fit within that duration. Progress is clamped to 0–1; `smoothstep` is p²(3−2p). Zoom goes from 1 to 1+amount (or the reverse); pan uses fixed 1+amount zoom. Entrance opacity goes from 0 to 1, with slide translation from +48 px to 0. First/last states hold outside the range. Seeking recomputes the state deterministically; there is no CSS transition clock.

React and Python evaluate equivalent formulas. FFmpeg uses internally assembled [zoompan](https://ffmpeg.org/ffmpeg-filters.html#zoompan), [fade](https://ffmpeg.org/ffmpeg-filters.html#fade) and [overlay](https://ffmpeg.org/ffmpeg-filters.html#overlay) filters. The text inputs are looped at 30 fps; overlay slide uses timestamps on that same timeline. Preview/export share the actual caption and callout PNGs and IBM Plex font. Export scales these to draft or final resolution. Resampling and encoding mean pixel identity is not expected.

Preview preloads current/next text overlays. A frame tick updates CSS only, without another PNG request or audio seek/play. The existing media controller and PCM intermediate/single AAC encode path are preserved. Motion does not alter scene duration, source trim, narration trim or SRT timestamps. Scene-level SRT has no animation/callout drawing data.

## Scope and verification

See [Task 07 results](gemini-nano-task-07-results.md) and [runtime metrics](qa/motion-runtime.json). `script/verify_motion_runtime.py` creates isolated fixtures, compares initial/mid/final exported frames against the **actual TypeScript evaluator composed with PIL**, checks audio equality and restart persistence. This numeric comparison is distinct from the browser screenshot checks documented in the report.

Safe-area coordinates are this editor's existing guides, not a guarantee against every YouTube overlay. The pointer dot has a 6 px radius around its bounded target. Caption placement retains its existing manual controls; automatic caption/callout collision detection is not part of Task 07. Review the first and last frames when changing framing or focus. Splitting a silent scene starts each new scene's preset independently; motion continuity across cuts and crossfades are not implemented. No background/object tracking, arbitrary keyframes, text exit animation or per-word caption alignment is added.

Native WebKit performance, real Nano under load, and the destination Mac mini still require device verification. Browser playback smoke checks and renderer timings are not a measured native 30 fps guarantee.
