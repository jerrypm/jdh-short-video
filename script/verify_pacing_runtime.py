"""Measure real bundled TTS/export timing in disposable projects (no Nano calls)."""

import argparse
import copy
import io
import json
from pathlib import Path
import subprocess
import tempfile
import time
import wave
import numpy as np
from PIL import Image
from verify_content_memory_runtime import ROOT, runtime, call


def wait_job(client, job):
    until = time.monotonic() + 180
    while time.monotonic() < until:
        state = call(client, "GET", "/jobs/" + job["id"])
        if state["status"] in {"failed", "cancelled"}:
            raise AssertionError(state)
        if state["status"] == "completed":
            return state
        time.sleep(0.2)
    raise AssertionError("Timed out waiting for QA job")


def setup(client, directory):
    project = call(
        client,
        "POST",
        "/projects",
        json={"name": "Task 06 · QA timing", "language": "en", "target": 15},
    )
    pid = project["id"]
    picture = io.BytesIO()
    Image.new("RGB", (360, 640), "#284961").save(picture, format="PNG")
    image = call(
        client,
        "POST",
        f"/projects/{pid}/media",
        files={"file": ("qa.png", picture.getvalue(), "image/png")},
    )["asset"]
    rate = 24000
    t = np.arange(rate * 3) / rate
    samples = np.where(
        ((t >= 0.3) & (t < 1)) | ((t >= 1.6) & (t < 2.3)),
        np.sin(2 * np.pi * 440 * t) * 12000,
        0,
    ).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setparams((1, 2, rate, 0, "NONE", "not compressed"))
        output.writeframes(samples.tobytes())
    tone = call(
        client,
        "POST",
        f"/projects/{pid}/media",
        files={"file": ("qa-tone.wav", buffer.getvalue(), "audio/wav")},
    )["asset"]
    project = call(client, "GET", f"/projects/{pid}")
    project["scenes"] = [
        {
            "id": "tone1",
            "name": "Tone one",
            "caption": "Measure the whole audio.",
            "duration": 150,
            "audio_id": tone["id"],
            "media_id": image["id"],
        },
        {
            "id": "tone2",
            "name": "Tone two",
            "caption": "Keep the creative pause.",
            "duration": 150,
            "audio_id": tone["id"],
            "media_id": image["id"],
        },
        {
            "id": "speech",
            "name": "Real local speech",
            "caption": "One idea. One short.",
            "duration": 150,
            "narration": "One idea. One short. Keep the final word intact.",
            "media_id": image["id"],
        },
    ]
    project = call(client, "PUT", f"/projects/{pid}", json=project)
    job = wait_job(
        client,
        call(client, "POST", f"/projects/{pid}/tts", json={"scene_id": "speech"}),
    )
    (directory / "speech.wav").write_bytes(
        client.get(f"/api/jobs/{job['id']}/files/narration.wav").content
    )
    project = call(
        client,
        "POST",
        f"/projects/{pid}/tts/{job['id']}/apply",
        json={"revision": project["revision"]},
    )
    return project


def decode(ffmpeg, path):
    data = subprocess.run(
        [
            str(ffmpeg),
            "-v",
            "error",
            "-i",
            str(path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-f",
            "f32le",
            "pipe:1",
        ],
        capture_output=True,
        check=True,
    ).stdout
    return np.frombuffer(data, dtype="<f4")


def starts(audio):
    # 10 ms peak windows; the 440 Hz fixture has exact 0.3/1.6 s onsets.
    blocks = [np.max(np.abs(audio[i : i + 160])) for i in range(0, len(audio), 160)]
    return [
        i / 100
        for i, value in enumerate(blocks)
        if value > 0.05 and (i == 0 or blocks[i - 1] <= 0.05)
    ]


def main(app, report):
    resources = app.resolve() / "Contents/Resources"
    checks, metrics = [], {}
    with tempfile.TemporaryDirectory(prefix="jdh-pacing-runtime-qa-") as temporary:
        directory = Path(temporary)
        with runtime(resources, directory) as client:
            project = setup(client, directory)
            pid = project["id"]
            proposal = call(
                client,
                "POST",
                f"/pacing/{pid}/analyze",
                json={"revision": project["revision"]},
            )
            assert call(client, "GET", f"/projects/{pid}") == project
            assert proposal["rows"][0]["audio"]["seconds"] == 3
            assert [x["kind"] for x in proposal["rows"][0]["audio"]["silences"]] == [
                "leading",
                "internal",
                "trailing",
            ]
            body = {
                "edits": [
                    {
                        "scene_id": row["scene_id"],
                        "duration": row["minimum_frames"]
                        + (15 if row["scene_id"] == "speech" else 0),
                        "caption": row["caption"]["text"],
                    }
                    for row in proposal["rows"]
                ]
            }
            prefix = f"/pacing/{pid}/{proposal['id']}"
            summary = call(client, "POST", prefix + "/preview", json=body)
            applied = call(client, "POST", prefix + "/apply", json=body)
            assert call(client, "POST", prefix + "/apply", json=body) == applied
            assert (
                json.loads((directory / pid / "project.backup.json").read_text())
                == project
            )
            assert all(
                a["audio_in"] == b["audio_in"]
                for a, b in zip(project["scenes"], applied["scenes"])
            )
            assert call(client, "GET", f"/projects/{pid}/preflight")["issues"] == []
            checks += [
                "real bundled Kokoro English speech",
                "measured PCM and silence",
                "analysis leaves project unchanged",
                "review and full-audio apply",
                "atomic backup and retry",
                "audio trim preserved",
            ]
            expected_starts = [0.3, 1.6, 3.3, 4.6]
            ffmpeg = resources / "tools/bin/ffmpeg"
            for preset in ["draft", "final"]:
                job = wait_job(
                    client,
                    call(
                        client,
                        "POST",
                        f"/projects/{pid}/render",
                        json={"preset": preset},
                    ),
                )
                paths = {}
                for name in [preset + ".mp4", "narration.wav", "captions.srt"]:
                    path = directory / name
                    response = client.get(f"/api/jobs/{job['id']}/files/{name}")
                    response.raise_for_status()
                    path.write_bytes(response.content)
                    paths[name] = path
                audio = decode(ffmpeg, paths[preset + ".mp4"])
                narration = decode(ffmpeg, paths["narration.wav"])
                measured_starts = starts(audio)[:4]
                errors = [
                    round(actual - expected, 4)
                    for actual, expected in zip(measured_starts, expected_starts)
                ]
                expected_seconds = summary["total_frames"] / 30
                metrics[preset] = {
                    "expected_seconds": expected_seconds,
                    "decoded_audio_seconds": len(audio) / 16000,
                    "preview_timeline_tone_onsets": expected_starts,
                    "export_tone_onsets": measured_starts,
                    "onset_errors_seconds": errors,
                    "narration_seconds": len(narration) / 16000,
                }
                print(json.dumps({preset: metrics[preset]}), flush=True)
                assert len(errors) == 4 and max(abs(e) for e in errors) <= 1 / 30
                assert abs(len(narration) / 16000 - expected_seconds) <= 1 / 16000
                # Entire speech waveform preserved at the preview scene's 6 s boundary.
                speech = decode(ffmpeg, directory / "speech.wav")
                kept = narration[96000 : 96000 + len(speech)]
                assert (
                    len(kept) == len(speech) and np.max(np.abs(speech - kept)) < 0.001
                )
                srt = paths["captions.srt"].read_text()
                assert "00:00:03,000 --> 00:00:06,000" in srt
                checks += [
                    preset + " export timing within one frame",
                    preset + " complete speech waveform and SRT boundaries",
                ]
            undo = copy.deepcopy(project)
            undo["revision"] = applied["revision"]
            restored = call(client, "PUT", f"/projects/{pid}", json=undo)
            assert restored["scenes"] == project["scenes"]
            redo = copy.deepcopy(applied)
            redo["revision"] = restored["revision"]
            restored = call(client, "PUT", f"/projects/{pid}", json=redo)
            assert restored["scenes"] == applied["scenes"]
            checks += ["revision-checked Undo and Redo"]
            music = io.BytesIO()
            with wave.open(music, "wb") as output:
                output.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
                notes = (
                    np.sin(2 * np.pi * 880 * np.arange(16800) / 24000) * 4000
                ).astype("<i2")
                output.writeframes(notes.tobytes())
            imported = call(
                client,
                "POST",
                f"/projects/{pid}/media",
                files={"file": ("qa-music.wav", music.getvalue(), "audio/wav")},
            )
            mixed = imported["project"]
            mixed["music_id"], mixed["music_volume"] = imported["asset"]["id"], 0.04
            mixed = call(client, "PUT", f"/projects/{pid}", json=mixed)
            job = wait_job(
                client,
                call(
                    client, "POST", f"/projects/{pid}/render", json={"preset": "draft"}
                ),
            )
            path = directory / "mixed.mp4"
            response = client.get(f"/api/jobs/{job['id']}/files/draft.mp4")
            response.raise_for_status()
            path.write_bytes(response.content)
            audio = decode(ffmpeg, path)
            onsets = starts(audio)[:4]
            assert (
                len(onsets) == 4
                and max(abs(a - b) for a, b in zip(onsets, expected_starts)) <= 1 / 30
            )
            # Narration is silent here, but the 0.7 s music file keeps looping.
            assert all(
                np.mean(np.abs(audio[int(t * 16000) : int((t + 0.1) * 16000)])) > 0.001
                for t in [2.6, 5.6]
            )
            metrics["music_loop"] = {
                "source_seconds": 0.7,
                "export_tone_onsets": onsets,
                "nonzero_in_narration_gaps": True,
            }
            checks += ["looping music export preserves narration timing"]
        with runtime(resources, directory) as client:
            assert (
                call(client, "GET", f"/projects/{pid}")["scenes"] == applied["scenes"]
            )
            assert client.post("/api" + prefix + "/apply", json=body).status_code == 409
            checks += [
                "restart persistence and expired proposal rejection",
                "clean sidecar shutdown",
            ]
    result = {
        "version": "0.2.6",
        "isolated_data": True,
        "real_nano_inference": False,
        "real_speech": "bundled local Kokoro af_heart English",
        "metrics": metrics,
        "checks": checks,
        "passed": True,
    }
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, default=ROOT / "dist/JDH Shorts Studio.app")
    parser.add_argument(
        "--report", type=Path, default=ROOT / "docs/qa/pacing-runtime.json"
    )
    args = parser.parse_args()
    main(args.app, args.report)
