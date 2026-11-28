/* Live status polling: fetch() a JSON endpoint every second until the work is finished. */
(() => {
  const root = document.getElementById("live");
  if (!root) return;

  const url = root.dataset.pollUrl;
  const kind = root.dataset.kind; // "report" | "product"
  const $ = (sel) => root.querySelector(`[data-bind="${sel}"]`);
  let delay = 1000;

  const setText = (name, value) => { const el = $(name); if (el) el.textContent = value ?? "-"; };

  function renderReport(d) {
    const status = $("status");
    status.textContent = d.status_label;
    status.className = `badge badge--${d.status}`;

    const bar = $("bar");
    bar.style.width = `${d.progress}%`;
    bar.className = "progress__bar" +
      (d.status === "processing" ? " is-live" : d.status === "done" ? " is-done" : d.status === "failed" ? " is-failed" : "");
    $("progressbar").setAttribute("aria-valuenow", d.progress);
    setText("percent", d.progress);
    setText("rows", d.rows.toLocaleString());
    setText("celery_state", d.celery_state || "-");

    d.steps.forEach((s) => {
      const li = root.querySelector(`[data-step="${s.key}"]`);
      if (!li) return;
      li.className = `step step--${s.state}`;
      li.querySelector("[data-hint]").textContent = s.hint;
    });

    const err = $("error");
    err.hidden = !d.error;
    err.textContent = d.error || "";

    const warn = $("email_error");
    warn.hidden = d.email_status !== "retrying";
    setText("email_error_text", d.email_error);

    const dl = $("download");
    if (d.download_url) { dl.href = d.download_url; dl.hidden = false; } else { dl.hidden = true; }
  }

  function renderProduct(d) {
    const status = $("status");
    status.textContent = d.state_label;
    status.className = `badge badge--p-${d.state}`;
    d.variants.forEach((v) => {
      const box = root.querySelector(`.variant[data-label="${v.label}"]`);
      if (!box) return;
      box.classList.toggle("is-ready", v.ready);
      const holder = box.querySelector(".variant__img");
      if (v.ready && !holder.querySelector("img")) {
        holder.innerHTML = "";
        const img = new Image();
        img.src = v.url; img.alt = v.label;
        holder.appendChild(img);
      }
      box.querySelector("small").textContent = `${v.px}px max` + (v.ready ? ` · ${v.size}` : "");
    });
    const err = $("error");
    err.hidden = !d.error;
    err.textContent = d.error || "";
  }

  function setConn(ok) {
    const chip = $("conn");
    chip.textContent = ok ? "● live" : "● reconnecting…";
    chip.classList.toggle("is-off", !ok);
  }

  async function tick() {
    try {
      const res = await fetch(url, { headers: { Accept: "application/json" }, cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      kind === "report" ? renderReport(data) : renderProduct(data);
      setConn(true);
      delay = 1000;
      if (data.terminal) { $("conn").textContent = "● finished"; return; } // stop polling
    } catch (e) {
      setConn(false);
      delay = Math.min(delay * 2, 8000); // back off while the server is unreachable
    }
    setTimeout(tick, delay);
  }

  tick();
})();
