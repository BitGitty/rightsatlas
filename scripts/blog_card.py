"""Branded title card for a blog post when Wikimedia Commons has no public-domain image.

  python scripts/blog_card.py <out-name.jpg> "Title" "1925" ["Verified public domain (US)"]

Writes content/blog/img/<out-name.jpg>, 1200x675 (16:9, good for link previews).
"""
import sys
import textwrap
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent.parent / "content" / "blog" / "img"
INK, PAPER, OK, WARN, NO = "#141414", "#F6F6F3", "#0E6B57", "#EDB045", "#B23A17"


def card(name, title, year, tag="Verified public domain (US)"):
    # PIL has neither Burmese glyphs in these fonts nor complex-script shaping: Burmese would render as boxes or in
    # the wrong order (2026-11-20). Keep cards Latin; put Burmese in the page text, where browsers shape it.
    if any("က" <= ch <= "႟" for ch in f"{title}{year}{tag}"):
        raise SystemExit("blog_card: Burmese text cannot be drawn correctly on a card; use English on the card")
    W, H = 1200, 675
    im = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(im)
    for i, c in enumerate((OK, WARN, OK, "#C9C9C2", NO)):  # the site's five-bar mark
        d.rectangle((60 + i * 22, 60, 76 + i * 22, 110), fill=c)
    d.text((190, 64), "RIGHTSATLAS", font=ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 40), fill=INK)
    big = ImageFont.truetype("C:/Windows/Fonts/georgiab.ttf", 84)
    lines = textwrap.wrap(title, 22)[:3]
    y = 200
    for ln in lines:
        d.text((60, y), ln, font=big, fill=INK)
        y += 100
    d.text((60, y + 10), str(year), font=ImageFont.truetype("C:/Windows/Fonts/georgia.ttf", 60), fill="#55554F")
    d.rectangle((0, H - 90, W, H), fill=INK)
    d.text((60, H - 68), tag, font=ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 40), fill=PAPER)
    OUT.mkdir(parents=True, exist_ok=True)
    im.save(OUT / name, quality=88)
    return OUT / name


if __name__ == "__main__":
    print(card(*sys.argv[1:]))
