(function(){
  // Row filter for every table with a filter box.
  document.querySelectorAll('input.filter[data-filter-for]').forEach(function(box){
    var table = document.getElementById(box.getAttribute('data-filter-for'));
    if(!table) return;
    box.addEventListener('input', function(){
      var q = box.value.trim().toLowerCase();
      table.querySelectorAll('tbody tr').forEach(function(tr){
        tr.style.display = (!q || tr.textContent.toLowerCase().indexOf(q) !== -1) ? '' : 'none';
      });
    });
  });
  // Decision recorder for the suggestions page (browser storage only; nothing is sent anywhere).
  var KEY = 'nfl-command-decisions-v1';
  var sel = document.querySelectorAll('select[data-decision]');
  if(sel.length){
    var saved = {};
    try { saved = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch(e) { saved = {}; }
    sel.forEach(function(s){
      var id = s.getAttribute('data-decision');
      if(saved[id]) s.value = saved[id];
      s.addEventListener('change', function(){
        saved[id] = s.value;
        localStorage.setItem(KEY, JSON.stringify(saved));
        flash('Saved in this browser');
      });
    });
    var status = document.getElementById('decision-status');
    function flash(t){ if(status){ status.textContent = t; setTimeout(function(){ status.textContent=''; }, 2000); } }
    var copy = document.getElementById('copy-decisions');
    if(copy) copy.addEventListener('click', function(){
      var lines = [];
      sel.forEach(function(s){ lines.push(s.getAttribute('data-decision') + ': ' + s.value); });
      var text = 'Decisions (NFL Command Center, as of 2026-11-12):\n' + lines.join('\n');
      if(navigator.clipboard){ navigator.clipboard.writeText(text).then(function(){ flash('Copied'); }, function(){ window.prompt('Copy:', text); }); }
      else { window.prompt('Copy:', text); }
    });
    var reset = document.getElementById('reset-decisions');
    if(reset) reset.addEventListener('click', function(){
      sel.forEach(function(s){ s.value = 'Pending'; });
      localStorage.removeItem(KEY); flash('Reset');
    });
  }
})();
