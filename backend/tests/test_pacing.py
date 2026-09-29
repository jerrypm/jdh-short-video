import math
import struct
import wave
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from backend import captions, pacing, repository as repo
from backend.app import app
from backend.models import Asset, CaptionStyle, NewProject, Scene


def audio_fixture(path, seconds=2.7, inverted=False):
    """Actual stereo PCM with leading, internal and trailing quiet regions."""
    rate = 16000
    with wave.open(str(path), "wb") as output:
        output.setparams((2, 2, rate, 0, "NONE", "not compressed"))
        data = bytearray()
        for i in range(round(seconds * rate)):
            t = i / rate
            active = 0.3 <= t < 1 or 1.6 <= t < 2.3
            sample = int(9000 * math.sin(2 * math.pi * 330 * t)) if active else 0
            data.extend(struct.pack("<hh", sample, -sample if inverted else sample))
        output.writeframes(data)


@pytest.fixture
def env(tmp_path, monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(repo, "ROOT", tmp_path)
    now = [100.0]
    monkeypatch.setattr(pacing, "service", pacing.Service(clock=lambda: now[0]))
    project = repo.create(NewProject(name="Pacing QA", language="en"))
    aid = uuid4().hex
    directory = repo.media_dir(project.id)
    directory.mkdir()
    path = directory / (aid + ".wav")
    audio_fixture(path)
    project.assets = [
        Asset(
            id=aid,
            file=path.name,
            name="Measured fixture",
            kind="audio",
            frames=81,
            has_audio=True,
        )
    ]
    project.scenes = [
        Scene(
            id="hook",
            name="Hook",
            duration=150,
            narration="Full audio.",
            audio_text="Full audio.",
            audio_id=aid,
            caption="One idea. One short.",
        ),
        Scene(id="end", name="End", duration=60, caption="Make the next one."),
    ]
    project = repo.save(project)
    with TestClient(app) as client:
        client.headers["X-JDH-CSRF"] = client.get("/api/session").json()["csrf"]
        yield SimpleNamespace(client=client, project=project, path=path, now=now)


def analyze(env):
    response = env.client.post(
        f"/api/pacing/{env.project.id}/analyze", json={"revision": env.project.revision}
    )
    assert response.status_code == 200, response.text
    return response.json()


def endpoint(env, proposal, action="preview"):
    return f"/api/pacing/{env.project.id}/{proposal['id']}/{action}"


def selection(duration=81, caption="One idea. One short."):
    return {"edits": [{"scene_id": "hook", "duration": duration, "caption": caption}]}


def test_pcm_silence_is_measured_without_stereo_cancellation(env):
    audio_fixture(env.path, inverted=True)
    result = pacing.measure(env.path, 0)
    assert result["frames"] == 81 and result["seconds"] == 2.7
    assert [
        (s["start_seconds"], s["end_seconds"], s["kind"]) for s in result["silences"]
    ] == [(0, 0.3, "leading"), (1, 1.6, "internal"), (2.3, 2.7, "trailing")]
    trimmed = pacing.measure(env.path, 9)
    assert trimmed["frames"] == 72
    assert trimmed["silences"][0]["start_seconds"] == 0.7


def test_analysis_preserves_creative_gap_and_never_mutates(env):
    before = repo.load(env.project.id)
    proposal = analyze(env)
    row = proposal["rows"][0]
    assert row["duration"] == 150 and row["minimum_frames"] == 81
    assert row["extra_gap_frames"] == 69
    assert proposal["rows"][1]["audio"] is None
    assert repo.load(before.id) == before


def test_partial_apply_backup_retry_and_undo_save(env):
    proposal = analyze(env)
    data = selection()
    preview = env.client.post(endpoint(env, proposal), json=data)
    assert preview.status_code == 200
    assert preview.json()["total_frames"] == 141
    before = repo.load(env.project.id)
    response = env.client.post(endpoint(env, proposal, "apply"), json=data)
    assert response.status_code == 200, response.text
    saved = repo.load(before.id)
    assert saved.scenes[0].duration == 81
    assert (
        saved.scenes[0].audio_in == 0
        and saved.scenes[0].audio_id == before.scenes[0].audio_id
    )
    assert saved.scenes[1] == before.scenes[1]
    backup = (repo.project_dir(before.id) / "project.backup.json").read_text()
    assert '"duration": 150' in backup
    assert (
        env.client.post(endpoint(env, proposal, "apply"), json=data).json()
        == response.json()
    )
    assert (
        env.client.post(
            endpoint(env, proposal, "apply"), json=selection(90)
        ).status_code
        == 409
    )
    before.revision = saved.revision
    assert (
        env.client.put(
            f"/api/projects/{before.id}", json=before.model_dump()
        ).status_code
        == 200
    )
    assert repo.load(before.id).scenes[0].duration == 150
    assert (
        env.client.post(endpoint(env, proposal, "apply"), json=data).status_code == 409
    )


@pytest.mark.parametrize(
    "data",
    [
        selection(80),
        selection(81, "word " * 70),
        {"edits": []},
        {"edits": [*selection()["edits"], *selection()["edits"]]},
        {"edits": [{"scene_id": "missing", "duration": 100, "caption": ""}]},
        {"edits": [{"scene_id": "hook", "duration": True, "caption": ""}]},
    ],
)
def test_reject_invalid_or_cutting_proposals(env, data):
    proposal = analyze(env)
    before = repo.load(env.project.id)
    assert (
        env.client.post(endpoint(env, proposal, "apply"), json=data).status_code == 422
    )
    assert repo.load(before.id) == before


@pytest.mark.parametrize("change", ["revision", "file", "expired"])
def test_stale_proposals_are_rejected(env, change):
    proposal = analyze(env)
    if change == "revision":
        repo.save(repo.load(env.project.id))
    elif change == "file":
        audio_fixture(env.path, seconds=3)
    else:
        env.now[0] += 901
    assert (
        env.client.post(endpoint(env, proposal, "apply"), json=selection()).status_code
        == 409
    )


def test_short_scene_extends_but_short_video_blocks_apply(env):
    project = env.project
    vid = uuid4().hex
    video = repo.media_dir(project.id) / (vid + ".mp4")
    video.write_bytes(b"visual metadata fixture")
    project.assets.append(
        Asset(id=vid, file=video.name, name="Short video", kind="video", frames=60)
    )
    project.scenes[0].duration = 60
    project.scenes[0].media_id = vid
    env.project = repo.save(project)
    proposal = analyze(env)
    assert proposal["rows"][0]["duration"] == 81
    assert (
        env.client.post(endpoint(env, proposal, "apply"), json=selection()).status_code
        == 422
    )


def test_missing_and_overlong_audio_remain_explicit(env):
    env.path.unlink()
    proposal = analyze(env)
    assert proposal["rows"][0]["errors"]
    assert (
        env.client.post(endpoint(env, proposal, "apply"), json=selection()).status_code
        == 422
    )
    audio_fixture(env.path, seconds=60.1)
    with pytest.raises(ValueError, match="60 detik"):
        pacing.measure(env.path, 0)


def test_readability_layout_manual_break_and_srt_match(env):
    style = CaptionStyle()
    text = "One local idea becomes a short video that you can share today."
    result = captions.layout(text, style, 30)
    assert len(result["lines"]) == 2 and max(result["widths"]) <= 850
    assert result["warnings"] and not result["errors"]
    assert " ".join(result["lines"]) == text
    assert (
        captions.layout("My line\nMy second line", style)["text"]
        == "My line\nMy second line"
    )
    env.project.scenes[0].caption = text
    output = captions.srt(env.project)
    assert result["text"] in output
    assert "00:00:05,000 --> 00:00:07,000" in output
    env.project.caption_style.enabled = False
    assert captions.srt(env.project) == ""


def test_auth_csrf_body_limits_and_worker_guard(env):
    path = f"/api/pacing/{env.project.id}/analyze"
    assert (
        env.client.post(
            path, json={"revision": 0}, headers={"X-JDH-CSRF": "bad"}
        ).status_code
        == 403
    )
    assert env.client.post(path, content=b"x" * 65537).status_code == 413
    assert env.client.post(path, json={"revision": 999}).status_code == 409
    with pacing.service.worker:
        assert (
            env.client.post(path, json={"revision": env.project.revision}).status_code
            == 409
        )


def test_failed_atomic_apply_keeps_original_and_allows_retry(env, monkeypatch):
    proposal = analyze(env)
    before = repo.load(env.project.id)
    atomic = repo.atomic_json

    def fail_manifest(path, value):
        if path.name == "project.json":
            raise OSError("QA simulated disk failure")
        atomic(path, value)

    monkeypatch.setattr(repo, "atomic_json", fail_manifest)
    with pytest.raises(OSError, match="disk failure"):
        pacing.service.apply(
            before.id, proposal["id"], pacing.Selection.model_validate(selection())
        )
    assert repo.load(before.id) == before
    monkeypatch.setattr(repo, "atomic_json", atomic)
    result = pacing.service.apply(
        before.id, proposal["id"], pacing.Selection.model_validate(selection())
    )
    assert result.scenes[0].duration == 81


def test_total_project_limit_and_whole_silence(env):
    project = env.project
    project.scenes = [
        Scene(id=str(i), name=f"Scene {i}", duration=90) for i in range(60)
    ]
    env.project = repo.save(project)
    proposal = analyze(env)
    data = {"edits": [{"scene_id": "0", "duration": 91, "caption": ""}]}
    assert (
        env.client.post(endpoint(env, proposal, "apply"), json=data).status_code == 422
    )
    with wave.open(str(env.path), "wb") as output:
        output.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        output.writeframes(b"\0\0" * 16000)
    result = pacing.measure(env.path, 0)
    assert result["frames"] == 30 and result["silences"][0]["kind"] == "entire"
