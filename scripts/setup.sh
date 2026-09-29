#!/usr/bin/env bash
set -euo pipefail
studio_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$studio_root"
command -v uv >/dev/null || { echo 'Install uv first: brew install uv'; exit 1; }
command -v npm >/dev/null || { echo 'Install Node.js 22+ first.'; exit 1; }
command -v ffmpeg >/dev/null || { echo 'Install FFmpeg first: brew install ffmpeg'; exit 1; }
command -v ffprobe >/dev/null || { echo 'ffprobe is missing from PATH.'; exit 1; }
if [[ ! -x .venv/bin/python ]]; then uv venv --python 3.13 .venv; fi
uv pip install --python .venv/bin/python -r backend/requirements.lock
(cd web && npm ci && npm run build)
echo 'Ready. Run ./scripts/start.sh'
