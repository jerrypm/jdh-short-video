"""Scene proposals are data; only fixed editor capabilities can become a timeline."""

from typing import Annotated, Literal
from pydantic import Field, field_validator, model_validator
from .idea_contract import Model, ProjectID
from .motion import Motion
from . import captions
from .models import CaptionStyle


class DraftScene(Model):
    name: str = Field(min_length=1, max_length=120)
    narration: str = Field(min_length=1, max_length=1500)
    caption: str = Field(max_length=240)
    estimated_frames: int = Field(ge=9, le=1800)
    visual_need: str = Field(min_length=1, max_length=240)
    media_id: ProjectID | None
    media_status: Literal["available", "missing"]
    audio_id: ProjectID | None
    effect: Literal["static"]
    motion_intent: str = Field(min_length=1, max_length=200)
    motion: Motion = Field(default_factory=Motion)
    source_project_ids: list[ProjectID] = Field(max_length=5)

    @field_validator("name", "narration", "visual_need", "motion_intent")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Teks scene tidak boleh kosong.")
        return value.strip()

    @model_validator(mode="after")
    def consistent(self):
        if (self.media_id is None) != (self.media_status == "missing"):
            raise ValueError("Status media tidak sesuai ID media.")
        if len(set(self.source_project_ids)) != len(self.source_project_ids):
            raise ValueError("Sumber scene berulang.")
        return self


class Draft(Model):
    hook: str = Field(min_length=1, max_length=240)
    scenes: list[DraftScene] = Field(min_length=1, max_length=8)

    @model_validator(mode="after")
    def coherent(self):
        if not self.hook.strip() or not self.scenes[0].narration.startswith(self.hook):
            raise ValueError("Hook harus membuka narasi scene pertama.")
        if sum(scene.estimated_frames for scene in self.scenes) > 5400:
            raise ValueError("Total perkiraan melebihi 180 detik.")
        return self


def validate_draft(value, context):
    draft = Draft.model_validate(value)
    allowed = {ref["project_id"] for ref in context["references"]}
    assets = {a["id"]: a for a in context["assets"]}
    transcripts = context["audio_transcripts"]
    total = 0
    for scene in draft.scenes:
        if scene.motion.callout:
            callout = scene.motion.callout
            if captions.layout(
                callout.text,
                CaptionStyle(size=callout.size),
                max_width=callout.width - 32,
            )["errors"]:
                raise ValueError("Callout proposal terlalu panjang untuk kotaknya.")
        if not set(scene.source_project_ids) <= allowed:
            raise ValueError("Sumber scene tidak ada dalam konteks terpilih.")
        frames = scene.estimated_frames
        if scene.audio_id:
            asset = assets.get(scene.audio_id)
            if (
                not asset
                or asset["kind"] != "audio"
                or not asset["has_audio"]
                or asset["frames"] <= 0
            ):
                raise ValueError("Audio tidak terdaftar atau durasinya tidak valid.")
            if scene.narration not in transcripts.get(scene.audio_id, []):
                raise ValueError(
                    "Narasi tidak sesuai transkrip audio terkonfirmasi; buat audio baru setelah review."
                )
            frames = max(frames, asset["frames"])
            if frames > 1800:
                raise ValueError(
                    "Narasi melebihi 60 detik per scene; perlu dipisahkan secara manual."
                )
        if scene.media_id:
            asset = assets.get(scene.media_id)
            if not asset or asset["kind"] not in {"image", "video"}:
                raise ValueError("Visual tidak terdaftar pada proyek ini.")
            if asset["kind"] == "video" and asset["frames"] < frames:
                raise ValueError(
                    "Video lebih pendek dari scene; pilih visual lain agar narasi tidak terpotong."
                )
        total += frames
    if total > 5400:
        raise ValueError("Total durasi terukur melebihi 180 detik.")
    return draft


def response_schema():
    schema = Draft.model_json_schema()
    definitions = schema.pop("$defs")

    def expand(value):
        if isinstance(value, dict):
            if "$ref" in value:
                return expand(definitions[value["$ref"].split("/")[-1]])
            return {key: expand(item) for key, item in value.items()}
        if isinstance(value, list):
            return [expand(item) for item in value]
        return value

    return expand(schema)


class Start(Model):
    id: str = Field(max_length=36)
    idea_id: ProjectID
    base_revision: int = Field(ge=0)


class Selection(Model):
    draft: Draft
    selected: list[Annotated[int, Field(ge=0, le=7)]] = Field(
        min_length=1, max_length=8
    )
    mode: Literal["append", "replace"] = "append"

    @field_validator("selected")
    @classmethod
    def unique(cls, values):
        if len(set(values)) != len(values):
            raise ValueError("Pilihan scene berulang.")
        return values
