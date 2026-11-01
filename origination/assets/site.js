/* Minimal, dependency-free helpers: sortable tables and text filters. */
(function () {
  function cellValue(td) {
    var v = td.getAttribute('data-sort');
    if (v === null) v = td.textContent.trim();
    var n = parseFloat(v.replace(/[^0-9eE+\-.]/g, ''));
    if (!isNaN(n) && /^[-+]?[\d.,%$+\-eE]+$/.test(v.trim())) return n;
    return v.toLowerCase();
  }

  function sortTable(table, idx, asc) {
    var tb = table.tBodies[0];
    var rows = Array.prototype.slice.call(tb.rows);
    rows.sort(function (a, b) {
      var x = cellValue(a.cells[idx]), y = cellValue(b.cells[idx]);
      if (x === y) return 0;
      if (typeof x === 'number' && typeof y === 'number') return asc ? x - y : y - x;
      return asc ? String(x).localeCompare(String(y)) : String(y).localeCompare(String(x));
    });
    rows.forEach(function (r) { tb.appendChild(r); });
  }

  document.querySelectorAll('table.sortable').forEach(function (table) {
    var heads = table.tHead ? table.tHead.rows[0].cells : [];
    Array.prototype.forEach.call(heads, function (th, i) {
      if (th.classList.contains('nosort')) return;
      th.addEventListener('click', function () {
        var asc = th.getAttribute('data-asc') !== 'true';
        Array.prototype.forEach.call(heads, function (h) { h.removeAttribute('data-asc'); });
        th.setAttribute('data-asc', asc ? 'true' : 'false');
        sortTable(table, i, asc);
      });
    });
  });

  // text filter: <input data-filter="tableId">
  document.querySelectorAll('[data-filter]').forEach(function (input) {
    input.addEventListener('input', function () {
      var table = document.getElementById(input.getAttribute('data-filter'));
      if (!table) return;
      var q = input.value.toLowerCase();
      Array.prototype.forEach.call(table.tBodies[0].rows, function (row) {
        row.style.display = row.textContent.toLowerCase().indexOf(q) === -1 ? 'none' : '';
      });
    });
  });

  // tier filter: <select data-tierfilter="tableId">
  document.querySelectorAll('[data-tierfilter]').forEach(function (sel) {
    sel.addEventListener('change', function () {
      var table = document.getElementById(sel.getAttribute('data-tierfilter'));
      if (!table) return;
      var v = sel.value;
      Array.prototype.forEach.call(table.tBodies[0].rows, function (row) {
        var tier = row.getAttribute('data-tier') || '';
        row.style.display = (!v || tier === v) ? '' : 'none';
      });
    });
  });
})();
