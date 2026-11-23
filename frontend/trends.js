// Homepage "How They're Trending": one line per artist showing growth over
// time in the stat picked with the toggles (YouTube views, YouTube
// subscribers, Instagram Reel views, Instagram followers). Data comes from
// the saved stats snapshots (/api/trends), so it makes no live API calls.
(function () {
  const root = document.getElementById("trends-chart");
  if (!root) return;
  const note = document.getElementById("trends-note");
  const toggles = document.querySelectorAll("#trends .trend-toggle button");

  const METRICS = {
    youtube_views: { label: "YouTube views", noun: "views" },
    youtube_subs: { label: "YouTube subscribers", noun: "subscribers" },
    instagram_views: { label: "Instagram Reel views", noun: "Reel views" },
    instagram_followers: { label: "Instagram followers", noun: "followers" },
  };
  const COLORS = ["#2F5D3A", "#D98E04", "#B0187F", "#2B6CB0", "#C2410C", "#6B7F2A", "#7C3AED"];
  const fmt = (n) => Number(n).toLocaleString("en-US");
  const day = (ms) => new Date(ms).toLocaleDateString("en-US", { month: "short", day: "numeric" });

  let artists = [];
  let metric = "youtube_views";
  let chart = null;

  const chartLib = new Promise((resolve, reject) => {
    if (window.Chart) return resolve(window.Chart);
    const s = document.createElement("script");
    s.src = "https://cdn.jsdelivr.net/npm/chart.js@4.4.6/dist/chart.umd.min.js";
    s.onload = () => resolve(window.Chart);
    s.onerror = reject;
    document.head.appendChild(s);
  });

  // Growth % from the artist's first saved value of this stat. Snapshots
  // where the stat wasn't saved are skipped.
  function series(a) {
    const pts = a.points.filter((p) => p[metric] != null);
    if (!pts.length || !pts[0][metric]) return [];
    const base = pts[0][metric];
    return pts.map((p) => ({ x: Date.parse(p.captured_at), y: ((p[metric] - base) / base) * 100, v: p[metric] }));
  }

  function draw(Chart) {
    const m = METRICS[metric];
    const lines = artists.map((a, i) => ({ a, i, data: series(a) })).filter((l) => l.data.length);
    const missing = artists.filter((a) => !series(a).length).map((a) => a.name);
    if (chart) { chart.destroy(); chart = null; }

    if (!lines.length) {
      root.querySelector("canvas").style.display = "none";
      root.querySelector(".trends-empty").hidden = false;
      note.textContent = `${m.label} fill in here as stats are saved, about twice a day.`;
      return;
    }
    root.querySelector("canvas").style.display = "";
    root.querySelector(".trends-empty").hidden = true;

    const since = Math.min(...lines.map((l) => l.data[0].x));
    note.textContent =
      `Growth in ${m.label} since ${day(since)}, from each artist's first saved count.` +
      (missing.length ? ` Not charted yet: ${missing.join(", ")}.` : "");

    chart = new Chart(root.querySelector("canvas"), {
      type: "line",
      data: {
        datasets: lines.map(({ a, i, data }) => ({
          label: a.name,
          data,
          borderColor: COLORS[i % COLORS.length],
          backgroundColor: COLORS[i % COLORS.length],
          borderWidth: a.is_featured ? 3.5 : 2.5,
          pointRadius: 3,
          pointHoverRadius: 6,
          cubicInterpolationMode: "monotone",
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "nearest", intersect: false },
        scales: {
          x: {
            type: "linear",
            // One tick per calendar day (local midnight), so dates don't repeat.
            afterBuildTicks: (axis) => {
              const ticks = [];
              const d = new Date(axis.min); d.setHours(0, 0, 0, 0);
              if (d.getTime() < axis.min) d.setDate(d.getDate() + 1);
              for (; d.getTime() <= axis.max; d.setDate(d.getDate() + 1)) ticks.push({ value: d.getTime() });
              const fit = Math.max(2, Math.floor(axis.width / 64)); // labels that fit side by side
              const step = Math.ceil(ticks.length / fit);
              axis.ticks = ticks.filter((_, i) => i % step === 0);
            },
            ticks: { callback: (v) => day(v), color: "#6B6B6B", maxRotation: 0 },
            grid: { display: false },
          },
          y: {
            ticks: { callback: (v) => (v > 0 ? "+" : "") + parseFloat(Number(v).toFixed(2)) + "%", color: "#6B6B6B" },
            grid: { color: "rgba(20,20,20,0.08)" },
          },
        },
        plugins: {
          legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8, padding: 18, color: "#141414", font: { weight: "600" } } },
          tooltip: {
            callbacks: {
              title: (items) => (items.length ? day(items[0].parsed.x) : ""),
              label: (c) => ` ${c.dataset.label}: ${c.raw.y >= 0 ? "+" : ""}${c.raw.y.toFixed(1)}% (${fmt(c.raw.v)} ${m.noun})`,
            },
          },
        },
      },
    });
  }

  toggles.forEach((b) => b.addEventListener("click", () => {
    metric = b.dataset.metric;
    toggles.forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
    chartLib.then(draw);
  }));

  Promise.all([fetch("/api/trends").then((r) => r.json()), chartLib])
    .then(([d, Chart]) => { artists = d.artists || []; draw(Chart); })
    .catch(() => {
      root.innerHTML = '<p class="trends-empty">Couldn\'t load the chart right now.</p>';
    });
})();
