from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .motion import Motion
from .quality_contract import UploadMetadata, QualitySettings


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Asset(StrictModel):
    id: str = Field(pattern=r"^[a-f0-9]{32}$")
    name: str = Field(max_length=240)
    file: str = Field(pattern=r"^[a-f0-9]{32}\.[a-z0-9]+$")
    kind: Literal["image", "video", "audio"]
    frames: int = Field(default=0, ge=0, le=108000)
    width: int = Field(default=0, ge=0, le=16384)
    height: int = Field(default=0, ge=0, le=16384)
    has_audio: bool = False
    peaks: list[float] = Field(default_factory=list, max_length=100)


class ScenePlan(StrictModel):
    provider: Literal["gemini-nano-local"] = "gemini-nano-local"
    visual_need: str = Field(max_length=240)
    motion_intent: str = Field(max_length=200)
    estimated_frames: int = Field(ge=9, le=1800)
    source_revisions: dict[
        Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")], Annotated[int, Field(ge=0)]
    ] = Field(max_length=5)


class Scene(StrictModel):
    id: str = Field(max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    name: str = Field(default="Scene", max_length=120)
    narration: str = Field(default="", max_length=3000)
    caption: str = Field(default="", max_length=400)
    duration: int = Field(default=150, ge=9, le=1800)
    media_id: str | None = None
    audio_id: str | None = None
    audio_text: str = Field(default="", max_length=3000)
    source_in: int = Field(default=0, ge=0, le=108000)
    audio_in: int = Field(default=0, ge=0, le=108000)
    fit: Literal["fit", "fill"] = "fill"
    scale: float = Field(default=1, ge=1, le=2)
    x: int = Field(default=0, ge=-1080, le=1080)
    y: int = Field(default=0, ge=-1920, le=1920)
    source_volume: float = Field(default=0, ge=0, le=1)
    planning: ScenePlan | None = None
    motion: Motion = Field(default_factory=Motion)


class CaptionStyle(StrictModel):
    preset: Literal["putih", "lime", "bar"] = "lime"
    size: int = Field(default=48, ge=24, le=60)
    position: int = Field(default=78, ge=40, le=90)
    enabled: bool = True


class Project(StrictModel):
    schema_version: Literal[1] = 1
    id: str = Field(pattern=r"^[a-f0-9]{32}$")
    name: str = Field(min_length=1, max_length=120)
    language: Literal["id", "en"] = "id"
    target: Literal[15, 30, 45, 60] = 30
    script: str = Field(default="", max_length=12000)
    reference: str = Field(default="", max_length=2000)
    reference_notes: str = Field(default="", max_length=5000)
    scenes: list[Scene] = Field(default_factory=list, max_length=60)
    assets: list[Asset] = Field(default_factory=list, max_length=200)
    caption_style: CaptionStyle = Field(default_factory=CaptionStyle)
    narration_volume: float = Field(default=1, ge=0, le=1)
    music_id: str | None = None
    music_volume: float = Field(default=0.15, ge=0, le=1)
    motion_mode: Literal["gentle", "none"] = "gentle"
    upload: UploadMetadata = Field(default_factory=UploadMetadata)
    quality_settings: QualitySettings = Field(default_factory=QualitySettings)
    updated_at: str = ""
    revision: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_timeline(self):
        if sum(s.duration for s in self.scenes) > 5400:
            raise ValueError("Timeline maksimal 180 detik.")
        if len({s.id for s in self.scenes}) != len(self.scenes):
            raise ValueError("ID scene harus unik.")
        if len({a.id for a in self.assets}) != len(self.assets):
            raise ValueError("ID media harus unik.")
        return self


class NewProject(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    script: str = Field(default="", max_length=12000)
    target: Literal[15, 30, 45, 60] = 30
    language: Literal["id", "en"] = "id"
    reference: str = Field(default="", max_length=2000)


class RenderRequest(StrictModel):
    preset: Literal["draft", "final"] = "draft"
    check_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{32}$")


class TTSRequest(StrictModel):
    scene_id: str
    voice: Literal["af_heart", "af_bella", "am_adam", "am_michael"] = "af_heart"
    speed: float = Field(default=1, ge=0.5, le=2)
