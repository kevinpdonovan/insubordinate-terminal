(function () {
  "use strict";
  function store(k, v) { try { if (v === undefined) return localStorage.getItem(k); if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch (e) { return null; } }

  /* ---------- theme ---------- */
  var themeSel = document.getElementById("theme-select");
  if (themeSel) {
    themeSel.value = store("ift-theme") || "";
    themeSel.addEventListener("change", function () {
      var v = themeSel.value;
      if (v) { document.documentElement.dataset.theme = v; store("ift-theme", v); }
      else { delete document.documentElement.dataset.theme; store("ift-theme", null); }
    });
  }

  /* ---------- library proxy ---------- */
  var proxySel = document.getElementById("proxy-select");
  var links = Array.prototype.slice.call(document.querySelectorAll("a.scholarly"));
  links.forEach(function (a) { a.dataset.orig = a.getAttribute("href"); });
  function applyProxy(prefix) {
    links.forEach(function (a) {
      a.setAttribute("href", prefix ? prefix + encodeURIComponent(a.dataset.orig) : a.dataset.orig);
    });
  }
  if (proxySel) {
    var proxies = [];
    try { proxies = JSON.parse(proxySel.dataset.proxies || "[]"); } catch (e) {}
    proxies.forEach(function (p) {
      var o = document.createElement("option"); o.value = p.prefix; o.textContent = p.label; proxySel.appendChild(o);
    });
    var custom = document.createElement("option"); custom.value = "__custom"; custom.textContent = "Other (enter prefix)…"; proxySel.appendChild(custom);
    var saved = store("ift-proxy") || "";
    if (saved && !proxies.some(function (p) { return p.prefix === saved; })) {
      var o = document.createElement("option"); o.value = saved; o.textContent = "Custom"; proxySel.insertBefore(o, custom);
    }
    proxySel.value = saved;
    applyProxy(saved);
    proxySel.addEventListener("change", function () {
      var v = proxySel.value;
      if (v === "__custom") {
        v = (window.prompt("Paste your library's proxy prefix (ending in ?url=):", "") || "").trim();
        if (!v) { proxySel.value = store("ift-proxy") || ""; return; }
        var o = document.createElement("option"); o.value = v; o.textContent = "Custom"; proxySel.insertBefore(o, custom); proxySel.value = v;
      }
      store("ift-proxy", v || null);
      applyProxy(v);
    });
  }

  /* ---------- filters ---------- */
  var items = Array.prototype.slice.call(document.querySelectorAll(".item"));
  if (!items.length) return;
  var state = { sec: "", place: "", theme: "", q: "" };
  var segs = Array.prototype.slice.call(document.querySelectorAll(".seg-btn"));
  var fPlace = document.getElementById("f-place");
  var fTheme = document.getElementById("f-theme");
  var fQ = document.getElementById("f-q");
  var fCount = document.getElementById("f-count");
  var cols = Array.prototype.slice.call(document.querySelectorAll(".col"));
  var groups = Array.prototype.slice.call(document.querySelectorAll(".colgroup"));

  function run() {
    var q = state.q.toLowerCase(), shown = 0;
    items.forEach(function (el) {
      var ok = (!state.sec || el.dataset.section === state.sec) &&
        (!state.place || (" " + el.dataset.places + " ").indexOf(" " + state.place + " ") > -1) &&
        (!state.theme || (" " + el.dataset.themes + " ").indexOf(" " + state.theme + " ") > -1) &&
        (!q || el.textContent.toLowerCase().indexOf(q) > -1);
      el.hidden = !ok; if (ok) shown++;
    });
    cols.forEach(function (c) {
      c.hidden = !!state.sec && c.dataset.col !== state.sec;
      var any = c.querySelector(".item:not([hidden])");
      var fe = c.querySelector(".filtered-empty");
      if (fe) fe.hidden = !!any || !c.querySelector(".item");
    });
    groups.forEach(function (g) { g.hidden = !g.querySelector(".col:not([hidden])"); });
    document.body.classList.toggle("one-section", !!state.sec);
    var filtered = state.sec || state.place || state.theme || q;
    fCount.textContent = filtered ? shown + " of " + items.length + " items" : "";
  }
  segs.forEach(function (b) {
    b.addEventListener("click", function () {
      segs.forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
      state.sec = b.dataset.sec; run();
    });
  });
  fPlace.addEventListener("change", function () { state.place = fPlace.value; run(); });
  fTheme.addEventListener("change", function () { state.theme = fTheme.value; run(); });
  fQ.addEventListener("input", function () { state.q = fQ.value.trim(); run(); });
})();
