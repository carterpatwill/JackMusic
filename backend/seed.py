"""Seed data for the current week's drop.

Ported from the original design mockup. This is the real artist roster;
the weekly stats (followers, popularity, subs) are NOT stored here — those
are fetched live by refresh.py and written to the `snapshots` table.

To publish a new week: set CURRENT_WEEK / CURRENT_WEEK_LABEL, replace ARTISTS
with the new week's five (new slugs), then run `python -m backend.db --publish`
and click Refresh in the UI. Earlier weeks stay in the database and show up in
the archive (/archive.html). (`--reseed` wipes every week; avoid it once there
is history you want to keep.)
"""

CURRENT_WEEK = "2026-11-16"
CURRENT_WEEK_LABEL = "Week of Nov 16, 2026"

# Site-level brand images (not tied to one artist)
HERO_IMAGE = "4f12d7bf223e102db5eb1f722bebd02e.jpg"
BRAND_PHOTO = "d4e881bc38b26d497b3aafd9849b9d15.jpg"

# Font stacks used for each artist's name (fonts live in /assets)
_FONTS = {
    "armyrust": "'ArmyRust', 'Archivo Black', sans-serif",
    "papernotes": "'Papernotes', 'Archivo Black', sans-serif",
    "adventure": "'Adventure', 'Archivo Black', sans-serif",
    "vintage2": "'Vintage2', 'Archivo Black', sans-serif",
    "sorean": "'Sorean', 'Archivo Black', sans-serif",
}

ARTISTS = [
    {
        "slug": "arze",
        "name": "ARZE",
        "tag": "Indie R&B / Alt",
        "tag_color": "#2F7A1A",
        "tag_bg": "rgba(79,145,48,0.16)",
        "bio": "Seattle-based multi-talented creative ARZE directs his own visuals and has created an incredibly strong, consistent visual identity, to coincide with his unique sound. People were transcribing his lyrics before anyone had written a single article about him. He's this week's top pick, and worth your investment!",
        "spotify_id": "1mc1ff9UjEKIxGPY8CJdSA",
        "youtube_url": "https://youtu.be/oFea3kAnpk0?si=DdUPO1YM6VYQZkXA",
        "instagram_url": "https://www.instagram.com/_____arze_____",
        "card_photo": "e724744682731d449d9d5ee8e40bd68e.png",
        "title_font": _FONTS["armyrust"],
        "profile_href": "/artist-arze.html",
        "invest_href": "/invest.html?artist=arze",
        "is_featured": 1,
        "sort_order": 0,
    },
    {
        "slug": "ian-bolen",
        "name": "Ian Bolen",
        "tag": "R&B / Pop",
        "tag_color": "#5C7A4A",
        "tag_bg": "rgba(140,168,110,0.18)",
        "bio": "Indie Pop/R&B. Ian has only released two songs, with little to no marketing, but they've done really well on Spotify, he has great production and a unique voice. Ian is worth your investment!",
        "spotify_id": "5E2qcj2QQnEN61NePeYDDo",
        "youtube_url": "https://youtu.be/2hPu_C3C3QU?si=trLALnZj9ygLRa__",
        "instagram_url": "https://www.instagram.com/ianbolen/?hl=en",
        "card_photo": "15260380d989b44f2d03a898cf648694.png",
        "title_font": _FONTS["papernotes"],
        "profile_href": "/artist-ianbolen.html",
        "invest_href": "/invest.html?artist=ian-bolen",
        "is_featured": 0,
        "sort_order": 3,
    },
    {
        "slug": "themba",
        "name": "Themba!",
        "tag": "Electronic Swag Rap",
        "tag_color": "#1F4024",
        "tag_bg": "rgba(31,64,36,0.14)",
        "bio": "Electronic Swag Rap, early 2000s sound mixed with modern rap vocals. Themba! had a viral hit in late 2024 with Calling My Phone, with a really unique sound and look.",
        "spotify_id": "42rqSuMW9VQ8ccRKgpOZOD",
        "youtube_url": "https://youtu.be/y43o6mVcnL4?si=lgsZPemz0tMBEzfY",
        "instagram_url": "https://www.instagram.com/thembaaaaaaaaaa/",
        "card_photo": "fc6980ac883e3fb979bf52741ad7188d.png",
        "title_font": _FONTS["vintage2"],
        "profile_href": "/artist-themba.html",
        "invest_href": "/invest.html?artist=themba",
        "is_featured": 0,
        "sort_order": 1,
    },
    {
        "slug": "doov",
        "name": "Doov",
        "tag": "Electronic Rap-House",
        "tag_color": "#2F7A1A",
        "tag_bg": "rgba(79,145,48,0.16)",
        "bio": "\"What the fuck is Dance Rap.\" Doov has self titled the genre of music that he creates. His confidence stands out. He has \"Superstar\" potential. A song he just released in August 2026. I'm investing in Doov to be the next superstar.",
        "spotify_id": "5HRGHEtYLGW78bYOxCmhnm",
        "youtube_url": "https://www.youtube.com/channel/UCbQQA5AQYX9pkh76fo8-P5g",
        "instagram_url": "https://www.instagram.com/itsdoov/",
        "card_photo": "523aa4706442c81909864a951c7c07d8.png",
        "title_font": _FONTS["sorean"],
        "profile_href": "/artist-doov.html",
        "invest_href": "/invest.html?artist=doov",
        "is_featured": 0,
        "sort_order": 4,
    },
    {
        "slug": "tomb",
        "name": "Tomb",
        "tag": "Indie / Alt",
        "tag_color": "#5C7A4A",
        "tag_bg": "rgba(140,168,110,0.18)",
        "bio": "Genre-blending indie. Tomb's social presence is tiny, but a couple of his tracks have racked up huge streaming numbers off the back of real organic reach, not labels or ads. No official YouTube channel yet, truly under the radar.",
        "spotify_id": "4udkKl2jIWRX7CzPthWTvF",
        "youtube_url": "",
        "instagram_url": "https://www.instagram.com/tomb.___/",
        "card_photo": "177cda6fcc8b5d3403d41b47c1d70cae.png",
        "title_font": _FONTS["adventure"],
        "profile_href": "/artist-tomb.html",
        "invest_href": "/invest.html?artist=tomb",
        "is_featured": 0,
        "sort_order": 2,
    },
]
