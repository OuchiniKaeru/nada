const API_BASE = "/api";

function getToken() {
  return localStorage.getItem("nada_token");
}

function setToken(token) {
  localStorage.setItem("nada_token", token);
}

function clearToken() {
  localStorage.removeItem("nada_token");
}

async function api(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const token = getToken();
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    clearToken();
    window.location.hash = "#login";
    throw new Error("認証が必要です。");
  }

  const text = await response.text();
  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text || null;
  }

  if (!response.ok) {
    const message = data?.detail || `HTTP ${response.status}`;
    const error = new Error(message);
    error.status = response.status;
    error.body = data;
    throw error;
  }

  return data;
}

function getRouteId(prefix) {
  const hash = window.location.hash.replace("#", "");
  if (!hash.startsWith(`${prefix}/`)) return null;
  return hash.slice(prefix.length + 1) || null;
}

function sse(path, onMessage) {
  const token = getToken();
  const url = `${API_BASE}${path}${token ? `?access_token=${encodeURIComponent(token)}` : ""}`;

  const eventSource = new EventSource(url);

  eventSource.addEventListener("message", (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch {
      onMessage({ raw: event.data });
    }
  });

  eventSource.onerror = () => {
    eventSource.close();
  };

  return eventSource;
}
