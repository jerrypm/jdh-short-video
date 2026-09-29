"""Create explicitly labelled QA stills and a synthetic audio test tone."""

from pathlib import Path
import math
import struct
import wave
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[1]
out = root / "data/qa-input"
out.mkdir(parents=True, exist_ok=True)


def font(size):
    result = ImageFont.truetype(str(root / "assets/fonts/IBMPlexSans-Bold.ttf"), size)
    result.set_variation_by_axes([700, 100])
    return result


for i, (title, subtitle, color) in enumerate(
    [
        ("One idea.\nOne short.", "A small idea, clearly told.", "#29382B"),
        ("Show what\nyou build.", "Problem. Process. Result.", "#23374D"),
        ("Make the\nnext one.", "Save your style. Keep creating.", "#3B2D4D"),
    ]
):
    image = Image.new("RGB", (1080, 1920), color)
    draw = ImageDraw.Draw(image)
    draw.text((82, 110), "JDH / STUDIO TEST", font=font(30), fill="#C8F56A")
    draw.text((82, 520), title, font=font(116), fill="#F4F6F8", spacing=5)
    draw.line((82, 930, 998, 930), fill="#A9B3C2", width=2)
    draw.text((82, 990), subtitle, font=font(38), fill="#A9B3C2")
    draw.text(
        (82, 1730), f"FIXTURE QA  /  SCENE {i + 1:02}", font=font(28), fill="#A9B3C2"
    )
    image.save(out / f"scene-{i + 1}.png")
with wave.open(str(out / "test-tone.wav"), "wb") as wav:
    wav.setnchannels(1)
    wav.setsampwidth(2)
    wav.setframerate(24000)
    wav.writeframes(
        b"".join(
            struct.pack("<h", int(math.sin(i / 24000 * math.tau * 220) * 1500))
            for i in range(24000 * 3)
        )
    )
print(out)
