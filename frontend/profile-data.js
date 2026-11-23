// "Explore the Data" on each artist profile: interactive charts built from
// /api/artist/<slug>/history (live YouTube + Spotify data, plus the site's
// own stats snapshots). Usage:
//   <div id="explore-data" data-slug="arze"></div>
//   <script src="/profile-data.js" defer></script>
(function () {
  var root = document.getElementById("explore-data");
  if (!root) return;
  var slug = root.getAttribute("data-slug");

  var C = {
    ink: "#141414", green: "#2F5D3A", bright: "#2EB91F", sage: "#8FAE7C",
    gold: "#E0B323", muted: "#8A8A8A", line: "rgba(20,20,20,0.12)",
  };

  var css = document.createElement("style");
  css.textContent = [
    ".xd{background:#FFFFFF;border:1px solid rgba(20,20,20,.14);border-radius:16px;padding:24px;margin-bottom:12px}",
    ".xd-stats{display:grid;grid-template-columns:repeat(var(--n,4),minmax(0,1fr));gap:12px;margin-bottom:20px}",
    ".xd-stat{background:#EFEFEF;border-radius:12px;padding:12px 14px}",
    ".xd-stat b{display:block;white-space:nowrap;font-family:'Archivo Black',sans-serif;font-size:20px;color:#2F5D3A;line-height:1.2}",
    ".xd-stat span{font-size:12px;font-weight:600;color:#8A8A8A}",
    ".xd-platforms{display:flex;gap:4px;padding:4px;background:#EFEFEF;border:1px solid rgba(20,20,20,.14);border-radius:999px;margin-bottom:18px;width:fit-content;max-width:100%;overflow-x:auto}",
    ".xd-platform{display:inline-flex;align-items:center;gap:8px;font:800 15px 'Archivo',sans-serif;color:#6B6B6B;background:transparent;border:0;border-radius:999px;padding:10px 18px;cursor:pointer;white-space:nowrap}",
    ".xd-platform i{width:9px;height:9px;border-radius:50%;display:inline-block}",
    ".xd-platform[aria-selected=true]{background:#2F5D3A;color:#FFFFFF;box-shadow:0 1px 3px rgba(0,0,0,.15)}",
    ".xd-select{display:inline-flex;align-items:center;gap:10px;font:700 13px 'Archivo',sans-serif;color:#6B6B6B}",
    ".xd-select select{font:700 14px 'Archivo',sans-serif;color:#2F5D3A;background:#EFEFEF;border:1px solid rgba(20,20,20,.2);border-radius:999px;padding:8px 32px 8px 14px;cursor:pointer;appearance:none;-webkit-appearance:none;background-image:url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='6'%3E%3Cpath d='M0 0l5 6 5-6z' fill='%232F5D3A'/%3E%3C/svg%3E\");background-repeat:no-repeat;background-position:right 13px center}",
    ".xd-tabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:6px}",
    ".xd-tab{font:700 13px 'Archivo',sans-serif;color:#2F5D3A;background:transparent;border:1px solid rgba(20,20,20,.2);border-radius:999px;padding:6px 12px;cursor:pointer}",
    ".xd-tab[aria-selected=true]{background:#2F5D3A;color:#FFFFFF;border-color:#2F5D3A}",
    ".xd-desc{font-size:14px;line-height:1.5;color:#6B6B6B;margin:10px 0 14px}",
    ".xd-chart{position:relative;height:340px}",
    ".xd-empty{display:flex;align-items:center;justify-content:center;text-align:center;height:100%;color:#8A8A8A;font-size:15px;line-height:1.6;padding:0 20px}",
    ".xd-note{font-size:13px;color:#8A8A8A;margin:0 0 32px}",
    ".xd-stats.many b{font-size:17px}.xd-stats.many{gap:10px}.xd-stats.many .xd-stat{padding:12px}",
    "@media (max-width:560px){.xd{padding:16px}.xd-platform{padding:9px 13px;font-size:14px}.xd-stats{gap:8px}.xd-stat{padding:10px}.xd-stat b{font-size:15px}.xd-stat span{font-size:11px}.xd-chart{height:280px}}",
  ].join("");
  document.head.appendChild(css);

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function fmt(n) { return Number(n || 0).toLocaleString("en-US"); }
  function short(n) {
    n = Number(n || 0);
    if (n >= 1e6) return (n / 1e6).toFixed(n >= 1e7 ? 0 : 1).replace(/\.0$/, "") + "M";
    if (n >= 1e3) return (n / 1e3).toFixed(n >= 1e4 ? 0 : 1).replace(/\.0$/, "") + "K";
    return String(n);
  }
  // Spotify dates can be "2024", "2024-05" or "2024-05-17".
  function toDate(s) {
    var p = String(s).slice(0, 10).split("-");
    return new Date(Date.UTC(+p[0], (+p[1] || 1) - 1, +p[2] || 1));
  }
  function day(d) {
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" });
  }
  function month(d) {
    return d.toLocaleDateString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
  }

  root.className = "xd";
  root.innerHTML = '<div class="xd-empty" style="height:120px">Loading live data…</div>';

  var chartLib = new Promise(function (resolve, reject) {
    if (window.Chart) return resolve(window.Chart);
    var s = document.createElement("script");
    s.src = "https://cdn.jsdelivr.net/npm/chart.js@4.4.6/dist/chart.umd.min.js";
    s.onload = function () { resolve(window.Chart); };
    s.onerror = reject;
    document.head.appendChild(s);
  });

  Promise.all([
    fetch("/api/artist/" + encodeURIComponent(slug) + "/history").then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }),
    chartLib,
  ]).then(function (res) { render(res[0], res[1]); })
    .catch(function () {
      root.innerHTML = '<div class="xd-empty" style="height:120px">Couldn\'t load the data right now. Try refreshing the page.</div>';
    });

  function render(d, Chart) {
    var videos = (d.youtube && d.youtube.videos) || [];
    var releases = d.releases || [];
    var hasYT = videos.length > 0;
    var ig = d.instagram || {};
    var posts = ig.posts || [];
    var hasIG = !!ig.available && posts.length > 0;

    var totalViews = videos.reduce(function (sum, v) { return sum + v.views; }, 0);
    var snaps = d.snapshots || [];
    var latestSubs = null;
    snaps.forEach(function (x) { if (x.youtube_subs) latestSubs = x.youtube_subs; });
    var reelViews = posts.reduce(function (sum, p) { return sum + (p.views || 0); }, 0);
    var hasYTChannel = hasYT || !!(d.youtube && d.youtube.available);

    // One section per platform, each with its own numbers, charts and source note.
    var platforms = [];
    if (hasYTChannel) platforms.push({
      id: "youtube", label: "YouTube", dot: "#E5484D",
      stats: [[fmt(totalViews), "Total views"], [fmt(videos.length), videos.length === 1 ? "Video" : "Videos"]]
        .concat(latestSubs ? [[fmt(latestSubs), "Subscribers"]] : []),
      tabs: (hasYT ? [{ id: "release", label: "Views by video" }] : [])
        .concat([{ id: "ytgrowth", label: "Channel growth" }]),
      note: "Live from YouTube. YouTube shares each video's view count as of today, so \u201cViews by video\u201d shows where the views landed. \u201cChannel growth\u201d comes from Quigley Discovery's own weekly snapshots.",
    });
    if (ig.available) platforms.push({
      id: "instagram", label: "Instagram", dot: "#D6249F",
      stats: [[fmt(ig.followers), "Followers"]]
        .concat(posts.length ? [[fmt(posts.length), "Recent posts"], [fmt(reelViews), "Reel views"]] : []),
      select: true,
      tabs: (hasIG ? [
        { id: "igtop", label: "Top 5 posts" },
        { id: "igmonthly", label: "Views by month" },
        { id: "igengage", label: "Likes & comments by month" },
        { id: "instagram", label: "Every post (detailed)" },
      ] : []).concat([{ id: "iggrowth", label: "Follower growth" }]),
      note: "Live from Instagram. Views, likes and comments are as of today for the artist's recent posts. \u201cFollower growth\u201d comes from Quigley Discovery's own weekly snapshots.",
    });
    if (releases.length) platforms.push({
      id: "spotify", label: "Spotify", dot: "#1DB954",
      stats: [[fmt(releases.length), releases.length === 1 ? "Release" : "Releases"],
              [month(toDate(releases[0].date)), "First release"],
              [month(toDate(releases[releases.length - 1].date)), "Latest release"]],
      tabs: [{ id: "releases", label: "Releases over time" }],
      note: "Live from Spotify. Spotify doesn't share stream counts publicly, so this shows every single and album by release date.",
    });
    if (!platforms.length) {
      root.innerHTML = '<div class="xd-empty" style="height:120px">No data found for this artist yet.</div>';
      return;
    }

    root.innerHTML =
      '<div class="xd-platforms" role="tablist" aria-label="Choose a platform">' + platforms.map(function (pf, i) {
        return '<button type="button" class="xd-platform" role="tab" data-platform="' + pf.id + '" aria-selected="false"' +
          '><i style="background:' + pf.dot + '"></i>' + esc(pf.label) + "</button>";
      }).join("") + "</div>" +
      '<div class="xd-stats"></div><div class="xd-tabs" role="tablist"></div>' +
      '<p class="xd-desc"></p><div class="xd-chart"><canvas></canvas></div>';

    var note = document.createElement("p");
    note.className = "xd-note";
    root.parentNode.insertBefore(note, root.nextSibling);

    var desc = root.querySelector(".xd-desc");
    var box = root.querySelector(".xd-chart");
    var chart = null;

    Chart.defaults.font.family = "'Archivo', system-ui, sans-serif";
    Chart.defaults.color = C.muted;

    function axis(extra) {
      return Object.assign({
        grid: { color: C.line }, border: { display: false },
        ticks: { callback: function (v) { return short(v); } },
      }, extra || {});
    }
    var tooltip = {
      backgroundColor: "#141414", titleColor: "#FFFFFF", bodyColor: "#E9E3CC",
      padding: 12, cornerRadius: 10, displayColors: false,
    };

    function draw(config) {
      if (chart) chart.destroy();
      box.innerHTML = "<canvas></canvas>";
      chart = new Chart(box.querySelector("canvas"), config);
    }
    function empty(msg) {
      if (chart) { chart.destroy(); chart = null; }
      box.innerHTML = '<div class="xd-empty">' + msg + "</div>";
    }

    // 1. Every YouTube upload: bar = its views, line = running total.
    function byRelease() {
      desc.textContent = "Every video in order. Bars are each video's views; the line is the running total, so you can see which releases moved the needle. Click a bar to watch it.";
      var running = 0;
      var spanDays = (new Date(videos[videos.length - 1].published) - new Date(videos[0].published)) / 864e5;
      var longSpan = spanDays > 400;
      // Label where the month (or, over long spans, the year) changes, with
      // enough bars between labels that they never overlap.
      var narrow = box.clientWidth < 480;
      var gap = Math.max(1, Math.ceil(videos.length / (narrow ? 3 : 7))), lastShown = -Infinity, lastKey = null;
      var tickLabels = videos.map(function (v, i) {
        var d = new Date(v.published);
        var key = longSpan ? String(d.getUTCFullYear()) : month(d).replace(" 20", " \u2019");
        if (key === lastKey || i - lastShown < gap) return "";
        lastKey = key;
        lastShown = i;
        return key;
      });
      var cumulative = videos.map(function (v) { return (running += v.views); });
      draw({
        type: "bar",
        data: {
          labels: videos.map(function (v) { return month(new Date(v.published)); }),
          datasets: [
            { type: "line", label: "Running total", data: cumulative, yAxisID: "total",
              borderColor: C.green, backgroundColor: C.green, borderWidth: 2.5,
              pointRadius: videos.length > 40 ? 0 : narrow ? 1.5 : 2.5, tension: 0.25, order: 0 },
            { label: "Views", data: videos.map(function (v) { return v.views; }), yAxisID: "views",
              backgroundColor: C.sage, hoverBackgroundColor: C.bright, borderRadius: 4, maxBarThickness: 48, order: 1 },
          ],
        },
        options: {
          maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
          onClick: function (e, els, ch) {
            if (els.length) window.open("https://youtu.be/" + videos[els[0].index].id, "_blank", "noopener");
          },
          onHover: function (e, els) { e.native.target.style.cursor = els.length ? "pointer" : "default"; },
          plugins: {
            legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8 } },
            tooltip: Object.assign({}, tooltip, { callbacks: {
              title: function (items) { return videos[items[0].dataIndex].title; },
              beforeBody: function (items) { return day(new Date(videos[items[0].dataIndex].published)); },
              label: function (it) { return it.dataset.label + ": " + fmt(it.raw); },
            } }),
          },
          scales: {
            x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: false, callback: function (v, i) { return tickLabels[i]; } } },
            views: axis({ position: "left", beginAtZero: true, title: { display: true, text: "Views per video" } }),
            total: axis({ position: "right", beginAtZero: true, grid: { display: false }, title: { display: true, text: "Running total" } }),
          },
        },
      });
    }

    // 2. No YouTube channel: Spotify releases as a running count over time.
    function releaseTimeline() {
      if (!releases.length) return empty("No release history found yet.");
      desc.textContent = "Every song and album on Spotify, as a running count. Each step up is a new release; hover for the title.";
      var pts = releases.map(function (r, i) { return { x: toDate(r.date).getTime(), y: i + 1, r: r }; });
      var pad = 20 * 864e5;
      draw({
        type: "line",
        data: { datasets: [{ label: "Spotify releases", data: pts, stepped: "before", borderColor: C.green,
          backgroundColor: "rgba(47,93,58,0.12)", fill: true, borderWidth: 2.5, pointRadius: 4,
          pointBackgroundColor: C.green }] },
        options: {
          maintainAspectRatio: false, parsing: false,
          plugins: {
            legend: { display: false },
            tooltip: Object.assign({}, tooltip, { callbacks: {
              title: function (items) { return items[0].raw.r.name; },
              label: function (it) {
                return [day(new Date(it.raw.x)) + " \u00b7 " + (it.raw.r.type || "release"), "Release #" + it.raw.y];
              },
            } }),
          },
          scales: {
            x: { type: "linear", grid: { display: false }, min: pts[0].x - pad, max: Date.now() + pad,
              ticks: { maxTicksLimit: 6, callback: function (v) { return month(new Date(v)).replace(" 20", " \u2019"); } } },
            y: axis({ beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: "Releases" } }),
          },
        },
      });
    }

    // Instagram, simplified: posts grouped by the month they went up.
    // We fetch the most recent ~100 posts, so when that cap is hit the oldest
    // month may be incomplete; it's dropped rather than shown as a fake dip.
    function igByMonth() {
      var groups = {}, order = [];
      posts.forEach(function (p) {
        var d0 = new Date(p.timestamp);
        var key = d0.getUTCFullYear() + "-" + String(d0.getUTCMonth() + 1).padStart(2, "0");
        if (!groups[key]) { groups[key] = []; order.push(key); }
        groups[key].push(p);
      });
      order.sort();
      if (posts.length >= 100 && order.length > 1) order.shift();
      // Include months with no posts (as zero) so the timeline isn't squished.
      if (order.length) {
        var full = [], y = +order[0].slice(0, 4), mo = +order[0].slice(5, 7);
        var endY = +order[order.length - 1].slice(0, 4), endM = +order[order.length - 1].slice(5, 7);
        while (y < endY || (y === endY && mo <= endM)) {
          full.push(y + "-" + String(mo).padStart(2, "0"));
          mo++; if (mo > 12) { mo = 1; y++; }
        }
        order = full;
      }
      return order.map(function (k) {
        var list = groups[k] || [], v = 0, l = 0, c = 0, best = null;
        list.forEach(function (p) {
          v += p.views || 0; l += p.likes || 0; c += p.comments || 0;
          var score = p.views != null ? p.views : (p.likes || 0);
          if (!best || score > (best.views != null ? best.views : (best.likes || 0))) best = p;
        });
        var p0 = k.split("-");
        return { label: month(new Date(Date.UTC(+p0[0], +p0[1] - 1, 1))).replace(" 20", " \u2019"), posts: list.length,
          views: v, likes: l, comments: c, avgLikes: list.length ? Math.round(l / list.length) : null,
          avgComments: list.length ? Math.round(c / list.length) : null, best: best };
      });
    }
    function bestLine(m) {
      var b = m.best;
      return b ? "Best post: " + (b.caption || (b.type === "reel" ? "Reel" : "Post")).slice(0, 48) +
        (b.views != null ? " (" + short(b.views) + " views)" : " (" + short(b.likes) + " likes)") : "";
    }

    function igMonthly() {
      var months = igByMonth();
      var useViews = months.some(function (m) { return m.views > 0; });
      desc.textContent = useViews
        ? "Total views on the posts from each month, the quickest way to see when " + d.name + "'s Instagram took off. Hover a month for its best post."
        : "Total likes on the posts from each month. Hover a month for its best post.";
      draw({
        type: "bar",
        data: { labels: months.map(function (m) { return m.label; }), datasets: [{
          label: useViews ? "Views" : "Likes", data: months.map(function (m) { return useViews ? m.views : m.likes; }),
          backgroundColor: "#E7A3CF", hoverBackgroundColor: "#D6249F", borderRadius: 6, maxBarThickness: 56 }] },
        options: {
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: Object.assign({}, tooltip, { callbacks: {
              title: function (items) { return months[items[0].dataIndex].label; },
              label: function (it) {
                var m = months[it.dataIndex];
                return m.posts ? [it.dataset.label + ": " + fmt(it.raw), m.posts + (m.posts === 1 ? " post" : " posts"), bestLine(m)] : ["No posts this month"];
              },
            } }),
          },
          scales: { x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
            y: axis({ beginAtZero: true }) },
        },
      });
    }

    // Row under the pointer in a horizontal bar chart (its label or its bar), or null.
    function rowAt(ch, e) {
      var y = ch.scales.y;
      if (!y || e.x < y.left || e.x > ch.chartArea.right || e.y < y.top || e.y > y.bottom) return null;
      var i = Math.round(y.getValueForPixel(e.y));
      return i >= 0 && i < ch.data.labels.length ? i : null;
    }
    function igTop() {
      var hasViews = posts.some(function (p) { return p.views != null; });
      var key = hasViews ? "views" : "likes";
      var top = posts.slice().sort(function (a, b) { return (b[key] || 0) - (a[key] || 0); }).slice(0, 5);
      desc.textContent = "The five most-" + (hasViews ? "viewed" : "liked") + " recent posts. Click a bar or a post's name to open it on Instagram.";
      draw({
        type: "bar",
        data: { labels: top.map(function (p) {
          var t = p.caption || (p.type === "reel" ? "Reel" : "Post");
          return (t.length > 28 ? t.slice(0, 27) + "\u2026" : t) + " \u00b7 " + month(new Date(p.timestamp)).replace(" 20", " \u2019") + " \u2197";
        }), datasets: [{ label: hasViews ? "Views" : "Likes", data: top.map(function (p) { return p[key] || 0; }),
          backgroundColor: "#E7A3CF", hoverBackgroundColor: "#D6249F", borderRadius: 6, maxBarThickness: 40 }] },
        options: {
          indexAxis: "y", maintainAspectRatio: false,

          plugins: {
            legend: { display: false },
            tooltip: Object.assign({}, tooltip, { callbacks: {
              title: function (items) { return top[items[0].dataIndex].caption || "Post"; },
              label: function (it) {
                var p = top[it.dataIndex], out = [day(new Date(p.timestamp))];
                if (p.views != null) out.push("Views: " + fmt(p.views));
                if (p.likes != null) out.push("Likes: " + fmt(p.likes));
                if (p.comments != null) out.push("Comments: " + fmt(p.comments));
                return out;
              },
            } }),
          },
          scales: { x: axis({ beginAtZero: true }), y: { grid: { display: false }, ticks: { color: "#B0187F", font: { weight: "600" } } } },
        },
      });
      // Click a bar, or the post's name beside it, to open the post. (Chart.js
      // only reports clicks inside the plot, so listen on the canvas directly.)
      var ch = chart, canvas = ch.canvas;
      function postAt(ev) { return rowAt(ch, { x: ev.offsetX, y: ev.offsetY }); }
      canvas.addEventListener("click", function (ev) {
        var i = postAt(ev);
        if (i != null && top[i].url) window.open(top[i].url, "_blank", "noopener");
      });
      canvas.addEventListener("mousemove", function (ev) {
        canvas.style.cursor = postAt(ev) != null ? "pointer" : "default";
      });
    }

    function igEngage() {
      var months = igByMonth();
      desc.textContent = "The average likes and comments per post for each month: how engaged the audience is, not just how big it is.";
      draw({
        type: "line",
        data: { labels: months.map(function (m) { return m.label; }), datasets: [
          { label: "Avg likes per post", data: months.map(function (m) { return m.avgLikes; }), yAxisID: "likes",
            borderColor: "#B4237F", backgroundColor: "#B4237F", borderWidth: 2.5, pointRadius: 3.5, tension: 0.25 },
          { label: "Avg comments per post", data: months.map(function (m) { return m.avgComments; }), yAxisID: "comments",
            borderColor: C.gold, backgroundColor: C.gold, borderWidth: 2.5, pointRadius: 3.5, tension: 0.25 },
        ].map(function (ds) { ds.spanGaps = true; return ds; }) },
        options: {
          maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
          plugins: {
            legend: { position: "bottom", labels: { usePointStyle: true, boxWidth: 8 } },
            tooltip: Object.assign({}, tooltip, { callbacks: {
              label: function (it) { return it.raw == null ? null : it.dataset.label + ": " + fmt(it.raw); },
              afterBody: function (items) { var m = months[items[0].dataIndex]; return m.posts ? m.posts + (m.posts === 1 ? " post" : " posts") : "No posts this month"; },
            } }),
          },
          scales: { x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } },
            likes: axis({ position: "left", beginAtZero: true, title: { display: true, text: "Likes" } }),
            comments: axis({ position: "right", beginAtZero: true, grid: { display: false }, title: { display: true, text: "Comments" } }) },
        },
      });
    }

    // Instagram: every recent post. Bars = likes; dots = Reel views.
    function instagramPosts() {
      var hasViews = posts.some(function (p) { return p.views != null; });
      desc.textContent = "Every recent post in order. Bars are likes" +
        (hasViews ? "; dots are views on Reels (Instagram only shares views for Reels)" : "") +
        ". Click a bar to open the post.";
      var narrow = box.clientWidth < 480;
      var gap = Math.max(1, Math.ceil(posts.length / (narrow ? 3 : 7))), lastShown = -Infinity, lastKey = null;
      var labels = posts.map(function (p, i) {
        var key = month(new Date(p.timestamp)).replace(" 20", " \u2019");
        if (key === lastKey || i - lastShown < gap) return "";
        lastKey = key; lastShown = i; return key;
      });
      var datasets = [{ label: "Likes", data: posts.map(function (p) { return p.likes; }), yAxisID: "likes",
        backgroundColor: C.sage, hoverBackgroundColor: C.bright, borderRadius: 4, maxBarThickness: 48, order: 1 }];
      if (hasViews) datasets.unshift({ type: "line", label: "Reel views", yAxisID: "views", showLine: false,
        data: posts.map(function (p) { return p.views; }), borderColor: C.green, backgroundColor: C.green,
        pointRadius: narrow ? 3 : 4, pointHoverRadius: 6, order: 0 });
      var scales = {
        x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: false, callback: function (v, i) { return labels[i]; } } },
        likes: axis({ position: "left", beginAtZero: true, title: { display: true, text: "Likes" } }),
      };
      if (hasViews) scales.views = axis({ position: "right", beginAtZero: true, grid: { display: false }, title: { display: true, text: "Reel views" } });
      draw({
        type: "bar",
        data: { labels: posts.map(function (p, i) { return String(i); }), datasets: datasets },
        options: {
          maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
          onClick: function (e, els) { if (els.length && posts[els[0].index].url) window.open(posts[els[0].index].url, "_blank", "noopener"); },
          onHover: function (e, els) { e.native.target.style.cursor = els.length ? "pointer" : "default"; },
          plugins: {
            legend: { display: hasViews, position: "bottom", labels: { usePointStyle: true, boxWidth: 8 } },
            tooltip: Object.assign({}, tooltip, { callbacks: {
              title: function (items) { var p = posts[items[0].dataIndex]; return p.caption || (p.type === "reel" ? "Reel" : "Post"); },
              beforeBody: function (items) { var p = posts[items[0].dataIndex]; return day(new Date(p.timestamp)) + " \u00b7 " + (p.type === "reel" ? "Reel" : p.type || "post"); },
              label: function (it) { return it.raw == null ? null : it.dataset.label + ": " + fmt(it.raw); },
              afterBody: function (items) { var c = posts[items[0].dataIndex].comments; return c != null ? "Comments: " + fmt(c) : ""; },
            } }),
          },
          scales: scales,
        },
      });
    }

    // The site's own snapshots: real growth over time (one point per day).
    function growth(field, label, color, fill, emptyMsg) {
      var perDay = {};
      snaps.forEach(function (x) { if (x[field] != null) perDay[x.captured_at.slice(0, 10)] = x; });
      var pts = Object.keys(perDay).sort().map(function (k) {
        return { x: Date.parse(k + "T00:00:00Z"), y: perDay[k][field], subs: perDay[k].youtube_subs };
      });
      if (!pts.length) return empty(emptyMsg);
      var first = new Date(pts[0].x);
      desc.textContent = label + ", tracked by Quigley Discovery since " + day(first) + ". " + (pts.length < 2
        ? "One point so far; a new one is added with each refresh, so the line fills in week by week."
        : "This is real growth over time: one point per day the stats were refreshed.");
      var pad = 3 * 864e5;
      draw({
        type: "line",
        data: { datasets: [{ label: label, data: pts, borderColor: color, backgroundColor: fill, fill: true,
          borderWidth: 2.5, pointRadius: 4, pointBackgroundColor: color, tension: 0 }] },
        options: {
          maintainAspectRatio: false, parsing: false,
          plugins: {
            legend: { display: false },
            tooltip: Object.assign({}, tooltip, { callbacks: {
              title: function (items) { return day(new Date(items[0].raw.x)); },
              label: function (it) {
                var out = [label + ": " + fmt(it.raw.y)];
                if (field === "youtube_views" && it.raw.subs) out.push("Subscribers: " + fmt(it.raw.subs));
                if (it.dataIndex > 0) {
                  var diff = it.raw.y - pts[it.dataIndex - 1].y;
                  out.push((diff >= 0 ? "+" : "") + fmt(diff) + " since previous point");
                }
                return out;
              },
            } }),
          },
          scales: {
            x: { type: "linear", grid: { display: false }, min: pts[0].x - pad, max: pts[pts.length - 1].x + pad,
              ticks: { maxTicksLimit: 6, callback: function (v) {
                return new Date(v).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
              } } },
            y: axis({ grace: "10%", ticks: { maxTicksLimit: 6, callback: function (v) { return fmt(Math.round(v)); } } }),
          },
        },
      });
    }
    function ytGrowth() {
      growth("youtube_views", "Total YouTube channel views", C.green, "rgba(47,93,58,0.12)",
        "Tracking starts with the next stats refresh. A new point is added each time, and the line grows week by week.");
    }
    function igGrowth() {
      growth("instagram_followers", "Instagram followers", "#B4237F", "rgba(214,36,159,0.10)",
        "Follower tracking starts with the next stats refresh. A new point is added each time, and the line grows week by week.");
    }

    var views = { release: byRelease, releases: releaseTimeline, instagram: instagramPosts, ytgrowth: ytGrowth, iggrowth: igGrowth,
      igmonthly: igMonthly, igtop: igTop, igengage: igEngage };
    var statsEl = root.querySelector(".xd-stats");
    var tabsEl = root.querySelector(".xd-tabs");

    function showPlatform(pf) {
      statsEl.className = "xd-stats" + (pf.stats.length > 4 ? " many" : "");
      statsEl.style.setProperty("--n", pf.stats.length);
      statsEl.innerHTML = pf.stats.map(function (st) {
        return '<div class="xd-stat"><b>' + esc(st[0]) + "</b><span>" + esc(st[1]) + "</span></div>";
      }).join("");
      note.textContent = pf.note;
      if (pf.select) {
        tabsEl.innerHTML = '<label class="xd-select"><span>Show</span><select>' + pf.tabs.map(function (t) {
          return '<option value="' + t.id + '">' + esc(t.label) + "</option>";
        }).join("") + "</select></label>";
        tabsEl.style.display = pf.tabs.length > 1 ? "" : "none";
        var sel = tabsEl.querySelector("select");
        sel.addEventListener("change", function () { views[sel.value](); });
        views[pf.tabs[0].id]();
        return;
      }
      tabsEl.innerHTML = pf.tabs.map(function (t, i) {
        return '<button type="button" class="xd-tab" role="tab" data-tab="' + t.id + '" aria-selected="' + (i === 0) + '">' + esc(t.label) + "</button>";
      }).join("");
      tabsEl.style.display = pf.tabs.length > 1 ? "" : "none";
      var tabEls = tabsEl.querySelectorAll(".xd-tab");
      tabEls.forEach(function (btn) {
        btn.addEventListener("click", function () {
          tabEls.forEach(function (x) { x.setAttribute("aria-selected", String(x === btn)); });
          views[btn.getAttribute("data-tab")]();
        });
      });
      views[pf.tabs[0].id]();
    }

    var pfEls = root.querySelectorAll(".xd-platform");
    pfEls.forEach(function (btn, i) {
      btn.addEventListener("click", function () {
        pfEls.forEach(function (x) { x.setAttribute("aria-selected", String(x === btn)); });
        showPlatform(platforms[i]);
      });
    });
    // Open on whichever platform has the most to show for this artist.
    var weight = { youtube: videos.length, instagram: posts.length, spotify: 0 };
    var start = 0;
    platforms.forEach(function (pf, i) { if (weight[pf.id] > weight[platforms[start].id]) start = i; });
    pfEls.forEach(function (x, i) { x.setAttribute("aria-selected", String(i === start)); });
    showPlatform(platforms[start]);
  }
})();
