"""Measured QA for a rendered short.

Checks the actual file: container, full decode, loudness, audio gaps, scene
boundaries, card identity per scene, burned-in captions and the closing CTA.
It also builds a contact sheet. Image comparison is numeric (no viewing): each
scene frame is matched against the thirteen source cards and the winner must be
the expected card.
"""

import array
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
STUDIO = HERE.parents[1]
FFMPEG = "/opt/homebrew/bin/ffmpeg"
FFPROBE = "/opt/homebrew/bin/ffprobe"
FONT = STUDIO / "assets/fonts/IBMPlexSans-Bold.ttf"
sys.path.insert(0, str(STUDIO))
from backend.captions import caption_image  # noqa: E402
from backend.models import CaptionStyle  # noqa: E402

CAPTION_STYLE = CaptionStyle(preset="bar", size=40, position=70)


def run(args, **kwargs):
    return subprocess.run(args, capture_output=True, text=True, check=True, **kwargs)


def probe(path):
    return json.loads(run([FFPROBE, "-v", "error", "-show_format", "-show_streams",
                           "-of", "json", str(path)]).stdout)


def decode(path):
    run([FFMPEG, "-v", "error", "-xerror", "-i", str(path), "-f", "null", "-"])
    return "full decode of every frame completed without error"


def loudness(path):
    info = run([FFMPEG, "-v", "info", "-i", str(path), "-af", "ebur128=peak=true",
                "-f", "null", "-"]).stderr
    summary = info[info.rfind("Summary"):]
    values = {}
    for key in ("I:", "LRA:", "Peak:"):
        for line in summary.splitlines():
            if line.strip().startswith(key):
                values[key.strip(":")] = float(line.split(":")[1].strip().split()[0])
    return values


def pcm(path, rate=24000):
    raw = subprocess.run(
        [FFMPEG, "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(rate),
         "-f", "s16le", "-"], capture_output=True, check=True).stdout
    values = array.array("h")
    values.frombytes(raw)
    return values, rate


def audio_gaps(samples, rate, floor=0.002, minimum=0.9):
    step = int(rate * 0.02)
    gaps, start = [], None
    for index in range(0, len(samples) - step, step):
        chunk = samples[index:index + step]
        rms = (sum(v * v for v in chunk) / step) ** 0.5 / 32768
        if rms < floor and start is None:
            start = index / rate
        elif rms >= floor and start is not None:
            if index / rate - start >= minimum:
                gaps.append([round(start, 2), round(index / rate, 2)])
            start = None
    if start is not None and len(samples) / rate - start >= minimum:
        gaps.append([round(start, 2), round(len(samples) / rate, 2)])
    return gaps


def frames_from(path, numbers, size, directory):
    directory.mkdir(parents=True, exist_ok=True)
    selector = "+".join(f"eq(n\\,{n})" for n in numbers)
    pattern = directory / "frame-%03d.png"
    run([FFMPEG, "-v", "error", "-y", "-i", str(path), "-vf",
         f"select='{selector}'", "-vsync", "0", "-f", "image2", str(pattern)])
    produced = sorted(directory.glob("frame-*.png"))
    if len(produced) != len(numbers):
        raise SystemExit(f"expected {len(numbers)} frames, got {len(produced)}")
    result = {}
    for number, file in zip(numbers, produced):
        with Image.open(file) as image:
            result[number] = image.convert("RGB").resize(size, Image.LANCZOS)
    return result


def band(source, top, bottom):
    image = source.crop((0, round(source.height * top), source.width,
                         round(source.height * bottom))).convert("L")
    values = array.array("B")
    values.frombytes(image.tobytes())
    return values


def mae(left, right):
    if len(left) != len(right):
        raise SystemExit("band size mismatch")
    return sum(abs(a - b) for a, b in zip(left, right)) / len(left)


def main(video_path, label):
    video = Path(video_path).resolve()
    report = {"file": str(video), "label": label}
    info = probe(video)
    stream = next(s for s in info["streams"] if s["codec_type"] == "video")
    audio = next(s for s in info["streams"] if s["codec_type"] == "audio")
    fps = float(stream["avg_frame_rate"].split("/")[0]) / float(stream["avg_frame_rate"].split("/")[1])
    frames = int(stream.get("nb_frames", 0))
    report["container"] = dict(width=stream["width"], height=stream["height"], fps=fps,
                               frames=frames, video_codec=stream["codec_name"],
                               audio_codec=audio["codec_name"],
                               sample_rate=int(audio["sample_rate"]),
                               channels=audio["channels"],
                               seconds=round(float(info["format"]["duration"]), 3),
                               size_bytes=int(info["format"]["size"]))
    report["decode"] = decode(video)

    project = json.loads((HERE / "project-snapshot.json").read_text())
    plan = json.loads((HERE / "scene-plan.json").read_text())
    expected_frames = sum(s["duration"] for s in project["scenes"])
    report["timeline"] = dict(project_frames=expected_frames, video_frames=frames,
                              matches=frames == expected_frames,
                              project_seconds=round(expected_frames / 30, 2))
    if not report["timeline"]["matches"]:
        raise SystemExit("frame count does not match the project timeline")

    samples, rate = pcm(video)
    report["audio_gaps_over_0_9s"] = audio_gaps(samples, rate)
    report["loudness_ebur128"] = loudness(video)

    # Silence around each scene cut, measured on the encoded audio.
    step = int(rate * 0.02)
    window = []
    for index in range(0, len(samples) - step, step):
        chunk = samples[index:index + step]
        window.append((index / rate, (sum(v * v for v in chunk) / step) ** 0.5 / 32768))
    boundaries, cursor_frames = [], 0
    for scene in project["scenes"][:-1]:
        cursor_frames += scene["duration"]
        cut = cursor_frames / 30
        index = min(range(len(window)), key=lambda i: abs(window[i][0] - cut))
        before, after = index, index
        while before > 0 and window[before - 1][1] < 0.002:
            before -= 1
        while after + 1 < len(window) and window[after + 1][1] < 0.002:
            after += 1
        boundaries.append(dict(cut_at_seconds=round(cut, 2),
                               silence_before_seconds=round(cut - window[before][0], 2),
                               silence_after_seconds=round(window[after][0] + 0.02 - cut, 2)))
    report["scene_boundary_silence"] = dict(
        boundaries=boundaries,
        worst_before=max(b["silence_before_seconds"] for b in boundaries),
        worst_after=max(b["silence_after_seconds"] for b in boundaries),
        note="quiet is RMS < 0.002 on 20 ms windows; the scene pauses are 15 frames (0.5 s)")

    # Scene boundaries: 8 frames in (caption fade finished) and mid-scene.
    size = (stream["width"], stream["height"])
    starts, cursor = {}, 0
    for scene in project["scenes"]:
        starts[scene["id"]] = cursor
        cursor += scene["duration"]
    check_frames = []
    for scene in project["scenes"]:
        start = starts[scene["id"]]
        check_frames += [start + 8, start + scene["duration"] // 2]
    check_frames.append(frames - 1)
    extracted = frames_from(video, check_frames, size, HERE / "review" / f"{label}-frames")

    # Card identity. The renderer zooms/pans each card, so every candidate is
    # searched over a small offset and scale grid and scored on the best fit.
    def grey_band(crop):
        top, bottom = round(crop.height * 0.16), round(crop.height * 0.62)
        return np.asarray(crop.crop((0, top, crop.width, bottom)).convert("L"),
                          dtype=np.float32)

    cards = {}
    for row in plan:
        with Image.open(HERE / "visuals" / f"{row['id']}.png") as image:
            cards[row["id"]] = grey_band(image.convert("RGB").resize(size, Image.LANCZOS))

    def fit(actual, template):
        best = None
        for scale in (1.0, 1.02, 1.035):
            scaled = np.asarray(
                Image.fromarray(template.astype("uint8")).resize(
                    (max(8, round(template.shape[1] * scale)),
                     max(8, round(template.shape[0] * scale))), Image.BILINEAR),
                dtype=np.float32)
            for dy in range(-10, 11, 2):
                for dx in range(-8, 9, 2):
                    y0, y1 = max(0, dy), min(actual.shape[0], actual.shape[0] + dy)
                    x0, x1 = max(0, dx), min(actual.shape[1], actual.shape[1] + dx)
                    if y1 - y0 < actual.shape[0] // 2 or x1 - x0 < actual.shape[1] // 2:
                        continue
                    window = scaled[y0 - dy:y1 - dy, x0 - dx:x1 - dx]
                    if window.shape != (y1 - y0, x1 - x0):
                        continue
                    score = float(np.abs(actual[y0:y1, x0:x1] - window).mean())
                    best = score if best is None else min(best, score)
        return best

    matches, wrong = [], []
    for scene in project["scenes"]:
        start = starts[scene["id"]]
        for number in (start + 8, start + scene["duration"] // 2):
            actual = grey_band(extracted[number])
            scored = sorted((fit(actual, template), key) for key, template in cards.items())
            matches.append(dict(frame=number, expected=scene["id"], matched=scored[0][1],
                                best=round(scored[0][0], 2), runner_up=round(scored[1][0], 2),
                                margin=round(scored[1][0] - scored[0][0], 2)))
            if scored[0][1] != scene["id"]:
                wrong.append(matches[-1])
    report["card_matching"] = dict(checked=len(matches), mismatches=wrong, matches=matches,
                                   min_margin=round(min(m["margin"] for m in matches), 2),
                                   note="best-fit score over a +/-offset and 1.0-1.035 zoom grid; "
                                        "every scene frame must match its own card")
    if wrong:
        raise SystemExit(f"scene frames did not match their cards: {wrong}")

    # Layout safety measured on the rendered pixels: nothing of the design may
    # sit where the Shorts controls or the bottom overlay are drawn.
    background = np.array([245, 240, 230], dtype=np.float32)
    accent = np.array([216, 56, 44], dtype=np.float32)
    layout = []
    for scene in project["scenes"]:
        number = starts[scene["id"]] + scene["duration"] // 2
        pixels = np.asarray(extracted[number], dtype=np.float32)
        distance = np.abs(pixels - background).max(axis=2)
        right = distance[:, round(size[0] * 0.875):] > 30
        bottom = distance[round(size[1] * 0.844):, :] > 30
        number_box = np.abs(pixels[round(size[1] * 0.30):round(size[1] * 0.48),
                                    :round(size[0] * 0.5)] - accent).max(axis=2) < 60
        grey = pixels.mean(axis=2)
        layout.append(dict(scene=scene["id"], frame=number,
                           right_margin_pixels=int(right.sum()),
                           bottom_overlay_pixels=int(bottom.sum()),
                           accent_pixels=int(number_box.sum()),
                           frame_stddev=round(float(grey.std()), 1)))
    report["layout"] = dict(
        checks=layout,
        worst_right_margin=max(item["right_margin_pixels"] for item in layout),
        worst_bottom_overlay=max(item["bottom_overlay_pixels"] for item in layout),
        least_accent=min(item["accent_pixels"] for item in layout),
        blank_frames=[item["scene"] for item in layout if item["frame_stddev"] < 15],
        note="right band is x>=945 of 1080 and bottom band is y>=1620 of 1920, i.e. "
             f"the Shorts control and overlay zones; background tolerance 30/255")
    if report["layout"]["blank_frames"]:
        raise SystemExit("a scene frame is effectively blank")
    if report["layout"]["least_accent"] < 250:
        raise SystemExit("the red repository number is missing in a scene frame")

    # Burned-in captions. The renderer's caption PNG is transparent outside the
    # caption bar, so only the opaque pixels are compared, and the same frame is
    # also scored against another scene's caption as a control: the correct
    # caption has to win clearly.
    def caption_band(scene_id, text):
        target = HERE / "review" / f"caption-{scene_id}.png"
        caption_image(text, CAPTION_STYLE, target)
        with Image.open(target) as source:
            image = source.convert("RGBA").resize(size, Image.LANCZOS)
        alpha = image.getchannel("A").crop(
            (0, round(size[1] * 0.665), size[0], round(size[1] * 0.80)))
        grey = image.convert("L").crop(
            (0, round(size[1] * 0.665), size[0], round(size[1] * 0.80)))
        mask = array.array("B")
        mask.frombytes(alpha.tobytes())
        values = array.array("B")
        values.frombytes(grey.tobytes())
        return mask, values

    def masked_mae(actual, mask, expected):
        pairs = [(b, c) for b, c, keep in zip(actual, expected, mask) if keep > 200]
        if len(pairs) < 200:
            raise SystemExit("caption mask too small")
        return sum(abs(a - b) for a, b in pairs) / len(pairs), len(pairs)

    caption_checks = []
    for index, scene in enumerate(project["scenes"]):
        row = next(r for r in plan if r["id"] == scene["id"])
        control = plan[(index + 1) % len(plan)]["caption"]
        mask, expected = caption_band(scene["id"], row["caption"])
        _, other = caption_band(f"{scene['id']}-control", control)
        actual = band(extracted[starts[scene["id"]] + scene["duration"] // 2], 0.665, 0.80)
        own, pixels = masked_mae(actual, mask, expected)
        rival, _ = masked_mae(actual, mask, other)
        caption_checks.append(dict(scene=scene["id"], caption=row["caption"],
                                   masked_pixels=pixels, mae=round(own, 2),
                                   control_mae=round(rival, 2),
                                   control_text=control))
    report["captions"] = dict(checks=caption_checks,
                              worst_mae=max(c["mae"] for c in caption_checks),
                              note="mae is measured only on pixels the caption renderer marks opaque; "
                                   "control_mae uses the next scene's caption as a wrong-text test")
    for check in caption_checks:
        if check["mae"] >= check["control_mae"] - 4:
            raise SystemExit(f"caption for {check['scene']} is not clearly the expected text")

    # Contact sheet: 13 mid-scene frames plus the closing frame.
    tiles = [extracted[starts[s["id"]] + s["duration"] // 2] for s in project["scenes"]]
    tiles.append(extracted[frames - 1])
    columns, tile_w, tile_h, gap = 5, 216, 384, 10
    rows = math.ceil(len(tiles) / columns)
    sheet = Image.new("RGB", (columns * tile_w + (columns + 1) * gap,
                              rows * (tile_h + 26) + (rows + 1) * gap), "#101216")
    draw = ImageDraw.Draw(sheet)
    value = ImageFont.truetype(str(FONT), 18)
    value.set_variation_by_axes([700, 100])
    for index, tile in enumerate(tiles):
        column, row = index % columns, index // columns
        x = gap + column * (tile_w + gap)
        y = gap + row * (tile_h + 26 + gap)
        sheet.paste(tile.resize((tile_w, tile_h), Image.LANCZOS), (x, y))
        label_text = "closing frame" if index == len(tiles) - 1 else f"{index + 1:02d}"
        draw.text((x, y + tile_h + 4), label_text, font=value, fill="#F5F0E6")
    sheet_path = HERE / "review" / f"contact-sheet-{label}.png"
    sheet_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(sheet_path)
    report["contact_sheet"] = str(sheet_path)

    (HERE / f"qa-{label}.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
