// Quigley Discovery front-end: fetches artists + real stats from the API
// and renders the featured pick and the grid. No framework, no build step.

const WEEK_LABELS = { "2026-11-07": "Week of Nov 7, 2026" };

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

// Headline trend = week-over-week YouTube view growth (the liveliest signal
// for emerging artists). Spotify's API no longer shares stats on this tier.
function trendBadge(stats) {
  if (!stats.has_youtube_data) return "";  // e.g. Tomb (no YouTube)
  const pct = stats.views_trend_pct;
  // No badge until there's a snapshot ~a week older than the latest one,
  // so the number shown is always a real week-over-week change.
  if (pct === null || pct === undefined) return "";
  const dir = pct > 0 ? "up" : pct < 0 ? "down" : "flat";
  const arrow = `<svg class="${dir}" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"></line><polyline points="5 12 12 5 19 12"></polyline></svg>`;
  const sign = pct > 0 ? "+" : "";
  return `<span class="trend ${dir}" title="Week-over-week YouTube view change">${arrow}${sign}${pct}% views this week</span>`;
}

function fmt(n) {
  if (n === null || n === undefined) return "—";
  const v = Number(n);
  if (v >= 1_000_000) return (v / 1_000_000).toFixed(1).replace(/\.0$/, "") + "M";
  if (v >= 1_000) return (v / 1_000).toFixed(1).replace(/\.0$/, "") + "K";
  return v.toLocaleString();
}

function secondaryStats(stats) {
  const bits = [];
  if (stats.youtube_views != null) bits.push(`${fmt(stats.youtube_views)} YouTube views`);
  if (stats.youtube_subs != null && stats.youtube_subs > 0) bits.push(`${fmt(stats.youtube_subs)} subscribers`);
  if (!bits.length) return "";
  return `<div class="secondary-stats">${bits.map((b) => `<span>${esc(b)}</span>`).join("")}</div>`;
}

function socials(a) {
  const disco = a.spotify_url
    ? `<a href="#" class="disco" data-slug="${esc(a.slug)}" data-name="${esc(a.name)}">Discography →</a>`
    : "";
  const yt = a.has_youtube
    ? `<a href="${esc(a.youtube_url)}" target="_blank" rel="noopener">YouTube →</a>`
    : "";
  const ig = a.instagram_url
    ? `<a href="${esc(a.instagram_url)}" target="_blank" rel="noopener">Instagram →</a>`
    : "";
  return `<div class="socials">${disco}${yt}${ig}</div>`;
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

// ---- Reel-first cards (experiment) ----------------------------------------
// Each card leads with the artist's short-form video, the same Instagram
// reels/posts used on the full profiles. Artists without one get a Spotify
// player instead, so every card has something to press play on.
// TODO if this design sticks: move these into seed.py (a reel_url per artist).
const REELS = {
  arze: "https://www.instagram.com/reel/DdkZcuIPJ9C/embed",
  doov: "https://www.instagram.com/reel/DZvQyjfJ3kz/embed",
  themba: "https://www.instagram.com/p/DaTKS-GJCSZ/embed",
  tomb: "https://www.instagram.com/p/DeuiFUdOnul/embed",
};

// Some reels render taller inside Instagram's player; give them their full
// height so Instagram's own sound on/off button isn't cropped off.
const REEL_HEIGHTS = { doov: 640 };

function reel(a) {
  const ig = REELS[a.slug];
  if (ig) {
    const h = REEL_HEIGHTS[a.slug];
    return `<div class="reel-window"${h ? ` style="height:${h}px;"` : ""}><iframe src="${esc(ig)}" title="${esc(a.name)} on Instagram" loading="lazy" scrolling="no" allowtransparency="true" allow="autoplay; encrypted-media; picture-in-picture; web-share"></iframe></div>`;
  }
  if (a.spotify_url) {
    const src = a.spotify_url.replace("open.spotify.com/artist/", "open.spotify.com/embed/artist/") + "?theme=0";
    return `<div class="reel-window spotify"><iframe src="${esc(src)}" title="${esc(a.name)} on Spotify" loading="lazy" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture"></iframe></div>`;
  }
  return "";
}

// Plain-text labels (not pills) so they don't read as buttons.
function genreLabel(a) {
  return `<span class="genre-label"><i style="background:${esc(a.tag_color)};"></i>${esc(a.tag)}</span>`;
}

function trendText(stats) {
  const pct = stats && stats.views_trend_pct;
  if (!stats || !stats.has_youtube_data || pct === null || pct === undefined) return "";
  const dir = pct > 0 ? "up" : pct < 0 ? "down" : "flat";
  const arrow = pct > 0 ? "↑" : pct < 0 ? "↓" : "→";
  return `<span class="trend-text ${dir}" title="Week-over-week YouTube view change">${arrow} ${pct > 0 ? "+" : ""}${pct}% views this week</span>`;
}

function buttons(a) {
  const spotify = a.spotify_url
    ? `<a class="listen" href="${esc(a.spotify_url)}" target="_blank" rel="noopener"><svg width="10" height="10" viewBox="0 0 24 24" fill="#FFFBF1"><path d="M8 5v14l11-7z"></path></svg>Listen Now</a>`
    : "";
  const invest = a.invest_href ? `<a class="invest" href="${esc(a.invest_href)}">Invest →</a>` : "";
  return `<div class="actions">${spotify}${invest}</div>`;
}

function textLinks(a, full) {
  const bits = [];
  if (a.profile_href) bits.push(`<a href="${esc(a.profile_href)}">Full profile →</a>`);
  if (a.spotify_url) bits.push(`<a href="#" class="disco" data-slug="${esc(a.slug)}" data-name="${esc(a.name)}">Discography →</a>`);
  if (full && a.has_youtube) bits.push(`<a href="${esc(a.youtube_url)}" target="_blank" rel="noopener">YouTube →</a>`);
  if (full && a.instagram_url) bits.push(`<a href="${esc(a.instagram_url)}" target="_blank" rel="noopener">Instagram →</a>`);
  return `<div class="text-links">${bits.join("")}</div>`;
}

// The artist's name is itself a link to their full profile (the
// "Full profile →" link stays too).
function nameLink(a) {
  return a.profile_href
    ? `<a class="name-link" href="${esc(a.profile_href)}" title="${esc(a.name)}'s full profile">${esc(a.name)}</a>`
    : esc(a.name);
}

function featuredCard(a) {
  const hint = REELS[a.slug] ? "Press play on the reel" : "Press play to hear them";
  return `
    <div class="feat">
      <div class="feat-reel">${reel(a)}</div>
      <div class="feat-info">
        <span class="feat-eyebrow">★ Featured Pick · This week's top pick</span>
        <h3 class="feat-name" style="font-family:${a.title_font};">${nameLink(a)}</h3>
        ${genreLabel(a)}
        ${trendText(a.stats)}
        ${a.bio ? `<p class="feat-bio">${esc(a.bio)}</p>` : ""}
        <p class="play-hint"><span>◀</span> ${hint}</p>
        ${buttons(a)}
        ${textLinks(a, true)}
      </div>
    </div>`;
}

function gridCard(a) {
  return `
    <div class="reel-card">
      ${reel(a)}
      <div class="reel-info">
        <h3 class="reel-name" style="font-family:${a.title_font};">${nameLink(a)}</h3>
        ${genreLabel(a)}
        ${trendText(a.stats)}
        ${a.bio ? `<p class="reel-bio">${esc(a.bio)}</p>` : ""}
        ${buttons(a)}
        ${textLinks(a, false)}
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
  note.textContent = "Pulling live YouTube stats…";
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

// ---- Discography modal (Spotify artist image + album list) ----------------
function ensureModal() {
  let root = document.getElementById("disco-modal");
  if (root) return root;
  root = document.createElement("div");
  root.id = "disco-modal";
  root.className = "modal-backdrop hidden";
  root.innerHTML = `
    <div class="modal" role="dialog" aria-modal="true">
      <button class="modal-close" aria-label="Close">×</button>
      <div class="modal-head"></div>
      <div class="modal-body"></div>
    </div>`;
  document.body.appendChild(root);
  root.addEventListener("click", (e) => {
    if (e.target === root || e.target.classList.contains("modal-close")) closeModal();
  });
  return root;
}

function closeModal() {
  const root = document.getElementById("disco-modal");
  if (root) root.classList.add("hidden");
}

function albumCard(al) {
  const art = al.image
    ? `<img src="${esc(al.image)}" alt="" loading="lazy">`
    : `<div class="album-art-fallback">♪</div>`;
  const year = (al.release_date || "").slice(0, 10);
  const type = al.type ? al.type[0].toUpperCase() + al.type.slice(1) : "";
  const tracks = al.total_tracks ? ` · ${al.total_tracks} track${al.total_tracks > 1 ? "s" : ""}` : "";
  const inner = `
    <div class="album-art">${art}</div>
    <div class="album-name">${esc(al.name)}</div>
    <div class="album-meta">${esc(year)}${type ? " · " + esc(type) : ""}${tracks}</div>`;
  return al.url
    ? `<a class="album-card" href="${esc(al.url)}" target="_blank" rel="noopener">${inner}</a>`
    : `<div class="album-card">${inner}</div>`;
}

async function openDiscography(slug, name) {
  const root = ensureModal();
  const head = root.querySelector(".modal-head");
  const body = root.querySelector(".modal-body");
  head.innerHTML = `<h3>${esc(name)}</h3>`;
  body.innerHTML = `<p class="loading">Loading discography from Spotify…</p>`;
  root.classList.remove("hidden");

  try {
    const res = await fetch(`/api/artist/${encodeURIComponent(slug)}/spotify`);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Couldn't load discography");

    const img = data.image
      ? `<img class="modal-artist-img" src="${esc(data.image)}" alt="">`
      : "";
    const link = data.url
      ? `<a class="modal-open-spotify" href="${esc(data.url)}" target="_blank" rel="noopener">Open on Spotify →</a>`
      : "";
    head.innerHTML = `
      ${img}
      <div>
        <h3>${esc(data.name || name)}</h3>
        <p class="modal-sub">${data.albums.length} release${data.albums.length === 1 ? "" : "s"} on Spotify</p>
        ${link}
      </div>`;

    body.innerHTML = data.albums.length
      ? `<div class="album-grid">${data.albums.map(albumCard).join("")}</div>`
      : `<p class="loading">No releases found on Spotify.</p>`;
  } catch (e) {
    body.innerHTML = `<p class="loading">${esc(String(e.message || e))}</p>`;
  }
}

// ---- One player at a time ---------------------------------------------------
// The reels and Spotify players are third-party iframes, so the page can't
// tell them to pause. What it can see is which iframe has focus: clicking
// inside a player gives that iframe focus (document.activeElement). When a
// different player gets focus, the one used before is reset by reloading it,
// which stops its sound, so two songs never play over each other.
// Focus moving straight from one iframe to another fires no event on this
// page, so we also check activeElement a few times a second.
let activePlayer = null;

function stopPlayer(frame) {
  if (!frame || !frame.isConnected) return;
  // Swap in a brand-new copy of the player. Re-pointing the old iframe's src
  // sometimes left it blank in Chrome; a fresh element always loads cleanly.
  const fresh = frame.cloneNode(false);
  fresh.removeAttribute("loading");
  frame.replaceWith(fresh);
}

function checkActivePlayer() {
  const el = document.activeElement;
  if (!el || el.tagName !== "IFRAME" || !el.closest(".reel-window")) return;
  if (el === activePlayer) return;
  if (activePlayer) stopPlayer(activePlayer);
  activePlayer = el;
}

window.addEventListener("blur", () => setTimeout(checkActivePlayer, 0));
setInterval(checkActivePlayer, 250);

document.addEventListener("DOMContentLoaded", () => {
  loadArtists();
  document.getElementById("refresh-btn").addEventListener("click", refreshStats);
  // Reel rail arrows: scroll by roughly one card.
  document.querySelectorAll(".rail-btn").forEach((b) => b.addEventListener("click", () => {
    const rail = document.getElementById("artist-grid");
    const card = rail.querySelector(".reel-card");
    const stepPx = card ? card.getBoundingClientRect().width + 20 : 360;
    rail.scrollBy({ left: Number(b.dataset.dir) * stepPx, behavior: "smooth" });
  }));
  document.getElementById("signup-btn").addEventListener("click", subscribe);
  document.getElementById("signup-email").addEventListener("keydown", (e) => {
    if (e.key === "Enter") subscribe();
  });

  // Delegated: any "Discography →" link opens the modal.
  document.addEventListener("click", (e) => {
    const link = e.target.closest(".disco");
    if (link) {
      e.preventDefault();
      openDiscography(link.dataset.slug, link.dataset.name);
    }
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeModal();
  });
});
