// Shows the artist's homepage blurb (from seed.py via /api/artist/{slug})
// on their full profile, in the element marked data-artist-blurb.
// Usage: <script src="/profile-blurb.js" data-slug="arze" defer></script>
(function () {
  const slug = document.currentScript && document.currentScript.dataset.slug;
  const el = document.querySelector("[data-artist-blurb]");
  if (!slug || !el) return;
  fetch(`/api/artist/${encodeURIComponent(slug)}`)
    .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
    .then((a) => { if (a.bio) { el.textContent = a.bio; el.hidden = false; } })
    .catch(() => {});
})();
