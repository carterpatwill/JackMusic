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

CREAM, GREEN_LIGHT = (255, 255, 255), (143, 174, 124)  # title white


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
    # Trim plain white borders (some exported photos have a white strip).
    mask = img.convert("L").point(lambda v: 255 if v < 240 else 0)
    box = mask.getbbox()
    if box and (box[2] - box[0]) > img.width * 0.8 and (box[3] - box[1]) > img.height * 0.8:
        img = img.crop(box)
    if img.width > width:
        img = img.resize((width, round(img.height * width / img.width)), Image.LANCZOS)
    img.save(out_path, "JPEG", quality=82, optimize=True, progressive=True)
    return img.width, img.height


def fit(size, max_w=360, max_h=340):
    """Display size for a photo: its own shape, no bigger than max_w x max_h."""
    w, h = size
    scale = min(max_w / w, max_h / h)
    return round(w * scale), round(h * scale)


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
    """Header: the site's black-and-white crowd photo, kept bright, with a
    dark fade at the bottom for the title, like the site's hero."""
    src = Image.open(os.path.join(ASSETS, HERO)).convert("RGB")
    scale = max(w / src.width, h / src.height)
    src = src.resize((round(src.width * scale), round(src.height * scale)), Image.LANCZOS)
    left, top = (src.width - w) // 2, (src.height - h) // 2
    img = src.crop((left, top, left + w, top + h))
    img = ImageEnhance.Contrast(img).enhance(1.15)
    img = ImageEnhance.Brightness(img).enhance(0.85)
    # Dark fade over the lower half only, so the stage and lights stay visible.
    fade = Image.linear_gradient("L").resize((w, h)).point(lambda v: max(0, int((v - 90) * 1.45)))
    img = Image.composite(Image.new("RGB", (w, h), (8, 8, 8)), img, fade.point(lambda v: min(235, v)))

    d = ImageDraw.Draw(img)
    small = ImageFont.truetype(BOLD, 24)
    d.text((48, 44), f"DROP {issue:03d}", font=small, fill=CREAM)
    wk = label.upper()
    d.text((w - 48 - d.textlength(wk, font=small), 44), wk, font=small, fill=CREAM)
    d.line((48, 84, w - 48, 84), fill=(255, 255, 255, 120), width=2)

    title = ImageFont.truetype(BLACK, 112)
    d.text((44, h - 205), "Quigley", font=title, fill=CREAM, anchor="ls")
    d.text((44, h - 100), "Discovery", font=title, fill=CREAM, anchor="ls")
    tag = ImageFont.truetype(_font_file("'Sorean'"), 38)
    d.text((50, h - 42), "Today's independents, tomorrow's superstars.", font=tag, fill=(215, 215, 215), anchor="ls")
    img.save(out_path, "JPEG", quality=84, optimize=True, progressive=True)
    return w // 2, h // 2
