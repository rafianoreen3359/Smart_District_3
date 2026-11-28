(() => {
  "use strict";

  const MAX_LENGTH = Number(document.body.dataset.maxLength) || 500;
  const WS_ORIGIN = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}`;
  const $ = (sel) => document.querySelector(sel);
  const { ManagedSocket, setStatus, formatTime, addEntry } = window.Relay;

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
