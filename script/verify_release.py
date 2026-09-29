"""Validate the app copied OUT of a DMG using disposable data, never user projects."""

import argparse
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import tempfile
import time

from verify_content_memory_runtime import main as memory
from verify_daily_ideas_runtime import main as ideas
from verify_storyboard_runtime import main as storyboard
from verify_pacing_runtime import main as pacing
from verify_quality_runtime import main as quality
from verify_release_lifecycle import main as lifecycle

ROOT = Path(__file__).resolve().parents[1]


def command(args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, capture_output=True,
                          text=True, **kwargs).stdout


def audit(app):
    resources = app / "Contents/Resources"
    info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
    assert info["LSMinimumSystemVersion"] == "26.0"
    command(["/usr/bin/codesign", "--verify", "--deep", "--strict", app])
    assert not (resources / "studio/data").exists()
    macho = []
    for path in app.rglob("*"):
        if path.is_symlink():
            assert path.resolve().is_relative_to(app), f"External symlink: {path}"
            continue
        if not path.is_file():
            continue
        with path.open("rb") as stream:
            magic = stream.read(4)
        if magic not in (b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf"):
            continue
        architectures = command(["/usr/bin/lipo", "-archs", path]).split()
        assert "arm64" in architectures, f"Missing arm64: {path}"
        # otool -L lists a dylib's own LC_ID_DYLIB before its dependencies.
        # That historical build identifier is not a runtime dependency.
        identifiers = command(["/usr/bin/otool", "-arch", "arm64", "-D", path]).splitlines()[1:]
        linked = command(["/usr/bin/otool", "-arch", "arm64", "-L", path]).splitlines()[1:]
        for line in linked:
            dependency = line.strip().split(" (compatibility")[0]
            if dependency in identifiers:
                continue
            assert not dependency.startswith(("/opt/homebrew/", "/usr/local/", "/Users/")), (path, dependency)
        loads = command(["/usr/bin/otool", "-arch", "arm64", "-l", path])
        minimum = re.findall(r"\bminos (\d+(?:\.\d+)*)", loads)
        assert all(tuple(map(int, v.split('.'))) <= (26, 0, 0) for v in minimum), (path, minimum)
        macho.append({"path": str(path.relative_to(app)), "architectures": architectures,
                      "minimum_os": minimum})
    assert len(macho) > 10
    return {"version": info["CFBundleShortVersionString"], "build": info["CFBundleVersion"],
            "minimum_macos": info["LSMinimumSystemVersion"], "macho_files": macho,
            "signature": "ad-hoc; deep/strict verified", "notarized": False}


def offline(resources):
    with tempfile.TemporaryDirectory(prefix="jdh-release-offline-") as folder:
        python = resources / "python"
        environment = dict(os.environ, PYTHONHOME=str(python),
            PYTHONPATH=str(resources / "studio") + os.pathsep + str(python / "lib/python3.13/site-packages"),
            PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1", JDH_DATA_DIR=folder,
            JDH_KOKORO_DIR=str(resources / "models/kokoro"), JDH_ESPEAK_DIR=str(resources / "espeak-ng-data"),
            HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1", PATH=str(resources / "tools/bin")+":/usr/bin:/bin")
        environment.pop("VIRTUAL_ENV", None)
        code = '''
import json, socket
def denied(*args, **kwargs):
    raise RuntimeError("Offline check detected network attempt")
socket.socket.connect = socket.socket.connect_ex = socket.create_connection = denied
from backend import jobs, tts
from backend.models import Project, Scene, TTSRequest
p=Project(id="0"*32,name="Disposable offline QA",language="en",scenes=[Scene(id="voice",narration="One clear idea. Build it locally.")])
j=jobs.Job(p.id,"tts")
tts.generate(p,TTSRequest(scene_id="voice"),j)
assert (j.directory/"narration.wav").stat().st_size > 1000
assert j.result["frames"] > 0
print(json.dumps({"real_kokoro":True,"network":"Python sockets denied","frames":j.result["frames"]}))
'''
        return json.loads(command([python / "bin/python3.13", "-c", code], env=environment, cwd=folder).splitlines()[-1])


def main(app, report):
    app = app.resolve()
    report.parent.mkdir(parents=True, exist_ok=True)
    result = {"app_tested": str(app), "real_nano_inference": False, "suites": {}}
    print("Auditing relocated native binaries…", flush=True)
    result["bundle"] = audit(app)
    resources = app / "Contents/Resources"
    print("Running shipped companion JS with labelled model doubles…", flush=True)
    environment = dict(os.environ, JDH_COMPANION_SCRIPT=str(resources / "studio/backend/nano_web/companion.js"))
    command(["node", "--test", ROOT / "script/test_companion.mjs"], env=environment)
    result["companion_js_tests"] = 12
    print("Checking real Kokoro with Python network calls denied…", flush=True)
    result["offline"] = offline(resources)
    with tempfile.TemporaryDirectory(prefix="jdh-release-reports-") as folder:
        for name, run in [("memory", memory), ("ideas", ideas), ("storyboard", storyboard),
                          ("pacing", pacing), ("quality", lambda a, r: quality(a, r, False)),
                          ("lifecycle", lambda a, r: lifecycle(a, r, Path(tempfile.mkdtemp(prefix="jdh-release-fixtures-"))))]:
            print(f"Verifying relocated {name} workflow…", flush=True)
            started = time.monotonic()
            output = Path(folder) / (name + ".json")
            run(app, output)
            data = json.loads(output.read_text())
            # Older harnesses label their feature milestone; record the tested release explicitly.
            data["version"] = result["bundle"]["version"]
            data["build"] = result["bundle"]["build"]
            result["suites"][name] = {"seconds": round(time.monotonic()-started, 2), "result": data}
            report.write_text(json.dumps(result, indent=2))
    result["passed"] = True
    report.write_text(json.dumps(result, indent=2))
    print(f"Relocated release verification passed: {report}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    main(args.app, args.report)
