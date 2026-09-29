"""Real relocated render/cancel/restart with a labelled transport double for AI."""
import argparse
import io
import json
from pathlib import Path
import tempfile
import time
from uuid import uuid4
import zipfile

from verify_content_memory_runtime import runtime, call
from verify_pacing_runtime import wait_job
from verify_quality_runtime import setup


def main(app, report, artifacts):
    resources = app.resolve() / "Contents/Resources"
    artifacts.mkdir(parents=True, exist_ok=True)
    checks = []
    with tempfile.TemporaryDirectory(prefix="jdh-release-lifecycle-") as temporary:
        folder = Path(temporary)
        with runtime(resources, folder) as client:
            assert call(client, "GET", "/projects") == []
            assert not call(client, "GET", "/ai/status")["connected"]
            p = setup(client)
            p["name"] = "Task 09 · Imported legacy QA"
            p["caption_style"]["position"] = 65
            p = call(client, "PUT", f"/projects/{p['id']}", json=p)
            exported = wait_job(client, call(client, "POST", f"/projects/{p['id']}/render", json={"preset": "draft"}))
            package = client.get(f"/api/jobs/{exported['id']}/files/project.zip").content
            modified = io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(package)) as old, zipfile.ZipFile(modified, "w") as legacy:
                for name in old.namelist():
                    data = old.read(name)
                    if name == "project.json":
                        manifest = json.loads(data)
                        for key in ("upload", "quality_settings", "motion_mode"):
                            manifest.pop(key, None)
                        for scene in manifest["scenes"]:
                            scene.pop("motion", None)
                            scene.pop("planning", None)
                        data = json.dumps(manifest).encode()
                    legacy.writestr(name, data)
            package = modified.getvalue()
            (artifacts / "Task-09-legacy-project.zip").write_bytes(package)
            p = call(client, "POST", "/import-project", files={"file": ("legacy.zip", package, "application/zip")})
            pid = p["id"]
            assert p["upload"]["description"] == "" and p["quality_settings"]["caption_cps"] == 20
            assert p["scenes"][0]["motion"]["visual"]["preset"] == "none"
            checks += ["empty first run without companion", "real Kokoro/render with no Chrome connection",
                       "legacy project ZIP imports with additive defaults and media"]
            review = wait_job(client, call(client, "POST", f"/quality/{pid}/checks",
                json={"revision": p["revision"], "preset": "final"}))
            doc = str(uuid4())
            code = call(client, "POST", "/ai/pair", json={})["code"]
            headers = {"Origin": str(client.base_url).rstrip("/")}
            response = client.post("/nano/api/pair", json={"code": code, "document_id": doc}, headers=headers)
            response.raise_for_status()
            headers["X-JDH-Nano"] = response.json()["token"]

            def poll(availability):
                response = client.post("/nano/api/poll", headers=headers,
                    json={"document_id": doc, "english": availability, "indonesian": "unavailable"})
                response.raise_for_status()
                return response.json()

            poll("downloadable")
            assert call(client, "GET", "/ai/status")["availability"] == "downloadable"
            rejected = client.post("/api/ai/requests", json={"id": str(uuid4()), "operation": "hooks", "language": "en", "input": "QA"})
            assert rejected.status_code == 409
            checks.append("connected companion with missing model rejects inference")
            poll("available")
            rid = str(uuid4())
            endpoint = f"/quality/{pid}/{review['id']}/editorial"
            call(client, "POST", endpoint, json={"id": rid})
            assert poll("available")["job"]["operation"] == "editorial"
            job = call(client, "POST", f"/projects/{pid}/render", json={"preset": "final", "check_id": review["id"]})
            assert call(client, "GET", endpoint + "/" + rid)["status"] == "cancelled"
            measurements = []
            for _ in range(5):
                started = time.monotonic()
                assert call(client, "GET", f"/projects/{pid}") == p
                measurements.append(time.monotonic() - started)
            call(client, "POST", f"/jobs/{job['id']}/cancel", json={})
            for _ in range(100):
                cancelled = call(client, "GET", f"/jobs/{job['id']}")
                if cancelled["status"] not in ("running", "queued"):
                    break
                time.sleep(0.1)
            assert cancelled["status"] == "cancelled", cancelled
            assert cancelled["files"] == []
            assert not list((folder / "_jobs" / job["id"]).glob("*.mp4"))
            assert call(client, "GET", f"/projects/{pid}") == p
            checks += ["actual render cancels active editorial transport request",
                       "project reads respond during render", "render cancellation removes partial video and preserves project"]
            call(client, "POST", "/ai/disconnect", json={})
            assert not call(client, "GET", "/ai/status")["connected"]
            completed = wait_job(client, call(client, "POST", f"/projects/{pid}/render", json={"preset": "draft"}))
            assert completed["result"]["verification"]["frames"] == 270
            checks.append("render retry succeeds after cancellation and companion disconnect")
        with runtime(resources, folder) as client:
            assert call(client, "GET", f"/projects/{pid}") == p
            assert not call(client, "GET", "/ai/status")["connected"]
            checks.append("restart preserves migrated project and revokes AI pairing")
    result = {"passed": True, "real_nano_inference": False, "real_speech": True,
              "checks": checks, "project_read_max_ms": round(max(measurements)*1000, 2),
              "artifacts": str(artifacts)}
    report.write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--artifacts", required=True, type=Path)
    args = parser.parse_args()
    main(args.app, args.report, args.artifacts)
