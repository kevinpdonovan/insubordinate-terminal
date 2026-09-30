(function () {
  "use strict";
  var L = window.IFT_LABELS || { places: {}, themes: {}, sections: {} };
  var q = document.getElementById("s-q"), sec = document.getElementById("s-sec"),
      place = document.getElementById("s-place"), theme = document.getElementById("s-theme"),
      from = document.getElementById("s-from"), list = document.getElementById("s-results"),
      count = document.getElementById("s-count"), empty = document.getElementById("s-empty"),
      more = document.getElementById("s-more");
  var all = [], matches = [], shown = 0, PAGE = 60;

  function norm(s) { return (s || "").toString().toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, ""); }
  function el(tag, cls, text) { var e = document.createElement(tag); if (cls) e.className = cls; if (text) e.textContent = text; return e; }
  function niceDate(d) {
    if (!d) return "";
    var t = new Date(d + "T00:00:00");
    return isNaN(t) ? d : t.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
  }

  function render(it) {
    var li = el("li", "item");
    var a = el("a", "item-title" + (it.section === "research" || it.section === "archive" ? " scholarly" : ""), it.title);
    a.href = it.url; a.target = "_blank"; a.rel = "noopener";
    li.appendChild(a);
    var meta = el("div", "item-meta mono");
    [[L.sections[it.section] || it.section, "sec"], [it.source, "src"],
     [(it.authors || []).slice(0, 3).join(", ") + ((it.authors || []).length > 3 ? " et al." : ""), ""],
     [niceDate(it.date), ""], ["Issue " + it.week, ""]].forEach(function (p) {
      if (p[0]) meta.appendChild(el("span", p[1], p[0]));
    });
    li.appendChild(meta);
    if (it.note) li.appendChild(el("p", "item-note", it.note));
    var tags = el("div", "tags");
    (it.place_ids || []).forEach(function (p) { tags.appendChild(el("span", "tag tag-place", L.places[p] || p)); });
    (it.theme_ids || []).forEach(function (t) { tags.appendChild(el("span", "tag", L.themes[t] || t)); });
    if (tags.childNodes.length) li.appendChild(tags);
    return li;
  }

  function applyProxy(root) {
    var prefix = "";
    try { prefix = localStorage.getItem("ift-proxy") || ""; } catch (e) {}
    if (!prefix) return;
    root.querySelectorAll("a.scholarly").forEach(function (a) { a.href = prefix + encodeURIComponent(a.getAttribute("href")); });
  }

  function page() {
    var frag = document.createDocumentFragment();
    matches.slice(shown, shown + PAGE).forEach(function (it) { frag.appendChild(render(it)); });
    list.appendChild(frag);
    applyProxy(list);
    shown = Math.min(matches.length, shown + PAGE);
    more.hidden = shown >= matches.length;
  }

  function run() {
    var words = norm(q.value).split(/\s+/).filter(Boolean);
    matches = all.filter(function (it) {
      if (sec.value && it.section !== sec.value) return false;
      if (place.value && (it.place_ids || []).indexOf(place.value) < 0) return false;
      if (theme.value && (it.theme_ids || []).indexOf(theme.value) < 0) return false;
      if (from.value && it.week < from.value) return false;
      if (!words.length) return true;
      return words.every(function (w) { return it._text.indexOf(w) > -1; });
    });
    list.innerHTML = ""; shown = 0;
    count.textContent = matches.length + " of " + all.length + " items";
    empty.hidden = matches.length > 0;
    page();
  }

  fetch("items.json").then(function (r) { return r.json(); }).then(function (data) {
    all = data.map(function (it) {
      it._text = norm([it.title, it.source, (it.authors || []).join(" "), it.note].join(" "));
      return it;
    }).sort(function (a, b) { return (b.date || b.week || "").localeCompare(a.date || a.week || ""); });
    run();
  }).catch(function () { count.textContent = "Could not load the item index."; });

  var t;
  q.addEventListener("input", function () { clearTimeout(t); t = setTimeout(run, 150); });
  [sec, place, theme, from].forEach(function (s) { s.addEventListener("change", run); });
  more.addEventListener("click", page);
})();
