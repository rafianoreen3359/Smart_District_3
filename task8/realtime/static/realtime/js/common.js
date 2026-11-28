/* Shared helpers for every page: status pills, reconnecting socket, time format. */
(() => {
  "use strict";

  const RETRY_BASE_MS = 1000;
  const RETRY_MAX_MS = 10000;

  const timeFmt = new Intl.DateTimeFormat(undefined, { hour: "numeric", minute: "2-digit", second: "2-digit" });
  const formatTime = (iso) => {
    const d = iso ? new Date(iso) : new Date();
    return Number.isNaN(d.getTime()) ? "" : timeFmt.format(d);
  };

  /* ---------- Status pills ---------- */
  function setStatus(name, status, detail) {
    const labels = { connecting: "Connecting", open: "Open", closed: "Closed" };
    const text = detail ? `${labels[status]}, ${detail}` : labels[status];
    document.querySelectorAll(`[data-status-for="${name}"]`).forEach((pill) => {
      pill.dataset.status = status;
      pill.querySelector(".label").textContent = text;
    });
  }

  /* ---------- Socket with automatic reconnect ---------- */
  class ManagedSocket {
    constructor({ name, getUrl, onOpen, onMessage, maxAttempts = Infinity, onGiveUp }) {
      this.name = name;
      this.getUrl = getUrl;
      this.onOpen = onOpen;
      this.onMessage = onMessage;
      this.maxAttempts = maxAttempts;
      this.onGiveUp = onGiveUp;
      this.ws = null;
      this.attempt = 0;
      this.retryTimer = null;
      this.countdownTimer = null;
    }

    connect() {
      this.clearTimers();
      this.detach();
      setStatus(this.name, "connecting");

      let ws;
      try {
        ws = new WebSocket(this.getUrl());
      } catch (err) {
        this.scheduleRetry();
        return;
      }
      this.ws = ws;

      ws.addEventListener("open", () => {
        if (this.ws !== ws) return;
        this.attempt = 0;
        setStatus(this.name, "open");
        this.onOpen && this.onOpen();
      });

      ws.addEventListener("message", (event) => {
        if (this.ws !== ws) return;
        let data;
        try {
          data = JSON.parse(event.data);
        } catch (err) {
          data = { type: "error", detail: "Received a message that is not valid JSON." };
        }
        this.onMessage(data);
      });

      ws.addEventListener("close", () => {
        if (this.ws !== ws) return;
        this.ws = null;
        this.scheduleRetry();
      });
      // "error" is always followed by "close", which handles the retry.
    }

    scheduleRetry() {
      this.clearTimers();
      this.attempt += 1;
      if (this.attempt > this.maxAttempts) {
        setStatus(this.name, "closed");
        this.onGiveUp && this.onGiveUp();
        return;
      }
      const backoff = Math.min(RETRY_BASE_MS * 2 ** (this.attempt - 1), RETRY_MAX_MS);
      const delay = backoff + Math.random() * 300;
      const retryAt = Date.now() + delay;

      const tick = () => {
        const secs = Math.max(0, Math.ceil((retryAt - Date.now()) / 1000));
        setStatus(this.name, "closed", `retrying in ${secs}s`);
      };
      tick();
      this.countdownTimer = setInterval(tick, 250);
      this.retryTimer = setTimeout(() => this.connect(), delay);
    }

    send(payload) {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return false;
      this.ws.send(JSON.stringify(payload));
      return true;
    }

    /** Close the socket the way a network drop would, so the retry logic runs. */
    drop() {
      if (this.ws) this.ws.close(4000, "dropped by user");
    }

    detach() {
      if (!this.ws) return;
      const old = this.ws;
      this.ws = null; // listeners ignore events from sockets that are no longer current
      old.close(1000);
    }

    clearTimers() {
      clearTimeout(this.retryTimer);
      clearInterval(this.countdownTimer);
    }
  }

  /* ---------- Simple feed entry (used by the echo board and counter) ---------- */
  function addEntry(feed, kind, text, meta) {
    const empty = feed.querySelector(".empty");
    if (empty) empty.remove();

    const li = document.createElement("li");
    li.className = `msg ${kind}`;
    const body = document.createElement("span");
    body.textContent = text; // never innerHTML: messages are untrusted text
    li.appendChild(body);
    if (meta) {
      const m = document.createElement("span");
      m.className = "meta";
      m.textContent = meta;
      li.appendChild(m);
    }
    feed.appendChild(li);
    while (feed.children.length > 200) feed.firstElementChild.remove();
    feed.scrollTop = feed.scrollHeight;
  }

  window.Relay = { ManagedSocket, setStatus, formatTime, addEntry };
})();
