// Quigley Discovery front-end: fetches artists + real stats from the API
// and renders the featured pick and the grid. No framework, no build step.

const WEEK_LABELS = { "2026-11-07": "Week of Nov 7, 2026" };

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function trendBadge(stats) {
  const pct = stats.followers_trend_pct;
  if (!stats.has_data) return `<span class="trend flat">— no data yet</span>`;
  if (pct === null || pct === undefined) {
    return `<span class="trend flat">baseline set</span>`;
  }
  const dir = pct > 0 ? "up" : pct < 0 ? "down" : "flat";
  const arrow = `<svg class="${dir}" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"></line><polyline points="5 12 12 5 19 12"></polyline></svg>`;
  const sign = pct > 0 ? "+" : "";
  return `<span class="trend ${dir}" title="Week-over-week Spotify follower change">${arrow}${sign}${pct}%</span>`;
}

function fmt(n) {
  if (n === null || n === undefined) return "—";
  return Number(n).toLocaleString();
}

function secondaryStats(stats) {
  const bits = [];
  if (stats.spotify_followers != null) bits.push(`${fmt(stats.spotify_followers)} Spotify followers`);
  if (stats.spotify_popularity != null) {
    const d = stats.popularity_delta;
    const delta = d === null || d === undefined ? "" : ` (${d >= 0 ? "+" : ""}${d})`;
    bits.push(`Popularity ${stats.spotify_popularity}${delta}`);
  }
  if (stats.youtube_subs != null) bits.push(`${fmt(stats.youtube_subs)} YT subs`);
  if (!bits.length) return "";
  return `<div class="secondary-stats">${bits.map((b) => `<span>${esc(b)}</span>`).join("")}</div>`;
}

function socials(a) {
  const yt = a.has_youtube
    ? `<a href="${esc(a.youtube_url)}" target="_blank" rel="noopener">YouTube →</a>`
    : "";
  const ig = a.instagram_url
    ? `<a href="${esc(a.instagram_url)}" target="_blank" rel="noopener">Instagram →</a>`
    : "";
  return `<div class="socials">${yt}${ig}</div>`;
}

function actions(a) {
  const spotify = a.spotify_url
    ? `<a class="listen" href="${esc(a.spotify_url)}" target="_blank" rel="noopener"><svg width="10" height="10" viewBox="0 0 24 24" fill="#FFFBF1"><path d="M8 5v14l11-7z"></path></svg>Listen Now</a>`
    : "";
  const invest = a.invest_href
    ? `<a class="invest" href="${esc(a.invest_href)}">Invest →</a>`
    : "";
  return `<div class="actions">${trendBadge(a.stats)}${spotify}${invest}</div>`;
}

function featuredCard(a) {
  const photo = a.has_card_photo
    ? `<div class="card-bg"><img src="${esc(a.card_photo)}" alt=""><div class="overlay"></div></div>`
    : "";
  return `
    <div class="featured-card card-dark">
      ${photo}
      <div class="inner" style="padding:40px;">
        <div style="display:flex; gap:10px; flex-wrap:wrap; align-items:center;">
          <span class="tag featured-tag">Featured Pick</span>
          <span class="tag" style="color:${esc(a.tag_color)}; background:${esc(a.tag_bg)};">${esc(a.tag)}</span>
        </div>
        <div class="card-top">
          <div>
            <h3 class="artist-name" style="font-family:${a.title_font};">${esc(a.name)}</h3>
            <a class="full-profile" href="${esc(a.profile_href)}">Full profile</a>
          </div>
          ${actions(a)}
        </div>
        <p class="bio">${esc(a.bio)}</p>
        ${secondaryStats(a.stats)}
        ${socials(a)}
      </div>
    </div>`;
}

function gridCard(a) {
  if (a.has_card_photo) {
    return `
      <div class="artist-card photo card-dark">
        <div class="card-bg"><img src="${esc(a.card_photo)}" alt=""><div class="overlay"></div></div>
        <div class="inner">
          <span class="tag" style="color:${esc(a.tag_color)}; background:${esc(a.tag_bg)};">${esc(a.tag)}</span>
          <div class="card-top">
            <div>
              <h3 class="artist-name" style="font-family:${a.title_font};">${esc(a.name)}</h3>
              <a class="full-profile" href="${esc(a.profile_href)}">Full profile</a>
            </div>
            ${actions(a)}
          </div>
          <p class="bio">${esc(a.bio)}</p>
          ${secondaryStats(a.stats)}
          ${socials(a)}
        </div>
      </div>`;
  }
  return `
    <div class="artist-card">
      <div class="inner">
        <span class="tag" style="color:${esc(a.tag_color)}; background:${esc(a.tag_bg)};">${esc(a.tag)}</span>
        <div class="card-top">
          <div>
            <h3 class="artist-name" style="font-family:${a.title_font};">${esc(a.name)}</h3>
            <a class="full-profile" href="${esc(a.profile_href)}">Full profile</a>
          </div>
          ${actions(a)}
        </div>
        <p class="bio">${esc(a.bio)}</p>
        ${secondaryStats(a.stats)}
        ${socials(a)}
      </div>
    </div>`;
}

async function loadArtists() {
  const featuredEl = document.getElementById("featured");
  const gridEl = document.getElementById("artist-grid");
  featuredEl.innerHTML = `<p class="loading">Loading artists…</p>`;
  try {
    const res = await fetch("/api/artists");
    const data = await res.json();
    document.getElementById("week-date").textContent =
      WEEK_LABELS[data.week_of] || `Week of ${data.week_of}`;

    const artists = data.artists || [];
    const featured = artists.find((a) => a.is_featured) || artists[0];
    const others = artists.filter((a) => a !== featured);

    featuredEl.innerHTML = featured ? featuredCard(featured) : "";
    gridEl.innerHTML = others.map(gridCard).join("");
  } catch (e) {
    featuredEl.innerHTML = `<p class="loading">Couldn't load artists. Is the server running?</p>`;
  }
}

async function refreshStats() {
  const btn = document.getElementById("refresh-btn");
  const note = document.getElementById("refresh-note");
  btn.disabled = true;
  const orig = btn.textContent;
  btn.textContent = "Fetching…";
  note.textContent = "Pulling live stats from Spotify + YouTube…";
  try {
    const res = await fetch("/api/refresh", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Refresh failed");
    const errs = (data.artists || []).flatMap((a) => a.errors || []);
    note.textContent = errs.length
      ? `Updated, but some lookups failed (${errs.length}). Check keys/links.`
      : `Updated ${new Date(data.captured_at).toLocaleString()}.`;
    await loadArtists();
  } catch (e) {
    note.textContent = String(e.message || e);
  } finally {
    btn.disabled = false;
    btn.textContent = orig;
  }
}

async function subscribe() {
  const input = document.getElementById("signup-email");
  const msg = document.getElementById("signup-msg");
  const email = (input.value || "").trim();
  if (!email) { msg.textContent = "Enter an email first."; return; }
  msg.textContent = "Signing up…";
  try {
    const res = await fetch("/api/subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Signup failed");
    msg.textContent = data.created ? "You're on the list!" : "You're already subscribed.";
    input.value = "";
  } catch (e) {
    msg.textContent = String(e.message || e);
  }
}

document.addEventListener("DOMContentLoaded", () => {
  loadArtists();
  document.getElementById("refresh-btn").addEventListener("click", refreshStats);
  document.getElementById("signup-btn").addEventListener("click", subscribe);
  document.getElementById("signup-email").addEventListener("keydown", (e) => {
    if (e.key === "Enter") subscribe();
  });
});
