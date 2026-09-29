#!/usr/bin/env bash
set -euo pipefail
MODE="${1:-run}"
STUDIO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$STUDIO_ROOT"
APP_BUNDLE="$STUDIO_ROOT/dist/JDH Shorts Studio.app"
# SIGTERM is handled by the app: save first, then stop its own sidecar.
if pgrep -x JDHShortsStudio >/dev/null; then
  pkill -TERM -x JDHShortsStudio
  for attempt in {1..60}; do
    if ! pgrep -x JDHShortsStudio >/dev/null; then break; fi
    sleep 0.25
  done
  if pgrep -x JDHShortsStudio >/dev/null; then
    echo 'Studio is waiting for a quit decision. Finish that dialog before rebuilding.'
    exit 1
  fi
fi
case "$MODE" in run|--verify|--build|--qa|--logs|--telemetry|--debug) ;; *) echo 'Usage: build_and_run.sh [--build|--verify|--qa|--logs|--telemetry|--debug]'; exit 2 ;; esac
[[ -x .venv/bin/python ]] || { echo 'Run scripts/setup.sh and scripts/setup-kokoro.sh first.'; exit 1; }
(cd web && npm run build)
swift build --package-path macos --configuration release
.venv/bin/python script/package_macos.py
if [[ "$MODE" == '--build' ]]; then exit 0; fi
if [[ "$MODE" == '--qa' ]]; then
  /usr/bin/open -n "$APP_BUNDLE" --args --isolated-qa
else
  /usr/bin/open -n "$APP_BUNDLE"
fi
case "$MODE" in
  --verify) sleep 2; pgrep -x JDHShortsStudio >/dev/null; echo 'Native app process is running.' ;;
  --logs|--telemetry) /usr/bin/log stream --info --style compact --predicate 'process == "JDHShortsStudio"' ;;
  --debug) lldb -n JDHShortsStudio ;;
esac
