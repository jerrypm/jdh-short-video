from fastapi import APIRouter
from pydantic import Field
from . import quality, daily_ideas, storyboards, nano, repository as repo
from .motion import Model
from .quality_contract import Start, Selection, response_schema

router = APIRouter()


class EditorialStart(Model):
    id: str = Field(pattern=r"^[a-f0-9-]{36}$")


@router.post("/api/quality/{pid}/checks")
def start(pid: str, data: Start):
    with repo.LOCK:
        daily_ideas.service.defer()
        storyboards.service.defer()
        quality.service.defer()
        return quality.service.start(pid, data)


@router.post("/api/quality/{pid}/{key}/preview")
def preview(pid: str, key: str, data: Selection):
    return quality.service.preview(pid, key, data)


@router.post("/api/quality/{pid}/{key}/apply")
def apply(pid: str, key: str, data: Selection):
    return quality.service.apply(pid, key, data)


@router.post("/api/quality/{pid}/{key}/editorial")
def editorial(pid: str, key: str, data: EditorialStart):
    return quality.service.editorial_start(pid, key, data.id)


@router.get("/api/quality/{pid}/{key}/editorial/{request_id}")
def read(pid: str, key: str, request_id: str):
    return quality.service.editorial_read(pid, key, request_id)


@router.post("/api/quality/{pid}/{key}/editorial/{request_id}/cancel")
def cancel(pid: str, key: str, request_id: str):
    with repo.LOCK:
        quality.service.get(pid, key)
        if quality.service.editorials.get(request_id) not in {None, key}:
            raise ValueError("Permintaan milik laporan lain.")
        # Cancellation may arrive before an uncertain POST is accepted.
        return nano.broker.cancel(request_id)


@router.get("/nano/editorial-schema.json")
def schema():
    return response_schema()
