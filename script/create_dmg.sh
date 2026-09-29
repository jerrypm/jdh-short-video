#!/usr/bin/env bash
# Package the existing verified build without touching the running installation.
set -euo pipefail
STUDIO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_BUNDLE="$STUDIO_ROOT/dist/JDH Shorts Studio.app"
PLIST="$APP_BUNDLE/Contents/Info.plist"
[[ -f "$PLIST" ]] || { echo 'Build the app first: ./script/build_and_run.sh --build'; exit 1; }
[[ -x "$STUDIO_ROOT/.venv/bin/python" ]] || { echo 'The development Python environment is required for the runtime check.'; exit 1; }
VERSION="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleShortVersionString' "$PLIST")"
MINIMUM_OS="$(/usr/libexec/PlistBuddy -c 'Print :LSMinimumSystemVersion' "$PLIST")"
[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo 'Unexpected app version'; exit 1; }
OUTPUT="$STUDIO_ROOT/dist/JDH-Shorts-Studio-$VERSION-arm64.dmg"
PARTIAL="$STUDIO_ROOT/dist/JDH-Shorts-Studio-$VERSION-arm64.building.dmg"
REPORT="$STUDIO_ROOT/dist/JDH-Shorts-Studio-$VERSION-runtime-check.json"
RELEASE_REPORT="$STUDIO_ROOT/dist/JDH-Shorts-Studio-$VERSION-release-check.json"
KEEP_INSTALL_CHECK="${JDH_KEEP_INSTALL_CHECK:-0}"
[[ ! -e "$OUTPUT" && ! -e "$PARTIAL" ]] || { echo 'A DMG with this version already exists. Move it aside before rebuilding.'; exit 1; }
/usr/bin/codesign --verify --deep --strict "$APP_BUNDLE"
STAGE="$(mktemp -d /private/tmp/jdh-dmg-stage.XXXXXX)"
MOUNT="$(mktemp -d /private/tmp/jdh-dmg-check.XXXXXX)"
INSTALL_CHECK="$(mktemp -d /private/tmp/jdh-install-check.XXXXXX)"
MOUNTED=0
cleanup() {
  if [[ "$MOUNTED" == 1 ]]; then
    /usr/bin/hdiutil detach "$MOUNT" -quiet || true
  fi
  rm -rf "$STAGE"
  if [[ "$KEEP_INSTALL_CHECK" != 1 ]]; then rm -rf "$INSTALL_CHECK"; fi
  rmdir "$MOUNT" 2>/dev/null || true
  # Preserve an incomplete image for diagnosis/retry if verification fails.
}
trap cleanup EXIT
/usr/bin/ditto "$APP_BUNDLE" "$STAGE/JDH Shorts Studio.app"
ln -s /Applications "$STAGE/Applications"
{
  printf 'JDH Shorts Studio %s\nApple Silicon (M-series) · macOS %s or later\n\n' "$VERSION" "$MINIMUM_OS"
  cat <<'NOTES'
INSTALL ON YOUR MAC MINI

1. Open this disk image.
2. Drag JDH Shorts Studio into the Applications folder beside it.
   Quit an older version before replacing it.
3. Eject the disk image.
4. Open JDH Shorts Studio from Applications.

Python, Kokoro voices/models, FFmpeg and the editor are included.
No Terminal setup, Homebrew, Node.js or separate Python install is needed.
Allow at least 3 GB of free disk space for the app and initial working space;
video imports and exports need additional space.

FIRST OPEN ON ANOTHER MAC

This personal build is signed ad hoc, not Developer ID signed or notarized.
If macOS blocks it as an unidentified developer, first try opening the app,
then use System Settings > Privacy & Security > Open Anyway for this app.
Apple's instructions: https://support.apple.com/en-us/102445
Do not disable Gatekeeper globally. An alert saying the app is damaged should
be investigated by checking the transfer/checksum, not bypassed automatically.

YOUR PROJECTS

Projects are stored in:
~/Library/Application Support/JDH Shorts Studio/Projects

This installer contains no existing projects or personal media. To continue
an existing project on the Mac mini, export its project.zip on the other Mac
and choose "Impor paket proyek" on the Mac mini's project screen.

GEMINI NANO LOCAL COMPANION (OPTIONAL)

Nano runs locally in Google Chrome through a companion tab, not inside WebKit.
It is NOT bundled in this DMG. No cloud provider or API key is used.

1. Use your personal Chrome profile, not a work-managed account/profile.
2. In the Mac app open Setup & pengaturan > Buat tautan companion.
3. Copy the single-use link into personal Chrome within three minutes.
4. If offered, click Siapkan model lokal in the companion. Chrome decides
   device eligibility and downloads/stores Nano; internet is needed initially.
   Chrome's current hardware/storage requirements are documented at:
   https://developer.chrome.com/docs/ai/prompt-api#hardware-requirements
5. Keep Chrome and that companion tab open. Use English for AI features.
   After restarting the app, create a new companion link.

If Chrome is closed/disconnected or its model is unavailable, manual editing,
imported narration, bundled Kokoro English and exports remain available.
If Chrome reports ERR_BLOCKED_BY_CLIENT, investigate the personal profile's
policy/extensions; this app does not bypass browser protection or change it.
Real Nano inference in the integrated app has not yet been verified. Protocol,
proposal and browser-script tests use explicitly labelled fixtures/model doubles.

Review all AI suggestions before applying. Exported upload.zip is for manual
publishing: there is no YouTube login, account connection or automatic upload.

JRDEVHUB
NOTES
} > "$STAGE/Install.txt"
echo "Creating compressed disk image for version ${VERSION}..."
/usr/bin/hdiutil create -volname 'JDH Shorts Studio' -srcfolder "$STAGE" -fs HFS+ -format ULFO "$PARTIAL"
/usr/bin/hdiutil verify "$PARTIAL"
/usr/bin/hdiutil attach "$PARTIAL" -readonly -nobrowse -mountpoint "$MOUNT" -quiet
MOUNTED=1
[[ -L "$MOUNT/Applications" && "$(readlink "$MOUNT/Applications")" == /Applications ]]
[[ -s "$MOUNT/Install.txt" ]]
/usr/bin/codesign --verify --deep --strict "$MOUNT/JDH Shorts Studio.app"
echo 'Copying the application out of the DMG, as on a new Mac...'
/usr/bin/ditto "$MOUNT/JDH Shorts Studio.app" "$INSTALL_CHECK/JDH Shorts Studio.app"
/usr/bin/codesign --verify --deep --strict "$INSTALL_CHECK/JDH Shorts Studio.app"
echo 'Checking Kokoro and FFmpeg from the freshly installed copy...'
"$STUDIO_ROOT/.venv/bin/python" "$STUDIO_ROOT/script/verify_desktop_runtime.py" --app "$INSTALL_CHECK/JDH Shorts Studio.app" --report "$REPORT" --startup-timeout 120
echo 'Checking relocated release workflows and native dependencies...'
"$STUDIO_ROOT/.venv/bin/python" "$STUDIO_ROOT/script/verify_release.py" --app "$INSTALL_CHECK/JDH Shorts Studio.app" --report "$RELEASE_REPORT"
/usr/bin/hdiutil detach "$MOUNT" -quiet
MOUNTED=0
mv "$PARTIAL" "$OUTPUT"
(
  cd "$STUDIO_ROOT/dist"
  /usr/bin/shasum -a 256 "$(basename "$OUTPUT")" > "$(basename "$OUTPUT").sha256"
)
echo "DMG ready: $OUTPUT"
if [[ "$KEEP_INSTALL_CHECK" == 1 ]]; then echo "INSTALL_CHECK_APP=$INSTALL_CHECK/JDH Shorts Studio.app"; fi
ls -lh "$OUTPUT"
