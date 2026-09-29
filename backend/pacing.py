"""Measured local timing proposals. Silence is reported, never removed.

No model or transcriber is involved. All offsets are relative to the retained
audio after the user's existing audio_in, not word-level alignment.
"""

from array import array
from collections import OrderedDict
from dataclasses import dataclass
import math
import subprocess
import sys
import threading
import time
from uuid import uuid4
from pydantic import Field
from . import captions, media, repository as repo
from .models import Project, StrictModel


class Start(StrictModel):
    revision: int = Field(ge=0, strict=True)


class Edit(StrictModel):
    scene_id: str = Field(min_length=1, max_length=64)
    duration: int = Field(ge=9, le=1800, strict=True)
    caption: str = Field(max_length=400)


class Selection(StrictModel):
    edits: list[Edit] = Field(min_length=1, max_length=60)


def measure(path, audio_in: int, timeout: float = 10) -> dict:
    if not media.FFMPEG:
        raise ValueError("FFmpeg lokal belum tersedia.")
    try:
        decoded = subprocess.run(
            [
                media.FFMPEG,
                "-v",
                "error",
                "-nostdin",
                "-threads",
                "1",
                "-ss",
                str(audio_in / 30),
                "-protocol_whitelist",
                "file,pipe",
                "-i",
                str(path),
                "-t",
                "61",
                "-vn",
                "-ac",
                "2",
                "-ar",
                "16000",
                "-f",
                "s16le",
                "pipe:1",
            ],
            capture_output=True,
            check=True,
            timeout=timeout,
        ).stdout
    except (subprocess.SubprocessError, OSError) as error:
        raise ValueError(
            "Audio tidak dapat diukur. Periksa file lalu coba lagi."
        ) from error
    samples = array("h")
    samples.frombytes(decoded)
    if sys.byteorder != "little":
        samples.byteswap()
    count = len(samples) // 2
    if not count:
        raise ValueError("Tidak ada audio setelah titik trim narasi.")
    if count > 60 * 16000:
        raise ValueError(
            "Sisa narasi melebihi 60 detik. Gunakan audio per scene yang lebih pendek."
        )
    # 10 ms peak windows, either channel. RMS/mono downmix can hide quiet
    # syllables or phase-inverted stereo. Detection is advisory only.
    silence, start = [], None
    for offset in range(0, count, 160):
        end = min(count, offset + 160)
        quiet = max(abs(sample) for sample in samples[offset * 2 : end * 2]) <= 327
        if quiet and start is None:
            start = offset
        if not quiet and start is not None:
            if offset - start >= 4000:
                silence.append((start, offset))
            start = None
    if start is not None and count - start >= 4000:
        silence.append((start, count))
    intervals = [
        {
            "start_seconds": round(a / 16000, 4),
            "end_seconds": round(b / 16000, 4),
            "kind": "entire"
            if a == 0 and b == count
            else "leading"
            if a == 0
            else "trailing"
            if b == count
            else "internal",
        }
        for a, b in silence
    ]
    return {
        "seconds": round(count / 16000, 6),
        "frames": math.ceil(count * 30 / 16000),
        "silences": intervals,
        "threshold_dbfs": -40,
        "window_ms": 10,
        "minimum_silence_ms": 250,
    }


def signatures(project: Project) -> dict:
    result = {}
    for aid in {s.audio_id for s in project.scenes} | {
        s.media_id for s in project.scenes
    }:
        if aid:
            try:
                stat = repo.asset_path(project, aid).stat()
                result[aid] = (stat.st_ino, stat.st_size, stat.st_mtime_ns)
            except (ValueError, FileNotFoundError):
                result[aid] = None
    return result


@dataclass
class Proposal:
    project: Project
    files: dict
    rows: list[dict]
    created: float
    receipt: str | None = None
    result: Project | None = None


class Service:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.proposals: OrderedDict[str, Proposal] = OrderedDict()
        self.worker = threading.Lock()

    def analyze(self, pid: str, data: Start):
        if not self.worker.acquire(blocking=False):
            raise RuntimeError(
                "Analisis audio sedang berjalan. Coba lagi setelah selesai."
            )
        try:
            with repo.LOCK:
                project = repo.load(pid)
                if project.revision != data.revision:
                    raise RuntimeError("Proyek berubah. Simpan lalu analisis ulang.")
                if not project.scenes:
                    raise ValueError("Tambahkan scene terlebih dahulu.")
                files = signatures(project)
            rows, cache = [], {}
            deadline = time.monotonic() + 45
            assets = {asset.id: asset for asset in project.assets}
            for scene in project.scenes:
                audio, errors, warnings = None, [], []
                minimum = 9
                if scene.audio_id:
                    asset = assets.get(scene.audio_id)
                    if (
                        not asset
                        or asset.kind != "audio"
                        or files.get(scene.audio_id) is None
                    ):
                        errors.append("File narasi tidak tersedia.")
                    else:
                        key = (scene.audio_id, scene.audio_in)
                        if key not in cache:
                            if time.monotonic() >= deadline:
                                raise RuntimeError(
                                    "Batas waktu analisis tercapai. Kurangi jumlah audio lalu coba lagi."
                                )
                            try:
                                cache[key] = measure(
                                    repo.asset_path(project, scene.audio_id),
                                    scene.audio_in,
                                    min(10, deadline - time.monotonic()),
                                )
                            except ValueError as error:
                                cache[key] = str(error)
                        if isinstance(cache[key], str):
                            errors.append(cache[key])
                        else:
                            audio = cache[key]
                            minimum = max(
                                9, audio["frames"], asset.frames - scene.audio_in
                            )
                            if scene.audio_text != scene.narration:
                                warnings.append(
                                    "Teks narasi berubah sejak audio dibuat; timing ini mengikuti file audio."
                                )
                            if scene.audio_in:
                                warnings.append(
                                    "Titik trim audio yang sudah ada dipertahankan; periksa awal ucapan secara manual."
                                )
                else:
                    warnings.append(
                        "Belum ada file narasi; durasi ucapan belum dapat diukur."
                    )
                duration = max(scene.duration, minimum)
                if duration > 1800:
                    errors.append("Durasi melebihi batas 60 detik per scene.")
                visual = assets.get(scene.media_id)
                if (
                    visual
                    and visual.kind == "video"
                    and scene.source_in + duration > visual.frames
                ):
                    warnings.append(
                        "Video terlalu pendek untuk durasi usulan; ganti visual atau sesuaikan durasi sebelum menerapkan."
                    )
                caption = captions.layout(
                    scene.caption, project.caption_style, duration
                )
                rows.append(
                    {
                        "scene_id": scene.id,
                        "name": scene.name,
                        "old_duration": scene.duration,
                        "duration": min(duration, 1800),
                        "minimum_frames": minimum,
                        "audio": audio,
                        "caption": caption,
                        "extra_gap_frames": max(0, scene.duration - minimum)
                        if audio
                        else None,
                        "errors": errors,
                        "warnings": warnings,
                    }
                )
            with repo.LOCK:
                if (
                    repo.load(pid).revision != project.revision
                    or signatures(project) != files
                ):
                    raise RuntimeError(
                        "Proyek atau media berubah selama analisis. Analisis ulang."
                    )
                now = self.clock()
                for key in list(self.proposals):
                    if now - self.proposals[key].created > 900:
                        del self.proposals[key]
                while len(self.proposals) >= 8:
                    self.proposals.popitem(last=False)
                key = uuid4().hex
                self.proposals[key] = Proposal(project, files, rows, now)
                return {
                    "id": key,
                    "base_revision": project.revision,
                    "rows": rows,
                    "expires_in": 900,
                    "caption_enabled": project.caption_style.enabled,
                }
        finally:
            self.worker.release()

    def get(self, pid, key):
        proposal = self.proposals.get(key)
        if (
            not proposal
            or proposal.project.id != pid
            or self.clock() - proposal.created > 900
        ):
            raise RuntimeError(
                "Analisis kedaluwarsa. Analisis ulang sebelum menerapkan."
            )
        return proposal

    def candidate(self, proposal, data):
        project = proposal.project
        if (
            repo.load(project.id).revision != project.revision
            or signatures(project) != proposal.files
        ):
            raise RuntimeError(
                "Proyek atau media berubah. Analisis ulang sebelum menerapkan."
            )
        edits = {edit.scene_id: edit for edit in data.edits}
        if len(edits) != len(data.edits):
            raise ValueError("Scene terpilih tidak boleh berulang.")
        rows = {row["scene_id"]: row for row in proposal.rows}
        if not edits.keys() <= rows.keys():
            raise ValueError("Scene tidak ditemukan dalam analisis.")
        candidate = project.model_copy(deep=True)
        reports = []
        for scene in candidate.scenes:
            if scene.id not in edits:
                continue
            edit, row = edits[scene.id], rows[scene.id]
            if row["errors"]:
                raise ValueError(scene.name + ": " + " ".join(row["errors"]))
            if edit.duration < row["minimum_frames"]:
                raise ValueError(
                    scene.name
                    + ": durasi akan memotong narasi. Pertahankan seluruh audio."
                )
            visual = next((a for a in project.assets if a.id == scene.media_id), None)
            if (
                visual
                and visual.kind == "video"
                and scene.source_in + edit.duration > visual.frames
            ):
                raise ValueError(scene.name + ": video lebih pendek dari durasi scene.")
            caption = captions.layout(
                edit.caption, project.caption_style, edit.duration
            )
            if caption["errors"]:
                raise ValueError(scene.name + ": " + " ".join(caption["errors"]))
            scene.duration, scene.caption = edit.duration, caption["text"]
            reports.append(
                {
                    "scene_id": scene.id,
                    "name": scene.name,
                    "old_duration": row["old_duration"],
                    "duration": scene.duration,
                    "caption": caption,
                    "warnings": row["warnings"],
                }
            )
        candidate = Project.model_validate(candidate.model_dump())
        total = sum(s.duration for s in candidate.scenes)
        return candidate, {
            "scenes": reports,
            "old_frames": sum(s.duration for s in project.scenes),
            "total_frames": total,
            "exceeds_target": total > project.target * 30,
        }

    def preview(self, pid, key, data):
        with repo.LOCK:
            return self.candidate(self.get(pid, key), data)[1]

    def apply(self, pid, key, data):
        with repo.LOCK:
            proposal = self.get(pid, key)
            receipt = data.model_dump_json()
            if proposal.receipt:
                if (
                    proposal.receipt == receipt
                    and proposal.result
                    and repo.load(pid).revision == proposal.result.revision
                    and signatures(proposal.result) == proposal.files
                ):
                    return proposal.result
                raise RuntimeError(
                    "Proposal sudah diterapkan. Analisis ulang untuk perubahan berikutnya."
                )
            candidate, _ = self.candidate(proposal, data)
            result = repo.save(candidate, expected=proposal.project.revision)
            proposal.receipt, proposal.result = receipt, result
            return result


service = Service()
