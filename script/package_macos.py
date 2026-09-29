"""Stage a self-contained, local Apple Silicon application bundle.

Copies the tested uv Python runtime and installed packages. FFmpeg's non-system
libraries are recursively vendored and relocated; host Homebrew paths are not
required at runtime. This is a local ad-hoc build, not a notarized distribution.
"""

import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "dist/JDH Shorts Studio.app"
CONTENTS = BUNDLE / "Contents"
RESOURCES = CONTENTS / "Resources"


def run(args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def copy_tree(source, destination, ignore=None):
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination, symlinks=True, ignore=ignore)


def dependencies(binary):
    result = run(["/usr/bin/otool", "-L", binary], capture_output=True, text=True)
    return [
        line.strip().split(" (compatibility")[0]
        for line in result.stdout.splitlines()[1:]
    ]


def bundle_ffmpeg():
    tools = RESOURCES / "tools"
    (tools / "bin").mkdir(parents=True, exist_ok=True)
    (tools / "lib").mkdir(exist_ok=True)
    mapped = {}
    pending = []
    for name in ("ffmpeg", "ffprobe"):
        source = Path(shutil.which(name) or "")
        if not source.is_file():
            raise RuntimeError(f"{name} must be installed before packaging")
        target = tools / "bin" / name
        shutil.copy2(source, target)
        pending.append((source.resolve(), target))
    inventory = []
    while pending:
        source, target = pending.pop()
        for dependency in dependencies(source):
            if dependency.startswith(("/System/", "/usr/lib/", "@")):
                continue
            linked = Path(dependency).resolve()
            if linked == source:
                continue
            if not linked.is_file():
                raise RuntimeError(f"Missing native dependency: {dependency}")
            library = tools / "lib" / linked.name
            if linked.name in mapped and mapped[linked.name] != linked:
                raise RuntimeError(f"Conflicting library basenames: {linked.name}")
            if linked.name not in mapped:
                mapped[linked.name] = linked
                shutil.copy2(linked, library)
                pending.append((linked, library))
                inventory.append(
                    {
                        "name": linked.name,
                        "source": str(linked),
                        "sha256": hashlib.sha256(linked.read_bytes()).hexdigest(),
                    }
                )
            relative = os.path.relpath(library, target.parent)
            run(
                [
                    "/usr/bin/install_name_tool",
                    "-change",
                    dependency,
                    "@loader_path/" + relative,
                    target,
                ],
                capture_output=True,
            )
        if target.suffix == ".dylib":
            run(
                [
                    "/usr/bin/install_name_tool",
                    "-id",
                    "@loader_path/" + target.name,
                    target,
                ],
                capture_output=True,
            )
        run(
            ["/usr/bin/codesign", "--force", "--sign", "-", target], capture_output=True
        )
    (RESOURCES / "ffmpeg-libraries.json").write_text(json.dumps(inventory, indent=2))
    for target in list((tools / "bin").iterdir()) + list((tools / "lib").iterdir()):
        if any(
            dep.startswith(("/opt/homebrew/", "/usr/local/"))
            for dep in dependencies(target)
        ):
            raise RuntimeError(f"Unrelocated dependency in {target}")
    run([tools / "bin/ffmpeg", "-version"], stdout=subprocess.DEVNULL)
    run([tools / "bin/ffprobe", "-version"], stdout=subprocess.DEVNULL)


def main():
    CONTENTS.mkdir(parents=True, exist_ok=True)
    (CONTENTS / "MacOS").mkdir(exist_ok=True)
    RESOURCES.mkdir(exist_ok=True)
    binary_dir = run(
        [
            "swift",
            "build",
            "--package-path",
            ROOT / "macos",
            "-c",
            "release",
            "--show-bin-path",
        ],
        capture_output=True,
        text=True,
    ).stdout.strip()
    shutil.copy2(
        Path(binary_dir) / "JDHShortsStudio", CONTENTS / "MacOS/JDHShortsStudio"
    )
    (CONTENTS / "MacOS/JDHShortsStudio").chmod(0o755)
    info = {
        "CFBundleExecutable": "JDHShortsStudio",
        "CFBundleIdentifier": "com.jrdevhub.JDHShortsStudio",
        "CFBundleName": "JDH Shorts Studio",
        "CFBundleDisplayName": "JDH Shorts Studio",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "0.2.12",
        "CFBundleVersion": "14",
        "CFBundleIconFile": "AppIcon",
        "LSMinimumSystemVersion": "26.0",
        "LSMultipleInstancesProhibited": True,
        "NSPrincipalClass": "NSApplication",
        "NSHighResolutionCapable": True,
        "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
        "NSHumanReadableCopyright": "JDH Shorts Studio · JRDEVHUB",
    }
    with (CONTENTS / "Info.plist").open("wb") as stream:
        plistlib.dump(info, stream)
    iconset = ROOT / "macos/.build/AppIcon.iconset"
    run(["swift", ROOT / "script/make_icon.swift", iconset])
    run(["/usr/bin/iconutil", "-c", "icns", iconset, "-o", RESOURCES / "AppIcon.icns"])
    studio = RESOURCES / "studio"
    studio.mkdir(exist_ok=True)
    ignored = shutil.ignore_patterns("__pycache__", "*.pyc", "tests", ".DS_Store")
    for name in ("backend", "assets"):
        copy_tree(ROOT / name, studio / name, ignore=ignored)
    copy_tree(ROOT / "web/out", studio / "web/out")
    (studio / "scripts").mkdir(exist_ok=True)
    shutil.copy2(
        ROOT / "scripts/desktop_server.py", studio / "scripts/desktop_server.py"
    )
    for name in ("README.md", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(ROOT / name, studio / name)

    # Heavy runtimes are reused on incremental builds; explicit clean rebuilds
    # can remove dist/ while no app is running. No source/data paths are embedded.
    runtime = RESOURCES / "python"
    if not runtime.exists():
        print("Bundling Python runtime and Kokoro dependencies…", flush=True)
        copy_tree(Path(sys.base_prefix), runtime, ignore=ignored)
        copy_tree(
            ROOT / ".venv/lib/python3.13/site-packages",
            runtime / "lib/python3.13/site-packages",
            ignore=ignored,
        )
    model = ROOT / "data/models/kokoro"
    if not (RESOURCES / "espeak-ng-data").exists():
        copy_tree(
            ROOT / ".venv/lib/python3.13/site-packages/espeakng_loader/espeak-ng-data",
            RESOURCES / "espeak-ng-data",
        )
    if not (RESOURCES / "models/kokoro").exists():
        if not (model / "kokoro-v1_0.pth").is_file():
            raise RuntimeError(
                "Run ./scripts/setup-kokoro.sh before building the full desktop bundle."
            )
        copy_tree(
            model, RESOURCES / "models/kokoro", ignore=shutil.ignore_patterns(".cache")
        )
    if not (RESOURCES / "tools/bin/ffmpeg").exists():
        print("Bundling native renderer libraries…", flush=True)
        bundle_ffmpeg()

    # Confirm that the Python binary uses only its relocated bundle environment.
    env = dict(
        os.environ,
        PYTHONHOME=str(runtime),
        PYTHONPATH=str(runtime / "lib/python3.13/site-packages"),
        PYTHONNOUSERSITE="1",
        PYTHONDONTWRITEBYTECODE="1",
        HF_HUB_OFFLINE="1",
    )
    env.pop("VIRTUAL_ENV", None)
    run(
        [
            runtime / "bin/python3.13",
            "-c",
            'import sys, sqlite3, fastapi, torch, kokoro, en_core_web_sm; '
            'assert sqlite3.connect(":memory:").execute("SELECT 1").fetchone() == (1,); '
            'print("Bundled Python:", sys.prefix)',
        ],
        env=env,
    )
    run(
        ["/usr/bin/codesign", "--force", "--deep", "--sign", "-", BUNDLE],
        capture_output=True,
    )
    run(
        ["/usr/bin/codesign", "--verify", "--deep", "--strict", BUNDLE],
        capture_output=True,
    )
    print(f"App ready: {BUNDLE}", flush=True)


if __name__ == "__main__":
    main()
