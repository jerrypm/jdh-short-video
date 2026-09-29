# OpenCut audit — 2026-09-21

Source: [OpenCut Classic](https://github.com/OpenCut-app/opencut-classic), commit `cf5e79e919144200294fb9fed22a222592a0aeea`, MIT. Audit clone: `/private/tmp/jdh-opencut-classic` (temporary, not part of the deliverable).

Classic uses Next.js 16.1.3, React and a broad editor/storage/renderer stack. Its repository instructions also describe moving core logic to Rust. The initial install hit an extraction error for another workspace's Next dependency, but the web workspace's installed Next.js 16.1.3 started successfully. Environment validation initially failed without a local env file. Copying its supplied `.env.example` to `.env.local` resolved this, and the real `/projects` route returned HTTP 200. `/editor` is not a valid route; its actual editor route is `/editor/[project_id]`. A 404 there must not be interpreted as a broken editor.

The upstream repository is therefore **not established to be unusable**. The original requested full fork/reuse gate remains incomplete. Browser-level import, timeline playback, export, and storage tests of upstream were not finished. The replacement OpenCut repository was inspected only at a high level; its full comparative audit is also pending.

This milestone reused the actual Classic snapping resolver and related frame/scale utilities under `web/src/vendor/opencut`, with source commit and MIT license retained. MediaTime dependencies were adapted to the application's integer-frame model. The React panels, persistence and native renderer in this checkout were authored for JDH. Do not describe this as a completed OpenCut fork or a completed upstream evaluation.

Next architectural checkpoint: run the upstream editor workflow through the browser, compare its timeline/selection/command/storage modules against this milestone, and decide which can be adopted without restoring cloud service dependencies or browser FFmpeg export. Preserve the working manual → Kokoro → native export path during that integration.
