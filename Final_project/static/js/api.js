const API = "/api";
let access = localStorage.getItem("access");

async function request(path, { method = "GET", body, retry = true } = {}) {
  const res = await fetch(`${API}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(access && { Authorization: `Bearer ${access}` }),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401 && retry && (await refresh())) {
    return request(path, { method, body, retry: false });
  }
  if (!res.ok) throw Object.assign(new Error("API error"), { status: res.status, data: await res.json().catch(() => ({})) });
  return res.status === 204 ? null : res.json();
}

async function refresh() {
  const r = localStorage.getItem("refresh");
  if (!r) return false;
  const res = await fetch(`${API}/auth/token/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh: r }),
  });
  if (!res.ok) { localStorage.clear(); location.href = "/login/"; return false; }
  const data = await res.json();
  access = data.access;
  localStorage.setItem("access", access);
  if (data.refresh) localStorage.setItem("refresh", data.refresh);
  return true;
}

export async function login(email, password) {
  const res = await fetch(`${API}/auth/token/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error("Invalid credentials");
  const data = await res.json();
  access = data.access;
  localStorage.setItem("access", data.access);
  localStorage.setItem("refresh", data.refresh);
  return data.user;
}

export const api = {
  get: (p) => request(p),
  post: (p, body) => request(p, { method: "POST", body }),
  patch: (p, body) => request(p, { method: "PATCH", body }),
  del: (p) => request(p, { method: "DELETE" }),
};