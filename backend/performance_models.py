"""User-reviewed measurements, never inferred analytics or publication state."""

from datetime import date, datetime, timezone
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import Field, model_validator
from .motion import Model

Count = Annotated[int, Field(ge=0, le=10**12)]
METRICS = (
    "engaged_views",
    "average_view_duration_seconds",
    "average_view_percentage",
    "likes",
    "comments",
    "shares",
)


class Measurement(Model):
    # Empty mapping is permitted in CSV staging only; preview/apply require a real project.
    project_id: str = Field(default="", pattern=r"^([a-f0-9]{32})?$")
    video_id: str = Field(pattern=r"^[A-Za-z0-9_-]{11}$")
    published_on: str
    period_start: str
    period_end: str
    report_timezone: str = Field(min_length=1, max_length=80)
    captured_at: str = Field(max_length=40)
    definition: Literal["youtube_engaged_views_v1", "custom"]
    definition_note: str = Field(default="", max_length=120)
    source: str = Field(min_length=1, max_length=120)
    engaged_views: Count | None = None
    average_view_duration_seconds: Annotated[float, Field(ge=0, le=86400)] | None = None
    average_view_percentage: Annotated[float, Field(ge=0, le=10000)] | None = None
    likes: Count | None = None
    comments: Count | None = None
    shares: Count | None = None

    @model_validator(mode="after")
    def valid_report(self):
        try:
            dates = [
                date.fromisoformat(getattr(self, name))
                for name in ("published_on", "period_start", "period_end")
            ]
            if any(
                d.isoformat() != getattr(self, name)
                for d, name in zip(
                    dates, ("published_on", "period_start", "period_end")
                )
            ):
                raise ValueError
            report_zone = ZoneInfo(self.report_timezone)
            captured = datetime.fromisoformat(self.captured_at)
            if captured.tzinfo is None or captured > datetime.now(timezone.utc):
                raise ValueError
            if (
                not dates[0]
                <= dates[1]
                <= dates[2]
                <= captured.astimezone(report_zone).date()
            ):
                raise ValueError
        except (ValueError, ZoneInfoNotFoundError):
            raise ValueError(
                "Periksa tanggal publikasi, periode, zona waktu, dan waktu pengambilan data (dengan offset)."
            )
        if not self.source.strip() or (
            self.definition == "custom" and not self.definition_note.strip()
        ):
            raise ValueError("Sumber dan penjelasan definisi khusus wajib diisi.")
        if all(getattr(self, field) is None for field in METRICS):
            raise ValueError(
                "Isi minimal satu metrik; kosong berarti tidak tersedia, bukan nol."
            )
        return self


class Record(Measurement):
    id: str = Field(pattern=r"^[a-f0-9]{32}$")
    origin: Literal["manual", "csv"]
    imported_at: str
    included: bool = True
    exclusion_reason: str = Field(default="", max_length=240)


class State(Model):
    schema_version: Literal[1] = 1
    revision: int = 0
    records: list[Record] = Field(default_factory=list, max_length=1000)


class ParseCSV(Model):
    csv: str = Field(min_length=1, max_length=40000)


class Preview(Model):
    revision: int = Field(ge=0)
    rows: list[Measurement] = Field(min_length=1, max_length=100)
    origin: Literal["manual", "csv"]
    replace_conflicts: bool = False


class Apply(Model):
    review_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    reviewed: Literal[True]


class Inclusion(Model):
    revision: int = Field(ge=0)
    included: bool
    reason: str = Field(default="", max_length=240)
