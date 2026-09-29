"""Compare React evaluator reference frames with real bundled FFmpeg exports."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import time
import wave
import numpy as np
from PIL import Image, ImageDraw
from verify_content_memory_runtime import ROOT, runtime, call
from verify_pacing_runtime import wait_job


def picture(size):
    image = Image.new("RGB", size, "#1d3557")
    draw = ImageDraw.Draw(image)
    w, h = size
    draw.rectangle((0, 0, w / 2, h / 2), fill="#e63946")
    draw.rectangle((w / 2, 0, w, h / 2), fill="#457b9d")
    draw.rectangle((0, h / 2, w / 2, h), fill="#e9c46a")
    draw.rectangle((w / 2, h / 2, w, h), fill="#2a9d8f")
    for x in [0.2, 0.5, 0.8]:
        for y in [0.2, 0.5, 0.8]:
            r = min(w, h) * 0.035
            draw.ellipse((w * x - r, h * y - r, w * x + r, h * y + r), fill="white")
    return image


def setup(client, directory, ffmpeg):
    project = call(
        client,
        "POST",
        "/projects",
        json={"name": "Task 07 · QA motion", "language": "en"},
    )
    pid = project["id"]
    assets = {}
    for name, size in [
        ("portrait", (1080, 1920)),
        ("landscape", (1600, 900)),
        ("square", (900, 900)),
    ]:
        path = directory / (name + ".png")
        picture(size).save(path)
        assets[name] = call(
            client,
            "POST",
            f"/projects/{pid}/media",
            files={"file": (path.name, path.read_bytes(), "image/png")},
        )["asset"]
    video = directory / "source.mp4"
    subprocess.run(
        [
            str(ffmpeg),
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=640x360:rate=30:duration=3",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        check=True,
    )
    assets["video"] = call(
        client,
        "POST",
        f"/projects/{pid}/media",
        files={"file": (video.name, video.read_bytes(), "video/mp4")},
    )["asset"]
    sound = io.BytesIO()
    with wave.open(sound, "wb") as output:
        output.setparams((1, 2, 24000, 0, "NONE", "not compressed"))
        tone = (np.sin(2 * np.pi * 440 * np.arange(6000) / 24000) * 10000).astype("<i2")
        output.writeframes(tone.tobytes())
    audio = call(
        client,
        "POST",
        f"/projects/{pid}/media",
        files={"file": ("tone.wav", sound.getvalue(), "audio/wav")},
    )["asset"]
    scenes = []
    for index, (preset, source, fit, frames) in enumerate(
        [
            ("zoom_in", "portrait", "fill", 9),
            ("zoom_out", "landscape", "fit", 30),
            ("pan_left", "square", "fill", 30),
            ("pan_right", "landscape", "fill", 30),
            ("pan_up", "portrait", "fit", 30),
            ("pan_down", "video", "fit", 30),
            ("none", "portrait", "fill", 9),
            ("none", "square", "fit", 9),
        ]
    ):
        scenes.append(
            {
                "id": f"scene{index}",
                "name": f"{preset} {source} {fit}",
                "duration": frames,
                "media_id": assets[source]["id"],
                "audio_id": audio["id"],
                "source_in": 30 if source == "video" else 0,
                "fit": fit,
                "scale": 1.1 if index == 3 else 1,
                "x": 24 if index == 3 else 0,
                "caption": "Keep the whole word." if index >= 6 else "",
                "motion": {
                    "version": 1,
                    "visual": {
                        "preset": preset,
                        "amount": 0.12,
                        "focus_x": 0.3,
                        "focus_y": 0.7,
                    },
                    "caption": {
                        "preset": "fade"
                        if index == 6
                        else "slide_up"
                        if index == 7
                        else "none",
                        "start_frame": 2,
                        "end_frame": 8,
                    },
                    "callout": {
                        "text": "Focus here",
                        "entrance": {
                            "preset": "fade",
                            "start_frame": 2,
                            "end_frame": 8,
                        },
                    }
                    if index == 7
                    else None,
                },
            }
        )
    project = call(client, "GET", f"/projects/{pid}")
    project["scenes"] = scenes
    return call(client, "PUT", f"/projects/{pid}", json=project), assets


def extract(ffmpeg, video, frame, destination):
    subprocess.run(
        [
            str(ffmpeg),
            "-v",
            "error",
            "-y",
            "-i",
            str(video),
            "-vf",
            f"select=eq(n\\,{frame})",
            "-frames:v",
            "1",
            str(destination),
        ],
        check=True,
    )
    return Image.open(destination).convert("RGBA")


def reference(source, scene, state, size, caption, callout):
    w, h = size
    canvas = Image.new("RGBA", size, "#101216")
    factor = (min if scene["fit"] == "fit" else max)(
        w / source.width, h / source.height
    ) * scene["scale"]
    sw = max(2, round(source.width * factor / 2) * 2)
    sh = max(2, round(source.height * factor / 2) * 2)
    rendered = source.resize((sw, sh), Image.Resampling.BICUBIC).convert("RGBA")
    canvas.alpha_composite(
        rendered,
        (
            int((w - sw) / 2 + scene["x"] * w / 1080),
            int((h - sh) / 2 + scene["y"] * h / 1920),
        ),
    )
    visual = state["visual"]
    z = visual["scale"]
    canvas = canvas.transform(
        size,
        Image.Transform.AFFINE,
        (1 / z, 0, -visual["x"] * w / 1080 / z, 0, 1 / z, -visual["y"] * h / 1920 / z),
        Image.Resampling.BICUBIC,
    )
    for image, transform in [(caption, state["caption"]), (callout, state["callout"])]:
        if image is None or transform is None:
            continue
        overlay = image.resize(size, Image.Resampling.BICUBIC)
        alpha = np.asarray(overlay.getchannel("A"), dtype=float) * transform["opacity"]
        overlay.putalpha(Image.fromarray(np.rint(alpha).astype("uint8")))
        canvas.alpha_composite(overlay, (0, round(transform["y"] * h / 1920)))
    return canvas.convert("RGB")


def main(app, report, artifacts):
    resources = app.resolve() / "Contents/Resources"
    ffmpeg = resources / "tools/bin/ffmpeg"
    checks, metrics = [], []
    artifacts.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="jdh-motion-runtime-qa-") as temporary:
        directory = Path(temporary)
        with runtime(resources, directory) as client:
            project, assets = setup(client, directory, ffmpeg)
            pid = project["id"]
            cases = []
            for scene in project["scenes"]:
                for frame in sorted({0, scene["duration"] // 2, scene["duration"] - 1}):
                    cases.append(
                        {
                            "motion": scene["motion"],
                            "frame": frame,
                            "duration": scene["duration"],
                            "enabled": True,
                        }
                    )
            result = subprocess.run(
                ["node", "--import", "tsx", "../script/motion_reference.ts"],
                input=json.dumps(cases),
                text=True,
                capture_output=True,
                check=True,
                cwd=ROOT / "web",
            )
            states = iter(json.loads(result.stdout))
            samples = []
            for index, scene in enumerate(project["scenes"]):
                response = client.post(
                    "/api/caption-preview",
                    json={"text": scene["caption"], "style": project["caption_style"]},
                )
                response.raise_for_status()
                caption = Image.open(io.BytesIO(response.content)).convert("RGBA")
                label = None
                if scene["motion"]["callout"]:
                    response = client.post(
                        "/api/callout-preview", json=scene["motion"]["callout"]
                    )
                    response.raise_for_status()
                    label = Image.open(io.BytesIO(response.content)).convert("RGBA")
                asset = next(
                    a for a in project["assets"] if a["id"] == scene["media_id"]
                )
                for frame in sorted({0, scene["duration"] // 2, scene["duration"] - 1}):
                    if asset["kind"] == "video":
                        source = extract(
                            ffmpeg,
                            directory / "source.mp4",
                            scene["source_in"] + frame,
                            directory / "source-frame.png",
                        )
                    else:
                        source = Image.open(
                            directory
                            / (
                                next(
                                    name
                                    for name, a in assets.items()
                                    if a["id"] == asset["id"]
                                )
                                + ".png"
                            )
                        ).convert("RGBA")
                    samples.append(
                        (index, scene, frame, next(states), source, caption, label)
                    )
            narration_hash = None
            for preset, size in [("draft", (360, 640)), ("final", (1080, 1920))]:
                start = time.monotonic()
                job = wait_job(
                    client,
                    call(
                        client,
                        "POST",
                        f"/projects/{pid}/render",
                        json={"preset": preset},
                    ),
                )
                video = artifacts / (preset + ".mp4")
                video.write_bytes(
                    client.get(f"/api/jobs/{job['id']}/files/{preset}.mp4").content
                )
                narration_hash = hashlib.sha256(
                    client.get(f"/api/jobs/{job['id']}/files/narration.wav").content
                ).hexdigest()
                errors = []
                for index, scene, frame, state, source, caption, label in samples:
                    offset = sum(s["duration"] for s in project["scenes"][:index])
                    exported = extract(
                        ffmpeg,
                        video,
                        offset + frame,
                        artifacts / f"{preset}-{index}-{frame}-export.png",
                    ).convert("RGB")
                    expected = reference(source, scene, state, size, caption, label)
                    expected.save(
                        artifacts / f"{preset}-{index}-{frame}-react-reference.png"
                    )
                    mae = float(
                        np.abs(
                            np.asarray(exported, dtype=float)
                            - np.asarray(expected, dtype=float)
                        ).mean()
                    )
                    errors.append(round(mae, 3))
                    assert mae < 8, (preset, index, frame, mae)
                metrics.append(
                    {
                        "preset": preset,
                        "frame_samples": len(errors),
                        "mean_absolute_pixel_errors_0_255": errors,
                        "max_error": max(errors),
                        "render_and_compare_seconds": round(
                            time.monotonic() - start, 2
                        ),
                    }
                )
                print(json.dumps(metrics[-1]), flush=True)
            checks += [
                "48 sampled frames compared with actual React evaluator",
                "all seven visual presets",
                "fade and slide text",
                "shared PNG caption and callout fonts",
                "nine-frame short scenes and keyframe boundaries",
                "portrait landscape square fit fill and source scale",
                "video trim retains source frame",
                "draft and final decode",
            ]
            project["motion_mode"] = "none"
            project = call(client, "PUT", f"/projects/{pid}", json=project)
            job = wait_job(
                client,
                call(
                    client, "POST", f"/projects/{pid}/render", json={"preset": "draft"}
                ),
            )
            no_motion_hash = hashlib.sha256(
                client.get(f"/api/jobs/{job['id']}/files/narration.wav").content
            ).hexdigest()
            assert no_motion_hash == narration_hash
            assert job["result"]["frames"] == sum(
                s["duration"] for s in project["scenes"]
            )
            video = artifacts / "none.mp4"
            video.write_bytes(
                client.get(f"/api/jobs/{job['id']}/files/draft.mp4").content
            )
            for index, scene, frame, state, source, caption, label in [
                samples[0],
                samples[-1],
            ]:
                offset = sum(s["duration"] for s in project["scenes"][:index])
                state = {
                    "visual": {"scale": 1, "x": 0, "y": 0},
                    "caption": {"opacity": 1, "y": 0},
                    "callout": {"opacity": 1, "y": 0},
                }
                expected = reference(source, scene, state, (360, 640), caption, label)
                actual = extract(
                    ffmpeg, video, offset + frame, artifacts / f"none-{index}.png"
                ).convert("RGB")
                assert (
                    float(
                        np.abs(
                            np.asarray(actual, dtype=float)
                            - np.asarray(expected, dtype=float)
                        ).mean()
                    )
                    < 8
                )
            checks += [
                "project without motion renders static visuals and visible text",
                "identical narration WAV with motion enabled and disabled",
                "unchanged total timeline frames",
            ]
        with runtime(resources, directory) as client:
            restored = call(client, "GET", f"/projects/{pid}")
            assert (
                restored["scenes"] == project["scenes"]
                and restored["motion_mode"] == "none"
            )
            checks += ["versioned motion persists across bundled sidecar restart"]
    result = {
        "version": "0.2.7",
        "isolated_data": True,
        "real_nano_inference": False,
        "reference": "Actual React motion evaluator, composed with PIL; browser screenshots checked separately",
        "artifacts": str(artifacts),
        "metrics": metrics,
        "checks": checks,
        "passed": True,
    }
    report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, default=ROOT / "dist/JDH Shorts Studio.app")
    parser.add_argument(
        "--report", type=Path, default=ROOT / "docs/qa/motion-runtime.json"
    )
    parser.add_argument(
        "--artifacts",
        type=Path,
        default=Path(tempfile.mkdtemp(prefix="jdh-motion-frames-")),
    )
    args = parser.parse_args()
    main(args.app, args.report, args.artifacts)
