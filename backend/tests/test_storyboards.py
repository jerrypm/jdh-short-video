"""Structured fixture output, not real Nano inference."""

import copy
import json
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from backend import (
    nano,
    repository as repo,
    jobs,
    content_memory as memory,
    daily_ideas_store as ideas,
    storyboards,
)
from backend.app import app
from backend.models import NewProject, Asset, Scene


@pytest.fixture
def env(tmp_path, monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr(repo, "ROOT", tmp_path)
    monkeypatch.setattr(jobs, "JOB_DIR", tmp_path / "_jobs")
    monkeypatch.setattr(jobs, "JOBS", {})
    jobs.JOB_DIR.mkdir()
    broker = nano.Broker(clock=lambda: 100)
    monkeypatch.setattr(nano, "broker", broker)
    now = [100.0]
    service = storyboards.Service(clock=lambda: now[0])
    monkeypatch.setattr(storyboards, "service", service)
    project = repo.create(
        NewProject(
            name="Storyboard destination", script="Existing script.", language="en"
        )
    )
    project.scenes = [Scene(id="old", narration="Existing script.", duration=150)]
    project = repo.save(project)
    source = repo.create(
        NewProject(name="Source lesson", script="A counter uses State.", language="en")
    )
    from backend.content_memory_models import AddReferences

    catalog = memory.add_references(AddReferences(revision=0, project_ids=[source.id]))
    card = ideas.Card(
        id=uuid4().hex,
        category="series",
        title="QA idea: reset a counter",
        hook="Try a reset.",
        concept="Show reset state.",
        reason="A follow-up.",
        difference="Adds reset.",
        estimated_seconds=30,
        media_needs=["Counter screenshot"],
        source_project_ids=[source.id],
    )
    with memory.transaction() as connection:
        state = ideas.read(connection)
        state.batches = [
            ideas.Batch(
                id=str(uuid4()),
                key="qa",
                date="2026-09-24",
                timezone="Asia/Jakarta",
                language="en",
                created_at="2026-09-24T00:00:00+00:00",
                sources={source.id: source.revision},
                cards=[
                    card.model_copy(
                        update={"id": uuid4().hex, "category": "new_angle"}
                    ),
                    card.model_copy(
                        update={"id": uuid4().hex, "category": "experiment"}
                    ),
                    card,
                ],
            )
        ]
        ideas.write(connection, state)
    doc = str(uuid4())
    token = broker.pair(nano.Pair(code=broker.issue_pair()["code"], document_id=doc))[
        "token"
    ]
    broker.poll(
        token, nano.Poll(document_id=doc, english="available", indonesian="unavailable")
    )
    with TestClient(app) as client:
        client.headers["X-JDH-CSRF"] = client.get("/api/session").json()["csrf"]
        yield SimpleNamespace(
            client=client,
            broker=broker,
            service=service,
            project=project,
            source=source,
            catalog=catalog,
            card=card,
            token=token,
            doc=doc,
            now=now,
            root=tmp_path,
            monkeypatch=monkeypatch,
        )


def call(env, method, path, **kwargs):
    response = env.client.request(method, "/api" + path, **kwargs)
    assert response.status_code == 200, response.text
    return response.json()


def path(env, rid, suffix=""):
    return f"/storyboards/{env.project.id}/requests/{rid}{suffix}"


def test_motion_proposal_review_apply_and_unknown_filter_rejection(env):
    value = draft(env)
    value["scenes"][0]["motion"] = {
        "version": 1,
        "visual": {"preset": "zoom_in", "amount": 0.06},
        "caption": {"preset": "fade"},
        "callout": {"text": "Reset here"},
    }
    rid, value = complete(env, value)
    body = {"draft": value, "selected": [0], "mode": "append"}
    call(env, "POST", path(env, rid, "/preview"), json=body)
    invalid = copy.deepcopy(body)
    invalid["draft"]["scenes"][0]["motion"]["visual"]["filter"] = "movie=/tmp/private"
    assert (
        env.client.post("/api" + path(env, rid, "/apply"), json=invalid).status_code
        == 422
    )
    applied = call(env, "POST", path(env, rid, "/apply"), json=body)
    scene = applied["scenes"][-1]
    assert scene["motion"]["visual"]["preset"] == "zoom_in"
    assert scene["motion"]["callout"]["text"] == "Reset here"
    assert scene["duration"] == 150 and scene["audio_in"] == 0


def start(env, rid=None):
    data = {
        "id": rid or str(uuid4()),
        "idea_id": env.card.id,
        "base_revision": repo.load(env.project.id).revision,
    }
    return call(env, "POST", f"/storyboards/{env.project.id}/requests", json=data)


def draft(env):
    return {
        "hook": "Try a reset.",
        "scenes": [
            {
                "name": "Hook",
                "narration": "Try a reset. Show the initial counter.",
                "caption": "A reset button",
                "estimated_frames": 150,
                "visual_need": "Counter screenshot",
                "media_id": None,
                "media_status": "missing",
                "audio_id": None,
                "effect": "static",
                "motion_intent": "Keep the counter centered.",
                "source_project_ids": [env.source.id],
            },
            {
                "name": "Demo",
                "narration": "Tap reset to restore zero.",
                "caption": "Reset to zero",
                "estimated_frames": 180,
                "visual_need": "Counter screen recording",
                "media_id": None,
                "media_status": "missing",
                "audio_id": None,
                "effect": "static",
                "motion_intent": "Keep the button visible.",
                "source_project_ids": [env.source.id],
            },
        ],
    }


def finish(env, rid, value):
    env.broker.poll(
        env.token,
        nano.Poll(document_id=env.doc, english="available", indonesian="unavailable"),
    )
    return env.client.post(
        "/nano/api/result",
        headers={"Origin": "http://testserver", "X-JDH-Nano": env.token},
        json={
            "document_id": env.doc,
            "id": rid,
            "status": "completed",
            "storyboard": value,
        },
    )


def complete(env, value=None):
    rid = start(env)["id"]
    value = value or draft(env)
    result = finish(env, rid, value)
    assert result.status_code == 200, result.text
    proposal = call(env, "GET", path(env, rid))
    assert proposal["status"] == "completed"
    return rid, value


def selection(value, **updates):
    return {
        "draft": value,
        "selected": list(range(len(value["scenes"]))),
        "mode": "append",
        **updates,
    }


def asset(env, kind="image", frames=0, transcript=None):
    project = repo.load(env.project.id)
    aid = uuid4().hex
    item = Asset(
        id=aid,
        name="QA media",
        file=aid + {"image": ".png", "video": ".mp4", "audio": ".wav"}[kind],
        kind=kind,
        frames=frames,
        has_audio=kind == "audio",
    )
    project.assets.append(item)
    repo.media_dir(project.id).mkdir(exist_ok=True)
    repo.asset_path(project, aid).write_bytes(b"fixture transport only")
    if transcript:
        project.scenes.append(
            Scene(
                id="audio-scene",
                narration=transcript,
                audio_id=aid,
                audio_text=transcript,
                duration=max(9, frames),
            )
        )
    repo.save(project)
    return aid


def test_generate_has_no_side_effect_and_apply_partial_review_undo_roundtrip(env):
    before = repo.load(env.project.id).model_dump()
    rid, value = complete(env)
    assert repo.load(env.project.id).model_dump() == before
    value["scenes"][1]["narration"] = "User-edited reset demonstration."
    body = selection(value, selected=[1])
    summary = call(env, "POST", path(env, rid, "/preview"), json=body)
    assert summary["added_scenes"] == 1 and summary["removed_scenes"] == 0
    assert summary["total_frames"] == 330
    applied = call(env, "POST", path(env, rid, "/apply"), json=body)
    assert applied["scenes"][0] == before["scenes"][0]
    assert applied["script"] == "Existing script.\n\nUser-edited reset demonstration."
    assert applied["scenes"][-1]["planning"]["source_revisions"] == {
        env.source.id: env.source.revision
    }
    assert (
        call(env, "POST", path(env, rid, "/apply"), json=body) == applied
    )  # Uncertain response retry.
    assert (
        json.loads(
            (repo.project_dir(env.project.id) / "project.backup.json").read_text()
        )
        == before
    )
    undo = copy.deepcopy(before)
    undo["revision"] = applied["revision"]
    restored = call(env, "PUT", f"/projects/{env.project.id}", json=undo)
    assert (
        restored["script"] == before["script"]
        and restored["scenes"] == before["scenes"]
    )
    assert (
        env.client.post("/api" + path(env, rid, "/apply"), json=body).status_code == 409
    )


def test_replace_is_explicit_and_keeps_assets_and_other_settings(env):
    aid = asset(env)
    before = repo.load(env.project.id)
    rid, value = complete(env)
    value["scenes"][0].update(media_id=aid, media_status="available")
    body = selection(value, mode="replace")
    summary = call(env, "POST", path(env, rid, "/preview"), json=body)
    assert summary["removed_scenes"] == len(before.scenes)
    applied = call(env, "POST", path(env, rid, "/apply"), json=body)
    assert len(applied["scenes"]) == 2 and not applied["script"].startswith("Existing")
    assert applied["assets"] == [a.model_dump() for a in before.assets]
    assert applied["caption_style"] == before.caption_style.model_dump()
    assert repo.asset_path(before, aid).is_file()


@pytest.mark.parametrize(
    "fault",
    [
        "asset",
        "negative",
        "fractional",
        "effect",
        "source",
        "status",
        "total",
        "audio",
        "hook",
        "extra",
    ],
)
def test_json_semantic_validation_does_not_touch_original_project(env, fault):
    before = repo.load(env.project.id).model_dump()
    rid = start(env)["id"]
    value = draft(env)
    scene = value["scenes"][0]
    if fault == "asset":
        scene.update(media_id=uuid4().hex, media_status="available")
    if fault == "negative":
        scene["estimated_frames"] = -30
    if fault == "fractional":
        scene["estimated_frames"] = 30.5
    if fault == "effect":
        scene["effect"] = "zoom"
    if fault == "source":
        scene["source_project_ids"] = [uuid4().hex]
    if fault == "status":
        scene["media_status"] = "available"
    if fault == "total":
        value["scenes"] = [copy.deepcopy(scene) for _ in range(4)]
        for item in value["scenes"]:
            item["estimated_frames"] = 1800
    if fault == "audio":
        scene["audio_id"] = uuid4().hex
    if fault == "hook":
        value["hook"] = "A different hook"
    if fault == "extra":
        scene["filter"] = "arbitrary executable filter"
    assert finish(env, rid, value).status_code == 422
    assert call(env, "GET", path(env, rid))["status"] == "failed"
    assert repo.load(env.project.id).model_dump() == before


@pytest.mark.parametrize(
    "change", ["project", "source", "exclude", "forget", "profile", "media"]
)
def test_concurrent_changes_reject_preview_and_apply(env, change):
    aid = asset(env)
    rid, value = complete(env)
    body = selection(value)
    call(env, "POST", path(env, rid, "/preview"), json=body)
    if change == "project":
        project = repo.load(env.project.id)
        project.name = "Concurrent edit"
        repo.save(project)
    elif change == "source":
        source = repo.load(env.source.id)
        source.script += " Changed."
        repo.save(source)
    elif change == "media":
        repo.asset_path(repo.load(env.project.id), aid).unlink()
    elif change == "forget":
        memory.forget_reference(env.source.id, memory.operate().revision)
    else:

        def mutate(catalog):
            if change == "exclude":
                catalog.references[0].included = False
            else:
                catalog.profile.name = "Changed channel"

        memory.operate(action=mutate)
    before = repo.load(env.project.id).model_dump()
    assert (
        env.client.post("/api" + path(env, rid, "/apply"), json=body).status_code == 409
    )
    assert repo.load(env.project.id).model_dump() == before
    assert call(env, "GET", path(env, rid))["draft"] is None


def test_measured_audio_extends_estimate_and_rejects_short_visual_or_changed_text(env):
    text = draft(env)["scenes"][0]["narration"]
    aid = asset(env, "audio", 420, text)
    video = asset(env, "video", 180)
    image = asset(env)
    value = draft(env)
    value["scenes"][0]["audio_id"] = aid
    rid, value = complete(env, value)
    body = selection(value, selected=[0], mode="replace")
    preview = call(env, "POST", path(env, rid, "/preview"), json=body)
    assert preview["total_frames"] == 420
    invalid = copy.deepcopy(body)
    invalid["draft"]["scenes"][0].update(media_id=video, media_status="available")
    assert (
        env.client.post("/api" + path(env, rid, "/apply"), json=invalid).status_code
        == 422
    )
    invalid = copy.deepcopy(body)
    invalid["draft"]["scenes"][0]["narration"] += " More words."
    assert (
        env.client.post("/api" + path(env, rid, "/apply"), json=invalid).status_code
        == 422
    )
    body["draft"]["scenes"][0].update(media_id=image, media_status="available")
    applied = call(env, "POST", path(env, rid, "/apply"), json=body)
    assert (
        applied["scenes"][0]["duration"] == 420
        and applied["scenes"][0]["audio_in"] == 0
    )


def test_partial_and_combined_limits_revalidated_at_apply(env):
    project = repo.load(env.project.id)
    project.scenes = [Scene(id=f"scene{i}", duration=1750) for i in range(3)]
    repo.save(project)
    rid, value = complete(env)
    body = selection(value)
    assert (
        env.client.post("/api" + path(env, rid, "/preview"), json=body).status_code
        == 422
    )
    body["selected"] = [99]
    assert (
        env.client.post("/api" + path(env, rid, "/apply"), json=body).status_code == 422
    )
    body["selected"] = [0, 0]
    assert (
        env.client.post("/api" + path(env, rid, "/apply"), json=body).status_code == 422
    )
    body["selected"] = [0]
    assert (
        call(env, "POST", path(env, rid, "/apply"), json=body)["scenes"][-1]["duration"]
        == 150
    )


def test_atomic_write_failure_preserves_original(env):
    rid, value = complete(env)
    before = (repo.project_dir(env.project.id) / "project.json").read_bytes()
    original = repo.atomic_json

    def fail_manifest(path, data):
        if path.name == "project.json":
            raise RuntimeError("Disk write failed")
        original(path, data)

    env.monkeypatch.setattr(repo, "atomic_json", fail_manifest)
    assert (
        env.client.post(
            "/api" + path(env, rid, "/apply"), json=selection(value)
        ).status_code
        == 409
    )
    assert (repo.project_dir(env.project.id) / "project.json").read_bytes() == before


def test_cancel_replay_expiry_and_restart(env):
    rid = start(env)["id"]
    assert start(env, rid)["id"] == rid and len(env.broker.jobs) == 1
    call(env, "POST", path(env, rid, "/cancel"), json={})
    assert finish(env, rid, draft(env)).status_code == 409
    before = str(uuid4())
    call(env, "POST", path(env, before, "/cancel"), json={})
    assert start(env, before)["status"] == "cancelled"
    env.now[0] += 901
    assert env.client.get("/api" + path(env, rid)).status_code == 404
    rid, value = complete(env)
    env.monkeypatch.setattr(storyboards, "service", storyboards.Service())
    assert (
        env.client.post(
            "/api" + path(env, rid, "/apply"), json=selection(value)
        ).status_code
        == 404
    )


def test_generation_failure_render_deferral_and_security(env):
    from types import SimpleNamespace

    jobs.JOBS["render"] = SimpleNamespace(status="running")
    response = env.client.post(
        f"/api/storyboards/{env.project.id}/requests",
        json={
            "id": str(uuid4()),
            "idea_id": env.card.id,
            "base_revision": env.project.revision,
        },
    )
    assert response.status_code == 409
    jobs.JOBS.clear()
    rid = start(env)["id"]
    env.service.defer()
    assert call(env, "GET", path(env, rid))["status"] == "cancelled"
    env.broker.disconnect()
    assert (
        env.client.post(
            f"/api/storyboards/{env.project.id}/requests",
            json={
                "id": str(uuid4()),
                "idea_id": env.card.id,
                "base_revision": env.project.revision,
            },
        ).status_code
        == 409
    )
    assert (
        env.client.post(
            f"/api/storyboards/{env.project.id}/requests",
            headers={"X-JDH-CSRF": "bad"},
            json={},
        ).status_code
        == 403
    )
    assert (
        env.client.post(
            f"/api/storyboards/{env.project.id}/requests", content="x" * 65537
        ).status_code
        == 413
    )
    assert (
        env.client.post(
            "/api/ai/requests",
            json={
                "id": str(uuid4()),
                "operation": "storyboard",
                "input": "uncurated",
                "language": "en",
            },
        ).status_code
        == 422
    )
    schema = env.client.get("/nano/storyboard-schema.json").json()
    assert "$ref" not in json.dumps(schema)


def test_context_is_bounded_and_omits_paths(env):
    for _ in range(23):
        asset(env)
    rid = start(env)["id"]
    raw = env.broker.jobs[rid]["input"]
    context = json.loads(raw)
    assert len(raw) <= 12000 and len(context["assets"]) == 20
    assert str(env.root) not in raw and '"file"' not in raw
    assert context["capabilities"]["effects"] == ["static"]
