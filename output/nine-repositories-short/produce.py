"""Produce the nine-repository short through JDH Shorts Studio's local API.

Modes:
  prepare  create a new project, import the cards, generate Kokoro narration,
           apply it, then set scene durations, motion and captions
  level    measure the narration with FFmpeg, apply one conservative gain and
           re-import the levelled takes (loudness target -16 LUFS)
  draft    run the Shorts checks and render the 360x640 draft
  final    run the Shorts checks and render the 1080x1920 final

The server is a task-owned instance: JDH_DATA_DIR points at this task's data
folder, so the Heartwoodfall project and every existing asset stay untouched.
"""

import json
import math
import subprocess
import sys
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
STUDIO = HERE.parents[1]
STATE = HERE / "production-state.json"
PLAN = json.loads((HERE / "scene-plan.json").read_text())
BASE = "http://127.0.0.1:56125"
FFMPEG = "/opt/homebrew/bin/ffmpeg"
VOICE = "am_michael"
SPEED = 0.96
PAUSE_FRAMES = 9
CTA_PAUSE_FRAMES = 12
# Size 40 keeps the widest caption bar inside x<=930 of 1080, clear of the
# Shorts right-side controls, and the block bottom at 1468, clear of the bottom
# overlay. Verified again on the rendered pixels by qa_check.py.
CAPTION_STYLE = {"preset": "bar", "size": 40, "position": 70}
LUFS_TARGET = -16.0
TP_CEILING = -1.5
NAME = "Nine Repositories Worth a Look"
REFERENCE = ("Jerry PM — 9 Cool Repositories I Found on the Internet This Week "
             "(Stackademic, 6 September 2026; author-supplied PDF)")


def checkpoint(value):
    STATE.write_text(json.dumps(value, indent=2) + "\n")


def envelope(path, rate=24000, window=0.02):
    """Decode to mono PCM and return (window seconds, rms list)."""
    import array
    raw = subprocess.run(
        [FFMPEG, "-v", "error", "-nostdin", "-i", str(path), "-vn", "-ac", "1",
         "-ar", str(rate), "-f", "s16le", "-"], capture_output=True, check=True).stdout
    samples = array.array("h")
    samples.frombytes(raw)
    step = int(rate * window)
    values = []
    for index in range(0, len(samples) - step, step):
        chunk = samples[index:index + step]
        values.append((sum(sample * sample for sample in chunk) / step) ** 0.5 / 32768)
    return window, values


def speech_span(path):
    """First and last speech window, so leading/trailing near-silence can go."""
    window, values = envelope(path)
    ordered = sorted(values)
    loud = ordered[int(len(ordered) * 0.9)] or 1e-6
    threshold = max(0.002, loud * 0.02)
    active = [index for index, value in enumerate(values) if value >= threshold]
    if not active:
        raise SystemExit(f"no speech found in {path}")
    return (active[0] * window, (active[-1] + 1) * window, window * len(values), threshold)


def probe_duration(path):
    out = subprocess.run(
        ["/opt/homebrew/bin/ffprobe", "-v", "error", "-show_entries",
         "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def measure(paths, listing):
    """One-pass loudnorm measurement of the concatenated narration."""
    args = [FFMPEG, "-v", "info", "-nostdin", "-f", "concat", "-safe", "1", "-i",
            str(listing), "-af", "loudnorm=print_format=json", "-f", "null", "-"]
    text = subprocess.run(args, capture_output=True, text=True, check=True).stderr
    block = text[text.rfind("{"):text.rfind("}") + 1]
    return json.loads(block)


def main(mode):
    state = json.loads(STATE.read_text()) if STATE.exists() else {}
    with httpx.Client(base_url=BASE, trust_env=False, timeout=600) as client:
        client.headers["X-JDH-CSRF"] = client.get("/api/session").json()["csrf"]

        def call(method, path, **kwargs):
            response = client.request(method, "/api" + path, **kwargs)
            if response.status_code != 200:
                raise RuntimeError(f"{method} {path}: {response.status_code}: {response.text[:800]}")
            return response.json()

        def wait(job):
            started, last = time.monotonic(), None
            while True:
                current = call("GET", f"/jobs/{job['id']}")
                marker = (current["status"], current["message"])
                if marker != last:
                    print(json.dumps({"job": job["id"], "status": current["status"],
                                      "message": current["message"],
                                      "progress": current["progress"]}), flush=True)
                    last = marker
                if current["status"] == "completed":
                    return current
                if current["status"] in {"failed", "cancelled"}:
                    raise RuntimeError(current)
                if time.monotonic() - started > 1800:
                    raise RuntimeError("job timeout; project kept for continuation")
                time.sleep(0.5)

        def load():
            return call("GET", f"/projects/{state['project_id']}")

        def save(project):
            return call("PUT", f"/projects/{state['project_id']}", json=project)

        if not state:
            project = call("POST", "/projects", json={
                "name": NAME, "language": "en", "target": 60,
                "script": "\n\n".join(row["narration"] for row in PLAN),
                "reference": REFERENCE})
            state = {"project_id": project["id"], "visuals": {}, "audio": {}, "voice": VOICE,
                     "speed": SPEED, "tts_jobs": {}}
            checkpoint(state)
            print("created project", project["id"], flush=True)

        if mode == "rescript":
            # Editing narration invalidates its narration take on purpose: the
            # apply step refuses text that does not match the generated audio.
            project = load()
            for scene in project["scenes"]:
                row = next(r for r in PLAN if r["id"] == scene["id"])
                if scene["narration"] != row["narration"]:
                    state["audio"].pop(scene["id"], None)
                    scene["audio_id"] = None
                    scene["audio_text"] = ""
                scene["narration"] = row["narration"]
                scene["caption"] = row["caption"]
            project["script"] = "\n\n".join(row["narration"] for row in PLAN)
            project = save(project)
            checkpoint(state)
            print(json.dumps({"revision": project["revision"],
                              "pending_audio": [s["id"] for s in project["scenes"]
                                                if not s["audio_id"]]}), flush=True)

        elif mode == "prepare":
            for row in PLAN:
                if row["id"] in state["visuals"]:
                    continue
                path = HERE / "visuals" / f"{row['id']}.png"
                with path.open("rb") as stream:
                    value = call("POST", f"/projects/{state['project_id']}/media",
                                 files={"file": (f"{row['id']} card.png", stream, "image/png")})
                state["visuals"][row["id"]] = value["asset"]["id"]
                checkpoint(state)
            project = load()
            if not project["scenes"]:
                project["scenes"] = [
                    {"id": row["id"], "name": row["name"], "narration": row["narration"],
                     "caption": row["caption"], "duration": 150,
                     "media_id": state["visuals"][row["id"]], "fit": row["fit"],
                     "motion": {
                         "version": 1,
                         "visual": {"preset": row["motion"], "amount": 0.035,
                                    "focus_x": 0.5, "focus_y": 0.45},
                         "caption": {"preset": "fade", "end_frame": 6},
                         "callout": None}}
                    for row in PLAN]
                project["caption_style"] = dict(CAPTION_STYLE)
                project["narration_volume"] = 1.0
                project["music_volume"] = 0
                project["motion_mode"] = "gentle"
                project["reference_notes"] = (
                    "Built from the author-supplied PDF of '9 Cool Repositories I Found on the "
                    "Internet This Week' (Stackademic, 6 September 2026), pages 2, 3, 5, 6, 8, 9, 11, "
                    "12 and 13. Visuals are original typography cards plus crops of the article's own "
                    "section headings and repository slugs; they are excerpts, not live demos. "
                    "English narration was generated locally with Kokoro am_michael at 0.96 speed and "
                    "levelled locally with FFmpeg. Twemoji/Gemini Nano were not used. Star counts, "
                    "token-saving percentages and provider counts from the article are deliberately "
                    "omitted because they change.")
                project["upload"] = {
                    "title": "9 GitHub Repos Worth a Look | AI Tools for Developers",
                    "description": (
                        "Nine repositories from this roundup, one clear point each: agent skills and "
                        "hooks, command-line tools for desktop apps, screenshot-to-code, prompt-driven "
                        "scraping, an agent framework in developer preview, two prose editors and an AI "
                        "gateway.\n\nRepositories in the order I saved them:\n"
                        "1. ECC — https://github.com/affaan-m/ECC\n"
                        "2. CLI-Anything — https://github.com/HKUDS/CLI-Anything\n"
                        "3. screenshot-to-code — https://github.com/abi/screenshot-to-code\n"
                        "4. ScrapeGraphAI — https://github.com/ScrapeGraphAI/Scrapegraph-ai\n"
                        "5. Google Skills — https://github.com/google/skills\n"
                        "6. DeepSeek Harness — https://github.com/deepseek-ai/deepseek-harness\n"
                        "7. Humanizer — https://github.com/blader/humanizer\n"
                        "8. Stop Slop — https://github.com/hardikpandya/stop-slop\n"
                        "9. OmniRoute — https://github.com/diegosouzapw/OmniRoute\n\n"
                        "Source article: https://blog.stackademic.com/"
                        "9-cool-repositories-i-found-on-the-internet-this-week-4966841b1a22\n\n"
                        "Narration is local synthetic speech (Kokoro). Visuals are article imagery and "
                        "original typography, not live demonstrations of any repository.\n\n"
                        "#GitHub #DeveloperTools #AI #Coding")}
                project = save(project)
            for row in PLAN:
                project = load()
                scene = next(s for s in project["scenes"] if s["id"] == row["id"])
                if scene["audio_id"] and row["id"] in state["audio"]:
                    continue
                job = call("POST", f"/projects/{project['id']}/tts",
                           json={"scene_id": scene["id"], "voice": VOICE, "speed": SPEED})
                state["tts_jobs"][scene["id"]] = job["id"]
                checkpoint(state)
                result = wait(job)
                response = client.get(f"/api/jobs/{job['id']}/files/narration.wav")
                response.raise_for_status()
                (HERE / "audio").mkdir(exist_ok=True)
                (HERE / "audio" / f"{scene['id']}.wav").write_bytes(response.content)
                project = load()
                call("POST", f"/projects/{project['id']}/tts/{job['id']}/apply",
                     json={"revision": project["revision"]})
                print(json.dumps({"scene": scene["name"],
                                  "narration_seconds": round(result["result"]["frames"] / 30, 2)}),
                      flush=True)
            project = load()
            for scene in project["scenes"]:
                asset = next(a for a in project["assets"] if a["id"] == scene["audio_id"])
                state["audio"][scene["id"]] = asset["id"]
                pause = CTA_PAUSE_FRAMES if scene["id"] == "nine-repos-13" else PAUSE_FRAMES
                scene["duration"] = max(asset["frames"] + pause, 60)
            project["narration_volume"] = 1.0
            project = save(project)
            state["frames"] = sum(s["duration"] for s in project["scenes"])
            state["revision"] = project["revision"]
            checkpoint(state)
            (HERE / "project-snapshot.json").write_text(json.dumps(project, indent=2) + "\n")
            print(json.dumps({
                "project_id": project["id"], "seconds": round(state["frames"] / 30, 2),
                "revision": project["revision"],
                "scenes": [{"id": s["id"], "frames": s["duration"],
                            "audio": next(a for a in project["assets"]
                                          if a["id"] == s["audio_id"])["frames"]}
                           for s in project["scenes"]],
                "preflight": call("GET", f"/projects/{project['id']}/preflight")}), flush=True)

        elif mode == "level":
            # Speech only, one voice. A uniform trim would need +11 dB to reach
            # -16 LUFS, which would push the true peak 6 dB over the ceiling, so
            # each take is levelled with loudnorm (documented target, TP aware)
            # and then trimmed by one shared factor so the relative level between
            # scenes stays exactly as generated.
            normalized = HERE / "audio-normalized"
            target = HERE / "audio-leveled"
            normalized.mkdir(exist_ok=True)
            target.mkdir(exist_ok=True)
            listing = HERE / "audio" / "concat.txt"
            listing.write_text("\n".join(f"file '{row['id']}.wav'" for row in PLAN) + "\n")
            measured = measure(None, listing)
            durations = {row["id"]: probe_duration(HERE / "audio" / f"{row['id']}.wav")
                         for row in PLAN}
            for row in PLAN:
                subprocess.run(
                    [FFMPEG, "-v", "error", "-y", "-nostdin",
                     "-i", str(HERE / "audio" / f"{row['id']}.wav"),
                     "-af", f"loudnorm=I={LUFS_TARGET}:TP={TP_CEILING}:LRA=11",
                     "-ar", "48000", "-ac", "2", "-t", f"{durations[row['id']]:.3f}",
                     "-c:a", "pcm_s16le", str(normalized / f"{row['id']}.wav")], check=True)
            against = HERE / "audio-normalized" / "concat.txt"
            against.write_text("\n".join(f"file '{row['id']}.wav'" for row in PLAN) + "\n")
            first = measure(None, against)
            trim = round(min(LUFS_TARGET - float(first["input_i"]),
                             -1.4 - float(first["input_tp"])), 2)
            for row in PLAN:
                subprocess.run(
                    [FFMPEG, "-v", "error", "-y", "-nostdin",
                     "-i", str(normalized / f"{row['id']}.wav"),
                     "-af", f"volume={trim}dB", "-ar", "48000", "-ac", "2",
                     "-t", f"{durations[row['id']]:.3f}", "-c:a", "pcm_s16le",
                     str(target / f"{row['id']}.wav")], check=True)
            project = load()
            for row in PLAN:
                take = target / f"{row['id']}.wav"
                name = f"{row['name']} — Kokoro leveled.wav"
                existing = [a for a in project["assets"] if a["name"] == name]
                if existing:
                    asset = existing[0]
                else:
                    with take.open("rb") as stream:
                        value = call("POST", f"/projects/{project['id']}/media",
                                     files={"file": (name, stream, "audio/wav")})
                    asset = value["asset"]
                    project = load()
                state.setdefault("leveled", {})[row["id"]] = asset["id"]
                checkpoint(state)
            project = load()
            for scene in project["scenes"]:
                scene["audio_id"] = state["leveled"][scene["id"]]
                scene["audio_in"] = 0
                scene["audio_text"] = scene["narration"]
                asset = next(a for a in project["assets"] if a["id"] == scene["audio_id"])
                if asset["frames"] > scene["duration"]:
                    raise SystemExit(f"{scene['id']}: levelled audio longer than scene")
            project["narration_volume"] = 1.0
            project["reference_notes"] += (
                f" Narration levelled locally with FFmpeg loudnorm"
                f" (source {measured['input_i']} LUFS / {measured['input_tp']} dBTP,"
                f" per-take target {LUFS_TARGET} LUFS and {TP_CEILING} dBTP, shared trim"
                f" {trim} dB).")
            project = save(project)
            state["revision"] = project["revision"]
            state["loudness"] = {"source": measured, "after_loudnorm": first, "trim_db": trim}
            checkpoint(state)
            (HERE / "loudness-level.json").write_text(json.dumps(
                {"source": measured, "after_loudnorm": first, "trim_db": trim}, indent=2) + "\n")
            (HERE / "project-snapshot.json").write_text(json.dumps(project, indent=2) + "\n")
            print(json.dumps({"source": measured, "after_loudnorm": first, "trim_db": trim,
                              "revision": project["revision"],
                              "preflight": call("GET", f"/projects/{project['id']}/preflight")}),
                  flush=True)

        elif mode == "captions":
            project = load()
            project["caption_style"] = dict(CAPTION_STYLE)
            project = save(project)
            state["revision"] = project["revision"]
            checkpoint(state)
            (HERE / "project-snapshot.json").write_text(json.dumps(project, indent=2) + "\n")
            print(json.dumps({"caption_style": project["caption_style"],
                              "revision": project["revision"],
                              "preflight": call("GET", f"/projects/{project['id']}/preflight")}),
                  flush=True)

        elif mode == "pace":
            # The Kokoro takes carry about half a second of near-silence at each
            # end, so scene durations taken from the raw take leave a 1.3 s hole
            # between scenes. Trim the measured silence instead of padding it.
            trimmed = HERE / "audio-trimmed"
            trimmed.mkdir(exist_ok=True)
            project = load()
            report = []
            for row in PLAN:
                source = HERE / "audio-leveled" / f"{row['id']}.wav"
                start, end, total, threshold = speech_span(source)
                lead = max(0.0, start - 0.06)
                tail = min(total, end + 0.15)
                target = trimmed / f"{row['id']}.wav"
                subprocess.run(
                    [FFMPEG, "-v", "error", "-y", "-nostdin", "-i", str(source),
                     "-af", f"atrim=start={lead:.3f}:end={tail:.3f},asetpts=PTS-STARTPTS",
                     "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(target)],
                    check=True)
                name = f"{row['name']} — Kokoro leveled trimmed.wav"
                existing = [a for a in project["assets"] if a["name"] == name]
                if existing:
                    asset = existing[0]
                else:
                    with target.open("rb") as stream:
                        value = call("POST", f"/projects/{project['id']}/media",
                                     files={"file": (name, stream, "audio/wav")})
                    asset = value["asset"]
                    project = load()
                state.setdefault("trimmed", {})[row["id"]] = asset["id"]
                report.append(dict(scene=row["id"], source_seconds=round(total, 2),
                                   lead_trim=round(lead, 2), end_trim=round(total - tail, 2),
                                   kept_seconds=round(tail - lead, 2),
                                   take_frames=asset["frames"], threshold=round(threshold, 4)))
                checkpoint(state)
            project = load()
            for scene in project["scenes"]:
                scene["audio_id"] = state["trimmed"][scene["id"]]
                scene["audio_in"] = 0
                scene["audio_text"] = scene["narration"]
                asset = next(a for a in project["assets"] if a["id"] == scene["audio_id"])
                pause = 20 if scene["id"] == "nine-repos-13" else 15
                scene["duration"] = asset["frames"] + pause
            project = save(project)
            total = sum(s["duration"] for s in project["scenes"])
            state["revision"] = project["revision"]
            state["frames"] = total
            checkpoint(state)
            (HERE / "pacing-report.json").write_text(json.dumps(report, indent=2) + "\n")
            (HERE / "project-snapshot.json").write_text(json.dumps(project, indent=2) + "\n")
            print(json.dumps({"report": report, "seconds": round(total / 30, 2),
                              "revision": project["revision"],
                              "preflight": call("GET", f"/projects/{project['id']}/preflight")}),
                  flush=True)

        elif mode in {"draft", "final"}:
            project = load()
            checked = wait(call("POST", f"/quality/{project['id']}/checks",
                                json={"revision": project["revision"], "preset": mode}))
            (HERE / f"quality-{mode}-before.json").write_text(
                json.dumps(checked["result"], indent=2) + "\n")
            print(json.dumps({"findings": checked["result"].get("findings")}), flush=True)
            job = call("POST", f"/projects/{project['id']}/render",
                       json={"preset": mode, "check_id": checked["id"]})
            state[f"{mode}_job"] = job["id"]
            checkpoint(state)
            result = wait(job)
            downloads = HERE / mode
            downloads.mkdir(exist_ok=True)
            for name in result["files"]:
                response = client.get(f"/api/jobs/{job['id']}/files/{name}")
                response.raise_for_status()
                (downloads / name).write_bytes(response.content)
            (HERE / f"{mode}-verification.json").write_text(
                json.dumps(result["result"], indent=2) + "\n")
            print(json.dumps({"downloaded_to": str(downloads),
                              "verification": result["result"]}), flush=True)
        else:
            raise SystemExit(f"unknown mode {mode}")


if __name__ == "__main__":
    main(sys.argv[1])
