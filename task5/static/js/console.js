(function () {
  var state = { auth: null, page: 1, next: null, previous: null };

  function el(id) { return document.getElementById(id); }

  function toast(message, kind) {
    var box = el("toasts");
    var node = document.createElement("div");
    node.className = "toast " + (kind || "");
    node.textContent = message;
    box.appendChild(node);
    setTimeout(function () {
      node.classList.add("hide");
      setTimeout(function () { node.remove(); }, 450);
    }, 4500);
  }

  function decodeJwt(token) {
    try {
      var part = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
      while (part.length % 4) { part += "="; }
      return JSON.parse(atob(part));
    } catch (e) { return {}; }
  }

  function errorText(result) {
    var d = result.data;
    if (d && d.detail) { return String(d.detail); }
    if (d && typeof d === "object") { return JSON.stringify(d); }
    return "Request failed (" + result.status + ")";
  }

  function api(path, options) {
    options = options || {};
    var headers = { "Content-Type": "application/json" };
    if (state.auth) { headers["Authorization"] = state.auth.header; }
    var method = options.method || "GET";
    return fetch("/api/" + path, {
      method: method,
      headers: headers,
      body: options.body ? JSON.stringify(options.body) : undefined
    }).then(function (res) {
      return res.text().then(function (text) {
        var data = null;
        try { data = text ? JSON.parse(text) : null; } catch (e) { data = text; }
        el("log").textContent = method + " /api/" + path + "\n" + res.status + " " + res.statusText + "\n\n" +
          (typeof data === "string" ? data : JSON.stringify(data, null, 2));
        return { ok: res.ok, status: res.status, data: data };
      });
    });
  }

  function setWho() {
    var who = el("who");
    var main = el("who-main");
    main.textContent = "";
    if (!state.auth) { who.hidden = true; return; }
    var strong = document.createElement("strong");
    var chip = document.createElement("span");
    chip.className = "chip-role";
    if (state.auth.type === "jwt") {
      strong.textContent = state.auth.claims.email || "Signed in";
      chip.textContent = state.auth.claims.role || "user";
    } else {
      strong.textContent = "API key";
      chip.textContent = "read-only";
    }
    main.appendChild(strong);
    main.appendChild(chip);
    who.hidden = false;
    el("jwt-form").hidden = true;
    el("key-form").hidden = true;
  }

  function showForms() {
    var tab = document.querySelector(".tab.active").dataset.tab;
    el("jwt-form").hidden = tab !== "jwt";
    el("key-form").hidden = tab !== "key";
  }

  function button(label, cls, handler) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "btn sm " + cls;
    b.textContent = label;
    b.addEventListener("click", handler);
    return b;
  }

  function after(okMessage) {
    return function (result) {
      if (result.ok) { toast(okMessage, "success"); loadDocs(); }
      else { toast(errorText(result), "error"); }
    };
  }

  function renderDocs(results) {
    var box = el("docs");
    box.textContent = "";
    if (!results.length) {
      var empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "No documents visible to you.";
      box.appendChild(empty);
      return;
    }
    results.forEach(function (d) {
      var card = document.createElement("article");
      card.className = "dcard";

      var top = document.createElement("div");
      top.className = "top";
      var title = document.createElement("h3");
      title.textContent = d.title;
      var pill = document.createElement("span");
      pill.className = "pill " + d.status;
      pill.textContent = d.status;
      top.appendChild(title);
      top.appendChild(pill);

      var body = document.createElement("p");
      body.textContent = (d.content || "").slice(0, 140) || "(empty)";

      var meta = document.createElement("div");
      meta.className = "meta";
      meta.textContent = "#" + d.id + " - by " + d.owner_email;

      var row = document.createElement("div");
      row.className = "row";
      row.appendChild(button("Edit", "ghost", function () {
        var t = window.prompt("New title", d.title);
        if (t) { api("documents/" + d.id + "/", { method: "PATCH", body: { title: t } }).then(after("Document updated.")); }
      }));
      row.appendChild(button("Publish", "success", function () {
        api("documents/" + d.id + "/publish/", { method: "POST" }).then(after("Document published."));
      }));
      row.appendChild(button("Archive", "warn", function () {
        api("documents/" + d.id + "/archive/", { method: "POST" }).then(after("Document archived."));
      }));
      row.appendChild(button("Delete", "danger", function () {
        if (window.confirm("Delete '" + d.title + "'?")) {
          api("documents/" + d.id + "/", { method: "DELETE" }).then(after("Document deleted."));
        }
      }));

      card.appendChild(top);
      card.appendChild(body);
      card.appendChild(meta);
      card.appendChild(row);
      box.appendChild(card);
    });
  }

  function loadDocs() {
    if (!state.auth) { return; }
    api("documents/?page=" + state.page).then(function (result) {
      if (!result.ok) {
        toast(errorText(result), "error");
        return;
      }
      var data = result.data;
      renderDocs(data.results);
      el("count").textContent = data.count;
      state.next = data.next;
      state.previous = data.previous;
      el("prev").disabled = !data.previous;
      el("next").disabled = !data.next;
      el("page-label").textContent = "Page " + state.page;
    });
  }

  // ---- events ----
  document.querySelectorAll(".tab").forEach(function (tab) {
    tab.addEventListener("click", function () {
      document.querySelectorAll(".tab").forEach(function (t) { t.classList.remove("active"); });
      tab.classList.add("active");
      if (!state.auth) { showForms(); }
    });
  });

  el("jwt-form").addEventListener("submit", function (e) {
    e.preventDefault();
    fetch("/api/token/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: el("jwt-email").value, password: el("jwt-password").value })
    }).then(function (res) {
      return res.json().then(function (data) { return { ok: res.ok, data: data }; });
    }).then(function (r) {
      if (!r.ok) { toast(r.data.detail || "Login failed.", "error"); return; }
      state.auth = { type: "jwt", header: "Bearer " + r.data.access, claims: decodeJwt(r.data.access) };
      state.page = 1;
      setWho();
      toast("Signed in as " + (state.auth.claims.role || "user") + ".", "success");
      loadDocs();
    });
  });

  el("key-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var key = el("key-input").value.trim();
    if (!key) { return; }
    state.auth = { type: "key", header: "Api-Key " + key };
    state.page = 1;
    setWho();
    loadDocs();
  });

  el("logout").addEventListener("click", function () {
    state.auth = null;
    el("docs").textContent = "";
    el("count").textContent = "";
    el("page-label").textContent = "";
    el("prev").disabled = true;
    el("next").disabled = true;
    el("who").hidden = true;
    showForms();
    toast("Signed out.");
  });

  el("create-form").addEventListener("submit", function (e) {
    e.preventDefault();
    api("documents/", {
      method: "POST",
      body: { title: el("new-title").value, content: el("new-content").value }
    }).then(function (result) {
      if (result.ok) {
        el("create-form").reset();
        toast("Document created.", "success");
        loadDocs();
      } else { toast(errorText(result), "error"); }
    });
  });

  el("reload").addEventListener("click", loadDocs);
  el("prev").addEventListener("click", function () { if (state.previous) { state.page -= 1; loadDocs(); } });
  el("next").addEventListener("click", function () { if (state.next) { state.page += 1; loadDocs(); } });
})();
