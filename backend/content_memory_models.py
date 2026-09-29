"""Content memory is separate from project manifests and never owns media."""

from typing import Annotated, Literal
from pydantic import Field, field_validator, model_validator
from .models import StrictModel

ProjectID = Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]
Theme = Annotated[str, Field(min_length=1, max_length=80)]


class Labels(StrictModel):
    themes: list[Theme] = Field(default_factory=list, max_length=12)
    audience: str = Field(default="", max_length=160)
    series: str = Field(default="", max_length=120)
    summary: str = Field(default="", max_length=700)
    hook: str = Field(default="", max_length=240)
    format: str = Field(default="", max_length=80)

    @field_validator("themes")
    @classmethod
    def clean_themes(cls, values):
        values = [value.strip() for value in values]
        if any(not value for value in values) or len(
            {v.casefold() for v in values}
        ) != len(values):
            raise ValueError("Tema harus unik dan tidak kosong.")
        return values


class ChannelProfile(StrictModel):
    name: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=500)
    audience: str = Field(default="", max_length=160)
    language: Literal["en", "id", "mixed"] = "en"
    themes: list[Theme] = Field(default_factory=list, max_length=12)

    @field_validator("themes")
    @classmethod
    def clean_themes(cls, values):
        return Labels.clean_themes(values)


class Observation(StrictModel):
    source_revision: int = Field(ge=0)
    name: str = Field(max_length=120)
    language: Literal["id", "en"]
    updated_at: str = Field(max_length=80)
    duration_frames: int = Field(ge=0, le=5400)
    target_seconds: int = Field(ge=15, le=60)
    asset_ids: list[ProjectID] = Field(default_factory=list, max_length=200)
    excerpt: str = Field(max_length=700)
    hook_excerpt: str = Field(max_length=240)
    fingerprint: str = Field(pattern=r"^(|[a-f0-9]{64})$")
    exported_revision: int | None = Field(default=None, ge=0)
    export_job_id: ProjectID | None = None


class AIProposal(StrictModel):
    # Reserved provenance for later tasks. Task 03 neither generates nor accepts AI labels.
    provider: Literal["gemini-nano-local"]
    source_revision: int = Field(ge=0)
    labels: Labels


class IdeaFeedback(StrictModel):
    id: ProjectID
    idea: str = Field(min_length=1, max_length=400)
    verdict: Literal["saved", "skipped", "used"]
    reason: str = Field(default="", max_length=300)
    created_at: str


class Reference(StrictModel):
    project_id: ProjectID
    included: bool = True
    category: Literal["content", "qa", "duplicate"] = "content"
    published: bool = False
    missing: bool = False
    observed: Observation
    confirmed: Labels = Field(default_factory=Labels)
    suggested: AIProposal | None = None
    feedback: list[IdeaFeedback] = Field(default_factory=list, max_length=20)


class Catalog(StrictModel):
    schema_version: Literal[1] = 1
    revision: int = Field(default=0, ge=0)
    updated_at: str = ""
    profile: ChannelProfile = Field(default_factory=ChannelProfile)
    references: list[Reference] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def unique_references(self):
        if len({ref.project_id for ref in self.references}) != len(self.references):
            raise ValueError("Referensi proyek harus unik.")
        return self


class RevisionRequest(StrictModel):
    revision: int = Field(ge=0)


class AddReferences(RevisionRequest):
    project_ids: list[ProjectID] = Field(min_length=1, max_length=30)


class UpdateProfile(RevisionRequest):
    profile: ChannelProfile


class UpdateReference(RevisionRequest):
    source_revision: int = Field(ge=0)
    included: bool
    category: Literal["content", "qa", "duplicate"]
    published: bool
    confirmed: Labels


class AddFeedback(RevisionRequest):
    idea: str = Field(min_length=1, max_length=400)
    verdict: Literal["saved", "skipped", "used"]
    reason: str = Field(default="", max_length=300)

    @field_validator("idea")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Tulis ide yang ingin dicatat.")
        return value.strip()


class Retrieve(StrictModel):
    query: str = Field(default="", max_length=200)
    theme: str = Field(default="", max_length=80)
    language: Literal["id", "en"] | None = None
    series: str = Field(default="", max_length=120)
    recent_days: int | None = Field(default=None, ge=1, le=3650)
    limit: int = Field(default=5, ge=1, le=8)
    max_chars: int = Field(default=6000, ge=1000, le=12000)
