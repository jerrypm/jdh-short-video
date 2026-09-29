"""Motion v1: bounded data and frame evaluation, never user-supplied filters."""

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

PRESETS = ["none", "zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down"]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class FrameRange(Model):
    start_frame: int = Field(default=0, ge=0, le=1798)
    end_frame: int | None = Field(default=None, ge=1, le=1799)

    @model_validator(mode="after")
    def ordered(self):
        if self.end_frame is not None and self.end_frame <= self.start_frame:
            raise ValueError("Frame akhir motion harus setelah frame awal.")
        return self


class VisualMotion(FrameRange):
    preset: Literal[
        "none", "zoom_in", "zoom_out", "pan_left", "pan_right", "pan_up", "pan_down"
    ] = "none"
    amount: float = Field(default=0.06, ge=0, le=0.12)
    focus_x: float = Field(default=0.5, ge=0, le=1)
    focus_y: float = Field(default=0.5, ge=0, le=1)
    easing: Literal["linear", "smoothstep"] = "smoothstep"


class TextMotion(FrameRange):
    preset: Literal["none", "fade", "slide_up"] = "none"
    end_frame: int | None = Field(default=12, ge=1, le=1799)
    easing: Literal["linear"] = "linear"


class Callout(Model):
    text: str = Field(min_length=1, max_length=120)
    x: int = Field(default=100, ge=65, le=855)
    y: int = Field(default=200, ge=135, le=1450)
    width: int = Field(default=440, ge=160, le=800)
    size: int = Field(default=36, ge=24, le=48)
    target_x: int = Field(default=540, ge=65, le=1015)
    target_y: int = Field(default=600, ge=135, le=1612)
    entrance: TextMotion = Field(default_factory=TextMotion)

    @model_validator(mode="after")
    def inside_safe_area(self):
        if not self.text.strip() or self.x + self.width > 1015:
            raise ValueError("Callout harus berisi teks dan berada di area aman.")
        # Reserve the full 48 px entrance path, including the pointer. The box
        # limit leaves room for two lines at the largest supported font size.
        if self.entrance.preset == "slide_up" and (
            self.y > 1400 or self.target_y > 1564
        ):
            raise ValueError("Callout slide memerlukan ruang di bawah area tujuan.")
        return self


class Motion(Model):
    version: Literal[1] = 1
    visual: VisualMotion = Field(default_factory=VisualMotion)
    caption: TextMotion = Field(default_factory=TextMotion)
    callout: Callout | None = None

    @field_validator("version", mode="before")
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError("Versi motion harus integer.")
        return value


def frame_range(value: FrameRange, duration: int):
    # Shortening a scene clips its keyframes; the last frame remains reachable.
    last = max(1, duration - 1)
    start = min(value.start_frame, last - 1)
    end = max(
        start + 1, min(value.end_frame if value.end_frame is not None else last, last)
    )
    return start, end


def progress(value, frame, duration):
    start, end = frame_range(value, duration)
    p = max(0, min(1, (frame - start) / (end - start)))
    return p * p * (3 - 2 * p) if value.easing == "smoothstep" else p


def evaluate_visual(value: VisualMotion, frame: int, duration: int, enabled=True):
    if not enabled or value.preset == "none":
        return {"scale": 1, "x": 0, "y": 0}
    p = progress(value, frame, duration)
    z = 1 + value.amount * (
        p if value.preset == "zoom_in" else 1 - p if value.preset == "zoom_out" else 1
    )
    fx, fy = value.focus_x, value.focus_y
    if value.preset in {"pan_left", "pan_right"}:
        fx = max(0, min(1, fx + (p - 0.5) * (1 if value.preset == "pan_right" else -1)))
    if value.preset in {"pan_up", "pan_down"}:
        fy = max(0, min(1, fy + (p - 0.5) * (1 if value.preset == "pan_down" else -1)))
    return {"scale": z, "x": -(z - 1) * 1080 * fx, "y": -(z - 1) * 1920 * fy}


def evaluate_text(value: TextMotion, frame: int, duration: int, enabled=True):
    p = progress(value, frame, duration) if enabled and value.preset != "none" else 1
    return {
        "opacity": p,
        "y": 48 * (1 - p) if enabled and value.preset == "slide_up" else 0,
    }


def visual_filter(value, duration, width, height, enabled):
    if not enabled or value.preset == "none" or value.amount == 0:
        return "null"
    start, end = frame_range(value, duration)
    p = f"clip((on-{start})/{end - start},0,1)"
    if value.easing == "smoothstep":
        p = f"({p})*({p})*(3-2*({p}))"
    z = (
        f"1+{value.amount}*({p})"
        if value.preset == "zoom_in"
        else f"1+{value.amount}*(1-({p}))"
        if value.preset == "zoom_out"
        else str(1 + value.amount)
    )
    fx, fy = str(value.focus_x), str(value.focus_y)
    if value.preset in {"pan_left", "pan_right"}:
        fx = f"clip({fx}+(({p})-0.5)*{1 if value.preset == 'pan_right' else -1},0,1)"
    if value.preset in {"pan_up", "pan_down"}:
        fy = f"clip({fy}+(({p})-0.5)*{1 if value.preset == 'pan_down' else -1},0,1)"
    return f"zoompan=z='{z}':x='iw*(1-1/zoom)*({fx})':y='ih*(1-1/zoom)*({fy})':d=1:s={width}x{height}:fps=30"


def text_filter(value, duration, enabled):
    if not enabled or value.preset == "none":
        return "null", "0"
    start, end = frame_range(value, duration)
    fade = f"fade=t=in:start_frame={start}:nb_frames={end - start}:alpha=1"
    # overlay's n starts at 1; use timestamps on the 30 fps main timeline.
    y = (
        f"48*(1-clip((round(t*30)-{start})/{end - start},0,1))"
        if value.preset == "slide_up"
        else "0"
    )
    return fade, y
