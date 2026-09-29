"""Extract verifiable crops from the author-supplied article PDF.

Text extraction and word boxes come from Poppler (pdftotext). Every crop is
defined by line ranges and then checked: forbidden tokens (star counts, token
savings, percentages) must not fall inside the exported rectangle.
"""

import html
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image

PDF = Path(
    "/Users/jeripurnamamaulid/Downloads/9 Cool Repositories I Found on the "
    "Internet This Week _ by Jerry PM _ Sep, 2026 _ Stackademic.pdf"
)
HERE = Path(__file__).resolve().parent
PAGES = HERE / "pages"
CROPS = HERE / "crops"
DPI = 300
SCALE = DPI / 72

# id: article pages the crop is taken from; from/to match the first/last line
# text; end_word trims the last line horizontally so the star count that follows
# the repository slug is never inside the rectangle.
CROP_SPECS = [
    dict(id="hook-title", page=1,
         from_line="9 Cool Repositories I Found on the",
         to_line="Jerry PM 7 min read"),
    dict(id="ecc", page=2, split=True,
         from_line="1. ECC", to_line="affaan-m/ECC", end_word="affaan-m/ECC"),
    dict(id="cli-anything", page=3, split=True,
         from_line="2. CLI-Anything", to_line="HKUDS/CLI-Anything",
         end_word="HKUDS/CLI-Anything"),
    dict(id="screenshot-to-code", page=5, split=True,
         from_line="3. screenshot-to-code", to_line="abi/screenshot-to-code",
         end_word="abi/screenshot-to-code"),
    dict(id="scrapegraphai", page=6, split=True,
         from_line="4. ScrapeGraphAI", to_line="ScrapeGraphAI/Scrapegraph-ai",
         end_word="ScrapeGraphAI/Scrapegraph-ai"),
    dict(id="google-skills", page=9,
         from_line="npx skills add google/skills",
         to_line="npx skills add google/skills"),
    dict(id="deepseek-harness", page=9, split=True,
         from_line="6. DeepSeek Harness", to_line="deepseek-ai/deepseek-harness",
         end_word="deepseek-ai/deepseek-harness"),
    dict(id="humanizer", page=11, split=True,
         from_line="7. Humanizer", to_line="blader/humanizer",
         end_word="blader/humanizer"),
    dict(id="stop-slop", page=12, split=True,
         from_line="8. Stop Slop", to_line="hardikpandya/stop-slop",
         end_word="hardikpandya/stop-slop"),
    dict(id="omniroute", page=13, split=True,
         from_line="9. OmniRoute", to_line="diegosouzapw/OmniRoute",
         end_word="diegosouzapw/OmniRoute"),
    dict(id="pattern", page=13,
         from_line="The pattern, stated plainly",
         to_line="Harness, Humanizer, Stop Slop. Six of nine."),
]

# Tokens that must never appear inside an exported crop. The article reports
# changing numbers (stars, tokens, providers); the video deliberately omits them.
FORBIDDEN = [r"stars", r"\d+\s*k\b", r"~?\d+k", r"%", r"tokens", r"providers",
             r"commits", r"followers"]


def run(args):
    return subprocess.run(args, capture_output=True, check=True, text=True).stdout


def page_lines(page):
    raw = run(["pdftotext", "-f", str(page), "-l", str(page), "-bbox-layout", str(PDF), "-"])
    lines = []
    for block in re.finditer(r"<line ([^>]*)>(.*?)</line>", raw, re.S):
        words = []
        for word in re.finditer(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>',
                                block.group(2), re.S):
            words.append(dict(
                text=html.unescape(word.group(5)),
                x0=float(word.group(1)), y0=float(word.group(2)),
                x1=float(word.group(3)), y1=float(word.group(4)),
            ))
        if words:
            lines.append(" ".join(w["text"] for w in words))
    return raw, lines


def parse_page(page):
    raw, lines = page_lines(page)
    result = []
    for block in re.finditer(r"<line ([^>]*)>(.*?)</line>", raw, re.S):
        words = []
        for word in re.finditer(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>',
                                block.group(2), re.S):
            words.append(dict(
                text=html.unescape(word.group(5)),
                x0=float(word.group(1)), y0=float(word.group(2)),
                x1=float(word.group(3)), y1=float(word.group(4)),
            ))
        if words:
            result.append(dict(text=" ".join(w["text"] for w in words), words=words))
    return result


def render_pages(pages):
    PAGES.mkdir(exist_ok=True)
    for page in sorted(pages):
        target = PAGES / f"page-{page:02d}.png"
        if not target.exists():
            run(["pdftoppm", "-r", str(DPI), "-png", "-f", str(page), "-l", str(page),
                 str(PDF), str(PAGES / f"page-{page:02d}")])
            produced = sorted(PAGES.glob(f"page-{page:02d}*.png"))
            if len(produced) != 1:
                raise SystemExit(f"unexpected render for page {page}: {produced}")
            produced[0].rename(target)
        yield page, target


def crop_pages(spec, lines):
    """Return (rect in points, included words, notes)."""
    start = end = None
    for index, line in enumerate(lines):
        if start is None and spec["from_line"] in line["text"]:
            start = index
        if spec["to_line"] in line["text"]:
            end = index
            break
    if start is None or end is None or end < start:
        raise SystemExit(f"{spec['id']}: could not locate line range")
    selected = []
    for index in range(start, end + 1):
        words = lines[index]["words"]
        if index == end and spec.get("end_word"):
            trimmed = []
            for word in words:
                trimmed.append(word)
                if spec["end_word"] in word["text"]:
                    break
            if spec["end_word"] not in trimmed[-1]["text"]:
                raise SystemExit(f"{spec['id']}: end_word not found on last line")
            words = trimmed
        selected.extend(words)
    rect = (
        min(w["x0"] for w in selected), min(w["y0"] for w in selected),
        max(w["x1"] for w in selected), max(w["y1"] for w in selected),
    )
    return rect, selected


def all_specs():
    """Repository entries also expose their heading and slug as separate strips."""
    result = []
    for spec in CROP_SPECS:
        result.append(spec)
        if spec.get("split"):
            result.append(dict(id=f"{spec['id']}-head", page=spec["page"],
                               from_line=spec["from_line"],
                               to_line=spec["from_line"]))
            result.append(dict(id=f"{spec['id']}-slug", page=spec["page"],
                               from_line=spec["to_line"],
                               to_line=spec["to_line"], end_word=spec["end_word"]))
    return result


def main():
    CROPS.mkdir(exist_ok=True)
    specs = all_specs()
    page_numbers = {spec["page"] for spec in specs}
    pages = {page: parse_page(page) for page, _ in render_pages(page_numbers)}
    report = []
    for spec in specs:
        rect, words = crop_pages(spec, pages[spec["page"]])
        text = " ".join(w["text"] for w in words)
        for pattern in FORBIDDEN:
            if re.search(pattern, text, re.I):
                raise SystemExit(f"{spec['id']}: forbidden token {pattern!r} inside crop")
        pad = 10
        x0 = max(0, rect[0] - pad)
        y0 = max(0, rect[1] - pad)
        x1 = rect[2] + pad
        y1 = rect[3] + pad
        box = (round(x0 * SCALE), round(y0 * SCALE), round(x1 * SCALE), round(y1 * SCALE))
        with Image.open(PAGES / f"page-{spec['page']:02d}.png") as page:
            image = page.crop(box).convert("RGB")
        target = CROPS / f"{spec['id']}.png"
        image.save(target)
        line_height = max(w["y1"] - w["y0"] for w in words)
        report.append(dict(
            id=spec["id"], page=spec["page"], dpi=DPI,
            rect_points=[round(v, 2) for v in rect],
            rect_pixels=list(box), size=[image.width, image.height],
            lines=max(len({round(w["y0"], 1) for w in words}), 1),
            source_text_height_px=round(line_height * SCALE, 1),
            words=text,
            forbidden_checked=FORBIDDEN,
        ))
        print(f"{spec['id']:20s} p.{spec['page']:<2d} {image.width}x{image.height}px  {text[:70]}")
    (HERE / "crops.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"crops": len(report), "dpi": DPI}))


if __name__ == "__main__":
    sys.exit(main())
