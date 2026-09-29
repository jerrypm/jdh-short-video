from typing import Literal
from fastapi import APIRouter
from pydantic import Field
from .idea_contract import Model
from .daily_ideas_store import Preferences
from . import daily_ideas

router = APIRouter(prefix="/api/ideas")


class Start(Model):
    id: str = Field(max_length=36)
    timezone: str = Field(max_length=100)
    automatic: bool = False


class Settings(Model):
    timezone: str = Field(max_length=100)
    revision: int = Field(ge=0)
    preferences: Preferences


class Feedback(Model):
    timezone: str = Field(max_length=100)
    verdict: Literal["saved", "skipped", "none"]
    reason: str = Field(default="", max_length=300)


class Activity(Model):
    client_id: str = Field(max_length=36)
    editing: bool


@router.get("/status")
def status(timezone: str):
    return daily_ideas.service.status(timezone)


@router.post("/generate")
def generate(data: Start):
    return daily_ideas.service.start(data.id, data.timezone, data.automatic)


@router.post("/requests/{request_id}/cancel")
def cancel(request_id: str, timezone: str):
    return daily_ideas.service.cancel(request_id, timezone)


@router.put("/preferences")
def preferences(data: Settings):
    return daily_ideas.service.preferences(
        data.preferences, data.revision, data.timezone
    )


@router.put("/cards/{card_id}/feedback")
def feedback(card_id: str, data: Feedback):
    return daily_ideas.service.feedback(
        card_id, data.verdict, data.reason, data.timezone
    )


@router.post("/activity")
def activity(data: Activity):
    return daily_ideas.service.activity(data.client_id, data.editing)
