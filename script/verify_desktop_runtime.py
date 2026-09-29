"""Exercise the bundled sidecar from an unrelated working directory."""

import argparse
import io
import json
import os
import select
import subprocess
import tempfile
import time
from pathlib import Path
import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "dist/JDH Shorts Studio.app/Contents/Resources"


def main(resources=RESOURCES, report=ROOT / "docs/qa/macos-runtime-check.json", startup_timeout=30):
    runtime = resources / "python"
    with tempfile.TemporaryDirectory(prefix="jdh-app-check-") as directory:
        environment = dict(
            os.environ,
            PYTHONHOME=str(runtime),
            PYTHONPATH=str(runtime / "lib/python3.13/site-packages"),
            PYTHONNOUSERSITE="1",
            PYTHONDONTWRITEBYTECODE="1",
            HF_HUB_OFFLINE="1",
            TRANSFORMERS_OFFLINE="1",
            PATH=str(resources / "tools/bin") + ":/usr/bin:/bin",
            JDH_DATA_DIR=directory,
            JDH_KOKORO_DIR=str(resources / "models/kokoro"),
            JDH_ESPEAK_DIR=str(resources / "espeak-ng-data"),
            JDH_DESKTOP_TOKEN="integration-test-token",
        )
        environment.pop("VIRTUAL_ENV", None)
        log = Path(directory) / "server.log"
        with log.open("w") as errors:
            started_at = time.monotonic()
            child = subprocess.Popen(
                [
                    runtime / "bin/python3.13",
                    "-u",
                    resources / "studio/scripts/desktop_server.py",
                ],
                cwd=directory,
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=errors,
                text=True,
            )
            try:
                if not select.select([child.stdout], [], [], startup_timeout)[0]:
                    raise RuntimeError("Startup timeout: " + log.read_text())
                line = child.stdout.readline().strip()
                assert line.startswith("JDH_PORT="), (line, log.read_text())
                port = int(line.split("=")[1])
                with httpx.Client(
                    base_url=f"http://127.0.0.1:{port}", timeout=30
                ) as client:
                    for _ in range(80):
                        try:
                            response = client.get(
                                "/api/desktop/health",
                                headers={"X-JDH-Desktop": "integration-test-token"},
                            )
                            if response.status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                        time.sleep(0.25)
                    assert response.json()["ready"]
                    startup_seconds = round(time.monotonic() - started_at, 2)
                    assert client.get("/api/desktop/health").status_code == 403
                    assert client.get("/").status_code == 200
                    client.headers["X-JDH-CSRF"] = client.get("/api/session").json()[
                        "csrf"
                    ]
                    caps = client.get("/api/capabilities").json()
                    assert (
                        caps["desktop"]
                        and caps["ffmpeg"]
                        and caps["ffprobe"]
                        and caps["tts"]["available"]
                    ), caps
                    project = client.post(
                        "/api/projects",
                        json={"name": "Packaged runtime QA", "language": "en"},
                    ).json()
                    buffer = io.BytesIO()
                    Image.new("RGB", (360, 640), "#263847").save(buffer, format="PNG")
                    imported = client.post(
                        f"/api/projects/{project['id']}/media",
                        files={"file": ("fixture.png", buffer.getvalue(), "image/png")},
                    ).json()
                    project = imported["project"]
                    project["scenes"] = [
                        {
                            "id": "scene1",
                            "name": "Runtime test",
                            "narration": "One idea. One short.",
                            "caption": "One idea. One short.",
                            "duration": 150,
                            "media_id": imported["asset"]["id"],
                        }
                    ]
                    result = client.put(f"/api/projects/{project['id']}", json=project)
                    result.raise_for_status()
                    project = result.json()

                    def finished(job):
                        deadline = time.monotonic() + 120
                        while (
                            job["status"] in ("running", "queued")
                            and time.monotonic() < deadline
                        ):
                            time.sleep(0.3)
                            job = client.get("/api/jobs/" + job["id"]).json()
                        assert job["status"] == "completed", job
                        return job

                    speech = finished(
                        client.post(
                            f"/api/projects/{project['id']}/tts",
                            json={
                                "scene_id": "scene1",
                                "voice": "af_heart",
                                "speed": 1,
                            },
                        ).json()
                    )
                    applied = client.post(
                        f"/api/projects/{project['id']}/tts/{speech['id']}/apply",
                        json={"revision": project["revision"]},
                    )
                    applied.raise_for_status()
                    print("Bundled Kokoro produced real speech.", flush=True)
                    output = finished(
                        client.post(
                            f"/api/projects/{project['id']}/render",
                            json={"preset": "draft"},
                        ).json()
                    )
                    assert (
                        len(
                            client.get(
                                f"/api/jobs/{output['id']}/files/draft.mp4"
                            ).content
                        )
                        > 1000
                    )
                    print(
                        "Bundled FFmpeg rendered and verified an MP4 with narration.",
                        flush=True,
                    )
                    manifest = {
                        "startup": "passed",
                        "startup_seconds": startup_seconds,
                        "private_health": "passed",
                        "static_ui": "passed",
                        "kokoro": "real speech",
                        "ffmpeg": "draft MP4 + full decode",
                        "source_checkout_on_runtime_path": False,
                        "application_storage": caps["storage"],
                    }
                child.stdin.close()
                child.wait(timeout=15)
                assert child.returncode == 0
                manifest["shutdown"] = "EOF stopped owned sidecar"
                report.parent.mkdir(parents=True, exist_ok=True)
                report.write_text(json.dumps(manifest, indent=2))
                print(json.dumps(manifest, indent=2))
            finally:
                print("Sidecar return code:", child.poll(), flush=True)
                print(log.read_text()[-6000:], flush=True)
                if child.poll() is None:
                    child.stdin.close()
                    try:
                        child.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, default=RESOURCES.parent.parent)
    parser.add_argument("--report", type=Path, default=ROOT / "docs/qa/macos-runtime-check.json")
    parser.add_argument("--startup-timeout", type=float, default=30)
    arguments = parser.parse_args()
    main(arguments.app.resolve() / "Contents/Resources", arguments.report.resolve(), arguments.startup_timeout)
