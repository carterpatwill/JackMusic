"""Build the weekly email for the mailing list (a draft to paste into Kit).

    .venv/bin/python -m backend.email_draft            # current week
    .venv/bin/python -m backend.email_draft 2026-11-23 # a specific week

It sends nothing, and it reads only saved DB data (no API calls). It writes:

- frontend/email/<week>/  the images (header, artist names drawn in their
  own fonts, email-sized photos) plus index.html, the "view in browser"
  copy. Push these so the live site hosts the images, BEFORE sending.
- emails/week-<week>.html  the same email with full live-site links. Paste
  its HTML into a Kit broadcast (Kit adds the unsubscribe footer itself).

Email apps ignore web fonts and most CSS, so the layout is tables with
inline styles, and anything that needs a custom font is an image.
Needs Pillow locally (pip install pillow); see backend/email_art.py.
"""

import glob
import html
import os
import sys
from datetime import date

from . import db, email_art, seed

SITE = "https://www.quigleydiscovery.com"
PLAYLIST = "https://open.spotify.com/playlist/3cFHp7d52RIgABkrrFsjii"
ROOT = os.path.dirname(os.path.dirname(__file__))
OUT_DIR = os.path.join(ROOT, "emails")

# Colors (frontend/styles.css), plus the darker "stage" greens of the email.
# Black and white with neutral greys (no cream).
BG, CARD, INK, MUTED, ACCENT, LINE = "#EFEFEF", "#FFFFFF", "#141414", "#6B6B6B", "#111111", "#E2E2E2"
DEEP, DEEP_2, DEEP_3, SAGE, GOLD = "#111111", "#111111", "#2B2B2B", "#B8B8B8", "#FFFFFF"
MUTED_LIGHT = "#B8B8B8"  # quiet text on the black boxes
FONT = "Arial, Helvetica, sans-serif"
HEAVY = "'Arial Black', Arial, Helvetica, sans-serif"

# The intro under the header. Write your own each week, one string per
# paragraph. The last one is shown big, as the pull quote.
INTRO = [
    "Welcome to the first weekly release of Quigley Discovery. I'm super "
    "excited to share the first five artists with you for the week of "
    "November 23, 2026.",
    "The goal of Quigley Discovery is to showcase artists who raise the bar "
    "and are on track to break through to the next level. Each week, I figure "
    "out what I'm willing to invest in each artist. A playlist add? A follow? "
    "Sharing with a friend? Purchasing merch? Buying a concert ticket?",
    "How will you invest in these artists?",
]


def esc(s):
    return html.escape(s or "", quote=True)


def fmt(n):
    return f"{n:,}" if isinstance(n, int) else None


class Email:
    def __init__(self, week_of, base, banner_size):
        self.week_of = week_of
        self.base = base  # "" for the web copy (relative links), SITE for Kit
        self.banner_size = banner_size

    def url(self, path):
        return path if not path or path.startswith("http") else self.base + path

    def img(self, name):
        return self.url(f"/email/{self.week_of}/{name}")

    # ---- small pieces ----------------------------------------------------
    def button(self, href, label, fg, bg, border=None):
        border = border or bg
        return (f'<a href="{esc(self.url(href))}" style="display:inline-block;background:{bg};color:{fg};'
                f'border:2px solid {border};padding:10px 18px;border-radius:999px;font-family:{FONT};'
                f'font-size:14px;font-weight:bold;text-decoration:none;margin:0 6px 8px 0;">{esc(label)}</a>')

    def buttons(self, a, dark):
        solid_fg, solid_bg = (DEEP_2, CARD) if dark else (CARD, ACCENT)
        line = CARD if dark else ACCENT
        out = [self.button(a["profile_href"], "Full profile →", solid_fg, solid_bg)]
        for key, label in (("tiktok_url", "TikTok"), ("spotify_url", "Spotify"), ("youtube_url", "YouTube"),
                           ("instagram_url", "Instagram")):
            if a.get(key):
                out.append(self.button(a[key], label, line, "transparent", line))
        return "".join(out)

    def chips(self, a, dark):
        s, items = a["stats"], []
        if fmt(s.get("youtube_views")):
            items.append((fmt(s["youtube_views"]), "YouTube views"))
        if fmt(s.get("youtube_subs")):
            items.append((fmt(s["youtube_subs"]), "YouTube subs"))
        if fmt(a.get("ig_followers")):
            items.append((fmt(a["ig_followers"]), "IG followers"))
        pct = s.get("views_trend_pct")
        if s.get("has_youtube_data") and pct is not None:
            items.append((f"{'↑ +' if pct >= 0 else '↓ '}{pct:.1f}%", "views this week"))
        if not items:
            return ""
        bg, num, lab = (DEEP_3, CARD, SAGE) if dark else ("#F0F0F0", INK, MUTED)
        cells = "".join(
            f'<div style="display:inline-block;vertical-align:top;background:{bg};border-radius:10px;'
            f'padding:9px 13px;margin:0 6px 6px 0;">'
            f'<div style="font-family:{HEAVY};font-size:17px;line-height:1.2;color:{num};">{esc(v)}</div>'
            f'<div style="font-family:{FONT};font-size:10px;font-weight:bold;letter-spacing:.1em;'
            f'text-transform:uppercase;color:{lab};margin-top:2px;">{esc(k)}</div></div>'
            for v, k in items)
        return f'<div style="margin:16px 0 4px 0;">{cells}</div>'

    def tag(self, a, dark):
        bg, fg = (DEEP_3, SAGE) if dark else ("#EAEAEA", INK)
        return (f'<span style="display:inline-block;background:{esc(bg)};color:{esc(fg)};font-family:{FONT};'
                f'font-size:11px;font-weight:bold;letter-spacing:.1em;text-transform:uppercase;'
                f'padding:5px 11px;border-radius:999px;">{esc(a["tag"])}</span>')

    # ---- sections --------------------------------------------------------
    def artist(self, a, n, featured):
        dark = featured
        bg, text, num_color = (DEEP_2, "#E8E8E8", SAGE) if dark else (CARD, INK, INK)
        border = "" if dark else f"border:1px solid {LINE};"
        strip = "" if dark else (f'<tr><td style="height:8px;line-height:8px;font-size:0;background:{INK};'
                                 f'border-radius:16px 16px 0 0;">&nbsp;</td></tr>')
        pick = (f'<td align="right" style="vertical-align:middle;"><span style="display:inline-block;background:{GOLD};'
                f'color:{DEEP};font-family:{FONT};font-size:11px;font-weight:bold;letter-spacing:.12em;'
                f'padding:6px 12px;border-radius:999px;">★ TOP PICK</span></td>') if featured else ""
        name_w, name_h = a["_name_size"]
        profile = esc(self.url(a["profile_href"]))
        photo = ""
        if a.get("_photo"):
            pw, ph = a["_photo_size"]
            photo = (f'<a href="{profile}"><img src="{esc(self.img(a["_photo"]))}" '
                     f'width="{pw}" height="{ph}" alt="{esc(a["name"])}" style="display:block;width:{pw}px;'
                     f'max-width:100%;height:auto;border:0;border-radius:12px;margin:16px 0 0 0;"></a>')
        return f"""
<tr><td style="padding:0 0 22px 0;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"
         style="background:{bg};{border}border-radius:16px;">
    {strip}
    <tr><td style="padding:20px 22px 18px 22px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0"><tr>
        <td style="vertical-align:middle;font-family:{HEAVY};font-size:14px;letter-spacing:.1em;color:{esc(num_color)};">NO. {n:02d}</td>
        {pick}
      </tr></table>
      <a href="{profile}"><img src="{esc(self.img(a["_name"]))}" width="{name_w}" height="{name_h}"
         alt="{esc(a["name"])}" style="display:block;max-width:100%;height:auto;border:0;margin:14px 0 12px 0;
         font-family:{HEAVY};font-size:30px;color:{text};"></a>
      {self.tag(a, dark)}
      {photo}
      <p style="font-family:{FONT};font-size:16px;line-height:1.6;color:{text};margin:16px 0 0 0;">{esc(a["bio"])}</p>
      {self.chips(a, dark)}
      <div style="margin-top:12px;">{self.buttons(a, dark)}</div>
    </td></tr>
  </table>
</td></tr>"""

    def tracklist(self, artists):
        cell = "padding:11px 0;border-top:1px dashed #333333;"
        rows = "".join(
            f'<tr><td style="{cell}font-family:{HEAVY};font-size:13px;color:{MUTED_LIGHT};width:40px;">{i:02d}</td>'
            f'<td style="{cell}"><a href="{esc(self.url(a["profile_href"]))}" '
            f'style="font-family:{HEAVY};font-size:17px;color:{CARD};text-decoration:none;">{esc(a["name"])}</a></td>'
            f'<td align="right" style="{cell}font-family:{FONT};font-size:12px;color:#A3A3A3;">{esc(a["tag"])}</td></tr>'
            for i, a in enumerate(artists, 1))
        return f"""
<tr><td style="padding:0 0 26px 0;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{DEEP};border-radius:16px;">
    <tr><td style="padding:20px 22px 10px 22px;">
      <div style="font-family:{FONT};font-size:12px;font-weight:bold;letter-spacing:.2em;color:{MUTED_LIGHT};margin-bottom:10px;">IN THIS DROP</div>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">{rows}</table>
      <div style="padding:14px 0 10px 0;border-top:1px dashed #333333;">{self.button(PLAYLIST, "▶ Play the playlist on Spotify", DEEP, CARD)}</div>
    </td></tr>
  </table>
</td></tr>"""

    def intro(self):
        *paras, quote = INTRO
        body = "".join(f'<p style="font-family:{FONT};font-size:17px;line-height:1.6;color:{INK};margin:0 0 14px 0;">{esc(p)}</p>'
                       for p in paras)
        return f"""
<tr><td style="padding:28px 6px 26px 6px;">
  {body}
  <p style="font-family:{HEAVY};font-size:26px;line-height:1.25;color:{ACCENT};margin:20px 0 0 0;
            padding:2px 0 2px 16px;border-left:6px solid {INK};">{esc(quote)}</p>
</td></tr>"""

    def render(self, artists, label, subject, preheader):
        featured = [a for a in artists if a["is_featured"]]
        ordered = featured + [a for a in artists if not a["is_featured"]]
        cards = "".join(self.artist(a, i, a["is_featured"]) for i, a in enumerate(ordered, 1))
        bw, _ = self.banner_size
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{esc(subject)}</title>
<!-- Subject line: {esc(subject)} -->
</head>
<body style="margin:0;padding:0;background:{BG};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{esc(preheader)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{BG};">
<tr><td align="center" style="padding:18px 12px 30px 12px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="max-width:600px;">

    <tr><td align="right" style="padding:0 4px 10px 0;font-family:{FONT};font-size:12px;">
      <a href="{esc(self.url(f"/email/{self.week_of}/"))}" style="color:{MUTED};">View in browser</a>
    </td></tr>

    <tr><td><a href="{esc(self.url("/"))}"><img src="{esc(self.img("header.jpg"))}" width="{bw}" alt="Quigley Discovery. {esc(label)}"
      style="display:block;width:100%;max-width:{bw}px;height:auto;border:0;border-radius:18px;
      background:{DEEP};font-family:{HEAVY};font-size:28px;color:{CARD};"></a></td></tr>

    {self.intro()}
    {self.tracklist(ordered)}
    {cards}

    <tr><td style="padding:6px 0 0 0;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:{DEEP};border-radius:16px;">
        <tr><td align="center" style="padding:30px 22px 22px 22px;">
          <div style="font-family:{HEAVY};font-size:22px;line-height:1.3;color:{CARD};">Watch them grow.</div>
          <p style="font-family:{FONT};font-size:15px;line-height:1.6;color:#C8C8C8;margin:10px 0 18px 0;">
            Every artist's YouTube and Instagram numbers are tracked week over week on the site.</p>
          {self.button(PLAYLIST, "▶ Play the playlist on Spotify", DEEP, CARD)}<br>
          {self.button("/#trends", "See the charts →", CARD, "transparent", CARD)}
          {self.button("/archive.html", "Previous weeks", CARD, "transparent", CARD)}
          <p style="font-family:{FONT};font-size:14px;line-height:1.6;color:{MUTED_LIGHT};margin:14px 0 0 0;">
            Know someone who'd love these artists? Forward this email.</p>
        </td></tr>
      </table>
    </td></tr>

    <tr><td align="center" style="padding:22px 10px 0 10px;">
      <p style="font-family:{FONT};font-size:12px;line-height:1.6;color:{MUTED};margin:0;">
        Quigley Discovery · Los Angeles<br>
        You're getting this because you signed up at
        <a href="{esc(self.url("/"))}" style="color:{MUTED};">quigleydiscovery.com</a>.
      </p>
    </td></tr>

  </table>
</td></tr>
</table>
</body>
</html>
"""


def latest_ig_followers(week_of):
    """Newest saved Instagram follower count per artist slug."""
    conn = db.connect()
    rows = conn.execute(
        "SELECT a.slug, s.instagram_followers FROM snapshots s JOIN artists a ON a.id = s.artist_id "
        "WHERE a.week_of = ? AND s.instagram_followers IS NOT NULL ORDER BY s.captured_at ASC",
        (week_of,),
    ).fetchall()
    conn.close()
    return {r["slug"]: r["instagram_followers"] for r in rows}  # later rows win


def build(week_of=None):
    week_of = week_of or db.latest_week()
    artists = db.get_artists_for_week(week_of)
    ig = latest_ig_followers(week_of)
    label = (seed.CURRENT_WEEK_LABEL if week_of == seed.CURRENT_WEEK
             else "Week of " + date.fromisoformat(week_of).strftime("%b %-d, %Y"))
    issue = sorted(db.get_weeks()).index(week_of) + 1

    art_dir = os.path.join(ROOT, "frontend", "email", week_of)
    os.makedirs(art_dir, exist_ok=True)
    banner_size = email_art.banner(label, issue, os.path.join(art_dir, "header.jpg"))
    for a in artists:
        a["ig_followers"] = ig.get(a["slug"])
        a["tiktok_url"] = next((x.get("tiktok_url") for x in seed.ARTISTS if x["slug"] == a["slug"]), None)
        a["_name"] = f"name-{a['slug']}.png"
        color = CARD if a["is_featured"] else INK
        a["_name_size"] = email_art.name_image(
            a["name"], a["title_font"], color, os.path.join(art_dir, a["_name"]),
            ink_height=104 if a["is_featured"] else 80)
        # Email photo: assets/email-photos/<slug>.* if there is one, else the site card photo.
        override = next(iter(sorted(glob.glob(os.path.join(ROOT, "assets", "email-photos", a["slug"] + ".*")))), None)
        src = os.path.relpath(override, os.path.join(ROOT, "assets")) if override else (
            os.path.basename(a["card_photo"]) if a["card_photo"] else None)
        if src:
            a["_photo"] = f"photo-{a['slug']}.jpg"
            a["_photo_size"] = email_art.fit(email_art.photo(src, os.path.join(art_dir, a["_photo"])))

    top = next((a["name"] for a in artists if a["is_featured"]), artists[0]["name"] if artists else "")
    subject = f"This week's 5: {top} + 4 more independent artists"
    preheader = f"{label}: {', '.join(a['name'] for a in artists)}."

    web = Email(week_of, "", banner_size).render(artists, label, subject, preheader)
    kit = Email(week_of, SITE, banner_size).render(artists, label, subject, preheader)
    with open(os.path.join(art_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(web)
    os.makedirs(OUT_DIR, exist_ok=True)
    kit_path = os.path.join(OUT_DIR, f"week-{week_of}.html")
    with open(kit_path, "w", encoding="utf-8") as f:
        f.write(kit)
    return subject, kit_path, art_dir


def main():
    subject, kit_path, art_dir = build(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"Subject: {subject}\nFor Kit: {kit_path}\nImages + web copy: {art_dir} (push before sending)")


if __name__ == "__main__":
    main()
