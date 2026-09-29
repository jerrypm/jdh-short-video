"""Bounded output contract shared by the local broker and daily-idea cache."""

from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

ProjectID = Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ResearchClaim(Model):
    claim: str = Field(min_length=10, max_length=240)
    source_id: ProjectID
    quote: str = Field(min_length=20, max_length=240)

    @field_validator("claim", "quote")
    @classmethod
    def meaningful(cls, value, info):
        if len(value.strip()) < (20 if info.field_name == "quote" else 10):
            raise ValueError("Klaim dan kutipan riset terlalu pendek atau kosong.")
        return value


class Idea(Model):
    research_claims: list[ResearchClaim] = Field(default_factory=list, max_length=3)
    category: Literal["series", "new_angle", "experiment"]
    title: str = Field(min_length=1, max_length=100)
    hook: str = Field(min_length=1, max_length=240)
    concept: str = Field(min_length=1, max_length=400)
    reason: str = Field(min_length=1, max_length=280)
    difference: str = Field(min_length=1, max_length=240)
    estimated_seconds: Literal[15, 30, 45, 60]
    media_needs: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(
        min_length=1, max_length=5
    )
    source_project_ids: list[ProjectID] = Field(max_length=5)
    performance_ids: list[ProjectID] = Field(default_factory=list, max_length=3)

    @field_validator("title", "hook", "concept", "reason", "difference")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Teks ide kosong.")
        return value.strip()

    @field_validator("media_needs", "source_project_ids", "performance_ids")
    @classmethod
    def unique(cls, values):
        if any(not v.strip() for v in values) or len(set(values)) != len(values):
            raise ValueError("Daftar ide kosong atau berulang.")
        return values


class IdeaResponse(Model):
    ideas: list[Idea] = Field(min_length=3, max_length=3)


def validate_ideas(
    value, source_ids, performance=(), research=(), source_mode="history"
):
    ideas = IdeaResponse.model_validate({"ideas": value}).ideas
    if {i.category for i in ideas} != {"series", "new_angle", "experiment"}:
        raise ValueError("Jenis ide harus berbeda.")
    for field in ("title", "hook"):
        if len({getattr(i, field).casefold() for i in ideas}) != 3:
            raise ValueError("Ide berulang.")
    allowed = set(source_ids)
    for idea in ideas:
        if not set(idea.source_project_ids) <= allowed or (
            allowed and not idea.source_project_ids
        ):
            raise ValueError("Sumber ide tidak valid.")
    evidence = {r["id"]: r["project_id"] for r in performance}
    for idea in ideas:
        if any(
            rid not in evidence or evidence[rid] not in idea.source_project_ids
            for rid in idea.performance_ids
        ):
            raise ValueError("Bukti performa ide tidak valid.")
    if evidence and not any(i.performance_ids for i in ideas):
        raise ValueError("Ide belum menyertakan bukti performa yang tersedia.")
    references = {s["id"]: s for s in research}
    if source_mode == "research" and not references:
        raise ValueError("Sumber riset tidak tersedia.")
    for idea in ideas:
        if source_mode == "history" and idea.research_claims:
            raise ValueError("Mode riwayat tidak memakai klaim riset.")
        if source_mode == "research" and (
            not idea.research_claims or idea.source_project_ids or idea.performance_ids
        ):
            raise ValueError(
                "Mode riset wajib menyertakan bukti sumber terpisah dari riwayat."
            )
        for claim in idea.research_claims:
            source = references.get(claim.source_id)
            if (
                not source
                or not claim.quote.strip()
                or claim.quote not in source["text"]
            ):
                raise ValueError(
                    "Kutipan riset tidak cocok dengan catatan sumber yang diberikan."
                )
    return [idea.model_dump() for idea in ideas]


def response_schema():
    # Chrome's constrained decoder receives a flat schema, without $ref indirection.
    item = Idea.model_json_schema()
    item.pop("$defs", None)
    item["properties"]["research_claims"]["items"] = ResearchClaim.model_json_schema()
    item["required"].extend(["performance_ids", "research_claims"])
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["ideas"],
        "properties": {
            "ideas": {
                "type": "array",
                "minItems": 3,
                "maxItems": 3,
                "items": item,
            }
        },
    }
