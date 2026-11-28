(() => {
  "use strict";

  const MAX_LENGTH = Number(document.body.dataset.maxLength) || 500;
  const WS_ORIGIN = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}`;
  const RETRY_BASE_MS = 1000;
  const RETRY_MAX_MS = 10000;

  const $ = (sel) => document.querySelector(sel);
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
    constructor({ name, getUrl, onOpen, onMessage }) {
      this.name = name;
      this.getUrl = getUrl;
      this.onOpen = onOpen;
      this.onMessage = onMessage;
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

  /* ---------- Feed helper ---------- */
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

  /* ---------- Echo board ---------- */
  const boardFeed = $("#board-feed");
  const boardForm = $("#board-form");
  const boardInput = $("#board-input");
  const boardCount = $("#board-count");

  const board = new ManagedSocket({
    name: "board",
    getUrl: () => `${WS_ORIGIN}/ws/board/`,
    onMessage: (msg) => {
      if (msg.type === "echo") {
        addEntry(boardFeed, "echo", msg.text, `Server received at ${formatTime(msg.timestamp)}`);
      } else if (msg.type === "error") {
        addEntry(boardFeed, "error", msg.detail || "The server rejected that message.", msg.code || "");
      } else if (msg.type === "system") {
        addEntry(boardFeed, "system", msg.text);
      }
    },
  });

  function updateCount() {
    const n = boardInput.value.length;
    boardCount.textContent = `${n} / ${MAX_LENGTH}`;
    boardCount.classList.toggle("over", n > MAX_LENGTH);
  }

  boardInput.addEventListener("input", updateCount);
  boardInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      boardForm.requestSubmit();
    }
  });

  boardForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = boardInput.value;
    if (!text.trim()) return;
    // Over-limit text is sent on purpose so you can see the server's error event.
    if (board.send({ text })) {
      addEntry(boardFeed, "sent", text, `You sent at ${formatTime()}`);
      boardInput.value = "";
      updateCount();
    } else {
      addEntry(boardFeed, "system", "Not connected. Your message was not sent; it will work once the connection is open.");
    }
  });

  $("#board-drop").addEventListener("click", () => board.drop());

  /* ---------- Counter ---------- */
  const counterFeed = $("#counter-feed");
  const counterValue = $("#counter-value");
  const counterSub = $("#counter-sub");
  const counterStart = $("#counter-start");
  const counterError = $("#counter-error");
  const tickButton = $("#counter-tick");
  let startValue = 0;

  function showCount(value) {
    counterValue.textContent = String(value);
    counterValue.classList.remove("bump");
    void counterValue.offsetWidth; // restart the animation
    counterValue.classList.add("bump");
  }

  function setStartLabel() {
    document.querySelectorAll("[data-start-label]").forEach((el) => (el.textContent = startValue));
  }

  const counter = new ManagedSocket({
    name: "counter",
    getUrl: () => `${WS_ORIGIN}/ws/counter/${startValue}/`,
    onOpen: () => {
      tickButton.disabled = false;
    },
    onMessage: (msg) => {
      if (msg.type === "ready") {
        showCount(msg.value);
        counterSub.textContent = `Started at ${msg.value}`;
        addEntry(counterFeed, "system", `Counter ready, starting at ${msg.value}.`);
      } else if (msg.type === "counter") {
        showCount(msg.value);
        counterSub.textContent = `Updated ${formatTime(msg.timestamp)}`;
        addEntry(counterFeed, "echo", `Count is now ${msg.value}`, formatTime(msg.timestamp));
      } else if (msg.type === "error") {
        addEntry(counterFeed, "error", msg.detail || "The server rejected that action.", msg.code || "");
      }
    },
  });

  tickButton.addEventListener("click", () => {
    if (!counter.send({ action: "tick" })) {
      addEntry(counterFeed, "system", "Not connected. Wait for the connection to reopen, then tick again.");
    }
  });

  $("#counter-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const raw = counterStart.value.trim();
    if (!/^\d+$/.test(raw)) {
      counterError.textContent = "Enter a whole number that is zero or higher.";
      counterError.hidden = false;
      counterStart.focus();
      return;
    }
    counterError.hidden = true;
    startValue = Number(raw);
    setStartLabel();
    counterFeed.innerHTML = "";
    counter.attempt = 0;
    counter.connect();
  });

  /* ---------- Go ---------- */
  updateCount();
  setStartLabel();
  board.connect();
  counter.connect();
})();
