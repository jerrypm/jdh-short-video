from datetime import datetime, timezone
from fastapi import APIRouter
from . import research, research_fetch
from .research_models import Save, Fetch, Remove

router = APIRouter(prefix="/api/research")


@router.get("")
def read():
    return research.service.view()


@router.post("/fetch")
def fetch(data: Fetch):
    return {
        **research_fetch.fetch_public(data.url),
        "accessed_on": datetime.now(timezone.utc).date().isoformat(),
    }


@router.post("/sources")
def save(data: Save):
    return research.service.save(data)


@router.post("/sources/{sid}/remove")
def remove(sid: str, data: Remove):
    return research.service.remove(sid, data.revision)
