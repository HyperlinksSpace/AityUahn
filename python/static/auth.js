(() => {
  const TOKEN_KEY = "aityuahn-token";
  const USER_KEY = "aityuahn-user";

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

  function readApiBase() {
    const params = new URLSearchParams(location.search);
    const fromQuery = params.get("api");
    if (fromQuery) {
      const v = fromQuery.replace(/\/$/, "");
      localStorage.setItem("aityuahn-api-base", v);
      return v;
    }
    return (localStorage.getItem("aityuahn-api-base") || location.origin).replace(/\/$/, "");
  }

  async function saasApi(path, opts = {}) {
    const base = readApiBase();
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
    if (!r.ok) throw new Error(typeof body === "object" ? JSON.stringify(body) : body);
    return body;
  }

  window.AityAuth = { getToken, setSession, getUser, clearSession, readApiBase, saasApi };
})();
