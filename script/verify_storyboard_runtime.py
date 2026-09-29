"""Bundled-runtime storyboard QA with labelled transport fixtures and real PNG/WAV files."""

import argparse
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import wave
from uuid import uuid4
from PIL import Image
from verify_content_memory_runtime import ROOT, runtime, call


def main(app, report):
    checks = []
    resources = app.resolve() / "Contents/Resources"
    with tempfile.TemporaryDirectory(prefix="jdh-storyboard-qa-") as temporary:
        directory = Path(temporary)
        with runtime(resources, directory) as client:
            source = call(
                client,
                "POST",
                "/projects",
                json={
                    "name": "Source counter lesson",
                    "script": "A counter uses State.",
                    "language": "en",
                },
            )
            project = call(
                client,
                "POST",
                "/projects",
                json={
                    "name": "Storyboard QA destination",
                    "script": "QA original narration.",
                    "language": "en",
                },
            )
            pid = project["id"]
            picture = io.BytesIO()
            Image.new("RGB", (64, 64), "#748b59").save(picture, format="PNG")
            visual = call(
                client,
                "POST",
                f"/projects/{pid}/media",
                files={"file": ("qa.png", picture.getvalue(), "image/png")},
            )["asset"]
            sound = io.BytesIO()
            with wave.open(sound, "wb") as output:
                output.setnchannels(1)
                output.setsampwidth(2)
                output.setframerate(24000)
                output.writeframes(b"\0\0" * 48000)
            audio = call(
                client,
                "POST",
                f"/projects/{pid}/media",
                files={"file": ("qa.wav", sound.getvalue(), "audio/wav")},
            )["asset"]
            assert audio["frames"] >= 60
            project = call(client, "GET", f"/projects/{pid}")
            narration = "QA original narration. Show a reset button."
            project["scenes"] = [
                {
                    "id": "original",
                    "name": "Original",
                    "narration": narration,
                    "caption": "Original",
                    "duration": 150,
                    "audio_id": audio["id"],
                    "audio_text": narration,
                    "media_id": visual["id"],
                }
            ]
            original = call(client, "PUT", f"/projects/{pid}", json=project)
            hashes = {
                item["id"]: hashlib.sha256(
                    client.get(f"/api/projects/{pid}/media/{item['id']}").content
                ).hexdigest()
                for item in [visual, audio]
            }
            catalog = call(client, "GET", "/memory")["catalog"]
            call(
                client,
                "POST",
                "/memory/references",
                json={"revision": catalog["revision"], "project_ids": [source["id"]]},
            )
            doc = str(uuid4())
            code = call(client, "POST", "/ai/pair", json={})["code"]
            headers = {"Origin": str(client.base_url).rstrip("/")}
            paired = client.post(
                "/nano/api/pair",
                headers=headers,
                json={"code": code, "document_id": doc},
            )
            paired.raise_for_status()
            headers["X-JDH-Nano"] = paired.json()["token"]

            def poll():
                response = client.post(
                    "/nano/api/poll",
                    headers=headers,
                    json={
                        "document_id": doc,
                        "english": "available",
                        "indonesian": "unavailable",
                    },
                )
                response.raise_for_status()
                return response.json()

            def finish(rid, key, value):
                response = client.post(
                    "/nano/api/result",
                    headers=headers,
                    json={
                        "document_id": doc,
                        "id": rid,
                        "status": "completed",
                        key: value,
                    },
                )
                response.raise_for_status()

            poll()
            rid = str(uuid4())
            call(
                client,
                "POST",
                "/ideas/generate",
                json={"id": rid, "timezone": "Asia/Jakarta", "automatic": False},
            )
            assert poll()["job"]["operation"] == "ideas"
            ideas = [
                {
                    "category": category,
                    "title": f"QA FIXTURE {category}",
                    "hook": "Show a reset: " + category + ".",
                    "concept": "A fixture counter lesson.",
                    "reason": "Tests local reference transport.",
                    "difference": "Adds reset.",
                    "estimated_seconds": 30,
                    "media_needs": ["Screen image"],
                    "source_project_ids": [source["id"]],
                }
                for category in ["series", "new_angle", "experiment"]
            ]
            finish(rid, "ideas", ideas)
            card = call(
                client, "GET", "/ideas/status", params={"timezone": "Asia/Jakarta"}
            )["batch"]["cards"][0]
            assert any(
                i["card"]["id"] == card["id"]
                for i in call(client, "GET", "/storyboards/ideas")
            )
            rid = str(uuid4())
            prefix = f"/storyboards/{pid}/requests/{rid}"
            call(
                client,
                "POST",
                f"/storyboards/{pid}/requests",
                json={
                    "id": rid,
                    "idea_id": card["id"],
                    "base_revision": original["revision"],
                },
            )
            job = poll()["job"]
            assert job["operation"] == "storyboard" and len(job["input"]) <= 12000
            context = json.loads(job["input"])
            assert context["audio_transcripts"][audio["id"]] == [narration]
            draft = {
                "hook": "QA original narration.",
                "scenes": [
                    {
                        "name": "QA FIXTURE scene",
                        "narration": narration,
                        "caption": "Reset counter",
                        "estimated_frames": 30,
                        "visual_need": "Counter image",
                        "media_id": visual["id"],
                        "media_status": "available",
                        "audio_id": audio["id"],
                        "effect": "static",
                        "motion_intent": "Keep the button centered.",
                        "source_project_ids": [source["id"]],
                    }
                ],
            }
            finish(rid, "storyboard", draft)
            proposal = call(client, "GET", prefix)
            assert (
                proposal["status"] == "completed"
                and proposal["base_revision"] == original["revision"]
            )
            assert call(client, "GET", f"/projects/{pid}") == original
            checks += [
                "real imported PNG and measured WAV",
                "daily idea to storyboard",
                "bounded local context",
                "generation preserves project",
            ]
            body = {"draft": draft, "selected": [0], "mode": "append"}
            review = call(client, "POST", prefix + "/preview", json=body)
            assert (
                review["plan"][0]["frames"] == audio["frames"]
                and review["missing_media"] == 0
            )
            bad = copy.deepcopy(body)
            bad["draft"]["scenes"][0]["effect"] = "zoom"
            assert client.post("/api" + prefix + "/apply", json=bad).status_code == 422
            applied = call(client, "POST", prefix + "/apply", json=body)
            assert applied["scenes"][-1]["duration"] == audio["frames"]
            assert (
                applied["scenes"][-1]["audio_in"] == 0
                and applied["scenes"][0] == original["scenes"][0]
            )
            assert applied["scenes"][-1]["planning"]["provider"] == "gemini-nano-local"
            assert call(client, "POST", prefix + "/apply", json=body) == applied
            backup = json.loads((directory / pid / "project.backup.json").read_text())
            assert backup == original
            checks += [
                "review uses measured audio minimum",
                "unsupported animation rejected",
                "atomic append and planning provenance",
                "idempotent apply",
                "previous project backup",
            ]
            undo = copy.deepcopy(original)
            undo["revision"] = applied["revision"]
            restored = call(client, "PUT", f"/projects/{pid}", json=undo)
            assert (
                restored["scenes"] == original["scenes"]
                and restored["script"] == original["script"]
            )
            assert client.post("/api" + prefix + "/apply", json=body).status_code == 409
            for aid, digest in hashes.items():
                assert (
                    hashlib.sha256(
                        client.get(f"/api/projects/{pid}/media/{aid}").content
                    ).hexdigest()
                    == digest
                )
            checks += [
                "undo through normal revision-checked project save",
                "reapply after undo rejected",
                "media bytes preserved",
            ]
        with runtime(resources, directory) as client:
            persisted = call(client, "GET", f"/projects/{pid}")
            assert persisted["scenes"] == original["scenes"]
            assert client.get("/api" + prefix).status_code == 404
            checks += [
                "project survives sidecar restart",
                "expired session cannot replay proposal",
                "clean EOF shutdown",
            ]
    result = {
        "app": str(app),
        "version": "0.2.5",
        "isolated_data": True,
        "real_nano_inference": False,
        "fixture_label": "QA FIXTURE",
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
        "--report", type=Path, default=ROOT / "docs/qa/storyboard-runtime.json"
    )
    args = parser.parse_args()
    main(args.app, args.report)
