"""Cache-first daily suggestions through the existing local Nano broker only."""

from datetime import datetime, timezone
import hashlib
import json
import math
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import HTTPException
from . import content_memory as memory, daily_ideas_store as store, jobs, nano
from . import repository as repo, performance, research, research_store
from .content_memory_models import Retrieve
from .idea_contract import validate_ideas


def zone(name):
    try:
        if len(name) > 100:
            raise ValueError
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        raise HTTPException(422, "Zona waktu tidak valid.")


class Service:
    def __init__(self, clock=lambda: datetime.now(timezone.utc)):
        self.clock = clock
        self.owner = uuid4().hex
        self.editors = {}

    def busy(self):
        now = self.clock().timestamp()
        self.editors = {
            key: until for key, until in self.editors.items() if until > now
        }
        with jobs.LOCK:
            return bool(self.editors) or any(
                j.status in {"queued", "running"} for j in jobs.JOBS.values()
            )

    def context(self, catalog, state):
        if state.preferences.source_mode == "research":
            return {
                "references": [],
                "instruction": "Research mode; no project history or performance included.",
            }
        return memory.retrieve(
            Retrieve(language=state.preferences.language, max_chars=5000), catalog
        )

    def cache_key(self, catalog, state, timezone_name):
        date = self.clock().astimezone(zone(timezone_name)).date().isoformat()
        key = hashlib.sha256(
            json.dumps(
                {
                    "date": date,
                    "timezone": timezone_name,
                    "profile": catalog.profile.model_dump()
                    if state.preferences.source_mode == "history"
                    else None,
                    "catalog": catalog.revision
                    if state.preferences.source_mode == "history"
                    else None,
                    "preferences": state.preferences.model_dump(),
                    "feedback": state.feedback_revision,
                    "performance": state.performance_revision
                    if state.preferences.source_mode == "history"
                    else None,
                    "research": state.research_revision
                    if state.preferences.source_mode == "research"
                    else None,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()
        return date, key

    def end(self, state, status, message):
        if not state.active:
            return
        for attempt in state.attempts:
            if attempt.id == state.active.id:
                attempt.status, attempt.message = status, message
        state.active = None

    def reconcile(self, state, catalog, timezone_name):
        active = state.active
        if not active:
            return
        _, key = self.cache_key(catalog, state, timezone_name)
        if active.owner != self.owner:
            if nano.broker.active_id == active.id:
                nano.broker.cancel(active.id)
            self.end(
                state,
                "failed",
                "Aplikasi dibuka ulang; permintaan lama tidak dijalankan ulang.",
            )
            return
        if active.key != key or self.busy():
            nano.broker.cancel(active.id)
            self.end(
                state,
                "cancelled",
                "Konteks berubah atau editor/render aktif; buat ide lagi dari beranda.",
            )
            return
        try:
            result = nano.broker.read(active.id)
        except HTTPException:
            self.end(
                state,
                "failed",
                "Permintaan ide sudah kedaluwarsa. Coba lagi secara manual.",
            )
            return
        if result["status"] == "completed":
            try:
                ideas = validate_ideas(
                    result["ideas"],
                    active.sources,
                    active.performance,
                    active.research,
                    active.source_mode,
                )
            except ValueError:
                self.end(
                    state,
                    "failed",
                    "Hasil Nano tidak valid; cache sebelumnya tetap tersedia.",
                )
                return
            batch = store.Batch(
                id=active.id,
                key=key,
                date=active.date,
                timezone=active.timezone,
                language=active.language,
                created_at=self.clock().isoformat(),
                sources=active.sources,
                performance_revision=active.performance_revision,
                research_revision=active.research_revision,
                source_mode=active.source_mode,
                cards=[store.Card(id=uuid4().hex, **idea) for idea in ideas],
            )
            state.batches = (state.batches + [batch])[-14:]
            self.end(state, "completed", "Tiga ide lokal siap ditinjau.")
        elif result["status"] in nano.TERMINAL:
            self.end(state, result["status"], result["message"])

    def view(self, state, catalog, timezone_name, connection):
        date, key = self.cache_key(catalog, state, timezone_name)
        context = self.context(catalog, state)
        provider = nano.broker.status()
        busy = self.busy()
        onboarding = not (
            context["references"]
            or state.preferences.topic.strip()
            or catalog.profile.description.strip()
            or catalog.profile.themes
        )
        research_state = research_store.read(connection)
        research_context = (
            research.context(connection, self.clock().date())
            if state.preferences.source_mode == "research"
            else {"sources": []}
        )
        if state.preferences.source_mode == "research":
            onboarding = not research_context["sources"]
        candidates = [
            b
            for b in state.batches
            if b.language == state.preferences.language
            and b.source_mode == state.preferences.source_mode
            and research.current(research_state, b, self.clock().date())
        ]
        batch = next(
            (b for b in reversed(candidates) if b.key == key),
            candidates[-1] if candidates else None,
        )
        elapsed = (
            (
                self.clock() - datetime.fromisoformat(state.attempts[-1].created_at)
            ).total_seconds()
            if state.attempts
            else 86400
        )
        retry_after = max(0, math.ceil(30 - elapsed))
        ready = (
            provider["connected"]
            and provider["languages"].get(state.preferences.language) == "available"
            and state.preferences.language == "en"
        )
        auto_due = (
            state.preferences.source_mode == "history"
            and state.preferences.mode == "daily"
            and not any(
                a.date == date and a.timezone == timezone_name for a in state.attempts
            )
            and elapsed >= 900
            and not (batch and batch.key == key)
        )
        can_generate = (
            ready
            and not onboarding
            and not busy
            and not provider["busy"]
            and not state.active
            and not retry_after
        )
        message = state.attempts[-1].message if state.attempts else ""
        if onboarding:
            message = (
                "Tambahkan sumber riset yang masih baru dan sudah ditinjau; sumber lama/konflik tidak dipakai."
                if state.preferences.source_mode == "research"
                else "Pilih referensi di Memori atau isi topik channel untuk memulai."
            )
        elif busy:
            message = "Ide ditunda selama editor, preview, atau render aktif."
        elif not ready:
            message = (
                "Bahasa Indonesia belum tersedia di jalur Nano lokal ini; pilih English atau gunakan panduan manual."
                if state.preferences.language == "id"
                else "Hubungkan dan siapkan Gemini Nano lokal melalui Setup untuk ide baru."
            )
        elif provider["busy"] and not state.active:
            message = "Nano sedang digunakan. Ide akan menunggu sampai model bebas."
        return {
            "preferences": state.preferences,
            "settings_revision": state.settings_revision,
            "date": date,
            "timezone": timezone_name,
            "batch": batch,
            "stale": bool(batch and batch.key != key),
            "feedback": [
                {
                    **f.model_dump(),
                    "performance_stale": f.source_mode == "history"
                    and f.performance_revision != state.performance_revision,
                    "research_stale": not research.current(
                        research_state, f, self.clock().date()
                    ),
                }
                for f in state.feedback
            ],
            "performance_evidence": performance.cited_evidence(
                connection,
                catalog,
                (batch.cards if batch else [])
                + [
                    f.card
                    for f in state.feedback
                    if f.performance_revision == state.performance_revision
                ],
            ),
            "research_evidence": research.evidence(
                connection,
                (batch.cards if batch else []) + [f.card for f in state.feedback],
            ),
            "research_source_count": len(research_context["sources"]),
            "active_id": state.active.id if state.active else None,
            "message": message,
            "provider": provider,
            "onboarding": onboarding,
            "source_count": len(context["references"]),
            "can_generate": bool(can_generate),
            "auto_due": bool(auto_due),
            "retry_after": retry_after,
            "source_names": {
                r.project_id: r.observed.name
                for r in catalog.references
                if r.included and not r.missing and r.category == "content"
            },
        }

    def status(self, timezone_name):
        zone(timezone_name)
        with repo.LOCK:
            catalog = memory.operate()
            with memory.transaction() as connection:
                state = store.read(connection)
                before = state.model_dump_json()
                self.reconcile(state, catalog, timezone_name)
                if state.model_dump_json() != before:
                    store.write(connection, state)
                return self.view(state, catalog, timezone_name, connection)

    def start(self, request_id, timezone_name, automatic):
        try:
            return self._start(request_id, timezone_name, automatic)
        except Exception:
            with nano.broker.lock:
                job = nano.broker.jobs.get(request_id)
                if (
                    job
                    and job.get("operation") == "ideas"
                    and job.get("status") not in nano.TERMINAL
                ):
                    nano.broker.cancel(request_id)
            raise

    def _start(self, request_id, timezone_name, automatic):
        nano.valid_id(request_id)
        zone(timezone_name)
        with repo.LOCK:
            catalog = memory.operate()
            with memory.transaction() as connection:
                state = store.read(connection)
                self.reconcile(state, catalog, timezone_name)
                current = self.view(state, catalog, timezone_name, connection)
                if (
                    any(a.id == request_id for a in state.attempts)
                    or state.active
                    or not current["can_generate"]
                    or (automatic and not current["auto_due"])
                ):
                    store.write(connection, state)
                    return current
                context = self.context(catalog, state)
                measurements = performance.context(
                    connection, {r["project_id"] for r in context["references"]}
                )
                research_context = (
                    research.context(connection, self.clock().date())
                    if state.preferences.source_mode == "research"
                    else {"sources": []}
                )
                if state.preferences.source_mode == "research":
                    measurements = {"rows": []}
                research_state = research_store.read(connection)
                recent = [
                    {
                        "title": f.card.title,
                        "concept": f.card.concept[:200],
                        "verdict": f.verdict,
                        "reason": f.reason[:150],
                    }
                    for f in state.feedback[-4:]
                    if f.source_mode == state.preferences.source_mode
                    and (
                        f.source_mode == "research"
                        and research.current(research_state, f, self.clock().date())
                        or f.source_mode == "history"
                        and f.performance_revision == state.performance_revision
                    )
                ]
                prompt = json.dumps(
                    {
                        "history": context,
                        "performance": measurements,
                        "research": research_context,
                        "source_mode": state.preferences.source_mode,
                        "preferences": state.preferences.model_dump(),
                        "recent_feedback": recent,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                date, key = self.cache_key(catalog, state, timezone_name)
                active = store.Active(
                    research=research_context["sources"],
                    research_revision=state.research_revision,
                    source_mode=state.preferences.source_mode,
                    performance=measurements["rows"],
                    performance_revision=state.performance_revision,
                    id=request_id,
                    owner=self.owner,
                    key=key,
                    date=date,
                    timezone=timezone_name,
                    language=state.preferences.language,
                    sources={
                        r["project_id"]: r["source_revision"]
                        for r in context["references"]
                    },
                )
                # Persist before enqueue; if enqueue fails, transaction rolls back. Never store raw prompts.
                state.active = active
                state.attempts = (
                    state.attempts
                    + [
                        store.Attempt(
                            id=request_id,
                            key=key,
                            date=date,
                            timezone=timezone_name,
                            created_at=self.clock().isoformat(),
                        )
                    ]
                )[-60:]
                store.write(connection, state)
                try:
                    result = nano.broker.enqueue(
                        nano.Generate(
                            id=request_id,
                            operation="ideas",
                            language="en",
                            input=prompt,
                        )
                    )
                    if result["status"] in nano.TERMINAL:
                        self.end(state, result["status"], result["message"])
                        store.write(connection, state)
                except Exception:
                    nano.broker.cancel(request_id)
                    raise
                return self.view(state, catalog, timezone_name, connection)

    def cancel(self, request_id, timezone_name):
        nano.valid_id(request_id)
        with repo.LOCK, memory.transaction() as connection:
            state = store.read(connection)
            if state.active and state.active.id == request_id:
                nano.broker.cancel(request_id)
                self.end(
                    state,
                    "cancelled",
                    "Pembuatan ide dibatalkan; ide tersimpan tetap tersedia.",
                )
                store.write(connection, state)
            elif not any(a.id == request_id for a in state.attempts):
                # Cancel-before-POST is remembered by the shared broker.
                nano.broker.cancel(request_id)
        return self.status(timezone_name)

    def defer(self):
        with repo.LOCK:
            # Media work has priority even if the optional idea database is damaged.
            with nano.broker.lock:
                job = nano.broker.jobs.get(nano.broker.active_id)
                if job and job.get("operation") == "ideas":
                    nano.broker.cancel(job["id"])
            try:
                with memory.transaction() as connection:
                    state = store.read(connection)
                    if state.active:
                        self.end(
                            state,
                            "cancelled",
                            "Pembuatan ide ditunda karena editor atau render dibuka.",
                        )
                        store.write(connection, state)
            except RuntimeError:
                # The home API reports the storage error; rendering still remains usable.
                pass

    def activity(self, client_id, editing):
        nano.valid_id(client_id)
        with repo.LOCK:
            if editing:
                self.editors[client_id] = self.clock().timestamp() + 15
                self.defer()
            else:
                self.editors.pop(client_id, None)
        return {"accepted": True}

    def preferences(self, preferences, revision, timezone_name):
        zone(timezone_name)
        with repo.LOCK, memory.transaction() as connection:
            state = store.read(connection)
            if state.settings_revision != revision:
                raise RuntimeError("Preferensi berubah. Muat ulang sebelum menyimpan.")
            if state.preferences != preferences:
                if state.active:
                    nano.broker.cancel(state.active.id)
                    self.end(
                        state,
                        "cancelled",
                        "Preferensi berubah; buat ide baru saat siap.",
                    )
                state.preferences = preferences
                state.settings_revision += 1
                store.write(connection, state)
        return self.status(timezone_name)

    def feedback(self, card_id, verdict, reason, timezone_name):
        zone(timezone_name)
        with repo.LOCK:
            memory.operate()  # Validate provenance again before saving any card.
            with memory.transaction() as connection:
                state = store.read(connection)
                prior = next((f for f in state.feedback if f.card.id == card_id), None)
                batch = next(
                    (b for b in state.batches if any(c.id == card_id for c in b.cards)),
                    None,
                )
                if not prior and not batch:
                    raise HTTPException(
                        404, "Ide tidak tersedia atau referensinya berubah."
                    )
                card = (
                    prior.card
                    if prior
                    else next(c for c in batch.cards if c.id == card_id)
                )
                remaining = [f for f in state.feedback if f.card.id != card_id]
                if verdict != "none":
                    if (
                        verdict == "saved"
                        and sum(f.verdict == "saved" for f in remaining) >= 30
                    ):
                        raise ValueError(
                            "Maksimal 30 ide tersimpan; lepaskan ide lama dahulu."
                        )
                    remaining.append(
                        store.Feedback(
                            card=card,
                            source_mode=prior.source_mode
                            if prior
                            else batch.source_mode,
                            research_revision=prior.research_revision
                            if prior
                            else batch.research_revision,
                            sources=prior.sources if prior else batch.sources,
                            performance_revision=prior.performance_revision
                            if prior
                            else batch.performance_revision,
                            verdict=verdict,
                            reason=reason.strip(),
                            language=prior.language if prior else batch.language,
                            created_at=self.clock().isoformat(),
                        )
                    )
                saved = [f for f in remaining if f.verdict == "saved"]
                skipped = [f for f in remaining if f.verdict == "skipped"][-60:]
                state.feedback = sorted(saved + skipped, key=lambda f: f.created_at)
                state.feedback_revision += 1
                if state.active:
                    nano.broker.cancel(state.active.id)
                    self.end(
                        state,
                        "cancelled",
                        "Catatan ide berubah; buat ide baru saat siap.",
                    )
                store.write(connection, state)
        return self.status(timezone_name)


service = Service()
