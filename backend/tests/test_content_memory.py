import json
import os
import sqlite3
import subprocess
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from backend import repository as repo, jobs, content_memory as memory
from backend.app import app
from backend.models import NewProject, Scene
from backend.content_memory_models import Catalog, AIProposal


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(repo, "ROOT", tmp_path)
    monkeypatch.setattr(jobs, "JOB_DIR", tmp_path / "_jobs")
    jobs.JOB_DIR.mkdir()
    with TestClient(app) as client:
        client.headers["X-JDH-CSRF"] = client.get("/api/session").json()["csrf"]
        yield client


def project(name="Counter tutorial", script="State updates a counter.", language="en"):
    return repo.create(NewProject(name=name, script=script, language=language))


def catalog(client):
    response = client.get("/api/memory")
    assert response.status_code == 200, response.text
    return response.json()["catalog"]


def add(client, *projects):
    response = client.post(
        "/api/memory/references",
        json={
            "revision": catalog(client)["revision"],
            "project_ids": [p.id for p in projects],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["catalog"]


def update(client, pid, **changes):
    current = catalog(client)
    ref = next(ref for ref in current["references"] if ref["project_id"] == pid)
    values = {
        key: ref[key] for key in ("included", "category", "published", "confirmed")
    }
    values.update(changes)
    response = client.put(
        "/api/memory/references/" + pid,
        json={
            "revision": current["revision"],
            "source_revision": ref["observed"]["source_revision"],
            **values,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["catalog"]


def retrieve(client, **values):
    response = client.post("/api/memory/retrieve", json=values)
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_legacy_projects_and_explicit_opt_in(client):
    selected = project()
    secret = project("Unselected", "This private draft must not enter the catalog.")
    # An old schema-v1 manifest with default fields omitted remains readable.
    path = repo.project_dir(selected.id) / "project.json"
    path.write_text(
        json.dumps({"id": selected.id, "name": "Old project", "script": "Old script"})
    )
    empty = catalog(client)
    assert empty["revision"] == 0 and empty["references"] == []
    assert retrieve(client)["references"] == []
    saved = add(client, selected)
    assert saved["references"][0]["observed"]["excerpt"] == "Old script"
    assert secret.script not in json.dumps(saved)
    assert saved["references"][0]["suggested"] is None


def test_revision_refresh_keeps_user_labels_and_rejects_stale_forms(client):
    p = project()
    current = add(client, p)
    labels = {"themes": ["SwiftUI"], "summary": "User summary", "series": "Basics"}
    current = update(client, p.id, confirmed=labels)
    previous_revision = current["revision"]
    p.script = "A new explanation of State."
    p.scenes = [Scene(id="s1", duration=210)]
    repo.save(p, expected=p.revision)
    # A form opened before the source changed is refused, even before an explicit refresh.
    stale = client.put(
        "/api/memory/references/" + p.id,
        json={
            "revision": previous_revision,
            "source_revision": 0,
            "included": True,
            "category": "content",
            "published": False,
            "confirmed": labels,
        },
    )
    assert stale.status_code == 409
    current = catalog(client)
    ref = current["references"][0]
    assert current["revision"] > previous_revision
    assert ref["observed"]["source_revision"] == p.revision
    assert ref["observed"]["duration_frames"] == 210
    assert ref["observed"]["excerpt"] == p.script
    assert ref["confirmed"]["summary"] == "User summary"
    assert (
        client.put(
            "/api/memory/profile", json={"revision": previous_revision, "profile": {}}
        ).status_code
        == 409
    )
    assert (
        catalog(client)["revision"] == current["revision"]
    )  # Reading unchanged data is stable.


def test_qa_duplicates_exclusions_and_missing_sources(client):
    first = project()
    duplicate = project("Imported copy")
    qa = project("QA — scratch", "A separate test script")
    other = project("Other", "Another content idea")
    refs = add(client, first, duplicate, qa, other)["references"]
    assert [ref["category"] for ref in refs] == [
        "content",
        "duplicate",
        "qa",
        "content",
    ]
    update(client, other.id, included=False)
    # Even if both duplicates are manually marked content, retrieval deduplicates them.
    update(client, duplicate.id, included=True, category="content")
    found = retrieve(client)["references"]
    assert len(found) == 1 and found[0]["project_id"] in {first.id, duplicate.id}
    repo.contained(repo.project_dir(first.id), "project.json").unlink()
    state = catalog(client)
    assert next(ref for ref in state["references"] if ref["project_id"] == first.id)[
        "missing"
    ]
    assert [r["project_id"] for r in retrieve(client)["references"]] == [duplicate.id]


def test_export_is_measured_but_publication_requires_confirmation(client):
    p = project()
    jid = uuid4().hex
    folder = jobs.JOB_DIR / jid
    folder.mkdir()
    receipt = {
        "project_id": p.id,
        "kind": "render",
        "status": "running",
        "files": ["short.mp4"],
        "result": {"revision": p.revision},
    }
    repo.atomic_json(folder / "job.json", receipt)
    add(client, p)
    assert retrieve(client)["references"][0]["status"] == "draft"
    receipt["status"] = "completed"
    repo.atomic_json(folder / "job.json", receipt)
    result = retrieve(client)["references"][0]
    assert (
        result["status"] == "exported" and result["status_origin"] == "render_receipt"
    )
    assert not catalog(client)["references"][0]["published"]
    update(client, p.id, published=True)
    result = retrieve(client)["references"][0]
    assert result["status"] == "published" and result["status_origin"] == "user"


def test_forget_removes_feedback_and_context_without_touching_project_or_media(client):
    p = project()
    directory = repo.media_dir(p.id)
    directory.mkdir()
    marker = directory / "owned-media.txt"
    marker.write_text("Original media stays here")
    manifest = (repo.project_dir(p.id) / "project.json").read_bytes()
    current = add(client, p)
    feedback = client.post(
        f"/api/memory/references/{p.id}/feedback",
        json={
            "revision": current["revision"],
            "idea": "Add a reset button",
            "verdict": "skipped",
            "reason": "Already covered",
        },
    )
    assert feedback.status_code == 200
    assert retrieve(client)["references"][0]["feedback"][0]["verdict"] == "skipped"
    revision = catalog(client)["revision"]
    assert (
        client.post(
            f"/api/memory/references/{p.id}/forget", json={"revision": revision}
        ).status_code
        == 200
    )
    assert retrieve(client)["references"] == []
    assert catalog(client)["revision"] > revision
    assert (repo.project_dir(p.id) / "project.json").read_bytes() == manifest
    assert marker.read_text() == "Original media stays here"
    # A new connection cannot restore forgotten labels/feedback from a stale in-memory cache.
    assert memory.operate().references == []
    assert add(client, p)["references"][0]["feedback"] == []


def test_restart_reads_persisted_profile_labels_and_feedback(client):
    p = project()
    current = add(client, p)
    response = client.put(
        "/api/memory/profile",
        json={
            "revision": current["revision"],
            "profile": {"name": "JRDEVHUB", "themes": ["SwiftUI"]},
        },
    )
    assert response.status_code == 200
    update(
        client,
        p.id,
        confirmed={"series": "Build one thing", "audience": "iOS developers"},
    )
    assert (
        client.post(
            f"/api/memory/references/{p.id}/feedback",
            json={
                "revision": catalog(client)["revision"],
                "idea": "Add a reset button",
                "verdict": "saved",
            },
        ).status_code
        == 200
    )
    env = {**os.environ, "JDH_DATA_DIR": str(repo.ROOT)}
    output = subprocess.check_output(
        [
            __import__("sys").executable,
            "-c",
            "from backend.content_memory import operate; print(operate().model_dump_json())",
        ],
        env=env,
        text=True,
    )
    restored = json.loads(output)
    assert restored["profile"]["name"] == "JRDEVHUB"
    assert restored["references"][0]["confirmed"]["series"] == "Build one thing"
    assert restored["references"][0]["feedback"][0]["idea"] == "Add a reset button"


def test_write_failure_rolls_back_catalog_and_failed_forget(client):
    p = project()
    before = add(client, p)
    with sqlite3.connect(memory.database_path()) as connection:
        connection.execute(
            "CREATE TRIGGER fail_write BEFORE UPDATE ON catalog BEGIN SELECT RAISE(ABORT, 'simulated disk failure'); END"
        )
    response = client.post(
        f"/api/memory/references/{p.id}/forget", json={"revision": before["revision"]}
    )
    assert response.status_code == 409
    assert "tidak dapat" in response.json()["detail"]
    assert catalog(client) == before
    with sqlite3.connect(memory.database_path()) as connection:
        connection.execute("DROP TRIGGER fail_write")
    assert (
        client.post(
            f"/api/memory/references/{p.id}/forget",
            json={"revision": before["revision"]},
        ).status_code
        == 200
    )
    assert memory.operate().references == []


@pytest.mark.parametrize("failure", ["database", "schema", "document"])
def test_corrupt_or_future_catalog_is_not_silently_reset(client, failure):
    add(client, project())
    path = memory.database_path()
    if failure == "database":
        path.write_bytes(b"corrupt catalog; preserve for recovery")
        before = path.read_bytes()
    else:
        with sqlite3.connect(path) as connection:
            connection.execute(
                "PRAGMA user_version=99"
                if failure == "schema"
                else "UPDATE catalog SET document='{}broken'"
            )
    response = client.get("/api/memory")
    assert response.status_code == 409
    if failure == "database":
        assert path.read_bytes() == before


def test_retrieval_language_theme_series_recency_diversity_and_budget(client):
    swift = project("Counter", "Build one counter")
    related = project("State", "Explore State updates")
    diverse = project("Captions", "Keep captions readable")
    indonesian = project("Narasi", "Atur narasi dengan jelas", "id")
    add(client, swift, related, diverse, indonesian)
    update(
        client,
        swift.id,
        confirmed={
            "themes": ["SwiftUI"],
            "series": "Basics",
            "summary": "A user-approved counter summary",
        },
    )
    update(client, related.id, confirmed={"themes": ["SwiftUI"], "series": "Basics"})
    update(client, diverse.id, confirmed={"themes": ["Captions"], "series": "Editing"})
    result = retrieve(client, language="en", theme="SwiftUI", series="Basics", limit=1)
    assert result["references"][0]["project_id"] in {swift.id, related.id}
    result = retrieve(client, language="en", limit=2)
    assert diverse.id in {
        r["project_id"] for r in result["references"]
    }  # Diversity breaks a repeated theme/series.
    assert [r["project_id"] for r in retrieve(client, language="id")["references"]] == [
        indonesian.id
    ]
    result = retrieve(client, language="en", max_chars=1000)
    assert len(json.dumps(result, ensure_ascii=False, separators=(",", ":"))) <= 1000
    swift.updated_at = "2000-01-01T00:00:00+00:00"
    repo.atomic_json(repo.project_dir(swift.id) / "project.json", swift.model_dump())
    assert swift.id not in {
        r["project_id"] for r in retrieve(client, recent_days=30)["references"]
    }


def test_unconfirmed_ai_labels_never_become_retrieval_facts(client):
    p = project()
    add(client, p)
    with sqlite3.connect(memory.database_path()) as connection:
        saved = Catalog.model_validate_json(
            connection.execute("SELECT document FROM catalog").fetchone()[0]
        )
        saved.references[0].suggested = AIProposal.model_validate(
            {
                "provider": "gemini-nano-local",
                "source_revision": 0,
                "labels": {"summary": "Unverified best performer"},
            }
        )
        connection.execute("UPDATE catalog SET document=?", (saved.model_dump_json(),))
    result = retrieve(client)
    assert "Unverified best performer" not in json.dumps(result)
    assert result["references"][0]["summary_origin"] == "project_excerpt"


def test_http_security_payload_bounds_and_readonly_observations(client):
    p = project()
    current = add(client, p)
    assert (
        client.get(
            "/api/memory", headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/memory/references", json={}, headers={"X-JDH-CSRF": "wrong"}
        ).status_code
        == 403
    )
    assert (
        client.put(
            "/api/memory/profile", content=iter([b"x" * 40000, b"x" * 30000])
        ).status_code
        == 413
    )
    assert client.post("/api/memory/retrieve", json={"limit": 999}).status_code == 422
    assert (
        client.post("/api/memory/retrieve", json={"max_chars": 999999}).status_code
        == 422
    )
    assert (
        client.put(
            f"/api/memory/references/{p.id}",
            json={
                "revision": current["revision"],
                "source_revision": 0,
                "included": True,
                "category": "content",
                "published": False,
                "confirmed": {},
                "observed": {"exported_revision": 99},
            },
        ).status_code
        == 422
    )
    client.cookies.clear()
    assert client.get("/api/memory").status_code == 401


def test_process_exit_before_commit_recovers_previous_catalog(client):
    before = add(client, project())
    subprocess.check_call(
        [
            __import__("sys").executable,
            "-c",
            "import sqlite3,sys,os; c=sqlite3.connect(sys.argv[1]); c.execute('PRAGMA cache_size=1'); "
            "c.execute('BEGIN IMMEDIATE'); c.execute('UPDATE catalog SET document=?', ('x'*100000,)); os._exit(0)",
            str(memory.database_path()),
        ]
    )
    assert catalog(client) == before
