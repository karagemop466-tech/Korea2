/* Korea2 NFL Line Origination dashboard — dependency-free renderer.
 * All tables are rendered from data/*.json so every row carries its
 * official source links. BASE resolves whether we are at root or /pages/. */
(function () {
  "use strict";
  var BASE = window.location.pathname.indexOf("/pages/") !== -1 ? ".." : ".";

  var NAV = [
    { href: "index.html", label: "Dashboard" },
    { href: "pages/executive-summary.html", label: "Executive Summary" },
    { href: "pages/strategies.html", label: "Strategies" },
    { href: "pages/signals.html", label: "Signals" },
    { href: "pages/bet-types.html", label: "Bet Types" },
    { href: "pages/validation.html", label: "Validation Gates" },
    { href: "pages/correlations.html", label: "Correlations" },
    { href: "pages/leaderboard.html", label: "Leaderboard" },
    { href: "pages/data-sources.html", label: "Data & Sources" },
    { href: "pages/repo-review.html", label: "Repo Review" },
    { href: "pages/flagged.html", label: "⚑ Flagged for Review" }
  ];

  var state = { sources: {}, sourcesList: [] };

  function fetchJSON(name) {
    return fetch(BASE + "/data/" + name).then(function (r) {
      if (!r.ok) throw new Error("failed to load " + name + ": " + r.status);
      return r.json();
    });
  }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function srcChips(ids) {
    if (!ids || !ids.length) return '<span class="badge warn">NO SOURCE</span>';
    return '<span class="chips">' + ids.map(function (id) {
      var s = state.sources[id];
      if (!s) return '<span class="chip" title="unknown source id">' + esc(id) + " ?</span>";
      return '<span class="chip"><a href="' + esc(s.url) + '" target="_blank" rel="noopener noreferrer" title="' +
        esc(s.label + " — " + s.org + " (verified " + esc(s.verified_on || "2026-11-01") + ")") + '">' + esc(id) + " ↗</a></span>";
    }).join("") + "</span>";
  }

  function verifiedBadge(row) {
    if (row.verified === true) return '<span class="badge ok">VERIFIED</span>';
    if (row.value_status && /unverified/i.test(row.value_status)) return '<span class="badge warn">UNVERIFIED — BLANK</span>';
    if (row.status && /verified/i.test(row.status)) return '<span class="badge ok">' + esc(row.status.toUpperCase()) + "</span>";
    if (row.status) return '<span class="badge warn">' + esc(row.status.toUpperCase()) + "</span>";
    return "";
  }

  function valCell(row, key) {
    var v = row[key];
    if (v === "" || v == null) return '<span class="empty-val">— (blank: unverified, flagged)</span>';
    return esc(v);
  }

  function renderTable(el, rows, cols, opts) {
    opts = opts || {};
    var tools = document.createElement("div");
    tools.className = "table-tools";
    tools.innerHTML = '<input type="search" placeholder="Filter rows…" aria-label="Filter table">' +
      '<span class="count"></span>';
    el.appendChild(tools);
    var scroll = document.createElement("div");
    scroll.className = "table-scroll";
    var table = document.createElement("table");
    table.className = "data";
    var thead = "<thead><tr>" + cols.map(function (c) { return "<th>" + esc(c.label) + "</th>"; }).join("") + "</tr></thead>";
    table.innerHTML = thead + '<tbody></tbody>';
    scroll.appendChild(table);
    el.appendChild(scroll);
    var tbody = table.querySelector("tbody");

    function draw(filter) {
      tbody.innerHTML = "";
      var n = 0;
      rows.forEach(function (row) {
        var text = JSON.stringify(row).toLowerCase();
        if (filter && text.indexOf(filter.toLowerCase()) === -1) return;
        n++;
        var tr = document.createElement("tr");
        cols.forEach(function (c) {
          var td = document.createElement("td");
          td.innerHTML = c.render ? c.render(row) : esc(row[c.key]);
          tr.appendChild(td);
        });
        tbody.appendChild(tr);
      });
      tools.querySelector(".count").textContent = n + " / " + rows.length + " rows";
    }
    tools.querySelector("input").addEventListener("input", function (e) { draw(e.target.value); });
    draw("");
  }

  var idCell = { key: "id", label: "ID", render: function (r) { return '<span class="id-cell">' + esc(r.id) + "</span>"; } };
  var srcCol = { key: "sources", label: "Official source link(s)", render: function (r) { return srcChips(r.sources || r.inputs); } };

  var RENDERERS = {
    "league_facts": function (el, doc) {
      renderTable(el, doc.rows, [
        idCell,
        { key: "fact", label: "Fact" },
        { key: "value", label: "Value (as-of stamped where dynamic)" },
        { key: "verified", label: "Status", render: verifiedBadge },
        srcCol
      ]);
    },
    "sources": function (el, doc) {
      renderTable(el, doc.sources, [
        idCell,
        { key: "label", label: "Source" },
        { key: "org", label: "Organization" },
        { key: "type", label: "Type" },
        { key: "url", label: "Official link", render: function (r) { return '<a href="' + esc(r.url) + '" target="_blank" rel="noopener noreferrer">' + esc(r.url.replace(/^https:\/\//, "")) + " ↗</a>"; } },
        { key: "note", label: "What it verifies (checked " + (doc.meta ? "2026-11-01" : "") + ")" }
      ]);
    },
    "bet_types": function (el, doc) {
      renderTable(el, doc.rows, [
        idCell,
        { key: "name", label: "Bet type" },
        { key: "definition", label: "Official definition" },
        { key: "typical_price", label: "Typical price" },
        srcCol
      ]);
    },
    "signals": function (el, doc) {
      renderTable(el, doc.rows, [
        idCell,
        { key: "name", label: "Signal" },
        { key: "category", label: "Category" },
        { key: "description", label: "What it measures / why useful" },
        { key: "output", label: "Model output" },
        { key: "status", label: "Status", render: verifiedBadge },
        srcCol
      ]);
    },
    "strategies": function (el, doc) {
      renderTable(el, doc.rows, [
        idCell,
        { key: "name", label: "Strategy" },
        { key: "type", label: "Bet type" },
        { key: "description", label: "How it originates its own line & constructs bets" },
        { key: "inputs", label: "Signal inputs", render: function (r) { return '<span class="chips">' + (r.inputs || []).map(function (i) { return '<span class="chip">' + esc(i) + "</span>"; }).join("") + "</span>"; } },
        { key: "gates", label: "Gates", render: function (r) { return '<span class="chips">' + (r.gates || []).map(function (g) { return '<span class="chip">' + esc(g) + "</span>"; }).join("") + "</span>"; } },
        { key: "correlation_handling", label: "Correlation handling" },
        { key: "staking", label: "Staking" },
        { key: "performance", label: "Performance (blank until gates pass)", render: function (r) { return valCell(r, "performance") + ' <span class="badge warn">UNVERIFIED — NOT YET COMPUTED</span>'; } },
        srcCol
      ]);
    },
    "validation_gates": function (el, doc) {
      renderTable(el, doc.rows, [
        idCell,
        { key: "name", label: "Gate" },
        { key: "rule", label: "Rule (how luck is removed)" },
        { key: "pass_criteria", label: "Pass criteria" },
        srcCol
      ]);
    },
    "correlations": function (el, doc) {
      renderTable(el, doc.rows, [
        idCell,
        { key: "concept", label: "Concept" },
        { key: "method", label: "Method (how the value is determined)" },
        { key: "value", label: "Value", render: function (r) { return valCell(r, "value") + (r.value_status ? ' <span class="badge warn">UNVERIFIED</span>' : ""); } },
        { key: "value_status", label: "Value status / why blank" },
        srcCol
      ]);
    },
    "leaderboard": function (el, doc) {
      renderTable(el, doc.rows, [
        idCell,
        { key: "name", label: "Element" },
        { key: "description", label: "Design" },
        { key: "metric", label: "Metric" },
        srcCol
      ]);
    },
    "flagged": function (el, doc) {
      renderTable(el, doc.rows, [
        idCell,
        { key: "item", label: "Item flagged for review" },
        { key: "value", label: "Value", render: function (r) { return valCell(r, "value"); } },
        { key: "reason", label: "Reason it is blank / unverified" },
        srcCol
      ]);
    },
    "repo_review": function (el, doc) {
      renderTable(el, doc.rows, [
        { key: "file", label: "File" },
        { key: "lines", label: "Lines" },
        { key: "content", label: "Content (line-by-line)" },
        { key: "status", label: "Status", render: function (r) { return '<span class="badge ok">' + esc(r.status.toUpperCase()) + "</span>"; } },
        { key: "irregularity", label: "Irregularities flagged" },
        srcCol
      ]);
    }
  };

  function navBar(activeLabel) {
    var here = window.location.pathname.split("/").pop() || "index.html";
    var links = NAV.map(function (n) {
      var isActive = (n.href === here) || (n.href === "index.html" && here === "");
      return '<a class="' + (isActive ? "active" : "") + '" href="' + (window.location.pathname.indexOf("/pages/") !== -1 ? "../" : "") + n.href + '">' + esc(n.label) + "</a>";
    }).join("");
    return '<div class="topbar"><a class="brand" href="' + (window.location.pathname.indexOf("/pages/") !== -1 ? "../index.html" : "index.html") + '">🏈 Korea2 · NFL Line Origination<small>skill-based strategy lab · verified 2026-11-01</small></a><nav class="nav">' + links + "</nav></div>";
  }

  function footer() {
    return '<div class="footer">' +
      "Analytics research only — not financial advice, not a guarantee of profit. Sports wagering is legal only in some jurisdictions and only for adults 21+. " +
      'If gambling stops being fun, call or text the National Problem Gambling Helpline (operated by the <a href="https://www.ncpgambling.org/help-treatment/about-the-national-problem-gambling-helpline/" target="_blank" rel="noopener noreferrer">National Council on Problem Gambling</a>, 24/7/365, all 50 states + territories). ' +
      "All data rows link to official sources verified 2026-11-01; unverifiable values are blank and listed on the Flagged for Review page. Source code: <a href=\"https://github.com/karagemop466-tech/Korea2\">github.com/karagemop466-tech/Korea2</a>." +
      "</div>";
  }

  function mount(chrome) {
    document.body.insertAdjacentHTML("afterbegin", navBar());
    document.body.insertAdjacentHTML("beforeend", footer());
    var main = document.querySelector("main.wrap");
    return Promise.all([
      fetchJSON("sources.json"),
      fetchJSON(chrome.data)
    ]).then(function (res) {
      state.sources = {};
      res[0].sources.forEach(function (s) { state.sources[s.id] = s; });
      state.sourcesList = res[0].sources;
      var doc = res[1];
      var head = document.querySelector(".page-head");
      if (head && doc.meta) {
        head.querySelector("p").textContent = doc.meta.note || doc.meta.title || "";
        var ml = head.querySelector(".meta-line");
        if (ml) ml.textContent = (doc.meta.title || "") + " · verified/as-of: " + (doc.meta.verified_on || doc.meta.as_of || "2026-11-01");
      }
      var el = document.getElementById("table");
      RENDERERS[chrome.renderer](el, doc);
      if (chrome.after) chrome.after(doc);
    });
  }

  window.App = {
    init: function (chrome) { return mount(chrome); },
    state: state,
    fetchJSON: fetchJSON,
    srcChips: srcChips,
    esc: esc,
    navBar: navBar,
    footer: footer,
    BASE: BASE,
    renderTable: renderTable,
    RENDERERS: RENDERERS,
    verifiedBadge: verifiedBadge,
    valCell: valCell,
    idCell: idCell,
    srcCol: srcCol
  };
})();
