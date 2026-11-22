/* RightsAtlas first-party analytics v3 (2026-11-21). No cookies, no identity, no IP stored.
   Records: page, source (referrer or ?utm_source tag), human/bot/automation, phone/computer, browser time zone,
   returning-browser flag, seconds visible, real reader (15 s or scroll), site-search words, play clicks. */
(function () {
  try {
    var K = "sb_publishable_E2ECaIgR-2fLWAEeDfVnMA_5_balO9b";
    var U = "https://uumiwuvbxzmtxuwmutis.supabase.co/rest/v1/rpc/";
    var H = { "apikey": K, "Authorization": "Bearer " + K, "Content-Type": "application/json" };
    function rpc(fn, body) {
      return fetch(U + fn, { method: "POST", headers: H, body: JSON.stringify(body), keepalive: true });
    }
    var ua = navigator.userAgent || "";
    var kind = navigator.webdriver ? "automation"
      : (/bot|crawl|spider|slurp|headless|preview|lighthouse|facebookexternalhit|embedly|python|curl/i.test(ua) ? "bot" : "human");
    var q = new URLSearchParams(location.search);
    var utm = q.get("utm_source") || q.get("ref") || null;
    var w = Math.min(screen.width || 0, window.innerWidth || 9999);
    var device = w < 600 ? "phone" : (w < 1024 ? "tablet" : "computer");
    var tz = null; try { tz = Intl.DateTimeFormat().resolvedOptions().timeZone || null; } catch (e) {}
    var v = null, ret = null;
    try {
      v = sessionStorage.getItem("ra_v");
      if (!v) { v = Math.random().toString(36).slice(2, 12); sessionStorage.setItem("ra_v", v); }
      ret = localStorage.getItem("ra_seen") === "1";
      localStorage.setItem("ra_seen", "1");
    } catch (e) {}
    window.raEvent = function (k, label) {
      rpc("track_event", { p_site: "rightsatlas", p_kind: k, p_label: label || null, p_path: location.pathname }).catch(function () {});
    };
    rpc("track_view3", { p_site: "rightsatlas", p_path: location.pathname, p_ref: document.referrer || null,
      p_kind: kind, p_utm: utm, p_visit: v, p_device: device, p_tz: tz, p_returning: ret })
      .then(function (r) { return r.json(); })
      .then(function (id) {
        if (!id || !v) return;
        var shown = 0, since = document.visibilityState === "visible" ? Date.now() : 0, engaged = false, depth = 0;
        function secs() { return Math.round((shown + (since ? Date.now() - since : 0)) / 1000); }
        // how far down the page they read (max % scrolled), 11-22 owner: "how people read our blog posts"
        function measure() {
          var h = document.documentElement.scrollHeight - innerHeight;
          var pct = h > 0 ? Math.round(100 * scrollY / h) : 100;
          if (pct > depth) depth = Math.min(pct, 100);
        }
        addEventListener("scroll", measure, { passive: true }); measure();
        function send() { rpc("track_time", { p_id: id, p_visit: v, p_secs: secs(), p_engaged: engaged, p_depth: depth }).catch(function () {}); }
        document.addEventListener("visibilitychange", function () {
          if (document.visibilityState === "hidden") { if (since) { shown += Date.now() - since; since = 0; } send(); }
          else { since = Date.now(); }
        });
        addEventListener("pagehide", send);
        setTimeout(function () { if (document.visibilityState === "visible") { engaged = true; send(); } }, 15000);
        addEventListener("scroll", function () { if (!engaged && scrollY > 300) { engaged = true; send(); } }, { passive: true });
      }).catch(function () {});
    // what people search for on our site
    // a search from the home page arrives here as /search/?q=... (counted once); typing on the search page itself is
    // counted when the box is left or Enter is pressed ("change"), not on every key
    if (q.get("q") && /\/search\//.test(location.pathname)) window.raEvent("search", q.get("q"));
    document.addEventListener("change", function (ev) {
      var i = ev.target;
      if (i && i.matches && i.matches('input[type="search"]') && i.value && /\/search\//.test(location.pathname)) window.raEvent("search", i.value);
    }, true);
    // play clicks: our own audio players; the archive.org film player is an iframe (a click on it blurs the page)
    document.addEventListener("play", function (ev) { if (ev.target && ev.target.tagName === "AUDIO") window.raEvent("play_song"); }, true);
    addEventListener("blur", function () {
      setTimeout(function () { var a = document.activeElement; if (a && a.tagName === "IFRAME" && /archive\.org/.test(a.src)) window.raEvent("play_film"); }, 0);
    });
  } catch (e) {}
})();
