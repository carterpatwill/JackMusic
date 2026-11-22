// Fills a profile page's placeholder photo boxes (.ph-photo) with real images
// from Spotify: box 1 = the artist's Spotify photo, the rest = their newest
// release covers (each links to that release). Data comes from the server's
// /api/artist/{slug}/spotify endpoint, so no Spotify keys touch the browser.
// Usage: <script src="/profile-photos.js" data-slug="arze" defer></script>
// Add data-skip="1" to leave out the first photo(s) in that order.
(function () {
  const slug = document.currentScript && document.currentScript.dataset.slug;
  const skip = Number(document.currentScript.dataset.skip) || 0;
  if (!slug) return;

  function fill(box, src, alt, href) {
    box.innerHTML = "";
    const img = document.createElement("img");
    img.src = src;
    img.alt = alt;
    img.loading = "lazy";
    img.style.cssText = "width:100%;height:100%;object-fit:cover;display:block;";
    if (href) {
      const a = document.createElement("a");
      a.href = href;
      a.target = "_blank";
      a.rel = "noopener";
      a.title = alt;
      a.style.cssText = "display:block;width:100%;height:100%;";
      a.appendChild(img);
      box.appendChild(a);
    } else {
      box.appendChild(img);
    }
  }

  fetch(`/api/artist/${encodeURIComponent(slug)}/spotify`)
    .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
    .then((data) => {
      const photos = [];
      if (data.image) photos.push({ src: data.image, alt: `${data.name} on Spotify`, href: data.url });
      const seen = new Set();
      for (const al of data.albums || []) {
        if (!al.image || seen.has(al.image)) continue;
        seen.add(al.image);
        photos.push({ src: al.image, alt: `${al.name} — cover art`, href: al.url });
      }

      // Each placeholder sits inside a rounded square box; fill the box.
      const boxes = [...document.querySelectorAll(".ph-photo")].map((el) => el.parentElement);
      boxes.forEach((box, i) => {
        const p = photos[i + skip];
        if (p) fill(box, p.src, p.alt, p.href);
        else box.style.display = "none"; // not enough images: hide the empty box
      });
    })
    .catch(() => { /* leave the placeholders if Spotify is unavailable */ });
})();
