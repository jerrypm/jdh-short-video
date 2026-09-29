from datetime import date
from typing import Literal
from pydantic import Field, field_validator, model_validator
from .motion import Model
from .research_fetch import canonical_url


class SourceInput(Model):
    title: str = Field(min_length=1, max_length=160)
    url: str = Field(default="", max_length=2000)
    published_on: str = Field(default="", max_length=10)
    accessed_on: str = Field(max_length=10)
    text: str = Field(min_length=20, max_length=1200)
    kind: Literal["summary", "excerpt"] = "summary"
    included: bool = True
    conflict_with: str = Field(default="", pattern=r"^([a-f0-9]{32})?$")
    caution: str = Field(default="", max_length=240)

    @field_validator("url")
    @classmethod
    def public_url(cls, value):
        return canonical_url(value.strip())

    @field_validator("title", "text")
    @classmethod
    def clean(cls, value, info):
        value = value.strip()
        if not value or (info.field_name == "text" and len(value) < 20):
            raise ValueError("Judul wajib diisi dan isi catatan minimal 20 karakter.")
        return value

    @model_validator(mode="after")
    def dates(self):
        try:
            accessed = date.fromisoformat(self.accessed_on)
            if accessed.isoformat() != self.accessed_on or accessed > date.today():
                raise ValueError
            if self.published_on:
                published = date.fromisoformat(self.published_on)
                if published.isoformat() != self.published_on or published > accessed:
                    raise ValueError
        except ValueError:
            raise ValueError(
                "Tanggal harus YYYY-MM-DD, publikasi tidak sesudah akses, dan akses tidak di masa depan."
            )
        if self.conflict_with and not self.caution.strip():
            raise ValueError("Jelaskan informasi yang bertentangan sebelum menyimpan.")
        return self


class Source(SourceInput):
    id: str = Field(pattern=r"^[a-f0-9]{32}$")
    updated_at: str


class State(Model):
    schema_version: Literal[1] = 1
    revision: int = 0
    sources: list[Source] = Field(default_factory=list, max_length=200)


class Save(Model):
    revision: int = Field(ge=0)
    id: str = Field(default="", pattern=r"^([a-f0-9]{32})?$")
    source: SourceInput
    reviewed: Literal[True]


class Fetch(Model):
    url: str = Field(min_length=1, max_length=2000)


class Remove(Model):
    revision: int = Field(ge=0)
