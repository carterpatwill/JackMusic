"""Images for the weekly email, made with Pillow (local only, not on Render).

Email apps can't load the site's custom fonts, so each artist's name is
drawn as a PNG in that artist's own font, and the header is one image. The
artist photos are also shrunk to email-sized JPEGs (the originals run up to
1 MB). Everything goes in frontend/email/<week>/ so the live site hosts it
once pushed.

    pip install pillow
"""

import os
import re

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(__file__))
ASSETS = os.path.join(ROOT, "assets")
SYS_FONTS = "/System/Library/Fonts/Supplemental"

# Font family name (as written in seed.py title_font) -> file in assets/
FONT_FILES = {
    "Adventure": "9167230e83ae24466f565fabf7c1d930.otf",
    "ArmyRust": "924a37efddfe4c3dac73fe7e70cf0ed0.ttf",
    "Papernotes": "7513f410d59f84e3142de7ce592420e2.otf",
    "Vintage2": "1d1fd18bafb0ef484e8f29990dfd18a8.ttf",
    "Sorean": "aaada8b12fd73dc00a2ff7e16de3a2cd.otf",
}
HERO = "4f12d7bf223e102db5eb1f722bebd02e.jpg"
BLACK = os.path.join(SYS_FONTS, "Arial Black.ttf")
BOLD = os.path.join(SYS_FONTS, "Arial Bold.ttf")

CREAM, GREEN_LIGHT = (255, 251, 241), (143, 174, 124)


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _font_file(title_font):
    m = re.search(r"'([^']+)'", title_font or "")
    name = m.group(1) if m else ""
    return os.path.join(ASSETS, FONT_FILES[name]) if name in FONT_FILES else BLACK


# Some fonts look smaller than others at the same letter height.
OPTICAL = {"Adventure": 1.18}


def _has_glyph(font, ch):
    """False when the font would draw its 'missing glyph' box (or nothing)."""
    if ch.isspace():
        return True
    missing = font.getmask("\U0010FFFD")
    mask = font.getmask(ch)
    return mask.size != (0, 0) and (mask.size != missing.size or bytes(mask) != bytes(missing))


def name_image(text, title_font, color, out_path, ink_height=88, max_width=1000):
    """Artist name in its own font on a transparent background, sized so the
    letters' visible height is the same for every font. Characters the font
    lacks (e.g. the "!" in Themba!) fall back to Arial Black, like the site's
    font stack. Returns (w, h) at 1x (the PNG is 2x for sharp screens)."""
    path = _font_file(title_font)
    m = re.search(r"'([^']+)'", title_font or "")
    ink_height = int(ink_height * OPTICAL.get(m.group(1) if m else "", 1))

    probe = ImageFont.truetype(path, 200)
    own = "".join(ch for ch in text if _has_glyph(probe, ch)) or text
    l, t, r, b = probe.getbbox(own)
    size = int(200 * ink_height / max(1, b - t))

    def draw(size):
        font = ImageFont.truetype(path, size)
        # Fallback sized so its capital letters match this font's.
        fb_probe = ImageFont.truetype(BLACK, size)
        cap = font.getbbox("H")
        fb_cap = fb_probe.getbbox("H")
        fb = ImageFont.truetype(BLACK, max(1, int(size * (cap[3] - cap[1]) / max(1, fb_cap[3] - fb_cap[1]))))
        canvas = Image.new("RGBA", (size * (len(text) + 2), size * 3), (0, 0, 0, 0))
        d = ImageDraw.Draw(canvas)
        x, y = size // 2, size * 2
        for ch in text:
            f = font if _has_glyph(font, ch) else fb
            d.text((x, y), ch, font=f, fill=_hex(color) + (255,), anchor="ls")
            x += d.textlength(ch, font=f)
        return canvas.crop(canvas.getbbox())

    img = draw(size)
    if img.width > max_width:
        img = draw(int(size * max_width / img.width))
    pad = 6
    out = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    out.paste(img, (pad, pad))
    out.save(out_path, optimize=True)
    return out.width // 2, out.height // 2


def photo(src_name, out_path, width=1120):
    img = Image.open(os.path.join(ASSETS, src_name)).convert("RGB")
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    img.save(out_path, "JPEG", quality=82, optimize=True, progressive=True)
    return img.width // 2, img.height // 2


def _center(draw, y, text, font, fill, width, spacing=0):
    if spacing:
        widths = [draw.textlength(ch, font=font) for ch in text]
        x = (width - (sum(widths) + spacing * (len(text) - 1))) / 2
        for ch, w in zip(text, widths):
            draw.text((x, y), ch, font=font, fill=fill)
            x += w + spacing
    else:
        draw.text(((width - draw.textlength(text, font=font)) / 2, y), text, font=font, fill=fill)


def banner(label, issue, out_path, w=1200, h=760):
    """Header: the site's crowd photo, darkened and green-tinted, with the
    title, tagline and a 'drop' stamp."""
    src = Image.open(os.path.join(ASSETS, HERO)).convert("RGB")
    scale = max(w / src.width, h / src.height)
    src = src.resize((round(src.width * scale), round(src.height * scale)), Image.LANCZOS)
    left, top = (src.width - w) // 2, (src.height - h) // 2
    img = ImageEnhance.Brightness(src.crop((left, top, left + w, top + h))).enhance(0.55)
    tint = Image.new("RGB", (w, h), (20, 48, 28))
    img = Image.blend(img, tint, 0.35)
    # Fade the bottom to near-black so the text reads.
    fade = Image.linear_gradient("L").resize((w, h))
    img = Image.composite(Image.new("RGB", (w, h), (14, 22, 14)), img, fade.point(lambda v: int(v * 0.85)))

    d = ImageDraw.Draw(img)
    stamp_font = ImageFont.truetype(BOLD, 26)
    stamp = f"DROP {issue:03d}  ·  {label.upper()}"
    sw = d.textlength(stamp, font=stamp_font) + 56
    sx = (w - sw) / 2
    d.rounded_rectangle((sx, 64, sx + sw, 118), radius=27, outline=GREEN_LIGHT, width=3)
    _center(d, 76, stamp, stamp_font, GREEN_LIGHT, w)

    title = ImageFont.truetype(BLACK, 118)
    _center(d, h - 380, "QUIGLEY", title, CREAM, w, spacing=4)
    _center(d, h - 250, "DISCOVERY", title, (122, 190, 104), w, spacing=4)
    tag = ImageFont.truetype(_font_file("'Sorean'"), 46)
    _center(d, h - 96, "Today's independents, tomorrow's superstars.", tag, (216, 210, 184), w)
    img.save(out_path, "JPEG", quality=84, optimize=True, progressive=True)
    return w // 2, h // 2
