"""Local float PCM measurements. Sample peaks are not true-peak/loudness ratings."""

from array import array
import math
import sys
from . import media, repository as repo

RATE = 48000


def metrics(path, settings):
    threshold = 10 ** (settings.silence_dbfs / 20)
    warning = 10 ** (settings.peak_warning_dbfs / 20)
    peak, near, clipped, frames = 0.0, 0, 0, 0
    silences, quiet_start = [], None
    with path.open("rb") as source:
        while raw := source.read(480 * 2 * 4):
            samples = array("f")
            samples.frombytes(raw)
            if sys.byteorder != "little":
                samples.byteswap()
            absolute = [abs(v) for v in samples]
            if not absolute or any(not math.isfinite(v) for v in absolute):
                raise ValueError("PCM audio kosong atau tidak valid.")
            maximum = max(absolute)
            peak = max(peak, maximum)
            near += sum(v >= warning for v in absolute)
            clipped += sum(v >= 1 for v in absolute)
            if maximum <= threshold:
                if quiet_start is None:
                    quiet_start = frames
            elif quiet_start is not None:
                if (frames - quiet_start) / RATE >= settings.long_silence_seconds:
                    silences.append([quiet_start / RATE, frames / RATE])
                quiet_start = None
            frames += len(samples) // 2
    if (
        quiet_start is not None
        and (frames - quiet_start) / RATE >= settings.long_silence_seconds
    ):
        silences.append([quiet_start / RATE, frames / RATE])
    return {
        "seconds": frames / RATE,
        "peak_dbfs": round(20 * math.log10(peak), 3) if peak else None,
        "near_full_scale_samples": near,
        "at_full_scale_samples": clipped,
        "long_silences": silences,
        "sample_rate": RATE,
        "window_ms": 10,
    }


def decode(path, destination, job, offset=0, duration=61):
    job.process(
        [
            media.FFMPEG,
            "-v",
            "error",
            "-nostdin",
            "-y",
            "-ss",
            str(offset),
            "-protocol_whitelist",
            "file,pipe",
            "-i",
            str(path),
            "-t",
            str(duration),
            "-vn",
            "-ar",
            str(RATE),
            "-ac",
            "2",
            "-f",
            "f32le",
            str(destination),
        ]
    )


def mix(project, directory, job):
    """Measure the same gains, trim and music loop before export's music limiter."""
    segments = []
    for index, scene in enumerate(project.scenes):
        job.check()
        seconds = scene.duration / 30
        args = [
            media.FFMPEG,
            "-v",
            "error",
            "-nostdin",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r=48000:cl=stereo:d={seconds}",
        ]
        filters, streams, inputs = [], ["[0:a]"], 1
        asset = next((a for a in project.assets if a.id == scene.media_id), None)
        for aid, offset, gain in [
            (scene.audio_id, scene.audio_in, project.narration_volume),
            (
                scene.media_id if asset and asset.has_audio else None,
                scene.source_in,
                scene.source_volume,
            ),
        ]:
            if aid and gain:
                args += [
                    "-ss",
                    str(offset / 30),
                    "-protocol_whitelist",
                    "file,pipe",
                    "-i",
                    str(repo.asset_path(project, aid)),
                ]
                filters.append(
                    f"[{inputs}:a]aresample=48000,aformat=channel_layouts=stereo,volume={gain},apad,atrim=duration={seconds},asetpts=PTS-STARTPTS[a{inputs}]"
                )
                streams.append(f"[a{inputs}]")
                inputs += 1
        filters.append(
            "".join(streams)
            + f"amix=inputs={len(streams)}:duration=first:normalize=0[out]"
        )
        segment = directory / f"mix-{index}.wav"
        job.process(
            args
            + [
                "-filter_complex",
                ";".join(filters),
                "-map",
                "[out]",
                "-t",
                str(seconds),
                "-c:a",
                "pcm_f32le",
                "-ar",
                "48000",
                "-ac",
                "2",
                str(segment),
            ]
        )
        segments.append(segment)
    listing = directory / "audio-concat.txt"
    listing.write_text("\n".join(f"file '{p.name}'" for p in segments))
    joined = directory / "joined.wav"
    job.process(
        [
            media.FFMPEG,
            "-v",
            "error",
            "-nostdin",
            "-y",
            "-f",
            "concat",
            "-safe",
            "1",
            "-i",
            str(listing),
            "-c",
            "copy",
            str(joined),
        ]
    )
    out = directory / "mix.f32"
    if project.music_id and project.music_volume:
        job.process(
            [
                media.FFMPEG,
                "-v",
                "error",
                "-nostdin",
                "-y",
                "-i",
                str(joined),
                "-stream_loop",
                "-1",
                "-protocol_whitelist",
                "file,pipe",
                "-i",
                str(repo.asset_path(project, project.music_id)),
                "-filter_complex",
                f"[1:a]volume={project.music_volume}[music];[0:a][music]amix=inputs=2:duration=first:normalize=0[out]",
                "-map",
                "[out]",
                "-t",
                str(sum(s.duration for s in project.scenes) / 30),
                "-ar",
                "48000",
                "-ac",
                "2",
                "-f",
                "f32le",
                str(out),
            ]
        )
    else:
        decode(joined, out, job, duration=180)
    return metrics(out, project.quality_settings)
