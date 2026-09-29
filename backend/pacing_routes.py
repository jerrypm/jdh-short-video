from fastapi import APIRouter
from . import pacing

router = APIRouter()


@router.post("/api/pacing/{pid}/analyze")
def analyze(pid: str, data: pacing.Start):
    return pacing.service.analyze(pid, data)


@router.post("/api/pacing/{pid}/{proposal_id}/preview")
def preview(pid: str, proposal_id: str, data: pacing.Selection):
    return pacing.service.preview(pid, proposal_id, data)


@router.post("/api/pacing/{pid}/{proposal_id}/apply")
def apply(pid: str, proposal_id: str, data: pacing.Selection):
    return pacing.service.apply(pid, proposal_id, data)
