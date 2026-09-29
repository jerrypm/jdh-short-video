"""Ephemeral, on-device Chrome companion broker. Never calls a cloud service."""

import hashlib
import json
import secrets
import threading
import time
from collections import OrderedDict
from typing import Literal
from uuid import UUID
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictStr

Availability = Literal["unavailable", "downloadable", "downloading", "available"]
Operation = Literal["hooks", "draft", "ideas", "storyboard", "editorial"]
TERMINAL = {"completed", "failed", "cancelled"}
MESSAGES = {
    "disconnected": "Companion Chrome terputus. Buka kembali tab companion lalu coba lagi.",
    "reloaded": "Companion dimuat ulang. Jalankan kembali permintaan AI.",
    "replaced": "Koneksi companion diganti. Jalankan kembali permintaan AI.",
    "timeout": "Nano belum selesai dalam dua menit. Coba naskah yang lebih pendek.",
    "cancelled": "Permintaan AI dibatalkan.",
    "generation_failed": "Nano gagal memproses naskah. Coba lagi dari editor.",
    "invalid_response": "Hasil Nano tidak sesuai format. Naskah Anda belum berubah.",
    "context_limit": "Naskah melebihi kapasitas model. Pendekkan naskah lalu coba lagi.",
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Generate(StrictModel):
    id: StrictStr = Field(pattern=r"^[a-f0-9-]{36}$")
    operation: Operation
    language: Literal["en"]
    input: StrictStr = Field(min_length=1, max_length=12000)


class Pair(StrictModel):
    code: StrictStr = Field(min_length=32, max_length=128)
    document_id: StrictStr = Field(pattern=r"^[a-f0-9-]{36}$")


class Poll(StrictModel):
    document_id: StrictStr = Field(pattern=r"^[a-f0-9-]{36}$")
    english: Availability
    indonesian: Availability
    progress: float = Field(default=0, ge=0, le=1, allow_inf_nan=False)
    accept_job: bool = True
    wait: bool = False
    running_id: StrictStr | None = Field(default=None, max_length=36)


class Finish(StrictModel):
    document_id: StrictStr = Field(pattern=r"^[a-f0-9-]{36}$")
    id: StrictStr = Field(pattern=r"^[a-f0-9-]{36}$")
    status: Literal["completed", "failed"]
    suggestions: list[StrictStr] | None = None
    ideas: list[dict] | None = None
    storyboard: dict | None = None
    editorial: dict | None = None
    error: (
        Literal[
            "generation_failed",
            "invalid_response",
            "context_limit",
            "cancelled",
            "timeout",
        ]
        | None
    ) = None


def valid_id(value):
    try:
        if str(UUID(value)) != value:
            raise ValueError
    except (ValueError, AttributeError):
        raise HTTPException(422, "ID permintaan tidak valid.")


def validate_suggestions(value, operation):
    count = 3 if operation == "hooks" else 1
    if not isinstance(value, list) or len(value) != count:
        raise ValueError("Jumlah saran tidak sesuai.")
    if any(
        not isinstance(text, str) or not text.strip() or len(text) > 3000
        for text in value
    ):
        raise ValueError("Teks saran tidak valid.")
    if len({text.strip().casefold() for text in value}) != count:
        raise ValueError("Saran berulang.")
    return value


class Broker:
    lease_seconds = 10
    request_seconds = 120
    retention_seconds = 600

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.RLock()
        self.pair_code = ""
        self.pair_until = 0
        self.token_hash = ""
        self.document_id = ""
        self.last_seen = None
        self.languages = {"en": "unavailable", "id": "unavailable"}
        self.progress = 0
        self.jobs = OrderedDict()
        self.active_id = None

    def _connected(self):
        return (
            self.last_seen is not None
            and self.clock() - self.last_seen <= self.lease_seconds
        )

    def _terminal(self, job, state, reason=None):
        job["status"] = state
        job["error"] = reason
        job["input"] = ""  # Source is only retained while it is needed by inference.
        if state != "completed":
            job["suggestions"] = None
            job["ideas"] = None
            job["storyboard"] = None
            job["editorial"] = None
        if self.active_id == job["id"]:
            self.active_id = None

    def _expire(self):
        now = self.clock()
        active = self.jobs.get(self.active_id)
        if active:
            if now >= active["deadline"]:
                self._terminal(active, "failed", "timeout")
            elif not self._connected():
                self._terminal(active, "failed", "disconnected")
        for key, job in list(self.jobs.items()):
            if (
                job["status"] in TERMINAL
                and now - job["created"] > self.retention_seconds
            ):
                del self.jobs[key]

    def _public(self, job):
        return {
            "id": job["id"],
            "operation": job["operation"],
            "status": job["status"],
            "suggestions": job.get("suggestions"),
            "ideas": job.get("ideas"),
            "storyboard": job.get("storyboard"),
            "editorial": job.get("editorial"),
            "error": job.get("error"),
            "message": MESSAGES.get(job.get("error"), ""),
        }

    def status(self):
        with self.lock:
            self._expire()
            connected = self._connected()
            return {
                "provider": "gemini-nano-local",
                "transport": "chrome-companion",
                "connected": connected,
                "availability": self.languages["en"] if connected else "unavailable",
                "languages": self.languages.copy()
                if connected
                else {"en": "unavailable", "id": "unavailable"},
                "busy": self.active_id is not None,
                "download_progress": self.progress if connected else 0,
                "message": "Gemini Nano lokal · English"
                if connected
                else "Hubungkan companion Chrome dari Setup.",
            }

    def issue_pair(self):
        with self.lock:
            self.pair_code = secrets.token_urlsafe(32)
            self.pair_until = self.clock() + 180
            return {"code": self.pair_code, "expires_in": 180}

    def pair(self, data):
        valid_id(data.document_id)
        with self.lock:
            if (
                not self.pair_code
                or self.clock() > self.pair_until
                or not secrets.compare_digest(data.code, self.pair_code)
            ):
                raise HTTPException(
                    403,
                    "Tautan kedaluwarsa atau sudah dipakai. Buat tautan baru di Setup.",
                )
            self.disconnect("replaced")
            token = secrets.token_urlsafe(32)
            self.token_hash = hashlib.sha256(token.encode()).hexdigest()
            self.document_id = data.document_id
            self.last_seen = self.clock()
            self.pair_code = ""
            return {"token": token}

    def authenticate(self, token):
        digest = hashlib.sha256(token.encode()).hexdigest()
        if not self.token_hash or not secrets.compare_digest(digest, self.token_hash):
            raise HTTPException(401, "Pasangkan kembali companion dari Setup aplikasi.")

    def disconnect(self, reason="disconnected"):
        with self.lock:
            active = self.jobs.get(self.active_id)
            if active:
                self._terminal(active, "failed", reason)
            self.token_hash = ""
            self.document_id = ""
            self.last_seen = None
            self.languages = {"en": "unavailable", "id": "unavailable"}
            self.progress = 0
            self.pair_code = ""

    def poll(self, token, data):
        valid_id(data.document_id)
        with self.lock:
            self.authenticate(token)
            self._expire()
            if self.document_id != data.document_id:
                active = self.jobs.get(self.active_id)
                if active:
                    self._terminal(active, "failed", "reloaded")
                self.document_id = data.document_id
            self.last_seen = self.clock()
            self.languages = {"en": data.english, "id": data.indonesian}
            self.progress = data.progress
            active = self.jobs.get(self.active_id)
            dispatch = None
            if active and active["status"] == "queued" and data.accept_job:
                active["status"] = "running"
                dispatch = {key: active[key] for key in ("id", "operation", "input")}
            return {
                "job": dispatch,
                "active_id": self.active_id,
                "request_timeout_ms": self.request_seconds * 1000,
            }

    def drop(self, token, document_id):
        with self.lock:
            if self.document_id == document_id:
                self.authenticate(token)
                self.last_seen = None
                self._expire()

    def enqueue(self, data):
        valid_id(data.id)
        if not data.input.strip():
            raise HTTPException(422, "Tulis naskah dahulu.")
        fingerprint = hashlib.sha256(data.model_dump_json().encode()).hexdigest()
        with self.lock:
            self._expire()
            if data.id in self.jobs:
                prior = self.jobs[data.id]
                if prior["fingerprint"] not in (None, fingerprint):
                    raise HTTPException(409, "ID permintaan sudah digunakan.")
                return self._public(prior)
            if not self._connected():
                raise HTTPException(409, MESSAGES["disconnected"])
            if self.languages["en"] != "available":
                raise HTTPException(
                    409, "Siapkan model lokal pada tab companion terlebih dahulu."
                )
            if self.active_id:
                raise HTTPException(409, "Nano masih memproses permintaan lain.")
            if len(self.jobs) >= 32:
                raise HTTPException(429, "Terlalu banyak permintaan. Tunggu sebentar.")
            job = {
                "id": data.id,
                "operation": data.operation,
                "input": data.input,
                "status": "queued",
                "created": self.clock(),
                "deadline": self.clock() + self.request_seconds,
                "fingerprint": fingerprint,
                "suggestions": None,
                "error": None,
            }
            self.jobs[data.id] = job
            self.active_id = data.id
            return self._public(job)

    def read(self, request_id):
        valid_id(request_id)
        with self.lock:
            self._expire()
            if request_id not in self.jobs:
                raise HTTPException(
                    404, "Permintaan AI tidak ditemukan atau telah kedaluwarsa."
                )
            return self._public(self.jobs[request_id])

    def cancel(self, request_id):
        valid_id(request_id)
        with self.lock:
            self._expire()
            if request_id not in self.jobs:
                if len(self.jobs) >= 32:
                    raise HTTPException(429, "Terlalu banyak permintaan.")
                # A cancellation arriving before its POST must prevent late execution.
                self.jobs[request_id] = {
                    "id": request_id,
                    "operation": None,
                    "fingerprint": None,
                    "created": self.clock(),
                    "suggestions": None,
                }
            job = self.jobs[request_id]
            if job.get("status") != "completed":
                self._terminal(job, "cancelled", "cancelled")
            return self._public(job)

    def finish(self, token, data):
        with self.lock:
            self.authenticate(token)
            self._expire()
            job = self.jobs.get(data.id)
            if (
                data.document_id != self.document_id
                or not job
                or job["status"] != "running"
            ):
                raise HTTPException(409, "Hasil dari permintaan lama ditolak.")
            if data.status == "completed":
                try:
                    if job["operation"] == "editorial":
                        from .quality_contract import validate_editorial

                        if any(
                            v is not None
                            for v in (data.suggestions, data.ideas, data.storyboard)
                        ):
                            raise ValueError("Unexpected output")
                        job["editorial"] = validate_editorial(
                            data.editorial, json.loads(job["input"])
                        ).model_dump()
                    elif data.editorial is not None:
                        raise ValueError("Unexpected editorial")
                    elif job["operation"] == "storyboard":
                        from .storyboard_contract import validate_draft

                        if data.suggestions is not None or data.ideas is not None:
                            raise ValueError("Unexpected output")
                        job["storyboard"] = validate_draft(
                            data.storyboard, json.loads(job["input"])
                        ).model_dump()
                    elif data.storyboard is not None:
                        raise ValueError("Unexpected storyboard")
                    elif job["operation"] == "ideas":
                        from .idea_contract import validate_ideas

                        context = json.loads(job["input"])
                        job["ideas"] = validate_ideas(
                            data.ideas,
                            [r["project_id"] for r in context["history"]["references"]],
                            context.get("performance", {}).get("rows", []),
                            context.get("research", {}).get("sources", []),
                            context.get("source_mode", "history"),
                        )
                        if data.suggestions is not None:
                            raise ValueError("Unexpected suggestions")
                    else:
                        if data.ideas is not None:
                            raise ValueError("Unexpected ideas")
                        job["suggestions"] = validate_suggestions(
                            data.suggestions, job["operation"]
                        )
                except ValueError:
                    self._terminal(job, "failed", "invalid_response")
                    raise HTTPException(422, MESSAGES["invalid_response"])
                self._terminal(job, "completed")
            else:
                self._terminal(
                    job,
                    "cancelled" if data.error == "cancelled" else "failed",
                    data.error or "generation_failed",
                )
            return {"accepted": True}


broker = Broker()
