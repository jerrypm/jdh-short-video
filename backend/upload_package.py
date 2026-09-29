"""Create a local upload handoff. This module never contacts YouTube."""

import zipfile
from fractions import Fraction
from . import repository, quality_audio


def write(project, preset, output, info, job, report):
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    expected = sum(s.duration for s in project.scenes)
    fps = Fraction(video["avg_frame_rate"])
    frames = int(video.get("nb_frames", 0))
    if fps != 30 or frames != expected:
        raise ValueError(
            "Jumlah frame atau frame rate output tidak cocok dengan timeline."
        )
    job.update(95, "Memeriksa audio hasil dan menyiapkan paket unggah")
    pcm = job.directory / "temp" / "output.f32"
    quality_audio.decode(output, pcm, job, duration=181)
    audio = quality_audio.metrics(pcm, project.quality_settings)
    verification = {
        "verified_file": True,
        "full_decode_passed": True,
        "width": video["width"],
        "height": video["height"],
        "fps": float(fps),
        "frames": frames,
        "container_seconds": float(info["format"]["duration"]),
        "audio": audio,
        "sample_peak_only": True,
    }
    metadata = {
        "title": project.upload.title.strip() or project.name[:100],
        "description": project.upload.description,
        "language": project.language,
        "project_revision": project.revision,
        "preset": preset,
        "upload_method": "manual",
        "verification": verification,
    }
    repository.atomic_json(job.directory / "upload-metadata.json", metadata)
    repository.atomic_json(
        job.directory / "quality-report.json",
        {
            "pre_export": report,
            "pre_export_checked": report is not None,
            "output_verification": verification,
            "note": "Temuan terukur dan ambang produk; bukan penilaian editorial AI atau jaminan platform.",
        },
    )
    (job.directory / "upload-notes.txt").write_text(
        f"Judul: {metadata['title']}\n\n{metadata['description']}\n\n"
        "Paket ini disiapkan untuk unggah manual. Periksa video dan suara sebelum publikasi.\n",
        encoding="utf-8",
    )
    files = [
        output.name,
        "upload-metadata.json",
        "upload-notes.txt",
        "quality-report.json",
    ]
    if (job.directory / "captions.srt").read_text().strip():
        files.append("captions.srt")
    with zipfile.ZipFile(
        job.directory / "upload.zip", "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for name in files:
            job.check()
            archive.write(job.directory / name, name)
    return verification
