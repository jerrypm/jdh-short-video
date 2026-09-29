"""Task 08 uses real local PCM/FFmpeg fixtures; Nano responses below are fixtures."""

from array import array
import io
import json
import math
import time
import wave
import zipfile
from uuid import uuid4
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from backend import jobs, nano, quality, quality_audio, repository as repo
from backend.app import app
from backend.models import NewProject, Scene, Asset, Project
from backend.quality_contract import QualitySettings, validate_editorial


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(repo, "ROOT", tmp_path)
    monkeypatch.setattr(jobs, "JOB_DIR", tmp_path / "_jobs")
    monkeypatch.setattr(jobs, "JOBS", {})
    jobs.JOB_DIR.mkdir()
    now = [100.0]
    monkeypatch.setattr(quality, "service", quality.Service(clock=lambda: now[0]))
    monkeypatch.setattr(nano, "broker", nano.Broker(clock=lambda: 100))
    project = repo.create(NewProject(name="Task 08 QA", language="en"))
    directory = repo.media_dir(project.id)
    directory.mkdir()
    visual, audio = uuid4().hex, uuid4().hex
    Image.new("RGB", (360, 640), "#2b4562").save(directory / (visual + ".png"))
    with wave.open(str(directory / (audio + ".wav")), "wb") as wav:
        wav.setparams((1, 2, 48000, 0, "NONE", "not compressed"))
        wav.writeframes(
            array(
                "h",
                [
                    round(30000 * math.sin(2 * math.pi * 440 * i / 48000))
                    if i < 48000
                    else 0
                    for i in range(144000)
                ],
            ).tobytes()
        )
    project.assets = [
        Asset(
            id=visual,
            file=visual + ".png",
            name="Owned QA.png",
            kind="image",
            width=360,
            height=640,
        ),
        Asset(
            id=audio,
            file=audio + ".wav",
            name="QA tone.wav",
            kind="audio",
            has_audio=True,
            frames=90,
        ),
    ]
    project.scenes = [
        Scene(
            id="hook",
            name="Hook",
            duration=120,
            media_id=visual,
            audio_id=audio,
            narration="One idea.",
            audio_text="One idea.",
            caption="One idea.",
        )
    ]
    project = repo.save(project)
    with TestClient(app) as client:
        client.headers["X-JDH-CSRF"] = client.get("/api/session").json()["csrf"]
        yield SimpleNamespace(client=client, project=project, now=now, root=tmp_path)
    for job in list(jobs.JOBS.values()):
        if job.status in {"queued", "running"}:
            job.cancelled.set()
            for _ in range(500):
                if job.status not in {"queued", "running"}:
                    break
                time.sleep(0.01)


def wait(env, response):
    assert response.status_code == 200, response.text
    job = response.json()
    for _ in range(2000):
        if job["status"] not in ["queued", "running"]:
            break
        time.sleep(0.01)
        job = env.client.get("/api/jobs/" + job["id"]).json()
    assert job["status"] == "completed", job
    return job


def check(env, preset="draft"):
    p = repo.load(env.project.id)
    return wait(
        env,
        env.client.post(
            f"/api/quality/{p.id}/checks",
            json={"revision": p.revision, "preset": preset},
        ),
    )["result"]


def selection(env, **updates):
    p = repo.load(env.project.id)
    return {
        "upload": {"title": "Reviewed title", "description": "A local draft."},
        "scenes": [],
        "caption_position": p.caption_style.position,
        "narration_volume": p.narration_volume,
        "music_volume": p.music_volume,
        **updates,
    }


def endpoint(env, report, action):
    return f"/api/quality/{env.project.id}/{report['id']}/{action}"


def test_defaults_pcm_stereo_peaks_silence_and_thresholds(tmp_path):
    p = Project(id="a" * 32, name="Legacy")
    assert p.upload.title == "" and p.quality_settings.long_silence_seconds == 1.5
    path = tmp_path / "stereo.f32"
    path.write_bytes(array("f", [1.1, -1.1] * 480 + [0.0] * 48000 * 2 * 2).tobytes())
    result = quality_audio.metrics(path, QualitySettings())
    assert result["peak_dbfs"] > 0 and result["at_full_scale_samples"] == 960
    assert result["long_silences"] == [[0.01, 2.01]]
    assert not quality_audio.metrics(path, QualitySettings(long_silence_seconds=3))[
        "long_silences"
    ]


def test_scan_measures_and_never_mutates_project(env):
    before = repo.load(env.project.id)
    report = check(env)
    assert repo.load(before.id) == before
    assert report["rows"][0]["minimum_frames"] == 90
    assert (
        report["output"]["frames"] == 120 and report["output"]["verified_file"] is False
    )
    assert report["rows"][0]["audio"]["long_silences"] == [[1.0, 3.0]]
    assert {"narration_silence", "mix_silence"} <= {
        f["code"] for f in report["findings"]
    }
    assert all(f["start_frame"] <= f["end_frame"] <= 120 for f in report["findings"])


def test_missing_media_cut_narration_caption_and_overlap(env):
    p = repo.load(env.project.id)
    p.scenes[0].duration = 30
    p.scenes[0].motion.callout = __import__(
        "backend.motion", fromlist=["Callout"]
    ).Callout(text="Pointer", target_y=1550)
    p.caption_style.position = 80
    repo.save(p, expected=p.revision)
    report = check(env)
    codes = {f["code"] for f in report["findings"]}
    assert "narration_cut" in codes and "overlay_overlap" in codes
    p = repo.load(p.id)
    p.scenes[0].caption = "one two three " * 28
    repo.save(p, expected=p.revision)
    assert "caption_layout" in {f["code"] for f in check(env)["findings"]}
    repo.asset_path(p, p.scenes[0].media_id).unlink()
    assert "missing_media" in {f["code"] for f in check(env)["findings"]}


def test_overlay_checks_follow_animation_and_can_ignore_disabled_caption(env):
    p = repo.load(env.project.id)
    p.caption_style.position = 90
    from backend.motion import TextMotion

    p.scenes[0].motion.caption = TextMotion(preset="slide_up")
    repo.save(p, expected=p.revision)
    assert "caption_safe_area" in {f["code"] for f in check(env)["findings"]}
    p = repo.load(p.id)
    p.caption_style.enabled = False
    repo.save(p, expected=p.revision)
    assert not any(f["code"].startswith("caption") for f in check(env)["findings"])


def test_review_apply_backup_retry_and_changed_review(env):
    report = check(env)
    data = selection(
        env, scenes=[{"scene_id": "hook", "duration": 90, "caption": "Full audio."}]
    )
    assert env.client.post(endpoint(env, report, "apply"), json=data).status_code == 409
    assert (
        env.client.post(endpoint(env, report, "preview"), json=data).status_code == 200
    )
    changed = {**data, "caption_position": 60}
    assert (
        env.client.post(endpoint(env, report, "apply"), json=changed).status_code == 409
    )
    result = env.client.post(endpoint(env, report, "apply"), json=data)
    assert result.status_code == 200, result.text
    saved = repo.load(env.project.id)
    assert saved.scenes[0].duration == 90 and saved.upload.title == "Reviewed title"
    assert (
        '"duration": 120'
        in (repo.project_dir(saved.id) / "project.backup.json").read_text()
    )
    assert (
        env.client.post(endpoint(env, report, "apply"), json=data).json()
        == result.json()
    )
    assert (
        env.client.post(
            f"/api/projects/{saved.id}/render",
            json={"preset": "draft", "check_id": report["id"]},
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "edit",
    [
        {"scene_id": "hook", "duration": 89, "caption": "Cut"},
        {"scene_id": "unknown", "duration": 120, "caption": ""},
        {"scene_id": "hook", "duration": True, "caption": ""},
        {"scene_id": "hook", "duration": 120, "caption": "x" * 300},
    ],
)
def test_invalid_edits_do_not_write(env, edit):
    report = check(env)
    before = repo.load(env.project.id)
    assert (
        env.client.post(
            endpoint(env, report, "preview"), json=selection(env, scenes=[edit])
        ).status_code
        == 422
    )
    assert repo.load(before.id) == before


@pytest.mark.parametrize("change", ["revision", "media", "expiry", "restart"])
def test_stale_reports_are_rejected(env, change, monkeypatch):
    report = check(env)
    if change == "revision":
        p = repo.load(env.project.id)
        p.name = "Changed"
        repo.save(p, expected=p.revision)
    elif change == "media":
        path = repo.asset_path(env.project, env.project.scenes[0].audio_id)
        path.write_bytes(path.read_bytes() + b"changed")
    elif change == "expiry":
        env.now[0] += 901
    else:
        monkeypatch.setattr(quality, "service", quality.Service())
    assert (
        env.client.post(
            endpoint(env, report, "preview"), json=selection(env)
        ).status_code
        == 409
    )


def test_source_gain_music_mix_and_upload_package(env):
    p = repo.load(env.project.id)
    p.music_id = p.scenes[0].audio_id
    p.music_volume = 1
    p.upload.title = "Manual metadata"
    p.upload.description = "User description."
    repo.save(p, expected=p.revision)
    report = check(env)
    assert report["mix"]["peak_dbfs"] > 0
    assert "mix_peak" in {f["code"] for f in report["findings"]}
    job = wait(
        env,
        env.client.post(
            f"/api/projects/{p.id}/render",
            json={"preset": "draft", "check_id": report["id"]},
        ),
    )
    output = env.client.get(f"/api/jobs/{job['id']}/files/upload.zip")
    with zipfile.ZipFile(io.BytesIO(output.content)) as z:
        assert set(z.namelist()) == {
            "draft.mp4",
            "captions.srt",
            "upload-metadata.json",
            "quality-report.json",
            "upload-notes.txt",
        }
        metadata = json.loads(z.read("upload-metadata.json"))
        assert (
            metadata["title"] == "Manual metadata"
            and metadata["description"] == "User description."
        )
        assert (
            metadata["verification"]["frames"] == 120
            and metadata["verification"]["full_decode_passed"]
        )
        assert json.loads(z.read("quality-report.json"))["pre_export_checked"]
        assert z.read("draft.mp4")


def pair():
    broker = nano.broker
    doc = str(uuid4())
    token = broker.pair(nano.Pair(code=broker.issue_pair()["code"], document_id=doc))[
        "token"
    ]
    poll = nano.Poll(document_id=doc, english="available", indonesian="unavailable")
    broker.poll(token, poll)
    return broker, doc, token, poll


def test_editorial_is_text_only_validated_and_never_auto_applies(env):
    report = check(env)
    before = repo.load(env.project.id)
    broker, doc, token, poll = pair()
    rid = str(uuid4())
    response = env.client.post(endpoint(env, report, "editorial"), json={"id": rid})
    assert response.status_code == 200, response.text
    dispatch = broker.poll(token, poll)["job"]
    context = json.loads(dispatch["input"])
    assert context["analysis_basis"] == "text_and_user_visual_intent_only"
    assert "assets" not in context and "file" not in context["scenes"][0]
    result = {
        "title": "QA FIXTURE title",
        "description": "QA fixture only",
        "notes": [
            {
                "scene_id": "hook",
                "start_frame": 0,
                "end_frame": 30,
                "category": "hook",
                "suggestion": "Consider a shorter opening.",
                "reason": "Focuses on the stated idea.",
            }
        ],
    }
    broker.finish(
        token,
        nano.Finish(id=rid, document_id=doc, status="completed", editorial=result),
    )
    value = env.client.get(endpoint(env, report, "editorial") + "/" + rid).json()
    assert value["editorial"] == result and repo.load(before.id) == before
    result["notes"][0]["end_frame"] = 121
    with pytest.raises(ValueError):
        validate_editorial(result, context)
    result["notes"][0]["end_frame"] = 30
    result["score"] = 99
    with pytest.raises(ValueError):
        validate_editorial(result, context)


def test_editorial_languages_cancel_and_cross_operation_payload(env):
    report = check(env)
    broker, doc, token, poll = pair()
    rid = str(uuid4())
    env.client.post(endpoint(env, report, "editorial"), json={"id": rid})
    broker.poll(token, poll)
    with pytest.raises(__import__("fastapi").HTTPException):
        broker.finish(
            token,
            nano.Finish(
                id=rid,
                document_id=doc,
                status="completed",
                suggestions=["Wrong operation"],
            ),
        )
    rid = str(uuid4())
    env.client.post(endpoint(env, report, "editorial") + "/" + rid + "/cancel", json={})
    assert (
        env.client.post(endpoint(env, report, "editorial"), json={"id": rid}).json()[
            "status"
        ]
        == "cancelled"
    )
    p = repo.load(env.project.id)
    p.language = "id"
    repo.save(p, expected=p.revision)
    report = check(env)
    assert (
        env.client.post(
            endpoint(env, report, "editorial"), json={"id": str(uuid4())}
        ).status_code
        == 422
    )
    assert (
        env.client.post(
            "/api/ai/requests",
            json={
                "id": str(uuid4()),
                "operation": "editorial",
                "language": "en",
                "input": "bypass",
            },
        ).status_code
        == 422
    )


def test_bounded_security_and_settings(env):
    path = f"/api/quality/{env.project.id}/checks"
    assert env.client.post(path, content="x" * 65537).status_code == 413
    assert (
        env.client.post(
            path,
            json={"revision": env.project.revision},
            headers={"X-JDH-CSRF": "wrong"},
        ).status_code
        == 403
    )
    assert (
        env.client.post(
            path,
            json={"revision": env.project.revision},
            headers={"Origin": "https://external.example"},
        ).status_code
        == 403
    )
    with pytest.raises(ValueError):
        QualitySettings(silence_dbfs=float("nan"))


def test_failed_atomic_apply_is_retryable(env, monkeypatch):
    from backend.quality_contract import Selection

    report = check(env)
    data = selection(env)
    env.client.post(endpoint(env, report, "preview"), json=data)
    original = repo.atomic_json
    before = repo.load(env.project.id)

    def fail(path, value):
        if path.name == "project.json":
            raise OSError("QA write failure")
        original(path, value)

    monkeypatch.setattr(repo, "atomic_json", fail)
    with pytest.raises(OSError):
        quality.service.apply(before.id, report["id"], Selection.model_validate(data))
    assert repo.load(before.id) == before
    monkeypatch.setattr(repo, "atomic_json", original)
    assert env.client.post(endpoint(env, report, "apply"), json=data).status_code == 200


def test_cancelled_report_and_wrong_preset_cannot_export(env):
    report = check(env)
    assert (
        env.client.post(
            f"/api/projects/{env.project.id}/render",
            json={"preset": "final", "check_id": report["id"]},
        ).status_code
        == 409
    )
    jobs.JOBS[report["id"]].status = "cancelled"
    assert (
        env.client.post(
            endpoint(env, report, "preview"), json=selection(env)
        ).status_code
        == 409
    )
