#!/usr/bin/env bash
set -euo pipefail
studio_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$studio_root"
[[ -x .venv/bin/python && -f web/out/index.html ]] || { echo 'Run ./scripts/setup.sh first.'; exit 1; }
export JDH_PORT="${JDH_PORT:-8741}"
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1
printf 'JDH Shorts Studio: http://127.0.0.1:%s\nPress Ctrl+C to stop.\n' "$JDH_PORT"
exec .venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port "$JDH_PORT"
