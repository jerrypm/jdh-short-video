from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from .models import CaptionStyle

FONT = Path(__file__).resolve().parents[1] / "assets/fonts/IBMPlexSans-Bold.ttf"


def layout(
    text: str, style: CaptionStyle, frames: int = 150, max_width: int = 850
) -> dict:
    """One layout for preview, export and review; explicit line breaks win."""
    font = ImageFont.truetype(str(FONT), style.size)
    font.set_variation_by_axes([700, 100])
    draw = ImageDraw.Draw(Image.new("L", (1, 1)))
    paragraphs = [" ".join(p.split()) for p in text.splitlines() if p.strip()]
    lines = []
    for paragraph in paragraphs:
        words = paragraph.split()
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if current and draw.textlength(candidate, font=font) > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
    # Balance only an automatically wrapped paragraph. Do not rewrite words or
    # override a user's explicit line break.
    if len(paragraphs) == 1 and len(lines) == 2:
        words = paragraphs[0].split()
        candidates = []
        for split in range(1, len(words)):
            pair = [" ".join(words[:split]), " ".join(words[split:])]
            widths = [draw.textlength(line, font=font) for line in pair]
            if max(widths) <= max_width:
                candidates.append((abs(widths[0] - widths[1]), pair))
        if candidates:
            lines = min(candidates, key=lambda item: item[0])[1]
    widths = [round(draw.textlength(line, font=font), 2) for line in lines]
    characters = len(" ".join(lines))
    cps = round(characters * 30 / max(frames, 1), 1)
    errors, warnings = [], []
    if len(lines) > 2 or any(width > max_width for width in widths):
        errors.append(
            "Caption terlalu panjang untuk dua baris. Pendekkan teks atau kurangi ukuran."
        )
    if characters and cps > 20:
        warnings.append(
            "Caption lebih dari 20 karakter/detik; pertimbangkan teks lebih pendek atau scene lebih lama."
        )
    if characters and frames < 30:
        warnings.append("Caption tampil kurang dari satu detik.")
    return {
        "text": "\n".join(lines),
        "lines": lines,
        "widths": widths,
        "characters_per_second": cps,
        "suggested_reading_frames": max(30, (characters * 30 + 19) // 20),
        "errors": errors,
        "warnings": warnings,
    }


def caption_image(text: str, style: CaptionStyle, path: Path):
    image = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    if not text.strip() or not style.enabled:
        image.save(path)
        return
    font = ImageFont.truetype(str(FONT), style.size)
    font.set_variation_by_axes([700, 100])
    draw = ImageDraw.Draw(image)
    measured = layout(text, style)
    if measured["errors"]:
        raise ValueError(" ".join(measured["errors"]))
    block = measured["text"]
    box = draw.multiline_textbbox((0, 0), block, font=font, spacing=8, align="center")
    width, height = box[2] - box[0], box[3] - box[1]
    x, y = (1080 - width) / 2, 1920 * style.position / 100
    if style.preset in {"lime", "bar"}:
        color = (200, 245, 106, 255) if style.preset == "lime" else (16, 18, 22, 199)
        draw.rounded_rectangle(
            (x - 18, y - 12, x + width + 18, y + height + 12), radius=8, fill=color
        )
    draw.multiline_text(
        (x, y - box[1]),
        block,
        font=font,
        fill="#14200B" if style.preset == "lime" else "#FFFFFF",
        spacing=8,
        align="center",
        stroke_width=2 if style.preset == "putih" else 0,
        stroke_fill="#101216",
    )
    image.save(path)


def callout_image(callout, path: Path):
    image = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    if callout is None:
        image.save(path)
        return
    measured = layout(
        callout.text, CaptionStyle(size=callout.size), max_width=callout.width - 32
    )
    if measured["errors"]:
        raise ValueError(
            "Callout terlalu panjang. Pendekkan teks, perbesar kotak atau kurangi ukuran."
        )
    font = ImageFont.truetype(str(FONT), callout.size)
    font.set_variation_by_axes([700, 100])
    draw = ImageDraw.Draw(image)
    box = draw.multiline_textbbox(
        (0, 0), measured["text"], font=font, spacing=8, align="center"
    )
    height = box[3] - box[1] + 32
    x, y, width = callout.x, callout.y, callout.width
    entrance_space = 48 if callout.entrance.preset == "slide_up" else 0
    if y + height + entrance_space > 1612:
        raise ValueError("Callout melewati batas bawah area aman.")
    tx, ty = callout.target_x, callout.target_y
    draw.line((x + width / 2, y + height / 2, tx, ty), fill="#C8F56A", width=4)
    draw.ellipse((tx - 6, ty - 6, tx + 6, ty + 6), fill="#C8F56A")
    draw.rounded_rectangle(
        (x, y, x + width, y + height),
        radius=12,
        fill="#101216",
        outline="#C8F56A",
        width=3,
    )
    draw.multiline_text(
        (x + (width - (box[2] - box[0])) / 2, y + 16 - box[1]),
        measured["text"],
        font=font,
        fill="#FFFFFF",
        spacing=8,
        align="center",
    )
    image.save(path)


def srt(project) -> str:
    def timestamp(frames):
        ms = round(frames / 30 * 1000)
        return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"

    offset, lines = 0, []
    for scene in project.scenes:
        if scene.caption.strip() and project.caption_style.enabled:
            block = layout(scene.caption, project.caption_style, scene.duration)["text"]
            lines.append(
                f"{len(lines) + 1}\n{timestamp(offset)} --> {timestamp(offset + scene.duration)}\n{block}\n"
            )
        offset += scene.duration
    return "\n".join(lines)
