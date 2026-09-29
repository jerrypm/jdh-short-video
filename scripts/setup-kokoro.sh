#!/usr/bin/env bash
set -euo pipefail
studio_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$studio_root"
[[ -x .venv/bin/python ]] || { echo 'Run ./scripts/setup.sh first.'; exit 1; }
export HF_HUB_DISABLE_TELEMETRY=1 HF_HOME="$studio_root/data/.huggingface"
unset HF_HUB_OFFLINE TRANSFORMERS_OFFLINE
uv pip install --python .venv/bin/python -r backend/requirements-kokoro.lock
.venv/bin/python scripts/download_kokoro.py
echo 'Kokoro ready. Restart the local server and reload the browser.'
