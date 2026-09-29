"""Bounded quality review data; editorial advice is never a technical finding."""

from typing import Literal
from pydantic import Field, model_validator
from .motion import Model


class UploadMetadata(Model):
    title: str = Field(default="", max_length=100)
    description: str = Field(default="", max_length=5000)


class QualitySettings(Model):
    long_silence_seconds: float = Field(default=1.5, ge=0.5, le=10)
    silence_dbfs: float = Field(default=-40, ge=-60, le=-20)
    peak_warning_dbfs: float = Field(default=-0.1, ge=-6, le=0)
    caption_cps: float = Field(default=20, ge=5, le=40)


class Start(Model):
    revision: int = Field(ge=0)
    preset: Literal["draft", "final"] = "final"


class SceneEdit(Model):
    scene_id: str = Field(min_length=1, max_length=64)
    duration: int = Field(ge=9, le=1800)
    caption: str = Field(max_length=400)


class Selection(Model):
    upload: UploadMetadata
    scenes: list[SceneEdit] = Field(default_factory=list, max_length=60)
    caption_position: int = Field(ge=40, le=90)
    narration_volume: float = Field(ge=0, le=1)
    music_volume: float = Field(ge=0, le=1)


class EditorialNote(Model):
    scene_id: str = Field(min_length=1, max_length=64)
    start_frame: int = Field(ge=0, le=5399)
    end_frame: int = Field(ge=1, le=5400)
    category: Literal["hook", "repetition", "pacing", "visual_intent"]
    suggestion: str = Field(min_length=1, max_length=400)
    reason: str = Field(min_length=1, max_length=400)


class Editorial(Model):
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(max_length=1500)
    notes: list[EditorialNote] = Field(max_length=8)

    @model_validator(mode="after")
    def nonempty(self):
        if not self.title.strip() or any(
            not n.suggestion.strip() or not n.reason.strip() for n in self.notes
        ):
            raise ValueError("Saran editorial harus berisi teks dan alasan.")
        return self


def validate_editorial(value, context):
    result = Editorial.model_validate(value)
    scenes = {s["id"]: s for s in context["scenes"]}
    for note in result.notes:
        scene = scenes.get(note.scene_id)
        if (
            not scene
            or not scene["start_frame"]
            <= note.start_frame
            < note.end_frame
            <= scene["end_frame"]
        ):
            raise ValueError("Rentang saran tidak cocok dengan scene sumber.")
    return result


def response_schema():
    schema = Editorial.model_json_schema()
    definitions = schema.pop("$defs", {})

    def expand(value):
        if isinstance(value, dict):
            if "$ref" in value:
                return expand(definitions[value["$ref"].split("/")[-1]])
            return {k: expand(v) for k, v in value.items()}
        if isinstance(value, list):
            return [expand(v) for v in value]
        return value

    return expand(schema)
