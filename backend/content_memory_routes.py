from fastapi import APIRouter
from . import content_memory as memory
from .content_memory_models import (
    AddReferences,
    UpdateReference,
    UpdateProfile,
    RevisionRequest,
    AddFeedback,
    Retrieve,
)

router = APIRouter(prefix="/api/memory")


@router.get("")
def read():
    return memory.view(memory.operate())


@router.put("/profile")
def profile(data: UpdateProfile):
    return memory.view(memory.update_profile(data))


@router.post("/references")
def add(data: AddReferences):
    return memory.view(memory.add_references(data))


@router.put("/references/{pid}")
def update(pid: str, data: UpdateReference):
    return memory.view(memory.update_reference(pid, data))


@router.post("/references/{pid}/forget")
def forget(pid: str, data: RevisionRequest):
    return memory.view(memory.forget_reference(pid, data.revision))


@router.post("/references/{pid}/feedback")
def feedback(pid: str, data: AddFeedback):
    return memory.view(memory.add_feedback(pid, data))


@router.post("/references/{pid}/feedback/{feedback_id}/forget")
def forget_feedback(pid: str, feedback_id: str, data: RevisionRequest):
    return memory.view(memory.delete_feedback(pid, feedback_id, data.revision))


@router.post("/retrieve")
def retrieve(data: Retrieve):
    return memory.retrieve(data)
