import shutil
import zipfile
from . import captions, media, repository, motion
from .models import Project


def issues(project: Project) -> list[str]:
    result = []
    for asset in project.assets:
        if not repository.asset_path(project, asset.id).is_file():
            result.append(
                f"Media {asset.name} hilang; pulihkan agar paket proyek lengkap."
            )
    if not project.scenes:
        result.append("Tambahkan minimal satu scene.")
    for i, scene in enumerate(project.scenes):
        for aid, kind in [(scene.media_id, "visual"), (scene.audio_id, "narasi")]:
            if not aid:
                if kind == "visual":
                    result.append(f"Scene {i + 1}: media belum dipilih.")
                continue
            try:
                path = repository.asset_path(project, aid)
                if not path.is_file():
                    result.append(f"Scene {i + 1}: media hilang.")
                asset = next(a for a in project.assets if a.id == aid)
                if kind == "visual" and asset.kind == "audio":
                    result.append(f"Scene {i + 1}: visual harus gambar/video.")
                if kind == "narasi" and not asset.has_audio:
                    result.append(f"Scene {i + 1}: narasi harus memiliki audio.")
                if (
                    kind == "visual"
                    and asset.kind == "video"
                    and scene.source_in + scene.duration > asset.frames + 1
                ):
                    result.append(
                        f"Scene {i + 1}: durasi melebihi akhir video. Trim scene."
                    )
                if kind == "narasi" and scene.audio_in >= asset.frames:
                    result.append(f"Scene {i + 1}: awal narasi di luar audio.")
                if (
                    kind == "narasi"
                    and asset.frames - scene.audio_in > scene.duration + 1
                ):
                    result.append(
                        f"Scene {i + 1}: narasi lebih panjang dari scene. Perpanjang durasi."
                    )
            except (ValueError, StopIteration):
                result.append(f"Scene {i + 1}: media tidak terdaftar.")
        if scene.audio_id and scene.audio_text and scene.audio_text != scene.narration:
            result.append(f"Scene {i + 1}: naskah berubah, perbarui narasi.")
    if project.music_id:
        try:
            if not repository.asset_path(project, project.music_id).is_file():
                result.append("Musik tidak ditemukan.")
        except ValueError:
            result.append("Musik tidak ditemukan.")
    return result


def render(project: Project, preset: str, job, quality_report=None):
    errors = issues(project)
    if errors:
        raise ValueError(" ".join(errors))
    if not media.FFMPEG:
        raise ValueError("FFmpeg belum terpasang.")
    if shutil.disk_usage(repository.ROOT).free < 500 * 1024 * 1024:
        raise ValueError("Ruang disk tidak cukup (minimal 500 MB).")
    width, height = (360, 640) if preset == "draft" else (1080, 1920)
    temp = job.directory / "temp"
    temp.mkdir()
    total = sum(s.duration for s in project.scenes) / 30
    segments = []
    narration_segments = []
    for index, scene in enumerate(project.scenes):
        job.check()
        duration = scene.duration / 30
        asset = next(a for a in project.assets if a.id == scene.media_id)
        source = repository.asset_path(project, asset.id)
        caption = temp / f"caption-{index}.png"
        captions.caption_image(scene.caption, project.caption_style, caption)
        # AAC adds encoder priming/padding to each independently encoded scene.
        # Keep sample-exact PCM intermediates and encode AAC once after concat.
        segment = temp / f"scene-{index}.mov"
        args = [media.FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-nostdin"]
        args += [
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x101216:s={width}x{height}:r=30:d={duration}",
        ]
        if asset.kind == "image":
            args += ["-loop", "1", "-framerate", "30"]
        else:
            args += ["-ss", str(scene.source_in / 30)]
        args += [
            "-protocol_whitelist",
            "file,pipe",
            "-i",
            str(source),
            "-loop",
            "1",
            "-framerate",
            "30",
            "-i",
            str(caption),
        ]
        factor = (min if scene.fit == "fit" else max)(
            width / asset.width, height / asset.height
        ) * scene.scale
        sw = max(2, round(asset.width * factor / 2) * 2)
        sh = max(2, round(asset.height * factor / 2) * 2)
        enabled = project.motion_mode != "none"
        caption_fade, caption_y = motion.text_filter(
            scene.motion.caption, scene.duration, enabled
        )
        filters = [
            f"[1:v]scale={sw}:{sh},setsar=1,fps=30,setpts=PTS-STARTPTS[v]",
            f"[0:v][v]overlay=x=(W-w)/2+{scene.x * width / 1080}:y=(H-h)/2+{scene.y * height / 1920}:shortest=1[base]",
            f"[base]{motion.visual_filter(scene.motion.visual, scene.duration, width, height, enabled)}[moving]",
            f"[2:v]format=rgba,{caption_fade},scale={width}:{height}[cap]",
            f"[moving][cap]overlay=x=0:y='({caption_y})*{height}/1920':shortest=1[captioned]",
        ]
        if scene.audio_id:
            audio = repository.asset_path(project, scene.audio_id)
            args += [
                "-ss",
                str(scene.audio_in / 30),
                "-protocol_whitelist",
                "file,pipe",
                "-i",
                str(audio),
            ]
            narration_input = "3:a"
        else:
            args += ["-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={duration}"]
            narration_input = "3:a"
        if scene.motion.callout:
            callout = temp / f"callout-{index}.png"
            captions.callout_image(scene.motion.callout, callout)
            args += ["-loop", "1", "-framerate", "30", "-i", str(callout)]
            fade, y = motion.text_filter(
                scene.motion.callout.entrance, scene.duration, enabled
            )
            filters += [
                f"[4:v]format=rgba,{fade},scale={width}:{height}[callout]",
                f"[captioned][callout]overlay=x=0:y='({y})*{height}/1920':shortest=1,format=yuv420p[outv]",
            ]
        else:
            filters += ["[captioned]format=yuv420p[outv]"]
        filters += [
            f"[{narration_input}]aresample=48000,aformat=channel_layouts=stereo,volume={project.narration_volume},apad,atrim=duration={duration},asetpts=PTS-STARTPTS[narr]"
        ]
        if asset.kind == "video" and asset.has_audio and scene.source_volume:
            filters += [
                f"[1:a]aresample=48000,aformat=channel_layouts=stereo,volume={scene.source_volume},apad,atrim=duration={duration},asetpts=PTS-STARTPTS[src]",
                "[narr][src]amix=inputs=2:normalize=0[a]",
            ]
        else:
            filters += ["[narr]anull[a]"]
        args += [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outv]",
            "-map",
            "[a]",
            "-t",
            str(duration),
            "-r",
            "30",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23" if preset == "draft" else "18",
            "-c:a",
            "pcm_s16le",
            "-ar",
            "48000",
            "-ac",
            "2",
            "-threads",
            "2",
            "-filter_complex_threads",
            "1",
            "-progress",
            "pipe:1",
            str(segment),
        ]
        job.message = f"Merender scene {index + 1} dari {len(project.scenes)}"
        job.process(
            args,
            index / len(project.scenes) * 80,
            (index + 1) / len(project.scenes) * 80,
            duration,
        )
        segments.append(segment)
        narrfile = temp / f"narration-{index}.wav"
        narg = [media.FFMPEG, "-v", "error", "-y", "-nostdin"]
        if scene.audio_id:
            narg += [
                "-ss",
                str(scene.audio_in / 30),
                "-protocol_whitelist",
                "file,pipe",
                "-i",
                str(repository.asset_path(project, scene.audio_id)),
            ]
        else:
            narg += ["-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={duration}"]
        narg += [
            "-af",
            f"volume={project.narration_volume},apad",
            "-t",
            str(duration),
            "-ar",
            "48000",
            "-ac",
            "2",
            str(narrfile),
        ]
        job.process(narg)
        narration_segments.append(narrfile)
    concat = temp / "concat.txt"
    concat.write_text("\n".join(f"file '{p.name}'" for p in segments))
    joined = temp / "joined.mov"
    job.message = "Menggabungkan scene"
    job.process(
        [
            media.FFMPEG,
            "-v",
            "error",
            "-y",
            "-nostdin",
            "-f",
            "concat",
            "-safe",
            "1",
            "-i",
            str(concat),
            "-c",
            "copy",
            str(joined),
        ]
    )
    output = job.directory / f"{preset}.mp4"
    if project.music_id and project.music_volume:
        job.message = "Mencampur musik"
        job.process(
            [
                media.FFMPEG,
                "-v",
                "error",
                "-y",
                "-nostdin",
                "-i",
                str(joined),
                "-stream_loop",
                "-1",
                "-protocol_whitelist",
                "file,pipe",
                "-i",
                str(repository.asset_path(project, project.music_id)),
                "-filter_complex",
                f"[1:a]volume={project.music_volume}[music];[0:a][music]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[a]",
                "-map",
                "0:v",
                "-map",
                "[a]",
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-t",
                str(total),
                "-movflags",
                "+faststart",
                "-progress",
                "pipe:1",
                str(output),
            ],
            82,
            92,
            total,
        )
    else:
        job.process(
            [
                media.FFMPEG,
                "-v",
                "error",
                "-y",
                "-nostdin",
                "-i",
                str(joined),
                "-c:v",
                "copy",
                "-c:a",
                "aac",
                "-t",
                str(total),
                "-movflags",
                "+faststart",
                str(output),
            ]
        )
    job.update(93, "Memvalidasi video dan audio")
    info = media.probe(output)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next(s for s in info["streams"] if s["codec_type"] == "audio")
    if (
        (v["width"], v["height"]) != (width, height)
        or v["codec_name"] != "h264"
        or a["codec_name"] != "aac"
        or abs(float(info["format"]["duration"]) - total) > 0.15
    ):
        raise ValueError(
            "Validasi output gagal: dimensi, codec, atau durasi tidak cocok."
        )
    job.process(
        [media.FFMPEG, "-v", "error", "-xerror", "-i", str(output), "-f", "null", "-"]
    )
    narrlist = temp / "narration.txt"
    narrlist.write_text("\n".join(f"file '{p.name}'" for p in narration_segments))
    job.process(
        [
            media.FFMPEG,
            "-v",
            "error",
            "-y",
            "-nostdin",
            "-f",
            "concat",
            "-safe",
            "1",
            "-i",
            str(narrlist),
            "-c",
            "copy",
            str(job.directory / "narration.wav"),
        ]
    )
    (job.directory / "captions.srt").write_text(captions.srt(project))
    repository.atomic_json(job.directory / "project.json", project.model_dump())
    with zipfile.ZipFile(
        job.directory / "project.zip", "w", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        archive.write(job.directory / "project.json", "project.json")
        for asset in project.assets:
            job.check()
            archive.write(
                repository.asset_path(project, asset.id), "media/" + asset.file
            )
    from .upload_package import write

    verification = write(project, preset, output, info, job, quality_report)
    job.files = [
        output.name,
        "narration.wav",
        "captions.srt",
        "project.json",
        "project.zip",
        "upload-metadata.json",
        "upload-notes.txt",
        "quality-report.json",
        "upload.zip",
    ]
    job.result = {
        "revision": project.revision,
        "width": width,
        "height": height,
        "frames": sum(s.duration for s in project.scenes),
        "verification": verification,
    }
