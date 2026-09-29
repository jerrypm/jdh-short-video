from pathlib import Path
import asyncio
import time
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import FileResponse
from . import nano

router = APIRouter()
ROOT = Path(__file__).resolve().parent / "nano_web"


def companion_token(request):
    # All browser mutations require an exact same-origin header as well as a token.
    if request.headers.get("origin") != f"http://{request.headers.get('host')}":
        raise HTTPException(403, "Origin companion ditolak.")
    return request.headers.get("x-jdh-nano", "")


@router.get("/api/ai/status")
def status():
    return nano.broker.status()


@router.post("/api/ai/pair")
def issue_pair():
    return nano.broker.issue_pair()


@router.post("/api/ai/disconnect")
def disconnect():
    nano.broker.disconnect()
    return nano.broker.status()


@router.post("/api/ai/requests")
def generate(data: nano.Generate):
    if data.operation in {"ideas", "storyboard", "editorial"}:
        raise HTTPException(422, "Gunakan halaman Ide hari ini dengan memori terpilih.")
    return nano.broker.enqueue(data)


@router.get("/api/ai/requests/{request_id}")
def read(request_id: str):
    return nano.broker.read(request_id)


@router.post("/api/ai/requests/{request_id}/cancel")
def cancel(request_id: str):
    return nano.broker.cancel(request_id)


@router.post("/nano/api/pair")
def pair(data: nano.Pair, request: Request):
    companion_token(request)
    return nano.broker.pair(data)


@router.post("/nano/api/poll")
async def poll(data: nano.Poll, request: Request):
    token = companion_token(request)
    deadline = time.monotonic() + 5
    while True:
        result = nano.broker.poll(token, data)
        if (
            not data.wait
            or result["job"]
            or result["active_id"] != data.running_id
            or time.monotonic() >= deadline
        ):
            return result
        if await request.is_disconnected():
            nano.broker.drop(token, data.document_id)
            return result
        # Server-held requests avoid dependence on a background tab's JS timers.
        await asyncio.sleep(0.25)


@router.post("/nano/api/result")
def finish(data: nano.Finish, request: Request):
    return nano.broker.finish(companion_token(request), data)


@router.post("/nano/api/disconnect")
def companion_disconnect(request: Request):
    with nano.broker.lock:
        nano.broker.authenticate(companion_token(request))
        nano.broker.disconnect()
    return {"disconnected": True}


@router.get("/nano/")
def companion():
    return FileResponse(ROOT / "index.html")


@router.get("/nano/idea-schema.json")
def idea_schema():
    from .idea_contract import response_schema

    return response_schema()


@router.get("/nano/{name}")
def companion_asset(name: str):
    if name not in {"companion.js", "styles.css"}:
        raise HTTPException(404)
    return FileResponse(ROOT / name)
