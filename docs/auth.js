(() => {
  const TOKEN_KEY = "aityuahn-token";
  const USER_KEY = "aityuahn-user";
  const STORAGE_FORGE = "aityuahn-forge-api";
  const STORAGE_SAAS = "aityuahn-saas-api";
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

  function readForgeBase() {
    const params = new URLSearchParams(location.search);
    const fromQuery = params.get("api") || params.get("forge");
    if (fromQuery) {
      const v = fromQuery.replace(/\/$/, "");
      localStorage.setItem(STORAGE_FORGE, v);
      return v;
    }
    const stored = localStorage.getItem(STORAGE_FORGE) || localStorage.getItem(STORAGE_API);
    if (stored) return stored.replace(/\/$/, "");
    if (cachedConfig?.defaultForgeApi) return String(cachedConfig.defaultForgeApi).replace(/\/$/, "");
    if (cachedConfig?.defaultApi) return String(cachedConfig.defaultApi).replace(/\/$/, "");
    if (cachedConfig?.defaultApiLocal) return String(cachedConfig.defaultApiLocal).replace(/\/$/, "");
    if (isLocalHost()) return location.origin.replace(/\/$/, "");
    return "";
  }

  function readSaasBase() {
    const params = new URLSearchParams(location.search);
    const fromQuery = params.get("saas");
    if (fromQuery) {
      const v = fromQuery.replace(/\/$/, "");
      localStorage.setItem(STORAGE_SAAS, v);
      return v;
    }
    const stored = localStorage.getItem(STORAGE_SAAS);
    if (stored) return stored.replace(/\/$/, "");
    if (cachedConfig?.defaultSaasApi) return String(cachedConfig.defaultSaasApi).replace(/\/$/, "");
    return readForgeBase();
  }

  function readApiBase() {
    return readForgeBase();
  }

  function setForgeBase(url) {
    const v = url.trim().replace(/\/$/, "");
    if (v) {
      localStorage.setItem(STORAGE_FORGE, v);
      localStorage.setItem(STORAGE_API, v);
    } else {
      localStorage.removeItem(STORAGE_FORGE);
      localStorage.removeItem(STORAGE_API);
    }
    return v;
  }

  function setApiBase(url) {
    return setForgeBase(url);
  }

  function setSaasBase(url) {
    const v = url.trim().replace(/\/$/, "");
    if (v) localStorage.setItem(STORAGE_SAAS, v);
    else localStorage.removeItem(STORAGE_SAAS);
    return v;
  }

  function parseError(body, status) {
    if (typeof body === "string") {
      if (body.includes("405") || body.includes("Not Allowed")) {
        return "This site is UI-only on GitHub Pages. Run aityuahn serve locally and connect the forge API.";
      }
      if (body.trim().startsWith("<")) {
        return `API error (${status}). Check forge vs cloud SaaS URLs in config.`;
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
    const base = readSaasBase();
    if (!base) {
      throw new Error(
        "Set defaultSaasApi in config (your Vercel URL) or run aityuahn serve --with-saas locally."
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
    readForgeBase,
    readSaasBase,
    readApiBase,
    setForgeBase,
    setSaasBase,
    setApiBase,
    probeApi,
    saasApi,
    isLocalHost,
    PENDING_AUTH_KEY: "aityuahn-pending-auth",
  };
})();
