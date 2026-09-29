"""Verify packaged content memory across real sidecar restarts, with disposable data."""

import argparse
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import select
import subprocess
import tempfile
import time
from uuid import uuid4
import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def runtime(resources, directory):
    python = resources / "python"
    token = uuid4().hex
    environment = dict(
        os.environ,
        PYTHONHOME=str(python),
        PYTHONPATH=str(python / "lib/python3.13/site-packages"),
        PYTHONNOUSERSITE="1",
        PYTHONDONTWRITEBYTECODE="1",
        JDH_DATA_DIR=str(directory),
        JDH_DESKTOP_TOKEN=token,
        JDH_KOKORO_DIR=str(resources / "models/kokoro"),
        JDH_ESPEAK_DIR=str(resources / "espeak-ng-data"),
        HF_HUB_OFFLINE="1",
        TRANSFORMERS_OFFLINE="1",
        PATH=str(resources / "tools/bin") + ":/usr/bin:/bin",
    )
    environment.pop("VIRTUAL_ENV", None)
    with (directory / "runtime.log").open("a") as log:
        child = subprocess.Popen(
            [
                python / "bin/python3.13",
                "-u",
                resources / "studio/scripts/desktop_server.py",
            ],
            cwd=directory,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=log,
            text=True,
        )
        try:
            if not select.select([child.stdout], [], [], 30)[0]:
                raise RuntimeError("Packaged runtime did not start in 30 seconds.")
            line = child.stdout.readline().strip()
            assert line.startswith("JDH_PORT="), line
            with httpx.Client(
                base_url="http://127.0.0.1:" + line.split("=")[1],
                timeout=15,
                trust_env=False,
            ) as client:
                for _ in range(80):
                    try:
                        if (
                            client.get(
                                "/api/desktop/health", headers={"X-JDH-Desktop": token}
                            ).status_code
                            == 200
                        ):
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(0.1)
                client.headers["X-JDH-CSRF"] = client.get("/api/session").json()["csrf"]
                yield client
        finally:
            child.stdin.close()
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.terminate()
                child.wait(timeout=5)
                raise RuntimeError("Packaged runtime did not shut down on EOF.")
            assert child.returncode == 0


def call(client, method, path, **kwargs):
    response = client.request(method, "/api" + path, **kwargs)
    response.raise_for_status()
    return response.json()


def main(app, report):
    resources = app.resolve() / "Contents/Resources"
    checks = []
    with tempfile.TemporaryDirectory(prefix="jdh-memory-runtime-qa-") as temporary:
        directory = Path(temporary)
        with runtime(resources, directory) as client:
            empty = call(client, "GET", "/memory")["catalog"]
            assert empty["references"] == []
            projects = [
                call(
                    client,
                    "POST",
                    "/projects",
                    json={"name": name, "script": script, "language": "en"},
                )
                for name, script in [
                    ("Counter tutorial", "A SwiftUI counter uses State."),
                    ("Counter duplicate", "A SwiftUI counter uses State."),
                    ("QA — scratch", "Test-only content"),
                    ("Unselected draft", "Do not add this source to memory"),
                ]
            ]
            selected = call(
                client,
                "POST",
                "/memory/references",
                json={
                    "revision": empty["revision"],
                    "project_ids": [p["id"] for p in projects[:3]],
                },
            )["catalog"]
            assert [r["category"] for r in selected["references"]] == [
                "content",
                "duplicate",
                "qa",
            ]
            assert projects[3]["script"] not in json.dumps(selected)
            checks += [
                "empty catalog",
                "explicit opt-in",
                "QA and duplicate separation",
            ]
            pid = projects[0]["id"]
            saved = call(
                client,
                "PUT",
                "/memory/references/" + pid,
                json={
                    "revision": selected["revision"],
                    "source_revision": 0,
                    "included": True,
                    "category": "content",
                    "published": False,
                    "confirmed": {
                        "themes": ["SwiftUI"],
                        "series": "Basics",
                        "summary": "User summary of the counter tutorial.",
                    },
                },
            )["catalog"]
            saved = call(
                client,
                "PUT",
                "/memory/profile",
                json={
                    "revision": saved["revision"],
                    "profile": {"name": "QA channel", "language": "en"},
                },
            )["catalog"]
            saved = call(
                client,
                "POST",
                f"/memory/references/{pid}/feedback",
                json={
                    "revision": saved["revision"],
                    "idea": "Show a reset button",
                    "verdict": "saved",
                    "reason": "Useful next example",
                },
            )["catalog"]
            stale_revision = saved["revision"]
            picture = io.BytesIO()
            Image.new("RGB", (48, 48), "#536575").save(picture, format="PNG")
            imported = call(
                client,
                "POST",
                f"/projects/{pid}/media",
                files={"file": ("qa-owned-image.png", picture.getvalue(), "image/png")},
            )
            asset_id = imported["asset"]["id"]
            project = imported["project"]
            project["script"] = "A revised explanation of the SwiftUI counter."
            project = call(client, "PUT", "/projects/" + pid, json=project)
            saved = call(client, "GET", "/memory")["catalog"]
            reference = next(r for r in saved["references"] if r["project_id"] == pid)
            assert reference["observed"]["source_revision"] == project["revision"]
            assert reference["observed"]["asset_ids"] == [asset_id]
            assert (
                reference["confirmed"]["summary"]
                == "User summary of the counter tutorial."
            )
            assert (
                client.put(
                    "/api/memory/profile",
                    json={"revision": stale_revision, "profile": {}},
                ).status_code
                == 409
            )
            context = call(
                client,
                "POST",
                "/memory/retrieve",
                json={"language": "en", "theme": "SwiftUI"},
            )
            assert (
                len(context["references"]) == 1
                and context["references"][0]["project_id"] == pid
            )
            assert context["references"][0]["status"] == "draft"
            assert (
                len(json.dumps(context, ensure_ascii=False, separators=(",", ":")))
                <= 6000
            )
            checks += [
                "profile and labels",
                "feedback",
                "source revision refresh",
                "conflict rejection",
                "bounded local retrieval",
            ]
            media_hash = hashlib.sha256(
                client.get(f"/api/projects/{pid}/media/{asset_id}").content
            ).hexdigest()
        # New bundled Python process, same isolated data directory, no browser/localStorage state.
        with runtime(resources, directory) as client:
            restored = call(client, "GET", "/memory")["catalog"]
            assert restored["profile"]["name"] == "QA channel"
            reference = next(
                r for r in restored["references"] if r["project_id"] == pid
            )
            assert reference["feedback"][0]["idea"] == "Show a reset button"
            assert reference["confirmed"]["series"] == "Basics"
            before = call(client, "GET", "/projects/" + pid)
            forgotten = call(
                client,
                "POST",
                f"/memory/references/{pid}/forget",
                json={"revision": restored["revision"]},
            )["catalog"]
            assert pid not in [r["project_id"] for r in forgotten["references"]]
            assert call(client, "POST", "/memory/retrieve", json={})["references"] == []
            assert call(client, "GET", "/projects/" + pid) == before
            assert (
                hashlib.sha256(
                    client.get(f"/api/projects/{pid}/media/{asset_id}").content
                ).hexdigest()
                == media_hash
            )
            checks += [
                "bundled sidecar restart",
                "forget invalidates retrieval",
                "project and media preserved",
                "EOF shutdown",
            ]
    result = {
        "app": str(app),
        "isolated_data": True,
        "real_nano_inference": False,
        "checks": checks,
        "passed": True,
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, default=ROOT / "dist/JDH Shorts Studio.app")
    parser.add_argument(
        "--report", type=Path, default=ROOT / "docs/qa/content-memory-runtime.json"
    )
    args = parser.parse_args()
    main(args.app, args.report)
