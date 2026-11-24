(function () {
  // Live clock in the top bar
  var clock = document.getElementById("clock");
  if (clock) {
    var tick = function () {
      clock.textContent = new Date().toLocaleString([], {
        weekday: "short", hour: "2-digit", minute: "2-digit", second: "2-digit"
      });
    };
    tick();
    setInterval(tick, 1000);
  }

  // Mobile sidebar
  var menu = document.getElementById("menu-btn");
  var sidebar = document.getElementById("sidebar");
  var backdrop = document.getElementById("backdrop");
  function setMenu(open) {
    if (!sidebar) return;
    sidebar.classList.toggle("open", open);
    if (backdrop) backdrop.classList.toggle("show", open);
  }
  if (menu) menu.addEventListener("click", function () { setMenu(!sidebar.classList.contains("open")); });
  if (backdrop) backdrop.addEventListener("click", function () { setMenu(false); });

  // Live search over the document table (no page reload)
  var search = document.getElementById("doc-search");
  var rows = document.querySelectorAll("#doc-table tbody tr[data-search]");
  var noMatch = document.getElementById("no-match");
  if (search) {
    search.addEventListener("input", function () {
      var q = search.value.trim().toLowerCase();
      var visible = 0;
      rows.forEach(function (row) {
        var show = row.dataset.search.indexOf(q) !== -1;
        row.style.display = show ? "" : "none";
        if (show) visible++;
      });
      if (noMatch) noMatch.hidden = visible !== 0 || rows.length === 0;
    });
  }

  // Toast messages fade away
  document.querySelectorAll(".toasts .toast").forEach(function (toast, i) {
    setTimeout(function () {
      toast.classList.add("hide");
      setTimeout(function () { toast.remove(); }, 450);
    }, 4000 + i * 600);
  });
})();
