"""Compose the visual cards and the scene plan for the nine-repository short.

Every card is 1080x1920 and keeps its content inside a safe band so the YouTube
Shorts right-side controls and the bottom overlay stay clear. Article crops come
from source/crops (see source/extract_source.py); this script only scales and
frames them, it never redraws article text.
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

STUDIO = Path("/Users/jeripurnamamaulid/Projects/01_PRODUCT-Claude/jdh-shorts-studio")
HERE = Path(__file__).resolve().parent
VIS = HERE / "visuals"
CROPS = HERE / "source/crops"
FONT = STUDIO / "assets/fonts/IBMPlexSans-Bold.ttf"

W, H = 1080, 1920
X0, X1 = 72, 920          # horizontal safe band
BG = "#F5F0E6"
PANEL = "#FFFDF8"
INK = "#141619"
BODY = "#3D4148"
MUTED = "#8A8377"
RED = "#D8382C"
RULE = "#DFD5C3"
BORDER = "#E3D9C7"

HEADER_Y = 112
RULE_Y = 166
LABEL_Y = 200
FRAME = (X0, 244, X1, 636)
NUMBER_Y = 684
TITLE_Y = 878
BENEFIT_Y = 1022
TITLE_SIZE = 92
BENEFIT_SIZE = 44
BENEFIT_LINE = 54

HEADER_SIZE = 27
LABEL_SIZE = 22
NUMBER_SIZE = 172
TRACK = 3


def font(size, weight=700):
    value = ImageFont.truetype(str(FONT), size)
    value.set_variation_by_axes([weight, 100])
    return value


def spaced(draw, xy, text, size, color, weight=600, track=TRACK):
    value = font(size, weight)
    x, y = xy
    for character in text:
        draw.text((x, y), character, font=value, fill=color)
        x += draw.textlength(character, font=value) + track
    return x


def spaced_width(draw, text, size, weight=600, track=TRACK):
    value = font(size, weight)
    return sum(draw.textlength(c, font=value) + track for c in text) - track


def wrap(draw, text, size, max_width, weight=700):
    value = font(size, weight)
    words, lines, current = text.split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and draw.textlength(candidate, font=value) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def grid(draw, image):
    for x in range(X0, X1 + 1, 106):
        draw.line((x, RULE_Y, x, 1560), fill="#EFE8DA", width=1)
    for y in range(RULE_Y, 1561, 106):
        draw.line((X0, y, X1, y), fill="#EFE8DA", width=1)
    draw.rectangle((0, 0, W, H), outline=None)
    return image


def header(draw, right):
    spaced(draw, (X0, HEADER_Y), "JRDEVHUB", HEADER_SIZE, MUTED)
    if right:
        width = spaced_width(draw, right, HEADER_SIZE, 600)
        spaced(draw, (X1 - width, HEADER_Y), right, HEADER_SIZE, MUTED)
    draw.line((X0, RULE_Y, X0 + 132, RULE_Y), fill=RED, width=4)
    draw.line((X0 + 132, RULE_Y, X1, RULE_Y), fill=RULE, width=3)


def excerpt(image, names, page, draw, report):
    """Stack the article strips inside one framed panel, scaled to stay readable."""
    draw.text((X0, LABEL_Y), f"FROM THE ARTICLE · PAGE {page}", font=font(LABEL_SIZE, 600),
              fill=MUTED)
    x0, y0, x1, y1 = FRAME
    draw.rectangle((x0, y0, x1, y1), fill=PANEL, outline=BORDER, width=3)
    strips = []
    for name in names:
        with Image.open(CROPS / f"{name}.png") as source:
            crop = source.convert("RGB")
        budget_w, budget_h = x1 - x0 - 28, 158 if len(names) > 1 else y1 - y0 - 28
        scale = min(budget_w / crop.width, budget_h / crop.height, 1.6)
        size = (max(1, round(crop.width * scale)), max(1, round(crop.height * scale)))
        strips.append((name, crop.resize(size, Image.LANCZOS)))
        report.append(dict(scene=name, crop=crop.size, scale=round(scale, 3),
                           placed=list(size),
                           text_height_px=None))
    gap = 26
    total = sum(s.height for _, s in strips) + gap * (len(strips) - 1)
    if total > y1 - y0 - 16:
        raise SystemExit(f"excerpt stack too tall: {total}")
    top = y0 + (y1 - y0 - total) // 2
    for _, strip in strips:
        image.paste(strip, (x0 + (x1 - x0 - strip.width) // 2, top))
        top += strip.height + gap


def text_block(draw, text, y, size, color, weight=700, leading=1.24, limit=2,
               shrink_to=None):
    lines = wrap(draw, text, size, X1 - X0, weight)
    if shrink_to:
        while size > shrink_to and any(
                draw.textlength(row, font=font(size, weight)) > X1 - X0 for row in lines):
            size -= 2
    if len(lines) > limit:
        raise SystemExit(f"text overflow: {text!r} -> {lines}")
    value = font(size, weight)
    for index, row in enumerate(lines):
        draw.text((X0, y + index * size * leading), row, font=value, fill=color)
    return [round(draw.textlength(row, font=value), 1) for row in lines]


def card(scene, page, report):
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    grid(draw, image)
    header(draw, scene["header_right"])
    if scene.get("crops"):
        excerpt(image, scene["crops"], page, draw, report)
    number = font(NUMBER_SIZE, 700)
    draw.text((X0 - 8, NUMBER_Y), scene["number"], font=number, fill=RED)
    widths = []
    if scene.get("title"):
        widths += text_block(draw, scene["title"], TITLE_Y, TITLE_SIZE, INK,
                             shrink_to=64)
    if scene.get("benefit"):
        draw.line((X0, BENEFIT_Y - 26, X0 + 64, BENEFIT_Y - 26), fill=RED, width=5)
        widths += text_block(draw, scene["benefit"], BENEFIT_Y, BENEFIT_SIZE, BODY,
                             weight=500)
    report.append(dict(scene=scene["id"], header_right=scene["header_right"],
                       number=scene["number"], title=scene.get("title"),
                       benefit=scene.get("benefit"), text_widths=widths,
                       widest=max(widths) if widths else 0))
    return image


def closing_card(scene, report):
    """CTA card: centered, no article excerpt."""
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    grid(draw, image)
    header(draw, scene["header_right"])
    spaced(draw, (X0, 560), "THAT'S ALL NINE", LABEL_SIZE, MUTED)
    # The spoken line and the burned-in caption are exactly "Subscribe for more
    # content."; the card sets the same sentence in two display lines.
    for index, (line, size, color) in enumerate([
            ("Subscribe", 150, INK), ("for more content.", 78, RED)]):
        value = font(size, 700)
        width = draw.textlength(line, font=value)
        if width > X1 - X0:
            raise SystemExit(f"CTA line too wide: {line}")
        draw.text((X0, 660 + (0 if index == 0 else 190)), line, font=value, fill=color)
        report.append(dict(scene=scene["id"], cta_line=line, width=round(width, 1)))
    draw.rectangle((X0, 1000, X0 + 132, 1006), fill=RED)
    body = font(42, 500)
    for index, line in enumerate([
        "Nine repositories, one pattern:",
        "more tools are being packaged",
        "for agents to use.",
    ]):
        draw.text((X0, 1090 + index * 56), line, font=body, fill=BODY)
    return image


SCENES = [
    dict(id="nine-repos-01", kind="hook", crops=["hook-title"], page=1, number="9",
         title="REPOSITORIES", header_right="SEP 6, 2026",
         benefit="Worth a closer look. One point each.",
         name="Hook", fit="fill", motion="zoom_in",
         narration="Nine repositories worth a closer look. One clear point each.",
         caption="Nine repositories worth a closer look."),
    dict(id="nine-repos-02", kind="repo", crops=["ecc-head", "ecc-slug"], page=2, number="01",
         title="ECC", header_right="1 / 9",
         benefit="Packaged skills, agents, and hooks. Choose selectively.",
         name="ECC", fit="fill", motion="zoom_out",
         narration="ECC packages skills, agents, and hooks. Start small.",
         caption="ECC packages skills, agents, and hooks."),
    dict(id="nine-repos-03", kind="repo", crops=["cli-anything-head", "cli-anything-slug"],
         page=3, number="02",
         title="CLI-Anything", header_right="2 / 9",
         benefit="Generates command-line tools agents can drive.",
         name="CLI-Anything", fit="fill", motion="pan_right",
         narration="CLI-Anything turns desktop software into command-line tools for agents.",
         caption="CLI-Anything turns desktop software into command-line tools."),
    dict(id="nine-repos-04", kind="repo",
         crops=["screenshot-to-code-head", "screenshot-to-code-slug"], page=5, number="03",
         title="Screenshot-to-code", header_right="3 / 9",
         benefit="Converts reference images into web layouts.",
         name="Screenshot-to-code", fit="fill", motion="zoom_in",
         narration="Screenshot-to-code turns reference images into web layouts. A first pass.",
         caption="Screenshot-to-code turns reference images into web layouts."),
    dict(id="nine-repos-05", kind="repo",
         crops=["scrapegraphai-head", "scrapegraphai-slug"], page=6, number="04",
         title="ScrapeGraphAI", header_right="4 / 9",
         benefit="Prompt-driven extraction of web data.",
         name="ScrapeGraphAI", fit="fill", motion="zoom_out",
         narration="ScrapeGraphAI extracts web data from prompts, not brittle selectors.",
         caption="ScrapeGraphAI extracts web data from prompts."),
    dict(id="nine-repos-06", kind="repo", crops=["google-skills"], page=9, number="05",
         title="Google Skills", header_right="5 / 9",
         benefit="Agent skills for cloud and developer workflows.",
         name="Google Skills", fit="fill", motion="pan_left",
         narration="Google Skills adds agent skills for cloud and developer workflows.",
         caption="Google Skills adds agent skills for cloud and developer workflows."),
    dict(id="nine-repos-07", kind="repo",
         crops=["deepseek-harness-head", "deepseek-harness-slug"], page=9, number="06",
         title="DeepSeek Harness", header_right="6 / 9",
         benefit="A plugin-based agent framework. Listed as a developer preview.",
         name="DeepSeek Harness", fit="fill", motion="zoom_in",
         narration="DeepSeek Harness is a plugin-based agent framework. A developer preview.",
         caption="DeepSeek Harness is a plugin-based agent framework."),
    dict(id="nine-repos-08", kind="repo", crops=["humanizer-head", "humanizer-slug"],
         page=11, number="07",
         title="Humanizer", header_right="7 / 9",
         benefit="Rewrites AI-style prose while preserving code and data.",
         name="Humanizer", fit="fill", motion="zoom_out",
         narration="Humanizer rewrites prose that sounds AI-generated, but leaves code alone.",
         caption="Humanizer rewrites prose that sounds AI-generated."),
    dict(id="nine-repos-09", kind="repo", crops=["stop-slop-head", "stop-slop-slug"],
         page=12, number="08",
         title="Stop Slop", header_right="8 / 9",
         benefit="Writing rules plus a rubric for reviewing prose.",
         name="Stop Slop", fit="fill", motion="zoom_in",
         narration="Stop Slop adds writing rules and a rubric for reviewing prose.",
         caption="Stop Slop adds writing rules and a rubric for reviewing prose."),
    dict(id="nine-repos-10", kind="repo", crops=["omniroute-head", "omniroute-slug"],
         page=13, number="09",
         title="OmniRoute", header_right="9 / 9",
         benefit="Routes requests across model providers.",
         name="OmniRoute", fit="fill", motion="zoom_out",
         narration="OmniRoute routes requests across model providers behind a single endpoint.",
         caption="OmniRoute routes requests across model providers."),
    dict(id="nine-repos-11", kind="pattern", crops=["pattern"], page=13, number="6/9",
         title="AGENT SKILLS", header_right="THE PATTERN",
         benefit="Six of nine install as something you hand to an agent.",
         name="The pattern", fit="fill", motion="pan_right",
         narration="The pattern? More tools are now packaged for agents to use.",
         caption="The pattern? More tools are now packaged for agents to use."),
    dict(id="nine-repos-12", kind="advice", crops=None, page=None, number="",
         title=None, header_right="BEFORE YOU INSTALL", benefit=None,
         name="Read the README", fit="fill", motion="zoom_in",
         narration="Pick what fits your workflow, and read the README first.",
         caption="Pick what fits your workflow. Read the README first."),
    dict(id="nine-repos-13", kind="cta", crops=None, page=None, number="", title=None,
         header_right="JRDEVHUB", benefit=None, name="Subscribe", fit="fill",
         motion="zoom_out", narration="Subscribe for more content.",
         caption="Subscribe for more content."),
]


def advice_card(scene, report):
    image = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(image)
    grid(draw, image)
    header(draw, scene["header_right"])
    spaced(draw, (X0, 520), "TWO CHECKS", LABEL_SIZE, MUTED)
    value = font(112, 700)
    for index, line in enumerate(["Read the", "README.", "Check the", "last commit."]):
        if draw.textlength(line, font=value) > X1 - X0:
            raise SystemExit(f"advice line too wide: {line}")
        draw.text((X0, 590 + index * 132), line, font=value,
                  fill=RED if index in {1, 3} else INK)
    draw.rectangle((X0, 1130, X0 + 132, 1136), fill=RED)
    body = font(42, 500)
    for index, line in enumerate([
        "Pick what fits your workflow.",
        "Cloned and read is not installed.",
    ]):
        draw.text((X0, 1190 + index * 56), line, font=body, fill=BODY)
    report.append(dict(scene=scene["id"], advice="Read the README. Check the last commit."))
    return image


def main():
    VIS.mkdir(exist_ok=True)
    report = []
    for scene in SCENES:
        if scene["kind"] == "cta":
            image = closing_card(scene, report)
        elif scene["kind"] == "advice":
            image = advice_card(scene, report)
        else:
            image = card(scene, scene.get("page"), report)
        target = VIS / f"{scene['id']}.png"
        image.save(target)
        assert image.size == (W, H), image.size
        print(f"{scene['id']} {scene['name']:18s} -> {target.name}")
    (HERE / "scene-plan.json").write_text(json.dumps(SCENES, indent=2) + "\n")
    (HERE / "visual-report.json").write_text(json.dumps(report, indent=2) + "\n")
    widest = max(item["widest"] for item in report if "widest" in item)
    smallest = min(item["scale"] for item in report if "scale" in item)
    print(json.dumps(dict(scenes=len(SCENES), widest_text_px=widest,
                          safe_band=[X0, X1], smallest_excerpt_scale=smallest)))


if __name__ == "__main__":
    sys.exit(main())
