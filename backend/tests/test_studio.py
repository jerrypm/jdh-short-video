import io
import math
import wave
from uuid import uuid4
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from backend import repository as repo, jobs, media, render
from backend.app import app
from backend.models import Project, Scene, CaptionStyle


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(repo, "ROOT", tmp_path)
    monkeypatch.setattr(jobs, "JOB_DIR", tmp_path / "_jobs")
    (tmp_path / "_jobs").mkdir()
    with TestClient(app) as client:
        token = client.get("/api/session").json()["csrf"]
        client.headers["X-JDH-CSRF"] = token
        yield client


def new_project(client):
    response = client.post(
        "/api/projects",
        json={"name": "Test project", "script": "One short. Three scenes."},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_session_origin_and_csrf(client):
    assert (
        client.get(
            "/api/projects", headers={"origin": "https://example.org"}
        ).status_code
        == 403
    )
    assert (
        client.get("/api/projects", headers={"host": "evil.example:8741"}).status_code
        == 403
    )
    assert (
        client.post(
            "/api/projects", json={"name": "Wrong"}, headers={"X-JDH-CSRF": "bad"}
        ).status_code
        == 403
    )
    client.cookies.clear()
    assert client.get("/api/projects").status_code == 401


def test_atomic_save_revision_and_asset_ownership(client):
    p = new_project(client)
    original = dict(p)
    p["name"] = "Updated"
    saved = client.put("/api/projects/" + p["id"], json=p)
    assert saved.status_code == 200
    assert saved.json()["revision"] == 1
    assert client.put("/api/projects/" + p["id"], json=original).status_code == 409
    assert client.get("/api/projects/" + p["id"]).json()["name"] == "Updated"
    assert (repo.project_dir(p["id"]) / "project.backup.json").exists()


def test_media_validation_and_symlink_escape(client, tmp_path):
    p = new_project(client)
    bad = client.post(
        "/api/projects/" + p["id"] + "/media",
        files={"file": ("bad.png", b"not an image", "image/png")},
    )
    assert bad.status_code in (400, 422)
    with pytest.raises(ValueError):
        repo.project_dir("../escape")
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("private")
    (tmp_path / "escape").symlink_to(outside)
    with pytest.raises(ValueError):
        repo.contained(tmp_path, "escape")


def test_caption_overflow_blocks_preflight(client):
    p = new_project(client)
    p["scenes"] = [{**Scene(id="scene1").model_dump(), "caption": "long word " * 100}]
    assert client.put("/api/projects/" + p["id"], json=p).status_code == 422
    preview = client.post(
        "/api/caption-preview",
        json={
            "text": "a moderately long caption " * 14,
            "style": CaptionStyle().model_dump(),
        },
    )
    assert preview.status_code == 422


def test_real_render_and_portable_roundtrip(client):
    p = new_project(client)
    images = []
    for color in ["#243747", "#465c3c", "#4f3554"]:
        buffer = io.BytesIO()
        Image.new("RGB", (360, 640), color).save(buffer, format="PNG")
        result = client.post(
            "/api/projects/" + p["id"] + "/media",
            files={"file": ("frame.png", buffer.getvalue(), "image/png")},
        )
        assert result.status_code == 200, result.text
        images.append(result.json()["asset"])
        p = result.json()["project"]
    audio = io.BytesIO()
    import struct

    with wave.open(audio, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(
            b"".join(
                struct.pack("<h", int(math.sin(i / 24000 * math.tau * 440) * 4000))
                for i in range(24000)
            )
        )
    result = client.post(
        "/api/projects/" + p["id"] + "/media",
        files={"file": ("test-tone.wav", audio.getvalue(), "audio/wav")},
    )
    assert result.status_code == 200, result.text
    a = result.json()["asset"]
    p = result.json()["project"]
    assert any(a["peaks"])
    p["scenes"] = [
        Scene(
            id=f"scene{i}",
            name=f"Scene {i + 1}",
            duration=30,
            media_id=im["id"],
            audio_id=a["id"],
            caption=f"Test scene {i + 1}",
        ).model_dump()
        for i, im in enumerate(images)
    ]
    p = client.put("/api/projects/" + p["id"], json=p).json()
    assert client.get("/api/projects/" + p["id"] + "/preflight").json()["issues"] == []
    project = Project.model_validate(p)
    job = jobs.Job(p["id"], "render")
    render.render(project, "draft", job)
    out = job.directory / "draft.mp4"
    info = media.probe(out)
    assert abs(float(info["format"]["duration"]) - 3) < 0.15
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (360, 640)
    assert set(job.files) == {
        "draft.mp4",
        "narration.wav",
        "captions.srt",
        "project.json",
        "project.zip",
        "upload.zip",
        "upload-metadata.json",
        "upload-notes.txt",
        "quality-report.json",
    }
    package = (job.directory / "project.zip").read_bytes()
    imported = client.post(
        "/api/import-project",
        files={"file": ("project.zip", package, "application/zip")},
    )
    assert imported.status_code == 200, imported.text
    restored = imported.json()
    assert restored["id"] != p["id"]
    assert len(restored["assets"]) == 4
    assert (
        client.get("/api/projects/" + restored["id"] + "/preflight").json()["issues"]
        == []
    )


def test_restart_recovery(client):
    job = jobs.Job(uuid4().hex, "render")
    job.status = "running"
    job.persist()
    result = jobs.read(job.id)
    assert result["status"] == "failed"
    assert "Layanan berhenti" in result["message"]


def test_missing_kokoro_model_keeps_manual_project_available(client, tmp_path, monkeypatch):
    from backend import tts

    monkeypatch.setattr(tts, "MODEL_DIR", tmp_path / "missing-model")
    p = new_project(client)
    p["scenes"] = [Scene(id="manual", narration="Keep this script.").model_dump()]
    p = client.put("/api/projects/" + p["id"], json=p).json()
    assert client.get("/api/capabilities").json()["tts"]["available"] is False
    response = client.post(f"/api/projects/{p['id']}/tts", json={"scene_id": "manual"})
    assert response.status_code == 422
    assert "Narasi impor tetap tersedia" in response.json()["detail"]
    assert client.get("/api/projects/" + p["id"]).json() == p


def test_low_disk_rejects_render_before_starting_encoder(client, monkeypatch):
    from types import SimpleNamespace

    p = new_project(client)
    image = io.BytesIO()
    Image.new("RGB", (20, 30), "green").save(image, format="PNG")
    imported = client.post(f"/api/projects/{p['id']}/media",
        files={"file": ("qa.png", image.getvalue(), "image/png")}).json()
    p = imported["project"]
    p["scenes"] = [Scene(id="valid", duration=30, media_id=imported["asset"]["id"]).model_dump()]
    p = client.put("/api/projects/" + p["id"], json=p).json()
    monkeypatch.setattr(render.shutil, "disk_usage", lambda _: SimpleNamespace(free=499 * 1024**2))
    job = jobs.Job(p["id"], "render")
    monkeypatch.setattr(job, "process", lambda *_a, **_k: pytest.fail("Encoder must not start"))
    with pytest.raises(ValueError, match="Ruang disk tidak cukup"):
        render.render(Project.model_validate(p), "final", job)
    assert not (job.directory / "final.mp4").exists()
    assert client.get("/api/projects/" + p["id"]).json() == p


def test_disk_full_atomic_save_preserves_previous_manifest(client, monkeypatch):
    import errno

    p = new_project(client)
    path = repo.project_dir(p["id"]) / "project.json"
    previous = path.read_bytes()
    original = repo.json.dump

    def full_disk(value, stream, **kwargs):
        if path.name in str(stream.name) and "backup" not in str(stream.name):
            stream.write('{"incomplete":')
            raise OSError(errno.ENOSPC, "QA simulated full disk")
        return original(value, stream, **kwargs)

    monkeypatch.setattr(repo.json, "dump", full_disk)
    changed = Project.model_validate(p)
    changed.name = "Pending unsaved edit"
    with pytest.raises(OSError) as failure:
        repo.save(changed, expected=p["revision"])
    assert failure.value.errno == errno.ENOSPC
    assert path.read_bytes() == previous
    assert repo.load(p["id"]).name == p["name"]
    assert not list(path.parent.glob(".*.tmp"))


def test_cancel_stops_process_and_removes_partial_output(client):
    import sys
    import time

    def action(job):
        (job.directory / "partial.mp4").write_bytes(b"incomplete")
        job.process([sys.executable, "-c", "import time; time.sleep(30)"])

    info = jobs.submit(uuid4().hex, "render", action)
    job = jobs.JOBS[info["id"]]
    deadline = time.monotonic() + 3
    while not (job.directory / "partial.mp4").exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    client.post(f"/api/jobs/{job.id}/cancel", json={})
    while job.status in {"queued", "running"} and time.monotonic() < deadline:
        time.sleep(0.02)
    assert job.status == "cancelled"
    assert not (job.directory / "partial.mp4").exists()


def test_tts_apply_is_explicit_and_checks_current_script(client):
    p = new_project(client)
    p["scenes"] = [Scene(id="s1", narration="Reviewed text").model_dump()]
    p = client.put("/api/projects/" + p["id"], json=p).json()
    job = jobs.Job(p["id"], "tts")
    with wave.open(str(job.directory / "narration.wav"), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(bytes(24000 * 2))
    asset = media.inspect_media(job.directory / "narration.wav", "Test audio.wav")
    job.result = {
        "asset": asset.model_dump(),
        "scene_id": "s1",
        "text": "Stale text",
        "frames": 30,
    }
    job.status = "completed"
    job.files = ["narration.wav"]
    job.persist()
    url = f"/api/projects/{p['id']}/tts/{job.id}/apply"
    assert client.post(url, json={"revision": p["revision"]}).status_code == 422
    assert client.get("/api/projects/" + p["id"]).json()["assets"] == []
    job.result["text"] = "Reviewed text"
    job.persist()
    result = client.post(url, json={"revision": p["revision"]})
    assert result.status_code == 200, result.text
    assert result.json()["scenes"][0]["audio_id"] == asset.id
    assert client.post(url, json={"revision": p["revision"]}).status_code == 409


def test_desktop_health_requires_private_launcher_token(client, monkeypatch):
    from backend import app as app_module

    monkeypatch.setattr(app_module, "DESKTOP_TOKEN", "local-launch-token")
    assert client.get("/api/desktop/health").status_code == 403
    assert (
        client.get(
            "/api/desktop/health", headers={"X-JDH-Desktop": "wrong"}
        ).status_code
        == 403
    )
    response = client.get(
        "/api/desktop/health", headers={"X-JDH-Desktop": "local-launch-token"}
    )
    assert response.status_code == 200
    assert response.json()["ready"] is True
