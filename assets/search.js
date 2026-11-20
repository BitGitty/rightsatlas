(async function () {
  const box = document.getElementById("q");
  const out = document.getElementById("results");
  if (!box) return;
  const incl = document.getElementById("inclq");           // "also show unresearched films" toggle
  const base = document.querySelector(".brand").getAttribute("href");
  const idx = await (await fetch(base + "assets/index.json")).json();
  const fuse = new Fuse(idx, { keys: ["title", "alt"], threshold: 0.35 });   // alt = Burmese title of a song

  function section(title, cls) {
    const h = document.createElement("div");
    h.className = "res-head " + cls;
    h.textContent = title;
    return h;
  }
  function link(item, path, cls, tag) {
    const a = document.createElement("a");
    a.href = base + path;
    a.className = "res " + cls;
    a.textContent = item.title + " (" + item.year + ")";
    if (tag) {
      const s = document.createElement("span");
      s.className = "q-tag";
      s.textContent = tag;
      a.appendChild(document.createTextNode(" "));
      a.appendChild(s);
    }
    return a;
  }

  function render() {
    const q = box.value.trim();
    out.innerHTML = "";
    if (q.length < 2) return;
    const hits = fuse.search(q).map((h) => h.item);
    const films = hits.filter((h) => h.kind === "verified").slice(0, 8);
    const songs = hits.filter((h) => h.kind === "song").slice(0, 8);
    const queued = (incl && incl.checked) ? hits.filter((h) => h.kind === "queue").slice(0, 8) : [];

    if (films.length) {
      out.appendChild(section("Films we have checked", "v"));
      films.forEach((h) => out.appendChild(link(h, "film/" + h.id + "/", "verified")));
    }
    if (songs.length) {
      out.appendChild(section("Songs we have checked", "v"));
      songs.forEach((h) => out.appendChild(link(h, "song/" + h.id + "/", "verified")));
    }
    if (queued.length) {
      out.appendChild(section("Films waiting to be researched (no answer yet)", "q"));
      queued.forEach((h) => out.appendChild(link(h, "queue/#" + h.id, "queue", "not researched yet")));
    }
    if (!films.length && !songs.length && !queued.length) {
      const a = document.createElement("a");
      a.href = base + "suggest/";
      a.textContent = "No match yet. Ask us to check this title.";
      out.appendChild(a);
    }
  }

  box.addEventListener("input", render);
  if (incl) incl.addEventListener("change", render);
  const pre = new URLSearchParams(location.search).get("q");   // from the home-page search form
  if (pre) { box.value = pre; render(); }
})();
