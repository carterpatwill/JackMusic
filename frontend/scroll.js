// Scroll feel for the homepage: hero parallax zoom, a fading scroll cue,
// reveal-on-scroll for content blocks, and a count-up on the stats.
// Progressive enhancement — if this never runs, everything is still visible.
(function () {
  "use strict";
  const root = document.documentElement;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Gate the reveal styles behind JS + motion preference, so the content is
  // never left invisible when animations are off or the script fails.
  if (!reduce) root.classList.add("reveal-on");

  // --- Reveal on scroll -----------------------------------------------------
  if (!reduce && "IntersectionObserver" in window) {
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (!e.isIntersecting) continue;
          e.target.classList.add("is-in");
          io.unobserve(e.target);
          if (e.target.matches(".stats-box")) countUp(e.target);
        }
      },
      { rootMargin: "0px 0px -10% 0px", threshold: 0.12 }
    );
    const scan = () =>
      document
        .querySelectorAll("[data-reveal]:not(.is-in)")
        .forEach((el) => io.observe(el));
    scan();
    // The featured card + grid render from an API call, so re-scan once they land.
    window.addEventListener("load", scan);
    setTimeout(scan, 700);
    setTimeout(scan, 1800);
  }

  // Tick a number from 0 up to its target when it first appears.
  function countUp(scope) {
    scope.querySelectorAll("[data-count]").forEach((el) => {
      const target = parseInt(el.getAttribute("data-count"), 10);
      if (!Number.isFinite(target)) return;
      const suffix = el.getAttribute("data-suffix") || "";
      const start = performance.now();
      const dur = 900;
      (function frame(now) {
        const p = Math.min((now - start) / dur, 1);
        const val = Math.round(target * (1 - Math.pow(1 - p, 3))); // ease-out
        el.textContent = val + suffix;
        if (p < 1) requestAnimationFrame(frame);
      })(start);
    });
  }

  // --- Hero parallax + scroll cue ------------------------------------------
  const heroImg = document.querySelector(".hero-bg img");
  const cue = document.querySelector(".scroll-cue");
  let ticking = false;
  function onScroll() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      const vh = window.innerHeight || 1;
      const p = Math.min((window.scrollY || 0) / vh, 1); // 0..1 over first screen
      if (heroImg && !reduce) {
        heroImg.style.transform = "scale(" + (1 + p * 0.12).toFixed(4) + ")";
      }
      if (cue) cue.style.opacity = String(Math.max(0, 1 - p * 2.4));
      ticking = false;
    });
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();
})();
