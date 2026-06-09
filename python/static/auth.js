(() => {
  const TOKEN_KEY = "aityuahn-token";
  const USER_KEY = "aityuahn-user";
  const STORAGE_API = "aityuahn-api-base";

  let cachedConfig = null;

  function getToken() {
    return localStorage.getItem(TOKEN_KEY) || "";
  }

  function setSession(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  }

  function getUser() {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY) || "null");
    } catch {
      return null;
    }
  }

  function clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  }

  async function loadConfig() {
    if (cachedConfig) return cachedConfig;
    try {
      const r = await fetch(new URL("config.json", document.baseURI).href);
      cachedConfig = r.ok ? await r.json() : {};
    } catch {
      cachedConfig = {};
    }
    return cachedConfig;
  }

  function isLocalHost() {
    return location.hostname === "127.0.0.1" || location.hostname === "localhost";
  }

  function readApiBase() {
    const params = new URLSearchParams(location.search);
    const fromQuery = params.get("api");
    if (fromQuery) {
      const v = fromQuery.replace(/\/$/, "");
      localStorage.setItem(STORAGE_API, v);
      return v;
    }
    const stored = localStorage.getItem(STORAGE_API);
    if (stored) return stored.replace(/\/$/, "");
    if (cachedConfig?.defaultApi) return String(cachedConfig.defaultApi).replace(/\/$/, "");
    if (isLocalHost()) return location.origin.replace(/\/$/, "");
    return "";
  }

  function setApiBase(url) {
    const v = url.trim().replace(/\/$/, "");
    if (v) localStorage.setItem(STORAGE_API, v);
    else localStorage.removeItem(STORAGE_API);
    return v;
  }

  function parseError(body, status) {
    if (typeof body === "string") {
      if (body.includes("405") || body.includes("Not Allowed")) {
        return "This site is UI-only on GitHub Pages. Enter your aityuahn serve URL (e.g. http://127.0.0.1:8765).";
      }
      if (body.trim().startsWith("<")) {
        return `API error (${status}). Check the backend URL — registration runs on aityuahn serve, not GitHub Pages.`;
      }
      return body.slice(0, 240);
    }
    return JSON.stringify(body);
  }

  async function probeApi(base) {
    const r = await fetch(`${base}/api/health`, { headers: { Accept: "application/json" } });
    if (!r.ok) throw new Error(`API not reachable at ${base} (HTTP ${r.status})`);
    return r.json();
  }

  async function saasApi(path, opts = {}) {
    await loadConfig();
    const base = readApiBase();
    if (!base) {
      throw new Error(
        "Set the API backend URL (run: aityuahn serve → http://127.0.0.1:8765). GitHub Pages hosts the UI only."
      );
    }
    const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
    const r = await fetch(`${base}/api/saas${path}`, { ...opts, headers });
    const text = await r.text();
    let body;
    try {
      body = JSON.parse(text);
    } catch {
      body = text;
    }
    if (!r.ok) throw new Error(parseError(body, r.status));
    return body;
  }

  window.AityAuth = {
    getToken,
    setSession,
    getUser,
    clearSession,
    loadConfig,
    readApiBase,
    setApiBase,
    probeApi,
    saasApi,
    isLocalHost,
    PENDING_AUTH_KEY: "aityuahn-pending-auth",
  };
})();
