from fastapi import APIRouter
from . import storyboards
from .storyboard_contract import Start, Selection, response_schema
from . import repository as repo

router = APIRouter()


@router.get("/api/storyboards/ideas")
def ideas():
    with repo.LOCK:
        _, cards = storyboards.service.idea()
        return cards


@router.post("/api/storyboards/{pid}/requests")
def start(pid: str, data: Start):
    return storyboards.service.start(pid, data)


@router.get("/api/storyboards/{pid}/requests/{request_id}")
def read(pid: str, request_id: str):
    return storyboards.service.read(pid, request_id)


@router.post("/api/storyboards/{pid}/requests/{request_id}/cancel")
def cancel(pid: str, request_id: str):
    return storyboards.service.cancel(pid, request_id)


@router.post("/api/storyboards/{pid}/requests/{request_id}/preview")
def preview(pid: str, request_id: str, data: Selection):
    return storyboards.service.preview(pid, request_id, data)


@router.post("/api/storyboards/{pid}/requests/{request_id}/apply")
def apply(pid: str, request_id: str, data: Selection):
    return storyboards.service.apply(pid, request_id, data)


@router.get("/nano/storyboard-schema.json")
def schema():
    return response_schema()
