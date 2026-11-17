# What data is available (and what isn't)

Plain-language reference for what stats and content this site can pull from
each music service. Written so a non-technical owner — or a Claude Code agent
picking up the project — knows exactly what's at hand before asking for a
feature. Status reflects what was actually tested on this project's API access,
not just what the services advertise.

Last verified: Nov 2026.

---

## YouTube — the main stats source ✅ LIVE & FREE

Connected and working now. Powers the "N views · N subscribers" line and the
growth badge on each artist card. Free API key (in `.env` as `YOUTUBE_API_KEY`).

**Available:**
- ✅ Subscriber count
- ✅ Total channel views
- ✅ Video count
- ✅ Per-video **views, likes, comments** *(not shown yet — easy to add)*
- ✅ Newest upload / latest release *(not shown yet — easy to add)*
- ✅ Channel info: creation date, country, description, thumbnail

**Not available:**
- ❌ Watch time, audience retention, viewer demographics — these are
  "channel owner only." We can't get them for artists we don't own.

**Notes:**
- Some artists' tracks live on auto-generated "Artist - Topic" channels, which
  show **0 subscribers but real view counts** (e.g. Doov). Pin the artist's
  official channel to fix subs.
- Quota is 10,000 free units/day; a full refresh costs ~5–10. Effectively
  unlimited for this use.

---

## Spotify — images & discography only ⚠️ NO STATS

Connected and working, but **only for content, not numbers.** This app's access
tier returns a stripped-down response. Powers the "Listen Now" links and the
"Discography" pop-up. Keys in `.env` (`SPOTIFY_CLIENT_ID` / `_SECRET`).

**Available:**
- ✅ Artist photo
- ✅ Discography — albums & singles with **cover art, release dates, type,
  track counts**
- ✅ Links to artist / album / track pages

**NOT available (confirmed blocked, even for Drake/Taylor Swift):**
- ❌ Follower count
- ❌ Popularity score
- ❌ Monthly listeners *(Spotify never offers this in any API)*
- ❌ Genres, top tracks (returns "forbidden")

**To unlock the numbers** you'd need Spotify's **Extended Quota Mode** (an
application aimed at commercial apps, not guaranteed) or a paid data provider
(see below). For now: **do not expect any Spotify stats** — use it for the
Listen button and discography only.

---

## Not connected yet — options on the table

These work but aren't wired in. Ask to add any of them.

| Source | Stats you'd get | Cost | Setup |
|--------|-----------------|------|-------|
| **Last.fm** | Listeners + playcount (real listening) | Free | ~2-min free key |
| **Deezer** | Fan count (followers) | Free | None (no key) — but slow-moving, small US audience |
| **Songstats** | **Spotify monthly listeners + followers**, playlist adds, cross-platform (Apple, TikTok…) | Paid | API key — the only route to real Spotify numbers |
| **Chartmetric** | Everything, deepest + demographics | $$$ | Enterprise |

**Not realistically available:** Instagram / TikTok follower counts (no free
official API — would need a paid provider or scraping).

---

## How "growth %" works (any source)

The green "+X% views" badge is **not** given by any service — the site builds it
itself. Each time you click **Refresh stats**, it saves a snapshot of the
current numbers. The growth % is the change between your last two snapshots.

- First refresh = a baseline (badge says "baseline set").
- Second refresh (later — next day/week) = the first real growth %.
- So the trend is only as fresh as your last refresh, and needs two to appear.

This works for **any** number above (YouTube, Last.fm, Deezer, etc.).

---

## Quick summary — what's on the cards today

- **Numbers:** YouTube views + subscribers (free, live)
- **Growth badge:** week-over-week YouTube view change (from snapshots)
- **Content:** Spotify "Listen Now" link + full "Discography" pop-up with art
- **Stat-less:** Tomb (no YouTube) — would need Last.fm or Deezer to cover him
