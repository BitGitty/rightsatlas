(async function () {
  const box = document.getElementById("q");
  const out = document.getElementById("results");
  if (!box) return;
  const incl = document.getElementById("inclq");           // "also search backlog" toggle
  const base = document.querySelector(".brand").getAttribute("href");
  const idx = await (await fetch(base + "assets/index.json")).json();
  const fuse = new Fuse(idx, { keys: ["title"], threshold: 0.35 });

  function section(title, cls) {
    const h = document.createElement("div");
    h.className = "res-head " + cls;
    h.textContent = title;
    return h;
  }
  function verifiedLink(item) {
    const a = document.createElement("a");
    a.href = base + "film/" + item.id + "/";
    a.className = "res verified";
    a.textContent = item.title + " (" + item.year + ")";
    return a;
  }
  function queueLink(item) {
    const a = document.createElement("a");
    a.href = base + "queue/#" + item.id;           // no per-title stub page — anchor into /queue/
    a.className = "res queue";
    a.innerHTML = item.title + " (" + item.year + ") <span class='q-tag'>not researched</span>";
    return a;
  }

  function render() {
    const q = box.value.trim();
    out.innerHTML = "";
    if (q.length < 2) return;
    const hits = fuse.search(q).map((h) => h.item);
    const verified = hits.filter((h) => h.kind === "verified").slice(0, 8);
    const queued = (incl && incl.checked) ? hits.filter((h) => h.kind === "queue").slice(0, 8) : [];

    if (verified.length) {
      out.appendChild(section("Verified dossiers", "v"));
      verified.forEach((h) => out.appendChild(verifiedLink(h)));
    }
    if (queued.length) {
      out.appendChild(section("In research queue — no conclusion", "q"));
      queued.forEach((h) => out.appendChild(queueLink(h)));
    }
    if (!verified.length && !queued.length) {
      const a = document.createElement("a");
      a.href = base + "methodology/";
      a.textContent = (incl && incl.checked)
        ? "No match — read how we research films, or suggest this title."
        : "No verified dossier — tick “also search the backlog”, or suggest this title.";
      out.appendChild(a);
    }
  }

  box.addEventListener("input", render);
  if (incl) incl.addEventListener("change", render);
})();
