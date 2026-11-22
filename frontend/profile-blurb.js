// Shows the artist's homepage blurb (from seed.py via /api/artist/{slug})
// on their full profile, in the element marked data-artist-blurb, and the
// real week-over-week YouTube views trend in data-artist-trend (hidden until
// there is a snapshot about a week older than the latest one).
// Usage: <script src="/profile-blurb.js" data-slug="arze" defer></script>
(function () {
  const slug = document.currentScript && document.currentScript.dataset.slug;
  const el = document.querySelector("[data-artist-blurb]");
  const trend = document.querySelector("[data-artist-trend]");
  if (!slug || (!el && !trend)) return;
  fetch(`/api/artist/${encodeURIComponent(slug)}`)
    .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
    .then((a) => {
      if (el && a.bio) { el.textContent = a.bio; el.hidden = false; }
      const st = a.stats || {};
      const pct = st.views_trend_pct;
      if (trend && st.has_youtube_data && pct !== null && pct !== undefined) {
        const arrow = pct > 0 ? "↑" : pct < 0 ? "↓" : "→";
        trend.textContent = `${arrow} ${pct > 0 ? "+" : ""}${pct}% views this week`;
        trend.style.display = "inline-flex";
      }
    })
    .catch(() => {});
})();
