"""Daily orchestration tests use a fake companion, never claim real Nano inference."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import sqlite3
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from backend import (
    daily_ideas,
    daily_ideas_store as store,
    nano,
    jobs,
    repository as repo,
)
from backend import content_memory as memory
from backend.app import app
from backend.content_memory_models import Catalog
from backend.models import NewProject

TZ = "Asia/Jakarta"


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(repo, "ROOT", tmp_path)
    monkeypatch.setattr(jobs, "JOB_DIR", tmp_path / "_jobs")
    monkeypatch.setattr(jobs, "JOBS", {})
    jobs.JOB_DIR.mkdir()
    now = [datetime(2026, 9, 23, 10, 0, tzinfo=timezone.utc)]
    service = daily_ideas.Service(clock=lambda: now[0])
    monkeypatch.setattr(daily_ideas, "service", service)
    broker = nano.Broker(clock=lambda: 100.0)
    monkeypatch.setattr(nano, "broker", broker)
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
            now=now,
            service=service,
            broker=broker,
            doc=doc,
            token=token,
            root=tmp_path,
        )


def call(env, method, path, **kwargs):
    response = env.client.request(method, "/api" + path, **kwargs)
    assert response.status_code == 200, response.text
    return response.json()


def status(env, tz=TZ):
    return call(env, "GET", "/ideas/status", params={"timezone": tz})


def preferences(env, **values):
    state = status(env)
    return call(
        env,
        "PUT",
        "/ideas/preferences",
        json={
            "timezone": TZ,
            "revision": state["settings_revision"],
            "preferences": {**state["preferences"], **values},
        },
    )


def selected(env):
    project = repo.create(
        NewProject(
            name="Counter tutorial",
            script="State updates a SwiftUI counter.",
            language="en",
        )
    )
    call(
        env,
        "POST",
        "/memory/references",
        json={"revision": memory.operate().revision, "project_ids": [project.id]},
    )
    return project


def start(env, automatic=False, rid=None, tz=TZ):
    return call(
        env,
        "POST",
        "/ideas/generate",
        json={"id": rid or str(uuid4()), "timezone": tz, "automatic": automatic},
    )


def dispatch(env):
    return env.broker.poll(
        env.token,
        nano.Poll(document_id=env.doc, english="available", indonesian="unavailable"),
    )["job"]


def ideas(sources):
    return [
        {
            "category": category,
            "title": f"QA fixture {category}",
            "hook": f"Try {category} next.",
            "concept": "A proposed short example.",
            "reason": "Fits the selected context.",
            "difference": "Adds a reset button.",
            "estimated_seconds": 30,
            "media_needs": ["New screen recording"],
            "source_project_ids": sources,
        }
        for category in ["series", "new_angle", "experiment"]
    ]


def finish(env, job, value=None, **kwargs):
    sources = [
        r["project_id"] for r in json.loads(job["input"])["history"]["references"]
    ]
    return env.client.post(
        "/nano/api/result",
        headers={"Origin": "http://testserver", "X-JDH-Nano": env.token},
        json={
            "document_id": env.doc,
            "id": job["id"],
            "status": "completed",
            "ideas": ideas(sources) if value is None else value,
            **kwargs,
        },
    )


def complete(env):
    assert start(env)["active_id"]
    job = dispatch(env)
    assert finish(env, job).status_code == 200
    return status(env)


def feedback(env, card, verdict="saved", reason="Useful follow-up"):
    return call(
        env,
        "PUT",
        f"/ideas/cards/{card['id']}/feedback",
        json={"timezone": TZ, "verdict": verdict, "reason": reason},
    )


def test_onboarding_no_fabricated_history_or_automatic_download(env):
    assert status(env)["onboarding"]
    assert not start(env, automatic=True)["active_id"]
    preferences(env, topic="SwiftUI basics", audience="New iOS developers")
    assert start(env, automatic=True)["active_id"]
    job = dispatch(env)
    context = json.loads(job["input"])
    assert context["history"]["references"] == []
    assert context["preferences"]["topic"] == "SwiftUI basics"
    assert finish(env, job).status_code == 200
    assert all(not c["source_project_ids"] for c in status(env)["batch"]["cards"])


def test_same_day_cache_restart_and_automatic_dedup(env, monkeypatch):
    selected(env)
    first = complete(env)
    env.now[0] += timedelta(hours=1)
    for _ in range(3):
        assert not start(env, automatic=True)["active_id"]
    monkeypatch.setattr(
        daily_ideas, "service", daily_ideas.Service(clock=lambda: env.now[0])
    )
    restored = status(env)
    assert restored["batch"] == first["batch"] and not restored["stale"]
    assert not restored["auto_due"]
    assert len(env.broker.jobs) == 1


def test_day_timezone_profile_language_and_manual_mode(env):
    selected(env)
    initial = complete(env)
    assert not status(env)["stale"]
    env.now[0] += timedelta(days=1)
    assert status(env)["auto_due"] and status(env)["stale"]
    shifted = status(env, "Pacific/Honolulu")
    assert shifted["timezone"] != initial["timezone"] and shifted["stale"]
    preferences(env, mode="manual")
    assert not status(env)["auto_due"]
    assert not start(env, automatic=True)["active_id"]
    catalog = memory.operate()
    call(
        env,
        "PUT",
        "/memory/profile",
        json={"revision": catalog.revision, "profile": {"themes": ["SwiftUI"]}},
    )
    assert status(env)["stale"]
    preferences(env, language="id")
    assert not status(env)["can_generate"] and status(env)["batch"] is None
    assert not start(env)["active_id"]
    preferences(env, language="en")
    assert status(env)["batch"] == initial["batch"]


def test_feedback_survives_new_batch_and_affects_context(env):
    project = selected(env)
    first = complete(env)
    card, skipped = first["batch"]["cards"][:2]
    saved = feedback(env, card)
    assert saved["stale"] and saved["feedback"][0]["verdict"] == "saved"
    feedback(env, skipped, "skipped", "Too similar")
    env.now[0] += timedelta(seconds=31)
    assert start(env)["active_id"]
    job = dispatch(env)
    context = json.loads(job["input"])
    assert [f["verdict"] for f in context["recent_feedback"]] == ["saved", "skipped"]
    assert context["history"]["references"][0]["project_id"] == project.id
    assert len(job["input"]) <= 12000
    assert finish(env, job).status_code == 200
    assert len(status(env)["feedback"]) == 2
    assert len(feedback(env, card, "none")["feedback"]) == 1


@pytest.mark.parametrize("operation", ["exclude", "forget", "source_change", "qa"])
def test_sources_invalidate_cache_saved_feedback_and_active_atomically(env, operation):
    project = selected(env)
    before = repo.load(project.id).model_dump()
    card = complete(env)["batch"]["cards"][0]
    feedback(env, card)
    env.now[0] += timedelta(seconds=31)
    active = start(env)["active_id"]
    dispatch(env)
    catalog = memory.operate()
    if operation == "forget":
        call(
            env,
            "POST",
            f"/memory/references/{project.id}/forget",
            json={"revision": catalog.revision},
        )
    elif operation == "source_change":
        project.script += " Now with reset."
        repo.save(project)
        memory.operate()
    else:
        call(
            env,
            "PUT",
            f"/memory/references/{project.id}",
            json={
                "revision": catalog.revision,
                "source_revision": project.revision,
                "included": operation != "exclude",
                "category": "qa" if operation == "qa" else "content",
                "published": False,
                "confirmed": {},
            },
        )
    # Check on-disk invalidation before querying daily status.
    with memory.transaction() as connection:
        stored = store.read(connection)
        assert not stored.batches and not stored.feedback and stored.active is None
    assert env.broker.read(active)["status"] == "cancelled"
    if operation != "source_change":
        assert repo.load(project.id).model_dump() == before
    assert (
        env.client.put(
            f"/api/ideas/cards/{card['id']}/feedback",
            json={"timezone": TZ, "verdict": "saved"},
        ).status_code
        == 404
    )


def test_cancel_and_late_response_and_cancel_before_post(env):
    selected(env)
    rid = start(env)["active_id"]
    job = dispatch(env)
    call(env, "POST", f"/ideas/requests/{rid}/cancel", params={"timezone": TZ}, json={})
    assert finish(env, job).status_code == 409
    assert status(env)["batch"] is None
    env.now[0] += timedelta(seconds=31)
    next_id = str(uuid4())
    call(
        env,
        "POST",
        f"/ideas/requests/{next_id}/cancel",
        params={"timezone": TZ},
        json={},
    )
    assert not start(env, rid=next_id)["active_id"]
    assert env.broker.read(next_id)["status"] == "cancelled"


def test_provider_failure_and_unavailable_keep_dated_cache(env):
    selected(env)
    first = complete(env)
    env.now[0] += timedelta(days=1)
    env.broker.disconnect()
    offline = start(env, automatic=True)
    assert not offline["active_id"] and offline["auto_due"]
    assert offline["batch"] == first["batch"] and offline["stale"]
    env.token = env.broker.pair(
        nano.Pair(code=env.broker.issue_pair()["code"], document_id=env.doc)
    )["token"]
    env.broker.poll(
        env.token,
        nano.Poll(document_id=env.doc, english="available", indonesian="unavailable"),
    )
    assert start(env, automatic=True)["active_id"]
    job = dispatch(env)
    assert (
        finish(env, job, status="failed", ideas=None, error="context_limit").status_code
        == 200
    )
    failed = status(env)
    assert (
        failed["batch"] == first["batch"]
        and not failed["active_id"]
        and not failed["auto_due"]
    )


@pytest.mark.parametrize(
    "fault",
    ["source", "duplicate", "category", "blank", "extra", "duration", "empty_sources"],
)
def test_reject_malformed_model_output(env, fault):
    project = selected(env)
    start(env)
    job = dispatch(env)
    value = ideas([project.id])
    if fault == "source":
        value[0]["source_project_ids"] = [uuid4().hex]
    if fault == "duplicate":
        value[1]["hook"] = value[0]["hook"]
    if fault == "category":
        value[1]["category"] = "series"
    if fault == "blank":
        value[0]["concept"] = "   "
    if fault == "extra":
        value[0]["views"] = 100000
    if fault == "duration":
        value[0]["estimated_seconds"] = 31
    if fault == "empty_sources":
        value[0]["source_project_ids"] = []
    assert finish(env, job, value).status_code == 422
    assert not status(env)["batch"] and not status(env)["active_id"]


def test_editor_lease_and_render_deferral(env):
    selected(env)
    rid = start(env)["active_id"]
    doc = str(uuid4())
    call(env, "POST", "/ideas/activity", json={"client_id": doc, "editing": True})
    assert env.broker.read(rid)["status"] == "cancelled"
    env.now[0] += timedelta(seconds=31)
    call(env, "POST", "/ideas/activity", json={"client_id": doc, "editing": True})
    assert not start(env)["active_id"]
    env.now[0] += timedelta(seconds=16)
    jobs.JOBS["render"] = SimpleNamespace(status="running")
    assert not start(env)["active_id"]
    jobs.JOBS.clear()
    assert start(env)["active_id"]
    env.service.defer()
    assert not status(env)["active_id"]


def test_restart_pending_context_changes_and_cooldowns(env, monkeypatch):
    selected(env)
    rid = start(env)["active_id"]
    assert start(env, rid=rid)["active_id"] == rid
    preferences(env, topic="A different focus")
    assert env.broker.read(rid)["status"] == "cancelled"
    assert not start(env)["active_id"]
    env.now[0] += timedelta(seconds=31)
    next_id = start(env)["active_id"]
    assert next_id and next_id != rid
    monkeypatch.setattr(
        daily_ideas, "service", daily_ideas.Service(clock=lambda: env.now[0])
    )
    assert not status(env)["active_id"]
    assert "dibuka ulang" in status(env)["message"]


def test_simultaneous_requests_only_enqueue_once(env):
    selected(env)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(lambda _: env.service.start(str(uuid4()), TZ, True), range(4))
        )
    assert len({result["active_id"] for result in results}) == 1
    assert len(env.broker.jobs) == 1


def test_v1_migration_is_additive_and_future_version_preserved(env):
    path = memory.database_path()
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE catalog (id INTEGER PRIMARY KEY, document TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO catalog VALUES (1, ?)",
            (Catalog(revision=7).model_dump_json(),),
        )
        connection.execute("PRAGMA user_version=1")
    assert status(env)["onboarding"]
    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 4
        assert (
            json.loads(
                connection.execute("SELECT document FROM catalog").fetchone()[0]
            )["revision"]
            == 7
        )
        connection.execute("PRAGMA user_version=99")
    before = path.read_bytes()
    assert (
        env.client.get("/api/ideas/status", params={"timezone": TZ}).status_code == 409
    )
    assert path.read_bytes() == before


def test_settings_conflict_security_budget_and_timezone_validation(env):
    preferences(env, topic="SwiftUI")
    assert (
        env.client.put(
            "/api/ideas/preferences",
            json={"revision": 0, "timezone": TZ, "preferences": {}},
        ).status_code
        == 409
    )
    assert (
        env.client.get(
            "/api/ideas/status", params={"timezone": "../../etc/passwd"}
        ).status_code
        == 422
    )
    assert (
        env.client.post(
            "/api/ideas/generate", headers={"X-JDH-CSRF": "bad"}, json={}
        ).status_code
        == 403
    )
    assert (
        env.client.post("/api/ideas/generate", content="x" * 65537).status_code == 413
    )
    assert (
        env.client.post(
            "/api/ai/requests",
            json={
                "id": str(uuid4()),
                "operation": "ideas",
                "language": "en",
                "input": "uncurated",
            },
        ).status_code
        == 422
    )
    schema = env.client.get("/nano/idea-schema.json").json()
    assert schema["properties"]["ideas"]["minItems"] == 3
    assert "$defs" not in json.dumps(schema)


def test_damaged_idea_storage_does_not_block_media_work(env, monkeypatch):
    from backend import render

    project = selected(env)
    rid = start(env)["active_id"]
    dispatch(env)
    with sqlite3.connect(memory.database_path()) as connection:
        connection.execute(
            "UPDATE daily_ideas SET document=?", ('{"schema_version":99}',)
        )
    monkeypatch.setattr(render, "issues", lambda project: [])
    monkeypatch.setattr(
        jobs, "submit", lambda pid, kind, action: {"kind": kind, "project_id": pid}
    )
    result = call(
        env, "POST", f"/projects/{project.id}/render", json={"preset": "draft"}
    )
    assert result["kind"] == "render"
    assert env.broker.read(rid)["status"] == "cancelled"
    assert (
        env.client.get("/api/ideas/status", params={"timezone": TZ}).status_code == 409
    )
