(async function () {
  const box = document.getElementById("q");
  const out = document.getElementById("results");
  if (!box) return;
  const base = document.querySelector(".brand").getAttribute("href");
  const idx = await (await fetch(base + "assets/index.json")).json();
  const fuse = new Fuse(idx, { keys: ["title"], threshold: 0.35 });
  box.addEventListener("input", () => {
    const q = box.value.trim();
    out.innerHTML = "";
    if (q.length < 2) return;
    const hits = fuse.search(q).slice(0, 8);
    if (!hits.length) {
      out.innerHTML = '<a href="' + base + 'methodology/">No dossier yet — ' +
        "read how we research films, or request this title.</a>";
      return;
    }
    for (const h of hits) {
      const a = document.createElement("a");
      a.href = base + "film/" + h.item.id + "/";
      a.textContent = h.item.title + " (" + h.item.year + ")";
      out.appendChild(a);
    }
  });
})();
