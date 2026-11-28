(() => {
  "use strict";

  const { ManagedSocket, formatTime } = window.Relay;
  const $ = (sel) => document.querySelector(sel);

  const app = $("#chat-app");
  const ROOM = app.dataset.room;
  const ME = app.dataset.username;
  const MAX_LENGTH = Number(app.dataset.maxLength) || 1000;
  const WS_ORIGIN = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}`;

  const feed = $("#chat-feed");
  const form = $("#chat-form");
  const input = $("#chat-input");
  const typingEl = $("#chat-typing");
  const onlineList = $("#online-list");
  const onlineCount = $("#online-count");
  const offline = $("#chat-offline");

  const seenIds = new Set(); // message ids already on screen (history and live can overlap)
  let lastPresence = null;

  /* ---------- Rendering ---------- */
  const hueFor = (name) => {
    let h = 0;
    for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) % 360;
    return h;
  };

  const nearBottom = () => feed.scrollHeight - feed.scrollTop - feed.clientHeight < 80;
  const scrollToEnd = () => (feed.scrollTop = feed.scrollHeight);

  function append(node, { force = false } = {}) {
    const stick = force || nearBottom();
    const empty = feed.querySelector(".empty");
    if (empty) empty.remove();
    feed.appendChild(node);
    if (stick) scrollToEnd();
  }

  function avatar(name) {
    const a = document.createElement("span");
    a.className = "avatar";
    a.style.setProperty("--hue", hueFor(name));
    a.textContent = name.charAt(0).toUpperCase();
    a.setAttribute("aria-hidden", "true");
    return a;
  }

  function messageNode(m) {
    const li = document.createElement("li");
    li.className = "chat-msg" + (m.username === ME ? " mine" : "");

    const body = document.createElement("div");
    body.className = "bubble";

    const head = document.createElement("div");
    head.className = "msg-head";
    const who = document.createElement("strong");
    who.textContent = m.username === ME ? "You" : m.username;
    const when = document.createElement("time");
    when.dateTime = m.created_at;
    when.textContent = formatTime(m.created_at);
    head.append(who, when);

    const text = document.createElement("p");
    text.textContent = m.content; // textContent: chat text is never treated as HTML
    body.append(head, text);

    li.append(avatar(m.username), body);
    return li;
  }

  function noteNode(text) {
    const li = document.createElement("li");
    li.className = "chat-note";
    li.textContent = text;
    return li;
  }

  function announcementNode(a) {
    const li = document.createElement("li");
    li.className = "chat-announce";
    li.setAttribute("role", "note");
    const title = document.createElement("strong");
    title.textContent = a.title;
    const body = document.createElement("p");
    body.textContent = a.body;
    const when = document.createElement("time");
    when.dateTime = a.created_at;
    when.textContent = `Announcement, ${formatTime(a.created_at)}`;
    li.append(title, body, when);
    return li;
  }

  function addMessage(m, opts) {
    if (seenIds.has(m.id)) return;
    seenIds.add(m.id);
    append(messageNode(m), opts);
  }

  /* ---------- Typing indicator (remote) ---------- */
  const typers = new Map(); // username -> expiry timer

  function renderTyping() {
    const names = [...typers.keys()];
    if (names.length === 0) typingEl.textContent = "";
    else if (names.length === 1) typingEl.textContent = `${names[0]} is typing…`;
    else if (names.length === 2) typingEl.textContent = `${names[0]} and ${names[1]} are typing…`;
    else typingEl.textContent = "Several people are typing…";
  }

  function setTyper(name, on) {
    clearTimeout(typers.get(name));
    typers.delete(name);
    // If the "stopped typing" event is lost, the indicator still expires.
    if (on) typers.set(name, setTimeout(() => { typers.delete(name); renderTyping(); }, 5000));
    renderTyping();
  }

  /* ---------- Online list ---------- */
  function renderPresence(users) {
    onlineList.replaceChildren(
      ...users.map((name) => {
        const li = document.createElement("li");
        const dot = document.createElement("span");
        dot.className = "presence-dot";
        const label = document.createElement("span");
        label.textContent = name === ME ? `${name} (you)` : name;
        li.append(avatar(name), label, dot);
        return li;
      })
    );
    onlineCount.textContent = String(users.length);

    if (lastPresence) {
      users.filter((u) => u !== ME && !lastPresence.has(u)).forEach((u) => append(noteNode(`${u} joined`)));
      [...lastPresence].filter((u) => !users.includes(u)).forEach((u) => append(noteNode(`${u} left`)));
    }
    lastPresence = new Set(users);
  }

  /* ---------- Socket ---------- */
  const socket = new ManagedSocket({
    name: "chat",
    getUrl: () => `${WS_ORIGIN}/ws/chat/${encodeURIComponent(ROOM)}/`,
    maxAttempts: 8,
    onOpen: () => {
      offline.hidden = true;
      lastPresence = null;
    },
    onGiveUp: () => {
      offline.hidden = false;
      renderPresence([]);
    },
    onMessage: (msg) => {
      switch (msg.type) {
        case "history": {
          feed.replaceChildren();
          seenIds.clear();
          if (msg.messages.length === 0) {
            const empty = document.createElement("li");
            empty.className = "empty";
            empty.textContent = "No messages yet. Say hello.";
            feed.appendChild(empty);
          }
          msg.messages.forEach((m) => addMessage(m, { force: true }));
          scrollToEnd();
          break;
        }
        case "message":
          setTyper(msg.message.username, false);
          addMessage(msg.message);
          break;
        case "presence":
          renderPresence(msg.users);
          break;
        case "typing":
          setTyper(msg.username, msg.is_typing);
          break;
        case "announcement":
          append(announcementNode(msg), { force: true });
          break;
        case "error":
          append(noteNode(msg.detail || "Something went wrong."), { force: true });
          break;
      }
    },
  });

  $("#chat-retry").addEventListener("click", () => {
    socket.attempt = 0;
    offline.hidden = true;
    socket.connect();
  });

  /* ---------- Composer and typing (local) ---------- */
  let typingSentAt = 0;
  let idleTimer = null;

  function sendTyping(on) {
    socket.send({ type: "typing", is_typing: on });
  }

  function stopTyping() {
    clearTimeout(idleTimer);
    if (typingSentAt) sendTyping(false);
    typingSentAt = 0;
  }

  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 160)}px`;

    if (!input.value.trim()) return stopTyping();
    const now = Date.now();
    if (now - typingSentAt > 2000) { // at most one event every 2 seconds
      sendTyping(true);
      typingSentAt = now;
    }
    clearTimeout(idleTimer);
    idleTimer = setTimeout(stopTyping, 2500);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      form.requestSubmit();
    }
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const content = input.value.trim();
    if (!content) return;
    if (content.length > MAX_LENGTH) {
      append(noteNode(`Messages can be up to ${MAX_LENGTH} characters.`), { force: true });
      return;
    }
    if (socket.send({ type: "message", content })) {
      stopTyping();
      input.value = "";
      input.style.height = "auto";
    } else {
      append(noteNode("Not connected yet. Your message was not sent."), { force: true });
    }
  });

  socket.connect();
  input.focus();
})();
