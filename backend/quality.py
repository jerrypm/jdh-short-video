"""Measured pre-export reports and revision-checked, explicitly reviewed edits."""

from collections import OrderedDict
from dataclasses import dataclass
import json
import math
import time
from PIL import Image, ImageDraw, ImageFont
from . import (
    captions,
    jobs,
    media,
    nano,
    pacing,
    quality_audio,
    render,
    repository as repo,
)
from .models import Project
from .motion import evaluate_text
from .quality_contract import Start, Selection


def signatures(project):
    result = pacing.signatures(project)
    for asset in project.assets:
        try:
            stat = repo.asset_path(project, asset.id).stat()
            result[asset.id] = (stat.st_ino, stat.st_size, stat.st_mtime_ns)
        except (ValueError, FileNotFoundError):
            result[asset.id] = None
    return result


def caption_bounds(text, style):
    font = ImageFont.truetype(str(captions.FONT), style.size)
    font.set_variation_by_axes([700, 100])
    draw = ImageDraw.Draw(Image.new("L", (1, 1)))
    box = draw.multiline_textbbox((0, 0), text, font=font, spacing=8, align="center")
    width, height = box[2] - box[0], box[3] - box[1]
    x, y = (1080 - width) / 2, 1920 * style.position / 100
    px, py = (18, 12) if style.preset in {"lime", "bar"} else (2, 2)
    return (x - px, y - py, x + width + px, y + height + py)


def overlap(a, b):
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


def scan(project, preset, job):
    directory = job.directory / "temp"
    directory.mkdir()
    findings, rows = [], []

    def finding(code, severity, message, scene=None, start=0, end=None):
        findings.append(
            {
                "code": code,
                "severity": severity,
                "message": message,
                "scene_id": scene.id if scene else None,
                "start_frame": start,
                "end_frame": end
                if end is not None
                else sum(s.duration for s in project.scenes),
            }
        )

    for problem in render.issues(project):
        finding("render_blocker", "error", problem)
    for asset in project.assets:
        if not repo.asset_path(project, asset.id).is_file():
            finding(
                "missing_media",
                "error",
                f"Media {asset.name} hilang; paket proyek memerlukan semua media terdaftar.",
            )
    offset, audio_cache = 0, {}
    for index, scene in enumerate(project.scenes):
        job.update(
            index / max(1, len(project.scenes)) * 70, f"Memeriksa scene {index + 1}"
        )
        end = offset + scene.duration
        minimum, measured = 9, None
        if scene.audio_id:
            try:
                path = repo.asset_path(project, scene.audio_id)
                key = (scene.audio_id, scene.audio_in)
                if key not in audio_cache:
                    pcm = directory / f"narration-{index}.f32"
                    quality_audio.decode(path, pcm, job, scene.audio_in / 30)
                    audio_cache[key] = quality_audio.metrics(
                        pcm, project.quality_settings
                    )
                    pcm.unlink()
                measured = audio_cache[key]
                if measured["seconds"] <= 0 or measured["seconds"] > 60:
                    raise ValueError(
                        "Audio kosong atau lebih dari 60 detik setelah trim."
                    )
                minimum = max(9, math.ceil(measured["seconds"] * 30 - 1e-6))
                if minimum > scene.duration:
                    finding(
                        "narration_cut",
                        "error",
                        f"Narasi {minimum / 30:.2f} dtk melebihi scene {scene.duration / 30:.2f} dtk.",
                        scene,
                        offset,
                        end,
                    )
                for a, b in measured["long_silences"]:
                    a, b = min(scene.duration / 30, a), min(scene.duration / 30, b)
                    if b > a:
                        finding(
                            "narration_silence",
                            "warning",
                            f"Level narasi di bawah ambang selama {b - a:.2f} dtk; periksa jeda secara manual.",
                            scene,
                            offset + int(a * 30),
                            min(end, offset + math.ceil(b * 30)),
                        )
                gap = scene.duration / 30 - measured["seconds"]
                if gap >= project.quality_settings.long_silence_seconds:
                    finding(
                        "narration_tail",
                        "warning",
                        f"Scene menyisakan {gap:.2f} dtk setelah file narasi berakhir.",
                        scene,
                        min(end - 1, offset + minimum),
                        end,
                    )
                if measured["near_full_scale_samples"]:
                    finding(
                        "narration_peak",
                        "warning",
                        f"Puncak sampel file narasi {measured['peak_dbfs']} dBFS mendekati skala penuh. Ini bukan bukti distorsi; periksa suara asli.",
                        scene,
                        offset,
                        end,
                    )
            except (ValueError, OSError) as error:
                measured = None
                finding("audio_unmeasured", "error", str(error), scene, offset, end)
        elif scene.narration.strip():
            finding(
                "missing_narration",
                "warning",
                "Ada naskah, belum ada file narasi; durasi ucapan belum terukur.",
                scene,
                offset,
                end,
            )
        if scene.audio_text and scene.audio_text != scene.narration:
            finding(
                "stale_narration",
                "error",
                "Naskah berbeda dari audio; buat ulang narasi.",
                scene,
                offset,
                end,
            )
        caption = captions.layout(scene.caption, project.caption_style, scene.duration)
        caption_box, callout_box = None, None
        if project.caption_style.enabled and scene.caption.strip():
            for error in caption["errors"]:
                finding("caption_layout", "error", error, scene, offset, end)
            if not caption["errors"]:
                caption_box = caption_bounds(caption["text"], project.caption_style)
            if caption["characters_per_second"] > project.quality_settings.caption_cps:
                finding(
                    "caption_readability",
                    "warning",
                    f"Caption {caption['characters_per_second']} karakter/dtk melebihi ambang produk {project.quality_settings.caption_cps:g}.",
                    scene,
                    offset,
                    end,
                )
        if scene.motion.callout:
            try:
                path = directory / f"callout-{index}.png"
                captions.callout_image(scene.motion.callout, path)
                with Image.open(path) as png:
                    callout_box = png.getbbox()
            except ValueError as error:
                finding("callout_layout", "error", str(error), scene, offset, end)
        frame_issues = {}
        for frame in range(scene.duration):
            job.check()
            enabled = project.motion_mode != "none"
            cap = evaluate_text(scene.motion.caption, frame, scene.duration, enabled)
            label = (
                evaluate_text(
                    scene.motion.callout.entrance, frame, scene.duration, enabled
                )
                if scene.motion.callout
                else None
            )
            a = (
                (
                    caption_box[0],
                    caption_box[1] + cap["y"],
                    caption_box[2],
                    caption_box[3] + cap["y"],
                )
                if caption_box and cap["opacity"] > 0
                else None
            )
            b = (
                (
                    callout_box[0],
                    callout_box[1] + label["y"],
                    callout_box[2],
                    callout_box[3] + label["y"],
                )
                if callout_box and label and label["opacity"] > 0
                else None
            )
            codes = []
            if a and (a[0] < 0 or a[1] < 0 or a[2] > 1080 or a[3] > 1920):
                codes.append("caption_cut")
            if a and (a[0] < 65 or a[1] < 135 or a[2] > 1015 or a[3] > 1612):
                codes.append("caption_safe_area")
            if a and b and overlap(a, b):
                codes.append("overlay_overlap")
            for code in codes:
                previous = frame_issues.get(code, [frame, frame])
                frame_issues[code] = [previous[0], frame]
        messages = {
            "caption_cut": "Batas caption melewati kanvas pada rentang ini.",
            "caption_safe_area": "Caption keluar dari guide area aman editor; guide ini bukan aturan YouTube.",
            "overlay_overlap": "Bounding box caption dan callout/pointer bertumpuk; periksa visual karena kotak dapat mencakup piksel transparan.",
        }
        for code, (a, b) in frame_issues.items():
            finding(
                code,
                "error" if code == "caption_cut" else "warning",
                messages[code],
                scene,
                offset + a,
                offset + b + 1,
            )
        rows.append(
            {
                "scene_id": scene.id,
                "name": scene.name,
                "start_frame": offset,
                "end_frame": end,
                "duration": scene.duration,
                "minimum_frames": minimum,
                "audio": measured,
                "caption": scene.caption,
                "suggested_duration": min(1800, max(scene.duration, minimum)),
                "suggested_caption": caption["text"]
                if not caption["errors"]
                else scene.caption,
            }
        )
        offset = end
    mix = None
    if not any(f["severity"] == "error" for f in findings):
        job.update(75, "Mengukur campuran audio lokal")
        try:
            mix = quality_audio.mix(project, directory, job)
            if mix["near_full_scale_samples"]:
                finding(
                    "mix_peak",
                    "warning",
                    f"Campuran sebelum limiter mencapai {mix['peak_dbfs']} dBFS. Turunkan gain bila perlu; clipping/distorsi perlu didengarkan.",
                )
            for a, b in mix["long_silences"]:
                finding(
                    "mix_silence",
                    "warning",
                    f"Campuran audio di bawah ambang selama {b - a:.2f} dtk.",
                    start=int(a * 30),
                    end=min(offset, math.ceil(b * 30)),
                )
        except (ValueError, OSError) as error:
            finding("mix_unmeasured", "error", str(error))
    else:
        finding(
            "mix_skipped",
            "info",
            "Pengukuran campuran menunggu masalah teknis diperbaiki.",
        )
    return {
        "id": job.id,
        "project_id": project.id,
        "base_revision": project.revision,
        "origin": "measured-local",
        "settings": project.quality_settings.model_dump(),
        "preset": preset,
        "output": {
            "width": 360 if preset == "draft" else 1080,
            "height": 640 if preset == "draft" else 1920,
            "fps": 30,
            "frames": offset,
            "seconds": offset / 30,
            "verified_file": False,
        },
        "findings": findings,
        "rows": rows,
        "mix": mix,
        "limitations": [
            "Puncak sampel, bukan true peak/LUFS atau bukti distorsi.",
            "Deteksi jeda berdasarkan level, bukan pengenalan kata.",
            "Overlap memakai bounding box semua frame, bukan penilaian estetika.",
            "Dimensi/durasi rencana diverifikasi lagi pada file hasil ekspor.",
        ],
    }


@dataclass
class Record:
    project: Project
    files: dict
    created: float
    report: dict | None = None
    receipt: str | None = None
    result: Project | None = None
    reviewed: str | None = None


class Service:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.records = OrderedDict()
        self.editorials = {}

    def expire(self):
        for key, record in list(self.records.items()):
            if self.clock() - record.created > 900:
                for request, check in list(self.editorials.items()):
                    if check == key:
                        nano.broker.cancel(request)
                        del self.editorials[request]
                del self.records[key]

    def start(self, pid, data: Start):
        with repo.LOCK:
            if not media.FFMPEG:
                raise ValueError("FFmpeg lokal belum tersedia.")
            self.expire()
            if len(self.records) >= 8:
                raise RuntimeError(
                    "Maksimal delapan laporan per 15 menit. Tunggu laporan lama kedaluwarsa."
                )
            project = repo.load(pid)
            if project.revision != data.revision:
                raise RuntimeError("Proyek berubah. Simpan dan periksa ulang.")
            if not project.scenes:
                raise ValueError("Tambahkan scene terlebih dahulu.")
            record = Record(project, signatures(project), self.clock())

            def work(job):
                report = scan(project, data.preset, job)
                with repo.LOCK:
                    self.fresh(record)
                    record.report = report
                    job.result = report
                    repo.atomic_json(job.directory / "quality-report.json", report)
                    job.files = ["quality-report.json"]

            job = jobs.submit(pid, "quality", work)
            self.records[job["id"]] = record
            return job

    def get(self, pid, key):
        self.expire()
        record = self.records.get(key)
        if (
            not record
            or record.project.id != pid
            or not record.report
            or jobs.read(key)["status"] != "completed"
        ):
            raise RuntimeError("Laporan belum selesai atau kedaluwarsa. Periksa ulang.")
        return record

    def fresh(self, record):
        if (
            repo.load(record.project.id).revision != record.project.revision
            or signatures(record.project) != record.files
        ):
            raise RuntimeError(
                "Proyek atau media berubah. Periksa ulang sebelum melanjutkan."
            )

    def export_report(self, pid, key, preset):
        record = self.get(pid, key)
        self.fresh(record)
        if record.report["preset"] != preset:
            raise RuntimeError("Preset berubah. Jalankan pemeriksaan ulang.")
        if any(f["severity"] == "error" for f in record.report["findings"]):
            raise ValueError("Perbaiki temuan teknis sebelum ekspor.")
        return record.report

    def candidate(self, record, selection: Selection):
        self.fresh(record)
        candidate = record.project.model_copy(deep=True)
        rows = {r["scene_id"]: r for r in record.report["rows"]}
        edits = {e.scene_id: e for e in selection.scenes}
        if len(edits) != len(selection.scenes) or not edits.keys() <= rows.keys():
            raise ValueError("Pilihan scene tidak valid atau berulang.")
        for scene in candidate.scenes:
            if scene.id in edits:
                edit = edits[scene.id]
                row = rows[scene.id]
                if (
                    scene.audio_id
                    and row["audio"] is None
                    and edit.duration != scene.duration
                ):
                    raise ValueError(
                        "Durasi audio belum terukur; perbaiki medianya dahulu."
                    )
                if edit.duration < rows[scene.id]["minimum_frames"]:
                    raise ValueError("Usulan durasi akan memotong narasi.")
                asset = next(
                    (a for a in candidate.assets if a.id == scene.media_id), None
                )
                if (
                    asset
                    and asset.kind == "video"
                    and scene.source_in + edit.duration > asset.frames
                ):
                    raise ValueError("Video terlalu pendek untuk usulan durasi.")
                if captions.layout(
                    edit.caption, candidate.caption_style, edit.duration
                )["errors"]:
                    raise ValueError("Caption usulan terlalu panjang.")
                scene.duration, scene.caption = edit.duration, edit.caption
        candidate.upload = selection.upload
        candidate.caption_style.position = selection.caption_position
        candidate.narration_volume = selection.narration_volume
        candidate.music_volume = selection.music_volume
        return Project.model_validate(candidate.model_dump())

    def preview(self, pid, key, selection):
        with repo.LOCK:
            record = self.get(pid, key)
            candidate = self.candidate(record, selection)
            record.reviewed = selection.model_dump_json()
            return {
                "before": {
                    "upload": record.project.upload,
                    "caption_position": record.project.caption_style.position,
                    "narration_volume": record.project.narration_volume,
                    "music_volume": record.project.music_volume,
                },
                "after": selection.model_dump(),
                "frames": sum(s.duration for s in candidate.scenes),
                "requires_recheck": True,
            }

    def apply(self, pid, key, selection):
        with repo.LOCK:
            record = self.get(pid, key)
            receipt = selection.model_dump_json()
            if record.receipt:
                if (
                    record.receipt == receipt
                    and record.result
                    and repo.load(pid).revision == record.result.revision
                    and signatures(record.result) == record.files
                ):
                    return record.result
                raise RuntimeError("Proposal sudah diterapkan. Periksa ulang.")
            if record.reviewed != receipt:
                raise RuntimeError(
                    "Tinjau perubahan sebelum menerapkan; edit memerlukan review ulang."
                )
            candidate = self.candidate(record, selection)
            result = repo.save(candidate, expected=record.project.revision)
            record.receipt, record.result = receipt, result
            return result

    def editorial_start(self, pid, key, request_id):
        nano.valid_id(request_id)
        with repo.LOCK:
            record = self.get(pid, key)
            self.fresh(record)
            project = record.project
            if project.language != "en":
                raise ValueError(
                    "Review Nano lokal saat ini hanya mendukung English; pemeriksaan teknis dan metadata manual tetap tersedia."
                )
            if request_id in self.editorials:
                if self.editorials[request_id] != key:
                    raise RuntimeError("ID permintaan digunakan oleh laporan lain.")
                return self.editorial_read(pid, key, request_id)
            if len(self.editorials) >= 16:
                raise RuntimeError(
                    "Terlalu banyak permintaan editorial. Tunggu laporan lama kedaluwarsa."
                )
            with jobs.LOCK:
                if any(j.status in {"queued", "running"} for j in jobs.JOBS.values()):
                    raise RuntimeError(
                        "Tunggu pemeriksaan, narasi atau render selesai."
                    )
            context = {
                "analysis_basis": "text_and_user_visual_intent_only",
                "scenes": [],
            }
            offset = 0
            for scene in project.scenes:
                context["scenes"].append(
                    {
                        "id": scene.id,
                        "start_frame": offset,
                        "end_frame": offset + scene.duration,
                        "narration": scene.narration[:600],
                        "caption": scene.caption,
                        "visual_intent": scene.planning.visual_need
                        if scene.planning
                        else "Not described",
                        "text_truncated": len(scene.narration) > 600,
                    }
                )
                offset += scene.duration
            payload = json.dumps(context, ensure_ascii=False)
            if len(payload) > 12000:
                raise ValueError(
                    "Proyek melebihi konteks editorial Nano. Gunakan metadata manual atau proyek lebih ringkas."
                )
            result = nano.broker.enqueue(
                nano.Generate(
                    id=request_id, operation="editorial", language="en", input=payload
                )
            )
            self.editorials[request_id] = key
            return result

    def editorial_read(self, pid, key, request_id):
        with repo.LOCK:
            record = self.get(pid, key)
            self.fresh(record)
            if self.editorials.get(request_id) != key:
                raise ValueError("Permintaan editorial tidak ditemukan.")
            return nano.broker.read(request_id)

    def defer(self):
        for request in list(self.editorials):
            if nano.broker.active_id == request:
                nano.broker.cancel(request)


service = Service()
