"""Draws static/icon.svg (red "H" on a dark rounded square) as PNG/ICO for the desktop packages."""
import sys
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 1024
S = SIZE / 64  # icon.svg uses a 64x64 viewBox


def draw():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), radius=14 * S, fill="#0b0b0f")
    for x, y, w, h in ((18, 12, 9, 40), (37, 12, 9, 40), (18, 28, 28, 8)):
        d.rectangle((x * S, y * S, (x + w) * S - 1, (y + h) * S - 1), fill="#e5202e")
    return img


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "build/icons")
    out.mkdir(parents=True, exist_ok=True)
    icon = draw()
    icon.save(out / "homeflix.png")
    icon.resize((256, 256), Image.LANCZOS).save(out / "homeflix-256.png")
    icon.save(out / "homeflix.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print(f"icons written to {out}")
