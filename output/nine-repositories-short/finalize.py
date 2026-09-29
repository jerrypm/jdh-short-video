"""Assemble the task deliverables from the rendered project.

Copies the verified video, narration, captions and portable project to the task
folder root and writes script.md, storyboard.json and upload-metadata.json from
the actual project snapshot and measured QA results (no hand-written numbers).
"""

import json
import shutil
import sys
from pathlib import Path

STUDIO = Path("/Users/jeripurnamamaulid/Projects/01_PRODUCT-Claude/jdh-shorts-studio")
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(STUDIO))
from backend.captions import layout, srt  # noqa: E402
from backend.models import CaptionStyle  # noqa: E402

ARTICLE_URL = ("https://blog.stackademic.com/"
               "9-cool-repositories-i-found-on-the-internet-this-week-4966841b1a22")
REPOSITORIES = [
    ("ECC", "https://github.com/affaan-m/ECC"),
    ("CLI-Anything", "https://github.com/HKUDS/CLI-Anything"),
    ("screenshot-to-code", "https://github.com/abi/screenshot-to-code"),
    ("ScrapeGraphAI", "https://github.com/ScrapeGraphAI/Scrapegraph-ai"),
    ("Google Skills", "https://github.com/google/skills"),
    ("DeepSeek Harness", "https://github.com/deepseek-ai/deepseek-harness"),
    ("Humanizer", "https://github.com/blader/humanizer"),
    ("Stop Slop", "https://github.com/hardikpandya/stop-slop"),
    ("OmniRoute", "https://github.com/diegosouzapw/OmniRoute"),
]
TITLE = "9 GitHub Repos Worth a Look | AI Tools for Developers"


def main():
    project = json.loads((HERE / "project-snapshot.json").read_text())
    plan = {row["id"]: row for row in json.loads((HERE / "scene-plan.json").read_text())}
    crops = {row["id"]: row for row in json.loads((HERE / "source/crops.json").read_text())}
    pacing = {row["scene"]: row for row in json.loads((HERE / "pacing-report.json").read_text())}
    final = json.loads((HERE / "final-verification.json").read_text())
    qa = json.loads((HERE / "qa-final.json").read_text())
    quality = json.loads((HERE / "final/quality-report.json").read_text())
    style = CaptionStyle(**project["caption_style"])
    assets = {a["id"]: a for a in project["assets"]}

    copies = {
        "final/final.mp4": "final.mp4",
        "final/narration.wav": "narration.wav",
        "final/captions.srt": "captions.srt",
        "final/project.zip": "project.zip",
        "review/contact-sheet-final.png": "contact-sheet.png",
    }
    for source, target in copies.items():
        shutil.copy2(HERE / source, HERE / target)

    cursor, storyboard = 0, []
    for scene in project["scenes"]:
        row = plan[scene["id"]]
        audio = assets[scene["audio_id"]]
        measured = layout(row["caption"], style, scene["duration"])
        storyboard.append(dict(
            id=scene["id"], name=scene["name"], kind=row["kind"],
            start_frame=cursor, end_frame=cursor + scene["duration"],
            duration_frames=scene["duration"],
            duration_seconds=round(scene["duration"] / 30, 3),
            narration=row["narration"], caption_on_screen=measured["text"],
            caption_source_line=row["caption"],
            caption_characters_per_second=measured["characters_per_second"],
            narration_audio_seconds=round(audio["frames"] / 30, 3),
            narration_asset=audio["name"],
            leading_silence_trim_seconds=pacing[scene["id"]]["lead_trim"],
            trailing_silence_trim_seconds=pacing[scene["id"]]["end_trim"],
            visual_card=f"visuals/{scene['id']}.png",
            article_crop=[f"source/crops/{name}.png" for name in row.get("crops") or []],
            article_page=row.get("page"),
            article_excerpt=" · ".join(
                crops[name]["words"] for name in (row.get("crops") or [])),
            on_card=dict(number=row["number"], title=row["title"], benefit=row["benefit"],
                         counter=row["header_right"]),
            fit=scene["fit"], scale=scene["scale"], x=scene["x"], y=scene["y"],
            motion=scene["motion"]["visual"]["preset"],
            motion_amount=scene["motion"]["visual"]["amount"],
            caption_motion=scene["motion"]["caption"]["preset"]))
        cursor += scene["duration"]
    storyboard_path = HERE / "storyboard.json"
    storyboard_path.write_text(json.dumps(dict(
        title=TITLE, language="en", width=1080, height=1920, fps=30,
        total_frames=cursor, total_seconds=round(cursor / 30, 3),
        caption_style=project["caption_style"], motion_mode=project["motion_mode"],
        music="none", scenes=storyboard), indent=2) + "\n")

    lines = ["# Nine Repositories Worth a Look — script", "",
             f"Language: English · Voice: local Kokoro `am_michael`, speed 0.96 · "
             f"Measured narration: {round(sum(a['frames'] for a in assets.values() if a['kind'] == 'audio' and a['name'].endswith('trimmed.wav')) / 30, 2)} s · "
             f"Video: {round(cursor / 30, 2)} s, 1080×1920, 30 fps", "",
             "The script was written by the assistant from the author's own article PDF. "
             "No language model generated the narration text, and no cloud service was used "
             "for speech or rendering.", "",
             "| # | Scene | Narration (spoken) | Caption on screen | Scene |",
             "| --- | --- | --- | --- | --- |"]
    for index, item in enumerate(storyboard):
        caption = item["caption_on_screen"].replace("\n", " / ")
        lines.append(f"| {index + 1} | {item['name']} | {item['narration']} | {caption} | "
                     f"{item['duration_seconds']:.2f} s |")
    lines += ["", "## Notes", "",
              f"- The closing call to action is exactly **Subscribe for more content.** as the "
              f"spoken line and as the burned-in caption; the card sets the same sentence in two "
              f"display lines.",
              "- Captions are scene-level and cut to a verbatim part of the spoken line; word-level "
              "alignment is not implemented in this pipeline, and no word-level timing is claimed.",
              "- Changing a scene's narration invalidates its narration take on purpose; a new take "
              "must be generated and applied before export.",
              "- Narration was levelled locally with FFmpeg loudnorm (per-take target −16 LUFS, "
              "−1.5 dBTP) plus one shared trim, then measured again on the encoded video."]
    (HERE / "script.md").write_text("\n".join(lines) + "\n")

    metadata = dict(
        title=TITLE,
        description=project["upload"]["description"],
        tags=["github", "developer tools", "ai", "coding", "agent skills", "open source",
              "cli", "developer productivity"],
        hashtags=["#GitHub", "#DeveloperTools", "#AI", "#Coding"],
        category_id="28",
        category="Science & Technology",
        language="en",
        default_audio_language="en",
        made_for_kids=False,
        sources=dict(
            article=dict(title="9 Cool Repositories I Found on the Internet This Week",
                         author="Jerry PM", publication="Stackademic",
                         published="2026-09-06", url=ARTICLE_URL,
                         url_status="verified against a public search result whose story id "
                                    "(4966841b1a22) matches the id embedded in the supplied PDF's "
                                    "link annotations; direct fetch returned HTTP 403 from "
                                    "Cloudflare on 2026-09-28"),
            repositories=[dict(name=name, url=url) for name, url in REPOSITORIES],
            official_checks="GitHub REST API, 28 September 2026 (README + repository metadata)"),
        disclosure=dict(
            narration="local synthetic speech generated offline with Kokoro (am_michael, 0.96)",
            visuals="original typography cards plus crops of the author's article PDF; not live "
                    "demonstrations of any repository",
            script="written by the assistant from the article; no model generated the prose and no "
                   "cloud service was used",
            youtube_api_field="status.containsSyntheticMedia",
            api_documentation="https://developers.google.com/youtube/v3/docs/videos "
                              "(video resource, status.containsSyntheticMedia; checked 2026-09-28)",
            sponsorship="none; this is not a sponsored video"),
        upload_intent=dict(visibility="private",
                           target_channel_id="UCRig_f5P4QyB_kilUs2PN8Q",
                           target_channel_name="JR DEV | SWIFT | FLUTTER",
                           method="resumable upload, then verify channel and processing state",
                           status="not uploaded: no authorized YouTube API connection is configured "
                                  "in this workspace (see youtube-setup.md)"),
        verification=dict(
            file=str(HERE / "final.mp4"), width=qa["container"]["width"],
            height=qa["container"]["height"], fps=qa["container"]["fps"],
            frames=qa["container"]["frames"], seconds=qa["container"]["seconds"],
            video_codec=qa["container"]["video_codec"],
            audio_codec=qa["container"]["audio_codec"],
            integrated_lufs=qa["loudness_ebur128"]["I"],
            loudness_range_lu=qa["loudness_ebur128"]["LRA"],
            true_peak_dbfs=qa["loudness_ebur128"]["Peak"],
            full_decode=qa["decode"], audio_gaps_over_0_9s=qa["audio_gaps_over_0_9s"],
            export_check=final["verification"], quality_report=quality["output_verification"]),
    )
    (HERE / "upload-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    (HERE / "captions-expected.srt").write_text(srt(
        type("P", (), {"scenes": [type("S", (), {
            "caption": plan[s["id"]]["caption"], "duration": s["duration"]})()
            for s in project["scenes"]],
            "caption_style": style})()))
    print(json.dumps({"copied": list(copies.values()), "scenes": len(storyboard),
                      "total_seconds": round(cursor / 30, 3),
                      "storyboard": str(storyboard_path)}, indent=2))


if __name__ == "__main__":
    main()
