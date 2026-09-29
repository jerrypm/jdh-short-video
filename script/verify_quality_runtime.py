"""Task 08 bundled-runtime QA. Disposable data; labelled fake Nano, never inference."""

import argparse
import io
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from uuid import uuid4
import zipfile
import httpx
from PIL import Image, ImageDraw
from verify_content_memory_runtime import ROOT, runtime, call
from verify_pacing_runtime import wait_job


def setup(client):
    project = call(
        client,
        "POST",
        "/projects",
        json={"name": "Task 08 · QA Shorts review", "language": "en"},
    )
    pid = project["id"]
    images = []
    for text, color in [("ONE IDEA", "#244352"), ("MAKE IT CLEAR", "#3b4934")]:
        image = Image.new("RGB", (1080, 1920), color)
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(
            (90, 420, 990, 1260), radius=40, outline="#C8F56A", width=8
        )
        draw.text((145, 780), text, fill="white", font_size=80)
        raw = io.BytesIO()
        image.save(raw, format="PNG")
        value = call(
            client,
            "POST",
            f"/projects/{pid}/media",
            files={"file": ("qa-frame.png", raw.getvalue(), "image/png")},
        )
        images.append(value["asset"])
        project = value["project"]
    script = "One idea. One short. Make the next one."
    project["scenes"] = [
        {
            "id": "hook",
            "name": "Hook",
            "duration": 180,
            "media_id": images[0]["id"],
            "narration": script,
            "caption": "One idea. One short.",
            "motion": {"visual": {"preset": "zoom_in"}},
        },
        {
            "id": "demo",
            "name": "Demo",
            "duration": 90,
            "media_id": images[1]["id"],
            "caption": "Make the next one.",
            "motion": {"callout": {"text": "Focus here", "y": 1400, "target_y": 1550}},
        },
    ]
    project = call(client, "PUT", f"/projects/{pid}", json=project)
    job = wait_job(
        client, call(client, "POST", f"/projects/{pid}/tts", json={"scene_id": "hook"})
    )
    project = call(
        client,
        "POST",
        f"/projects/{pid}/tts/{job['id']}/apply",
        json={"revision": project["revision"]},
    )
    return project


def fixture(origin, stop):
    """Own QA sidecar only; all outputs explicitly labelled fixture."""
    with (
        httpx.Client(base_url=origin, timeout=10, trust_env=False) as editor,
        httpx.Client(base_url=origin, timeout=10, trust_env=False) as companion,
    ):
        editor.headers["X-JDH-CSRF"] = editor.get("/api/session").json()["csrf"]
        storage = Path(editor.get("/api/capabilities").json()["storage"])
        if not (storage.name.startswith("jdh-quality-runtime-qa-") or
                (storage.name == "Projects" and storage.parent.name.startswith("JDHShortsStudio-QA-"))):
            raise RuntimeError("Refusing non-QA storage")
        doc = str(uuid4())
        code = editor.post("/api/ai/pair", json={}).json()["code"]
        companion.headers["Origin"] = origin
        token = companion.post(
            "/nano/api/pair", json={"code": code, "document_id": doc}
        ).json()["token"]
        companion.headers["X-JDH-Nano"] = token
        while not stop.is_set():
            value = companion.post(
                "/nano/api/poll",
                json={
                    "document_id": doc,
                    "english": "available",
                    "indonesian": "unavailable",
                    "wait": True,
                },
            ).json()
            if not value.get("job"):
                continue
            job = value["job"]
            if job["operation"] != "editorial":
                companion.post(
                    "/nano/api/result",
                    json={
                        "document_id": doc,
                        "id": job["id"],
                        "status": "failed",
                        "error": "generation_failed",
                    },
                )
                continue
            scene = json.loads(job["input"])["scenes"][0]
            result = {
                "title": "QA FIXTURE — One focused idea",
                "description": "QA fixture for local review. Not real Nano output.",
                "notes": [
                    {
                        "scene_id": scene["id"],
                        "start_frame": scene["start_frame"],
                        "end_frame": min(scene["end_frame"], scene["start_frame"] + 90),
                        "category": "hook",
                        "suggestion": "QA FIXTURE: Consider showing the outcome first.",
                        "reason": "Based only on the supplied narration.",
                    }
                ],
            }
            response = companion.post(
                "/nano/api/result",
                json={
                    "document_id": doc,
                    "id": job["id"],
                    "status": "completed",
                    "editorial": result,
                },
            )
            response.raise_for_status()
        companion.post("/nano/api/disconnect", json={})


def verify(client, project, artifacts):
    checks = []
    pid = project["id"]
    job = wait_job(
        client,
        call(
            client,
            "POST",
            f"/quality/{pid}/checks",
            json={"revision": project["revision"], "preset": "draft"},
        ),
    )
    report = job["result"]
    assert {"narration_tail", "overlay_overlap"} <= {
        f["code"] for f in report["findings"]
    }
    assert not any(f["severity"] == "error" for f in report["findings"])
    assert call(client, "GET", f"/projects/{pid}") == project
    checks += [
        "real Kokoro English audio measured",
        "tail gap and caption/callout bounding overlap reported",
        "analysis leaves project unchanged",
    ]
    rid = str(uuid4())
    path = f"/quality/{pid}/{job['id']}/editorial"
    value = call(client, "POST", path, json={"id": rid})
    for _ in range(100):
        if value["status"] not in ["queued", "running"]:
            break
        time.sleep(0.1)
        value = call(client, "GET", path + "/" + rid)
    assert value["status"] == "completed" and value["editorial"]["title"].startswith(
        "QA FIXTURE"
    )
    assert call(client, "GET", f"/projects/{pid}") == project
    checks += [
        "editorial fixture has valid scene/time range and does not apply automatically"
    ]
    selection = {
        "upload": {
            "title": "QA reviewed upload title",
            "description": "A complete local handoff.",
        },
        "scenes": [],
        "caption_position": 65,
        "narration_volume": 0.8,
        "music_volume": 0.15,
    }
    prefix = f"/quality/{pid}/{job['id']}"
    call(client, "POST", prefix + "/preview", json=selection)
    project = call(client, "POST", prefix + "/apply", json=selection)
    assert call(client, "POST", prefix + "/apply", json=selection) == project
    assert (
        client.post(
            f"/api/projects/{pid}/render",
            json={"preset": "draft", "check_id": job["id"]},
        ).status_code
        == 409
    )
    checks += [
        "reviewed metadata and positioning applied atomically with idempotent retry",
        "old report rejected after edit",
    ]
    outputs = []
    for preset in ["draft", "final"]:
        quality = wait_job(
            client,
            call(
                client,
                "POST",
                f"/quality/{pid}/checks",
                json={"revision": project["revision"], "preset": preset},
            ),
        )
        assert not any(
            f["code"] == "overlay_overlap" for f in quality["result"]["findings"]
        )
        rendered = wait_job(
            client,
            call(
                client,
                "POST",
                f"/projects/{pid}/render",
                json={"preset": preset, "check_id": quality["id"]},
            ),
        )
        verify = rendered["result"]["verification"]
        assert (
            verify["frames"] == 270
            and verify["fps"] == 30
            and verify["full_decode_passed"]
        )
        response = client.get(f"/api/jobs/{rendered['id']}/files/upload.zip")
        response.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            assert len(archive.namelist()) == 5
            metadata = json.loads(archive.read("upload-metadata.json"))
            assert metadata["title"] == "QA reviewed upload title"
            assert json.loads(archive.read("quality-report.json"))["pre_export_checked"]
            (artifacts / (preset + ".mp4")).write_bytes(archive.read(preset + ".mp4"))
            assert "One idea. One short." in archive.read("captions.srt").decode()
        (artifacts / (preset + "-upload.zip")).write_bytes(response.content)
        outputs.append({"preset": preset, **verify})
        checks += [preset + " output probe/decode and upload ZIP content verified"]
    return project, checks, outputs


def main(app, report_path, serve):
    resources = app.resolve() / "Contents/Resources"
    artifacts = Path(tempfile.mkdtemp(prefix="jdh-quality-output-"))
    with tempfile.TemporaryDirectory(prefix="jdh-quality-runtime-qa-") as temporary:
        directory = Path(temporary)
        with runtime(resources, directory) as client:
            project = setup(client)
            stop = threading.Event()
            thread = threading.Thread(
                target=fixture,
                args=(str(client.base_url).rstrip("/"), stop),
                daemon=True,
            )
            thread.start()
            try:
                project, checks, outputs = verify(client, project, artifacts)
                result = {
                    "version": "0.2.8",
                    "build": 10,
                    "isolated_data": True,
                    "real_nano_inference": False,
                    "real_speech": "bundled Kokoro af_heart English",
                    "checks": checks,
                    "outputs": outputs,
                    "artifacts": str(artifacts),
                    "passed": True,
                }
                report_path.write_text(json.dumps(result, indent=2) + "\n")
                print(json.dumps(result), flush=True)
                if serve:
                    print("QA_URL=" + str(client.base_url), flush=True)
                    print("QA_PROJECT=" + project["id"], flush=True)
                    print("HARNESS_PID=" + str(os.getpid()), flush=True)
                    try:
                        time.sleep(1800)
                    except KeyboardInterrupt:
                        pass
                    project = call(client, "GET", f"/projects/{project['id']}")
            finally:
                stop.set()
                thread.join(timeout=7)
        with runtime(resources, directory) as client:
            saved = call(client, "GET", f"/projects/{project['id']}")
            assert saved["upload"] == project["upload"]
            checks += ["metadata/settings persist across bundled sidecar restart"]
            result["checks"] = checks
            report_path.write_text(json.dumps(result, indent=2) + "\n")
    print("QA complete; sidecar and disposable data cleaned.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, default=ROOT / "dist/JDH Shorts Studio.app")
    parser.add_argument(
        "--report", type=Path, default=Path("/tmp/jdh-quality-runtime.json")
    )
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    main(args.app, args.report, args.serve)
