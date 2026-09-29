"""Daily ideas share the catalogue transaction but never alter project manifests."""

from typing import Literal
from pydantic import Field
from .idea_contract import Model, Idea


class Preferences(Model):
    source_mode: Literal["history", "research"] = "history"
    mode: Literal["daily", "manual"] = "daily"
    language: Literal["en", "id"] = "en"
    topic: str = Field(default="", max_length=240)
    audience: str = Field(default="", max_length=160)


class Card(Idea):
    id: str


class Batch(Model):
    id: str
    key: str
    date: str
    timezone: str
    language: str
    created_at: str
    sources: dict[str, int]
    performance_revision: int = 0
    research_revision: int = 0
    source_mode: Literal["history", "research"] = "history"
    cards: list[Card] = Field(min_length=3, max_length=3)


class Feedback(Model):
    card: Card
    sources: dict[str, int]
    performance_revision: int = 0
    research_revision: int = 0
    source_mode: Literal["history", "research"] = "history"
    verdict: Literal["saved", "skipped"]
    reason: str = Field(max_length=300)
    language: str
    created_at: str


class Attempt(Model):
    id: str
    key: str
    date: str
    timezone: str
    created_at: str
    status: str = "queued"
    message: str = ""


class Active(Model):
    research: list[dict] = Field(default_factory=list, max_length=3)
    performance: list[dict] = Field(default_factory=list, max_length=5)
    id: str
    owner: str
    key: str
    date: str
    timezone: str
    language: str
    sources: dict[str, int]
    performance_revision: int = 0
    research_revision: int = 0
    source_mode: Literal["history", "research"] = "history"


class State(Model):
    schema_version: Literal[1] = 1
    settings_revision: int = 0
    feedback_revision: int = 0
    performance_revision: int = 0
    research_revision: int = 0
    preferences: Preferences = Field(default_factory=Preferences)
    batches: list[Batch] = Field(default_factory=list, max_length=14)
    feedback: list[Feedback] = Field(default_factory=list, max_length=90)
    attempts: list[Attempt] = Field(default_factory=list, max_length=60)
    active: Active | None = None


def read(connection):
    row = connection.execute("SELECT document FROM daily_ideas WHERE id=1").fetchone()
    try:
        if not row or len(row[0].encode()) > 2 * 1024 * 1024:
            raise ValueError("Invalid size")
        return State.model_validate_json(row[0])
    except ValueError as error:
        raise RuntimeError(
            "Penyimpanan ide tidak valid; file dipertahankan untuk pemulihan."
        ) from error


def write(connection, state):
    validated = State.model_validate(state.model_dump())
    connection.execute(
        "UPDATE daily_ideas SET document=? WHERE id=1", (validated.model_dump_json(),)
    )


def prune(connection, catalog):
    """Forget/exclude/source changes invalidate cache and saved feedback atomically."""
    state = read(connection)
    before = state.model_dump_json()
    available = {
        r.project_id: r.observed.source_revision
        for r in catalog.references
        if r.included and not r.missing and r.category == "content"
    }

    def valid(sources):
        return all(available.get(pid) == revision for pid, revision in sources.items())

    state.batches = [b for b in state.batches if valid(b.sources)]
    feedback = [f for f in state.feedback if valid(f.sources)]
    if len(feedback) != len(state.feedback):
        state.feedback_revision += 1
    state.feedback = feedback
    cancelled = None
    if state.active and not valid(state.active.sources):
        cancelled = state.active.id
        for attempt in state.attempts:
            if attempt.id == cancelled:
                attempt.status = "cancelled"
                attempt.message = "Referensi berubah; permintaan ide dibatalkan."
        state.active = None
    if state.model_dump_json() != before:
        write(connection, state)
    return cancelled
