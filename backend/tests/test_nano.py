from uuid import uuid4
import asyncio
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from backend import nano
from backend.app import app


@pytest.fixture
def setup(monkeypatch):
    now = [100.0]
    broker = nano.Broker(clock=lambda: now[0])
    monkeypatch.setattr(nano, "broker", broker)
    with TestClient(app) as editor, TestClient(app) as chrome:
        csrf = editor.get("/api/session").json()["csrf"]
        editor.headers["X-JDH-CSRF"] = csrf
        chrome.headers["Origin"] = "http://testserver"
        yield broker, editor, chrome, now


def connect(editor, chrome):
    code = editor.post("/api/ai/pair", json={}).json()["code"]
    doc = str(uuid4())
    paired = chrome.post("/nano/api/pair", json={"code": code, "document_id": doc})
    assert paired.status_code == 200, paired.text
    chrome.headers["X-JDH-Nano"] = paired.json()["token"]
    heartbeat(chrome, doc)
    return doc, code


def heartbeat(chrome, doc, **extra):
    return chrome.post("/nano/api/poll", json={
        "document_id": doc, "english": "available", "indonesian": "unavailable", **extra,
    })


def enqueue(editor, **extra):
    data = {"id": str(uuid4()), "operation": "hooks", "language": "en", "input": "A SwiftUI counter uses State.", **extra}
    result = editor.post("/api/ai/requests", json=data)
    return data, result


def finish(chrome, doc, job_id, **extra):
    return chrome.post("/nano/api/result", json={
        "document_id": doc, "id": job_id, "status": "completed",
        "suggestions": ["First", "Second", "Third"], **extra,
    })


def test_pairing_expiry_replay_scope_and_revocation(setup):
    broker, editor, chrome, now = setup
    doc, code = connect(editor, chrome)
    assert editor.get("/api/ai/status").json()["connected"]
    assert chrome.get("/api/projects").status_code == 401
    assert chrome.post("/nano/api/pair", json={"code": code, "document_id": doc}).status_code == 403
    old_token = chrome.headers["X-JDH-Nano"]
    connect(editor, chrome)
    assert heartbeat(chrome, doc,).status_code == 200
    assert chrome.post("/nano/api/poll", json={"document_id": doc, "english": "available", "indonesian": "unavailable"},
                       headers={"X-JDH-Nano": old_token}).status_code == 401
    code = editor.post("/api/ai/pair", json={}).json()["code"]
    now[0] += 181
    assert chrome.post("/nano/api/pair", json={"code": code, "document_id": str(uuid4())}).status_code == 403
    editor.post("/api/ai/disconnect", json={})
    assert heartbeat(chrome, doc).status_code == 401


def test_complete_only_validated_output_and_no_source_in_status(setup):
    broker, editor, chrome, _ = setup
    doc, _ = connect(editor, chrome)
    data, result = enqueue(editor)
    assert result.status_code == 200
    assert "input" not in result.json()
    claimed = heartbeat(chrome, doc).json()["job"]
    assert claimed["input"] == data["input"]
    assert heartbeat(chrome, doc).json()["job"] is None
    assert finish(chrome, doc, data["id"]).status_code == 200
    job = editor.get("/api/ai/requests/" + data["id"]).json()
    assert job["status"] == "completed" and len(job["suggestions"]) == 3
    assert broker.jobs[data["id"]]["input"] == ""
    assert finish(chrome, doc, data["id"]).status_code == 409


@pytest.mark.parametrize("value", [None, [], ["one"], ["a", "A", "c"], [" ", "b", "c"], ["x" * 3001, "b", "c"]])
def test_invalid_output_fails_and_frees_slot(setup, value):
    _, editor, chrome, _ = setup
    doc, _ = connect(editor, chrome)
    data, _ = enqueue(editor)
    heartbeat(chrome, doc)
    assert finish(chrome, doc, data["id"], suggestions=value).status_code == 422
    job = editor.get("/api/ai/requests/" + data["id"]).json()
    assert job["status"] == "failed" and job["suggestions"] is None
    assert enqueue(editor)[1].status_code == 200


def test_cancel_before_submission_and_late_response(setup):
    _, editor, chrome, _ = setup
    doc, _ = connect(editor, chrome)
    request_id = str(uuid4())
    editor.post("/api/ai/requests/" + request_id + "/cancel", json={})
    data, result = enqueue(editor, id=request_id)
    assert result.json()["status"] == "cancelled"
    assert heartbeat(chrome, doc).json()["job"] is None
    data, _ = enqueue(editor)
    heartbeat(chrome, doc)
    editor.post("/api/ai/requests/" + data["id"] + "/cancel", json={})
    assert heartbeat(chrome, doc).json()["active_id"] is None
    assert finish(chrome, doc, data["id"]).status_code == 409


def test_disconnect_timeout_reload_and_restart(setup):
    broker, editor, chrome, now = setup
    doc, _ = connect(editor, chrome)
    data, _ = enqueue(editor)
    heartbeat(chrome, doc)
    now[0] += 11
    assert editor.get("/api/ai/requests/" + data["id"]).json()["error"] == "disconnected"
    heartbeat(chrome, doc)
    data, _ = enqueue(editor)
    heartbeat(chrome, doc)
    for _ in range(25):
        now[0] += 5
        heartbeat(chrome, doc)
    assert editor.get("/api/ai/requests/" + data["id"]).json()["error"] == "timeout"
    data, _ = enqueue(editor)
    heartbeat(chrome, doc)
    fresh_doc = str(uuid4())
    heartbeat(chrome, fresh_doc)
    assert editor.get("/api/ai/requests/" + data["id"]).json()["error"] == "reloaded"
    assert finish(chrome, doc, data["id"]).status_code == 409
    assert enqueue(editor)[1].status_code == 200
    with pytest.raises(HTTPException):
        nano.Broker().authenticate(chrome.headers["X-JDH-Nano"])


def test_request_bounds_busy_and_idempotency(setup):
    broker, editor, chrome, _ = setup
    doc, _ = connect(editor, chrome)
    data, _ = enqueue(editor)
    assert editor.post("/api/ai/requests", json=data).status_code == 200
    assert editor.post("/api/ai/requests", json={**data, "input": "Different"}).status_code == 409
    assert enqueue(editor)[1].status_code == 409
    assert enqueue(editor, operation="shell")[1].status_code == 422
    assert enqueue(editor, language="id")[1].status_code == 422
    assert enqueue(editor, input="x" * 12001)[1].status_code == 422
    assert enqueue(editor, input=" ")[1].status_code == 422
    assert enqueue(editor, id="not-a-uuid")[1].status_code == 422
    editor.post("/api/ai/requests/" + data["id"] + "/cancel", json={})
    for _ in range(31):
        editor.post("/api/ai/requests/" + str(uuid4()) + "/cancel", json={})
    assert enqueue(editor)[1].status_code == 429
    assert len(broker.jobs) == 32


def test_http_security_and_closed_transport(setup):
    _, editor, chrome, _ = setup
    doc, _ = connect(editor, chrome)
    payload = {"document_id": doc, "english": "available", "indonesian": "unavailable"}
    assert chrome.post("/nano/api/poll", json=payload, headers={"Origin": "https://evil.example"}).status_code == 403
    assert chrome.post("/nano/api/poll", json=payload, headers={"Host": "evil.example"}).status_code == 403
    assert chrome.post("/nano/api/poll", json=payload, headers={"X-JDH-Nano": "bad"}).status_code == 401
    assert editor.post("/api/ai/pair", json={}, headers={"X-JDH-CSRF": "bad"}).status_code == 403
    assert editor.post("/api/ai/pair", content="x" * 65537).status_code == 413
    assert editor.post("/api/ai/pair", content=iter([b"x" * 40000, b"x" * 30000])).status_code == 413
    assert chrome.post("/nano/api/result", json={}).status_code == 422
    assert chrome.get("/nano/secrets.py").status_code == 404
    page = chrome.get("/nano/")
    assert page.status_code == 200
    assert "connect-src 'self'" in page.headers["Content-Security-Policy"]
    assert "no-store" in page.headers["Cache-Control"]
    assert chrome.get("/nano/companion.js").status_code == 200


def test_source_and_results_expire_from_memory(setup):
    broker, editor, chrome, now = setup
    doc, _ = connect(editor, chrome)
    data, _ = enqueue(editor)
    heartbeat(chrome, doc)
    finish(chrome, doc, data["id"])
    now[0] += 601
    assert editor.get("/api/ai/requests/" + data["id"]).status_code == 404
    assert not broker.jobs


def test_companion_timeout_has_actionable_error(setup):
    _, editor, chrome, _ = setup
    doc, _ = connect(editor, chrome)
    data, _ = enqueue(editor)
    heartbeat(chrome, doc)
    assert finish(chrome, doc, data["id"], status="failed", suggestions=None, error="timeout").status_code == 200
    job = editor.get("/api/ai/requests/" + data["id"]).json()
    assert job["error"] == "timeout"
    assert "lebih pendek" in job["message"]


def test_held_poll_delivers_new_work_and_app_cancellation(setup):
    _, editor, chrome, _ = setup
    doc, _ = connect(editor, chrome)

    async def check():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://testserver", headers=dict(chrome.headers)) as client:
            body = {"document_id": doc, "english": "available", "indonesian": "unavailable", "wait": True}
            waiting = asyncio.create_task(client.post("/nano/api/poll", json=body))
            await asyncio.sleep(0.05)
            assert not waiting.done()
            data, response = enqueue(editor)
            assert response.status_code == 200
            result = await asyncio.wait_for(waiting, 2)
            assert result.json()["job"]["id"] == data["id"]
            waiting = asyncio.create_task(client.post("/nano/api/poll", json={**body, "running_id": data["id"]}))
            await asyncio.sleep(0.05)
            assert not waiting.done()
            editor.post("/api/ai/requests/" + data["id"] + "/cancel", json={})
            result = await asyncio.wait_for(waiting, 2)
            assert result.json()["active_id"] is None
    asyncio.run(check())
