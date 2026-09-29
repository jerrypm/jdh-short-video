"""Ephemeral reviewed proposals; atomic project writes use the existing repository."""

from collections import OrderedDict
import hashlib
import json
import time
from uuid import uuid4
from fastapi import HTTPException
from . import (
    repository as repo,
    nano,
    jobs,
    content_memory as memory,
    daily_ideas_store as ideas,
    research,
    research_store,
)
from .content_memory_models import Retrieve
from .models import Project, Scene, ScenePlan
from .storyboard_contract import validate_draft


class Service:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.entries = OrderedDict()

    def expire(self):
        for key, entry in list(self.entries.items()):
            if self.clock() - entry["created"] > 900:
                if nano.broker.active_id == key:
                    nano.broker.cancel(key)
                del self.entries[key]

    def idea(self, card_id=None):
        catalog = memory.operate()
        with memory.transaction() as connection:
            state = ideas.read(connection)
            research_state = research_store.read(connection)
        found = {}
        for batch in state.batches:
            if not research.current(research_state, batch):
                continue
            for card in batch.cards:
                found[card.id] = (card, batch.language)
        for feedback in state.feedback:
            if not research.current(research_state, feedback) or (
                feedback.source_mode == "history"
                and feedback.performance_revision != state.performance_revision
            ):
                continue
            found[feedback.card.id] = (feedback.card, feedback.language)
        if card_id is None:
            return catalog, [
                {"card": card, "language": language}
                for card, language in found.values()
            ]
        if card_id not in found:
            raise HTTPException(
                409,
                "Ide atau referensinya sudah berubah. Pilih ide yang masih tersedia.",
            )
        card, language = found[card_id]
        if language != "en":
            raise ValueError("Storyboard Nano lokal saat ini hanya mendukung English.")
        return catalog, card

    def context(self, project, catalog, card):
        # Only selected catalogue references and registered assets are described to Nano.
        context = memory.retrieve(Retrieve(language="en", max_chars=4500), catalog)
        required = set(card.source_project_ids)
        # Keep cited sources even when ranking would select a different group.
        if required:
            subset = catalog.model_copy(deep=True)
            subset.references = [
                r for r in catalog.references if r.project_id in required
            ]
            cited = memory.retrieve(Retrieve(language="en", max_chars=6000), subset)
            if {r["project_id"] for r in cited["references"]} != required:
                raise ValueError(
                    "Sumber ide melebihi batas konteks. Pilih ide dengan referensi lebih ringkas."
                )
            context = cited
        assets, transcripts = [], {}
        for asset in project.assets:
            if not repo.asset_path(project, asset.id).is_file():
                continue
            if len(assets) >= 20:
                break
            assets.append(
                {
                    "id": asset.id,
                    "name": asset.name[:100],
                    "kind": asset.kind,
                    "frames": asset.frames,
                    "has_audio": asset.has_audio,
                }
            )
            known = list(
                dict.fromkeys(
                    s.audio_text
                    for s in project.scenes
                    if s.audio_id == asset.id
                    and s.audio_in == 0
                    and s.audio_text
                    and s.audio_text == s.narration
                    and len(s.audio_text) <= 1500
                )
            )
            if known:
                transcripts[asset.id] = known[:1]
        value = {
            "idea": card.model_dump(),
            "references": context["references"],
            "profile": context["profile"],
            "target_seconds": project.target,
            "assets": assets,
            "audio_transcripts": transcripts,
            "capabilities": {
                "fps": 30,
                "effects": ["static"],
                "motion_version": 1,
                "motion_mode": project.motion_mode,
                "motion_presets": [
                    "none",
                    "zoom_in",
                    "zoom_out",
                    "pan_left",
                    "pan_right",
                    "pan_up",
                    "pan_down",
                ],
                "text_presets": ["none", "fade", "slide_up"],
                "transitions": ["cut"],
                "max_scene_frames": 1800,
                "max_total_frames": 5400,
            },
        }
        # Remove whole optional asset entries rather than truncating IDs or JSON.
        while len(json.dumps(value, ensure_ascii=False)) > 12000 and value["assets"]:
            dropped = value["assets"].pop()
            value["audio_transcripts"].pop(dropped["id"], None)
        if len(json.dumps(value, ensure_ascii=False)) > 12000:
            raise ValueError(
                "Konteks ide terlalu panjang. Ringkas label memori sebelum menyusun draft."
            )
        return value

    def start(self, pid, data):
        nano.valid_id(data.id)
        with repo.LOCK:
            self.expire()
            if data.id in self.entries:
                entry = self.entries[data.id]
                if (entry["project_id"], entry["idea_id"], entry["base_revision"]) != (
                    pid,
                    data.idea_id,
                    data.base_revision,
                ):
                    raise HTTPException(
                        409, "ID permintaan sudah dipakai untuk konteks lain."
                    )
                return self.read(pid, data.id)
            project = repo.load(pid)
            if project.revision != data.base_revision:
                raise RuntimeError(
                    "Proyek berubah; simpan dan muat ulang sebelum membuat proposal."
                )
            if project.language != "en":
                raise ValueError(
                    "Storyboard Nano lokal saat ini hanya mendukung proyek English."
                )
            with jobs.LOCK:
                if any(
                    job.status in {"queued", "running"} for job in jobs.JOBS.values()
                ):
                    raise RuntimeError(
                        "Tunggu render atau narasi selesai sebelum menyusun storyboard."
                    )
            if len(self.entries) >= 12:
                raise HTTPException(
                    429,
                    "Maksimal 12 proposal per 15 menit. Tunggu proposal lama kedaluwarsa.",
                )
            catalog, card = self.idea(data.idea_id)
            context = self.context(project, catalog, card)
            result = nano.broker.enqueue(
                nano.Generate(
                    id=data.id,
                    operation="storyboard",
                    language="en",
                    input=json.dumps(context, ensure_ascii=False),
                )
            )
            self.entries[data.id] = {
                "project_id": pid,
                "idea_id": data.idea_id,
                "base_revision": project.revision,
                "catalog_revision": catalog.revision,
                "created": self.clock(),
                "context": context,
                "draft": None,
                "status": result["status"],
                "message": result["message"],
                "applied": None,
            }
            return self.read(pid, data.id)

    def entry(self, pid, request_id):
        self.expire()
        entry = self.entries.get(request_id)
        if not entry or entry["project_id"] != pid:
            raise HTTPException(
                404,
                "Proposal tidak tersedia; buat ulang setelah aplikasi dibuka kembali.",
            )
        return entry

    def fresh(self, entry):
        project = repo.load(entry["project_id"])
        catalog, _ = self.idea(entry["idea_id"])
        if (
            project.revision != entry["base_revision"]
            or catalog.revision != entry["catalog_revision"]
        ):
            raise RuntimeError(
                "Proyek atau memori berubah sejak proposal dibuat. Buat proposal baru."
            )
        for asset in entry["context"]["assets"]:
            if not repo.asset_path(project, asset["id"]).is_file():
                raise RuntimeError(
                    "File media sumber tidak tersedia. Periksa media dan buat proposal baru."
                )
        return project

    def read(self, pid, request_id):
        with repo.LOCK:
            entry = self.entry(pid, request_id)
            if entry["applied"] is None and entry["status"] not in {
                "failed",
                "cancelled",
            }:
                try:
                    self.fresh(entry)
                except (RuntimeError, ValueError, HTTPException, OSError):
                    nano.broker.cancel(request_id)
                    entry.update(
                        status="failed",
                        draft=None,
                        message="Proyek, referensi, atau media berubah; buat proposal baru.",
                    )
                else:
                    if entry["draft"] is None:
                        result = nano.broker.read(request_id)
                        entry.update(status=result["status"], message=result["message"])
                        if result["status"] == "completed":
                            try:
                                entry["draft"] = validate_draft(
                                    result["storyboard"], entry["context"]
                                ).model_dump()
                            except ValueError:
                                entry.update(
                                    status="failed",
                                    message="Proposal tidak valid; proyek tetap utuh.",
                                )
            return {
                "id": request_id,
                "project_id": pid,
                "base_revision": entry["base_revision"],
                "catalog_revision": entry["catalog_revision"],
                "status": entry["status"],
                "message": entry["message"],
                "draft": entry["draft"],
                "sources": entry["context"]["references"],
                "assets": entry["context"]["assets"],
                "expires_in": max(0, int(900 - (self.clock() - entry["created"]))),
            }

    def candidate(self, entry, data):
        if entry["status"] != "completed" or entry["draft"] is None:
            raise RuntimeError("Proposal belum siap untuk ditinjau.")
        project = self.fresh(entry)
        draft = validate_draft(data.draft.model_dump(), entry["context"])
        if any(i >= len(draft.scenes) for i in data.selected):
            raise ValueError("Pilihan scene tidak ada dalam proposal.")
        assets = {asset.id: asset for asset in project.assets}
        scenes, plan = [], []
        for index in sorted(data.selected):
            scene = draft.scenes[index]
            duration = max(
                scene.estimated_frames,
                assets[scene.audio_id].frames if scene.audio_id else 0,
            )
            scenes.append(
                Scene(
                    id=uuid4().hex,
                    name=scene.name,
                    narration=scene.narration,
                    caption=scene.caption,
                    duration=duration,
                    media_id=scene.media_id,
                    audio_id=scene.audio_id,
                    audio_text=scene.narration if scene.audio_id else "",
                    motion=scene.motion,
                    planning=ScenePlan(
                        visual_need=scene.visual_need,
                        motion_intent=scene.motion_intent,
                        estimated_frames=scene.estimated_frames,
                        source_revisions={
                            r["project_id"]: r["source_revision"]
                            for r in entry["context"]["references"]
                            if r["project_id"] in scene.source_project_ids
                        },
                    ),
                )
            )
            plan.append(
                {
                    "index": index,
                    "frames": duration,
                    "estimated_frames": scene.estimated_frames,
                    "duration_origin": "measured_audio"
                    if scene.audio_id
                    else "estimate",
                    "media_missing": scene.media_id is None,
                }
            )
        proposal_script = "\n\n".join(s.narration for s in scenes)
        candidate = project.model_copy(deep=True)
        candidate.scenes = (project.scenes if data.mode == "append" else []) + scenes
        candidate.script = "\n\n".join(
            filter(
                None, [project.script if data.mode == "append" else "", proposal_script]
            )
        )
        candidate = Project.model_validate(candidate.model_dump())
        return candidate, {
            "mode": data.mode,
            "added_scenes": len(scenes),
            "removed_scenes": len(project.scenes) if data.mode == "replace" else 0,
            "old_frames": sum(s.duration for s in project.scenes),
            "total_frames": sum(s.duration for s in candidate.scenes),
            "missing_media": sum(s.media_id is None for s in scenes),
            "plan": plan,
            "exceeds_target": sum(s.duration for s in candidate.scenes)
            > project.target * 30,
        }

    def preview(self, pid, request_id, data):
        with repo.LOCK:
            _, summary = self.candidate(self.entry(pid, request_id), data)
            return summary

    def apply(self, pid, request_id, data):
        fingerprint = hashlib.sha256(data.model_dump_json().encode()).hexdigest()
        with repo.LOCK:
            entry = self.entry(pid, request_id)
            if entry["applied"]:
                project = repo.load(pid)
                if entry["applied"] != (fingerprint, project.revision):
                    raise RuntimeError(
                        "Proposal sudah diterapkan atau proyek berubah; muat ulang proyek."
                    )
                return project
            project, _ = self.candidate(entry, data)
            saved = repo.save(project, expected=entry["base_revision"])
            entry["applied"] = (fingerprint, saved.revision)
            return saved

    def cancel(self, pid, request_id):
        nano.valid_id(request_id)
        with repo.LOCK:
            entry = self.entries.get(request_id)
            if entry and entry["project_id"] != pid:
                raise HTTPException(404, "Proposal tidak ditemukan.")
            nano.broker.cancel(request_id)
            if entry and entry["applied"] is None:
                entry.update(
                    status="cancelled",
                    draft=None,
                    message="Proposal dibatalkan; proyek tetap utuh.",
                )
            return {"cancelled": True}

    def defer(self):
        with repo.LOCK, nano.broker.lock:
            job = nano.broker.jobs.get(nano.broker.active_id)
            if job and job.get("operation") == "storyboard":
                nano.broker.cancel(job["id"])


service = Service()
