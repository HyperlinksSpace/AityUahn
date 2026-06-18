(() => {
  const STORAGE_API = "aityuahn-api-base";
  const STORAGE_DEMO = "aityuahn-demo-overrides";
  const PENDING_AUTH_KEY = "aityuahn-pending-auth";
  const DEMO_DATA_URL = new URL("demo-data.json", document.baseURI).href;
  const CONFIG_URL = new URL("config.json", document.baseURI).href;

  const KANBAN = [
    { key: "backlog", label: "Backlog", statuses: ["idea", "backlog"] },
    { key: "in_progress", label: "In progress", statuses: ["in_progress"] },
    { key: "review", label: "Review", statuses: ["review"] },
    { key: "blocked", label: "Blocked", statuses: ["blocked"] },
    { key: "done", label: "Done", statuses: ["done", "cancelled"] },
  ];

  const ALL_STATUSES = ["backlog", "in_progress", "review", "blocked", "done"];

  let mode = "loading";
  let apiBase = "";
  let demoData = null;
  let dashboard = null;
  let selectedSlug = null;
  let currentView = "kanban";
  let providers = [];
  let teamProjects = [];
  let activeTeamProject = null;
  let tonPollTimer = null;
  let activeTonPaymentId = null;
  let authMode = null;

  function authHeaders() {
    const h = {};
    if (window.AityAuth?.getToken()) h.Authorization = `Bearer ${AityAuth.getToken()}`;
    return h;
  }

  function currentUser() {
    return window.AityAuth?.getUser() || null;
  }

  function updateAuthUI() {
    const user = currentUser();
    const badge = document.getElementById("userBadge");
    const signOut = document.getElementById("btnSignOut");
    const signIn = document.getElementById("btnSignIn");
    const newProj = document.getElementById("btnNewProject");
    const teamList = document.getElementById("teamProjectList");
    const upgrade = document.getElementById("btnUpgradeTeam");
    const tonPanel = document.getElementById("tonPaymentPanel");
    if (!badge) return;
    if (user) {
      badge.textContent = `${user.name} · ${user.plan}`;
      badge.classList.remove("hidden");
      signOut?.classList.remove("hidden");
      signIn?.classList.add("hidden");
      newProj?.classList.remove("hidden");
      teamList?.classList.remove("hidden");
      const isTeam = user.plan === "team";
      upgrade?.classList.toggle("hidden", isTeam);
      if (isTeam) {
        tonPanel?.classList.add("hidden");
        stopTonPoll();
      }
    } else {
      badge.classList.add("hidden");
      signOut?.classList.add("hidden");
      signIn?.classList.toggle("hidden", mode !== "live");
      newProj?.classList.add("hidden");
      teamList?.classList.add("hidden");
      upgrade?.classList.add("hidden");
      tonPanel?.classList.add("hidden");
      stopTonPoll();
    }
  }

  function readPendingAuth() {
    try {
      return JSON.parse(sessionStorage.getItem(PENDING_AUTH_KEY) || "null");
    } catch {
      return null;
    }
  }

  function hasAuthIntent() {
    const params = new URLSearchParams(location.search);
    return Boolean(params.get("auth") || readPendingAuth());
  }

  function needsBackendBeforeUse() {
    return hasAuthIntent() || Boolean(currentUser());
  }

  function clearPendingAuth() {
    sessionStorage.removeItem(PENDING_AUTH_KEY);
  }

  function fillAuthForm(payload) {
    if (!payload) return;
    if (payload.email) document.getElementById("authEmail").value = payload.email;
    if (payload.name) document.getElementById("authName").value = payload.name;
    if (payload.plan) document.getElementById("authPlan").value = payload.plan;
  }

  function openAuthDialog(nextMode = "login", payload = null) {
    if (mode !== "live") {
      toast("Connect your backend first (see setup steps)", true);
      document.getElementById("blockedOverlay")?.classList.remove("hidden");
      return;
    }
    authMode = nextMode;
    document.getElementById("authTitle").textContent = nextMode === "login" ? "Sign in" : "Create account";
    document.getElementById("authToggle").textContent = nextMode === "login" ? "Create account" : "Sign in instead";
    document.getElementById("authPlanWrap").classList.toggle("hidden", nextMode === "login");
    const errEl = document.getElementById("authError");
    errEl.style.display = "none";
    fillAuthForm(payload || readPendingAuth());
    document.getElementById("authDialog")?.showModal();
  }

  async function submitAuth(nextMode, fields) {
    const path = nextMode === "login" ? "/auth/login" : "/auth/register";
    const body =
      nextMode === "login"
        ? { email: fields.email, password: fields.password }
        : { email: fields.email, password: fields.password, name: fields.name, plan: fields.plan };
    const data = await AityAuth.saasApi(path, { method: "POST", body: JSON.stringify(body) });
    AityAuth.setSession(data.access_token, data.user);
    clearPendingAuth();
    updateAuthUI();
    document.getElementById("authDialog")?.close();
    await loadTeamProjects();
    await refresh();
    if (data.requires_ton_payment || (nextMode === "register" && fields.plan === "team")) {
      setView("team");
      await startTeamPayment();
    }
    toast(nextMode === "login" ? "Signed in" : "Account created");
    return data;
  }

  async function completePendingAuth() {
    const payload = readPendingAuth();
    if (!payload || mode !== "live") return false;
    try {
      await submitAuth(payload.mode || "register", payload);
      return true;
    } catch (ex) {
      openAuthDialog(payload.mode || "register", payload);
      toast(String(ex.message || ex), true);
      return false;
    }
  }

  async function afterBackendReady() {
    const params = new URLSearchParams(location.search);
    const completed = await completePendingAuth();
    if (completed) return;
    const pending = readPendingAuth();
    const modeParam = params.get("auth") || pending?.mode;
    if (modeParam) openAuthDialog(modeParam, pending);
    else if (params.get("upgrade") === "ton" && currentUser()?.plan !== "team") {
      setView("team");
      startTeamPayment();
    }
  }

  async function loadBillingSettings() {
    if (!AityAuth.getToken() || mode !== "live") return null;
    try {
      return await AityAuth.saasApi("/billing/ton-config");
    } catch {
      try {
        const plans = await AityAuth.saasApi("/pricing");
        const team = plans.find((p) => p.id === "team");
        if (team) {
          return { team_price_ton: team.price_ton ?? parseFloat(String(team.price_label)), enabled: true };
        }
      } catch {
        return null;
      }
      return null;
    }
  }

  function setUpgradeButtonLabel(priceTon) {
    const btn = document.getElementById("btnUpgradeTeam");
    if (!btn || !priceTon) return;
    btn.textContent = `Pay ${priceTon} TON — Team plan`;
  }

  function stopTonPoll() {
    if (tonPollTimer) {
      clearInterval(tonPollTimer);
      tonPollTimer = null;
    }
    activeTonPaymentId = null;
  }

  function showTonPayment(payment) {
    const panel = document.getElementById("tonPaymentPanel");
    if (!panel || !payment?.payment_id) return;
    activeTonPaymentId = payment.payment_id;
    document.getElementById("tonAmount").textContent = String(payment.amount_ton ?? 10);
    document.getElementById("tonWallet").value = payment.wallet_address || "";
    document.getElementById("tonComment").value = payment.comment || payment.payment_id;
    const link = document.getElementById("tonDeeplink");
    if (link) link.href = payment.deeplink || "#";
    document.getElementById("tonPaymentStatus").textContent =
      payment.status === "completed"
        ? "Payment confirmed — Team plan active."
        : "Waiting for on-chain deposit…";
    panel.classList.remove("hidden");
    document.getElementById("btnUpgradeTeam")?.classList.add("hidden");
    if (payment.status !== "completed" && !tonPollTimer) {
      tonPollTimer = setInterval(() => checkTonPayment(false), 8000);
    }
  }

  async function checkTonPayment(manual = true) {
    if (!activeTonPaymentId || !AityAuth.getToken()) return;
    try {
      const payment = await AityAuth.saasApi(`/billing/team-payment/${activeTonPaymentId}`);
      showTonPayment(payment);
      if (payment.status === "completed" || payment.plan === "team") {
        stopTonPoll();
        AityAuth.setSession(AityAuth.getToken(), { ...currentUser(), plan: "team" });
        updateAuthUI();
        toast("Team plan activated — thank you!");
      } else if (manual) {
        toast("Payment not detected yet — send TON with the exact comment");
      }
    } catch (ex) {
      if (manual) toast(String(ex.message || ex), true);
    }
  }

  async function startTeamPayment() {
    try {
      requireLive();
      const payment = await AityAuth.saasApi("/billing/team-payment", { method: "POST", body: "{}" });
      showTonPayment(payment);
      setView("team");
      toast(`Send ${payment.amount_ton ?? "the required"} TON with the payment ID as comment`);
    } catch (ex) {
      const msg = String(ex.message || ex);
      if (msg.includes("503") || msg.toLowerCase().includes("wallet not configured")) {
        try {
          const res = await AityAuth.saasApi("/billing/upgrade-team", { method: "POST", body: "{}" });
          AityAuth.setSession(AityAuth.getToken(), { ...currentUser(), plan: res.plan });
          updateAuthUI();
          toast(res.message || "Upgraded (demo mode)");
          return;
        } catch (inner) {
          toast(String(inner.message || inner), true);
          return;
        }
      }
      toast(msg, true);
    }
  }

  async function resumeTonPaymentIfAny() {
    if (!AityAuth.getToken() || currentUser()?.plan === "team") return;
    try {
      const payment = await AityAuth.saasApi("/billing/team-payment");
      if (payment?.payment_id) showTonPayment(payment);
    } catch {
      /* ignore */
    }
  }

  function toast(msg, isError = false) {
    const el = document.getElementById("toast");
    el.textContent = msg;
    el.className = `toast show${isError ? " error" : ""}`;
    setTimeout(() => el.classList.remove("show"), 3200);
  }

  function showOutput(id, data) {
    const el = document.getElementById(id);
    el.textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2);
    el.classList.remove("hidden");
  }

  async function loadConfig() {
    try {
      const r = await fetch(CONFIG_URL);
      if (!r.ok) return {};
      return r.json();
    } catch {
      return {};
    }
  }

  function applyBackendLinks(config) {
    if (window.AitySetup) {
      AitySetup.applyBackendLinks(config, AitySetup.IDS);
      return;
    }
    const local = (config?.defaultApiLocal || "http://127.0.0.1:8765").replace(/\/$/, "");
    const setHref = (id, href) => {
      const el = document.getElementById(id);
      if (el && href) el.href = href;
    };
    const setText = (id, value) => {
      const el = document.getElementById(id);
      if (el && value) el.textContent = value;
    };
    setHref("linkBackendZip", config?.backendZip);
    setHref("linkBackendRepo", config?.backendRepo);
    setHref("overlayBackendZip", config?.backendZip);
    setHref("overlayBackendRepo", config?.backendRepo);
    setText("overlayDefaultApi", local);
    setText("overlayHealthUrl", `${local}/api/health`);
  }

  function refreshSetupOverlayContext() {
    if (!window.AitySetup) return;
    const pending = readPendingAuth();
    const params = new URLSearchParams(location.search);
    const authIntent = params.get("auth");
    AitySetup.updateSetupContext({
      pendingAuth: pending,
      loggedIn: Boolean(currentUser()) && !pending && !authIntent,
      authIntent,
    });
  }

  function readApiBase(config) {
    if (window.AityAuth) {
      return AityAuth.readApiBase();
    }
    const params = new URLSearchParams(location.search);
    const fromQuery = params.get("api");
    if (fromQuery) {
      const v = fromQuery.replace(/\/$/, "");
      localStorage.setItem(STORAGE_API, v);
      return v;
    }
    const stored = localStorage.getItem(STORAGE_API);
    if (stored) return stored.replace(/\/$/, "");
    if (config?.defaultApi) return String(config.defaultApi).replace(/\/$/, "");
    if (location.hostname === "127.0.0.1" || location.hostname === "localhost") {
      return location.origin.replace(/\/$/, "");
    }
    return "";
  }

def format_uptime(seconds) {
    if (seconds == null || Number.isNaN(Number(seconds))) return "";
    const s = Number(seconds);
    if (s < 60) return `up ${Math.round(s)}s`;
    if (s < 3600) return `up ${Math.floor(s / 60)}m`;
    return `up ${Math.floor(s / 3600)}h`;
  }

  function setMode(next, detail = "") {
    mode = next;
    const pill = document.getElementById("statusPill");
    const labels = { live: "Forge live", static: "Offline demo", offline: "Forge offline", loading: "Connecting…" };
    pill.textContent = `${labels[next] || next}${detail ? " · " + detail : ""}`;
    pill.className = `status-pill ${next === "live" ? "live" : next} clickable`;
    pill.title = next === "live" ? "Click to refresh health" : next === "offline" ? "Click to reconnect" : "";
    const connectBtn = document.getElementById("btnConnect");
    if (connectBtn) connectBtn.textContent = next === "offline" ? "Reconnect" : "Connect";
    const hideOverlay = next === "live" || (next === "static" && !needsBackendBeforeUse());
    document.getElementById("blockedOverlay").classList.toggle("hidden", hideOverlay);
    if (!hideOverlay) refreshSetupOverlayContext();
    if (next === "offline") startReconnectPoll();
    else stopReconnectPoll();
    if (next === "live") startLiveHealthPoll();
    else stopLiveHealthPoll();
  }

  let liveHealthTimer = null;

  async function refreshLiveHealth() {
    if (mode !== "live" || !apiBase) return;
    try {
      const health = await probeLiveApi(apiBase);
      const parts = [];
      if (health.version) parts.push(`v${health.version}`);
      const up = formatUptime(health.uptime_seconds);
      if (up) parts.push(up);
      setMode("live", parts.join(" · ") || apiBase);
      await refreshSaasStatus();
    } catch {
      setMode("offline");
      toast("Lost connection to forge", true);
    }
  }

  function startLiveHealthPoll() {
    if (liveHealthTimer) return;
    liveHealthTimer = setInterval(refreshLiveHealth, 60000);
  }

  function stopLiveHealthPoll() {
    if (liveHealthTimer) {
      clearInterval(liveHealthTimer);
      liveHealthTimer = null;
    }
  }

  let reconnectTimer = null;

  function startReconnectPoll() {
    if (reconnectTimer) return;
    reconnectTimer = setInterval(async () => {
      if (mode !== "offline") return;
      const base = (document.getElementById("apiBaseInput")?.value || "").trim().replace(/\/$/, "");
      if (!base) return;
      try {
        await connectLive(base);
        updateAuthUI();
        await loadProviders();
        await refresh();
        await afterBackendReady();
        toast("Reconnected to forge");
      } catch {
        /* still offline */
      }
    }, 15000);
  }

  function stopReconnectPoll() {
    if (reconnectTimer) {
      clearInterval(reconnectTimer);
      reconnectTimer = null;
    }
  }

  function setSaasStatus(info) {
    const pill = document.getElementById("saasStatusPill");
    if (!pill) return;
    if (!info?.configured) {
      pill.classList.add("hidden");
      return;
    }
    pill.classList.remove("hidden");
    pill.textContent = info.label || "Cloud";
    const tone = info.state === "ok" ? "live" : info.state === "error" || info.state === "issues" ? "warn" : "offline";
    pill.className = `status-pill ${tone}`;
    pill.title = info.error || info.base || "Cloud SaaS API";
  }

  async function refreshSaasStatus() {
    if (!window.AityAuth?.probeSaasHealth) return;
    setSaasStatus(await AityAuth.probeSaasHealth());
  }

  function loadDemoOverrides() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_DEMO) || "{}");
    } catch {
      return {};
    }
  }

  function saveDemoOverrides(overrides) {
    localStorage.setItem(STORAGE_DEMO, JSON.stringify(overrides));
  }

  function recomputeProgress(tasks) {
    const counts = { idea: 0, backlog: 0, in_progress: 0, blocked: 0, review: 0, done: 0, cancelled: 0 };
    for (const t of tasks) counts[t.status] = (counts[t.status] || 0) + 1;
    const total = tasks.length;
    const done = (counts.done || 0) + (counts.cancelled || 0);
    return { total, done, percent: total ? Math.round((1000 * done) / total) / 10 : 0, ...counts };
  }

  function applyDemoOverrides(data) {
    const overrides = loadDemoOverrides();
    const clone = structuredClone(data);
    for (const project of clone.projects) {
      const taskOverrides = overrides[project.slug] || {};
      for (const task of project.tasks) {
        if (taskOverrides[task.id]) task.status = taskOverrides[task.id];
      }
      project.progress = recomputeProgress(project.tasks);
    }
    const totals = { tasks: 0, done: 0 };
    for (const p of clone.projects) {
      totals.tasks += p.progress.total;
      totals.done += p.progress.done;
    }
    clone.summary = {
      projects: clone.projects.length,
      tasks: totals.tasks,
      done: totals.done,
      percent: totals.tasks ? Math.round((1000 * totals.done) / totals.tasks) / 10 : 0,
    };
    return clone;
  }

  async function probeLiveApi(base) {
    if (!base) throw new Error("No API URL");
    const r = await fetch(`${base}/api/health`, { headers: { Accept: "application/json" } });
    if (!r.ok) throw new Error(`Health check failed (${r.status})`);
    return r.json();
  }

  async function connectLive(base) {
    const health = await probeLiveApi(base);
    apiBase = base;
    localStorage.setItem(STORAGE_API, apiBase);
    const parts = [];
    if (health.version) parts.push(`v${health.version}`);
    const up = formatUptime(health.uptime_seconds);
    if (up) parts.push(up);
    setMode("live", parts.join(" · ") || health.forge_data || apiBase);
    await refreshSaasStatus();
    return health;
  }

  async function connectDemo() {
    const r = await fetch(DEMO_DATA_URL);
    if (!r.ok) throw new Error("demo-data.json missing");
    demoData = await r.json();
    setMode("static", "kanban only — connect API for agents");
  }

  async function resolveBackend(preferDemo = false) {
    if (window.AityAuth) await AityAuth.loadConfig();
    const config = await loadConfig();
    applyBackendLinks(config);
    refreshSetupOverlayContext();
    apiBase = readApiBase(config);
    const localDefault = (config?.defaultApiLocal || "http://127.0.0.1:8765").replace(/\/$/, "");
    document.getElementById("apiBaseInput").value = apiBase;
    const overlayInput = document.getElementById("overlayApiInput");
    if (overlayInput) overlayInput.value = apiBase || localDefault;

    const authPending = hasAuthIntent();
    const skipDemo = authPending || needsBackendBeforeUse();

    if (preferDemo && !skipDemo) {
      await connectDemo();
      return;
    }
    if (apiBase) {
      try {
        await connectLive(apiBase);
        await afterBackendReady();
        return;
      } catch (e) {
        toast(`API unreachable: ${e.message}`, true);
      }
    }
    if (location.hostname.endsWith("github.io") || skipDemo) {
      setMode("offline");
      await refreshSaasStatus();
      return;
    }
    try {
      await connectDemo();
    } catch {
      setMode("offline");
    }
  }

  function requireLive() {
    if (mode !== "live") {
      throw new Error("Connect to a live AityUahn API for this action.");
    }
  }

  async function api(path, opts = {}) {
    requireLive();
    const r = await fetch(`${apiBase}${path}`, {
      headers: { "Content-Type": "application/json", ...authHeaders(), ...opts.headers },
      ...opts,
    });
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

  async function fetchDashboard() {
    if (mode === "live") {
      dashboard = await api("/api/dashboard");
    } else if (mode === "static") {
      if (!demoData) {
        const r = await fetch(DEMO_DATA_URL);
        demoData = await r.json();
      }
      dashboard = applyDemoOverrides(demoData);
    } else {
      dashboard = { summary: { projects: 0, tasks: 0, done: 0, percent: 0 }, projects: [] };
    }
    if (!selectedSlug && dashboard.projects.length) {
      selectedSlug = dashboard.projects[0].slug;
    }
    if (selectedSlug && !dashboard.projects.find((p) => p.slug === selectedSlug)) {
      selectedSlug = dashboard.projects[0]?.slug || null;
    }
  }

  async function updateTaskStatus(slug, taskId, status) {
    if (mode === "static") {
      const overrides = loadDemoOverrides();
      overrides[slug] = overrides[slug] || {};
      overrides[slug][taskId] = status;
      saveDemoOverrides(overrides);
      return;
    }
    await api("/api/task/status", {
      method: "PATCH",
      body: JSON.stringify({ slug, task_id: taskId, status }),
    });
  }

  function selectedProject() {
    return dashboard?.projects?.find((p) => p.slug === selectedSlug) || null;
  }

  function exportDashboardSnapshot() {
    if (mode !== "live" || !dashboard) {
      toast("Connect to a live forge to export", true);
      return;
    }
    const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
    const blob = new Blob([JSON.stringify(dashboard, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `aityuahn-dashboard-${stamp}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
    toast("Dashboard exported");
  }

  function renderSummary() {
    const s = dashboard?.summary || { projects: 0, tasks: 0, done: 0, percent: 0 };
    const exportBtn =
      mode === "live"
        ? `<button type="button" id="btnExportDashboard" class="setup-btn" style="align-self:center">Export snapshot</button>`
        : "";
    document.getElementById("summaryRow").innerHTML = `
      <div class="stat-card"><span class="muted">Projects</span><strong>${s.projects}</strong></div>
      <div class="stat-card"><span class="muted">Tasks done</span><strong>${s.done}/${s.tasks}</strong></div>
      <div class="stat-card"><span class="muted">Progress</span><strong>${s.percent}%</strong></div>
      ${exportBtn}
    `;
    document.getElementById("btnExportDashboard")?.addEventListener("click", exportDashboardSnapshot);
  }

  function renderProjectList() {
    const list = document.getElementById("projectList");
    const hint = document.getElementById("sidebarHint");
    const projects = dashboard?.projects || [];
    hint.classList.toggle("hidden", projects.length > 0);
    list.innerHTML = projects
      .map(
        (p) => `
      <li>
        <button type="button" class="${p.slug === selectedSlug ? "active" : ""}" data-slug="${p.slug}">
          ${p.title}
          <span class="slug">${p.slug} · ${p.progress.percent}%</span>
          <div class="progress-mini"><span style="width:${p.progress.percent}%"></span></div>
        </button>
      </li>`
      )
      .join("");
    list.querySelectorAll("[data-slug]").forEach((btn) => {
      btn.onclick = async () => {
        selectedSlug = btn.dataset.slug;
        await refresh();
      };
    });
  }

  function renderKanban() {
    const board = document.getElementById("kanbanBoard");
    const project = selectedProject();
    if (!project) {
      board.innerHTML = '<p class="muted">Select or create a project to view the kanban board.</p>';
      return;
    }

    board.innerHTML = KANBAN.map((col) => {
      const cards = project.tasks
        .filter((t) => col.statuses.includes(t.status))
        .map((t) => {
          const moves = ALL_STATUSES.filter((s) => s !== t.status)
            .map(
              (s) =>
                `<button type="button" data-move="${s}" data-id="${t.id}" data-slug="${project.slug}">${s.replace("_", " ")}</button>`
            )
            .join("");
          return `
            <article class="kanban-card">
              <div class="title">${t.title}</div>
              <div class="meta"><code>${t.id}</code> · P${t.priority}${t.test_command ? " · test" : ""}</div>
              <div class="move-row">${moves}</div>
            </article>`;
        })
        .join("");
      return `
        <div class="kanban-col" data-col="${col.key}">
          <h3>${col.label} (${project.tasks.filter((t) => col.statuses.includes(t.status)).length})</h3>
          <div class="kanban-cards">${cards || '<p class="muted" style="padding:0.5rem;font-size:0.8rem">Empty</p>'}</div>
        </div>`;
    }).join("");

    board.querySelectorAll("[data-move]").forEach((btn) => {
      btn.onclick = async () => {
        try {
          await updateTaskStatus(btn.dataset.slug, btn.dataset.id, btn.dataset.move);
          await refresh();
          toast("Task updated");
        } catch (e) {
          toast(String(e), true);
        }
      };
    });
  }

  function renderTaskTable() {
    const wrap = document.getElementById("taskTableWrap");
    const project = selectedProject();
    if (!project) {
      wrap.innerHTML = '<p class="muted">No project selected.</p>';
      return;
    }

    const rows = project.tasks
      .map(
        (t) => `
      <tr>
        <td><code>${t.id}</code></td>
        <td><strong>${t.title}</strong><br><span class="muted">${t.description || ""}</span></td>
        <td>${t.status}</td>
        <td>${t.priority}</td>
        <td>${(t.labels || []).join(", ")}</td>
        <td>
          <select data-status-id="${t.id}" data-status-slug="${project.slug}">
            ${ALL_STATUSES.map((s) => `<option value="${s}" ${s === t.status ? "selected" : ""}>${s}</option>`).join("")}
          </select>
        </td>
      </tr>`
      )
      .join("");

    wrap.innerHTML = `
      <table class="task-table">
        <thead><tr><th>ID</th><th>Task</th><th>Status</th><th>Pri</th><th>Labels</th><th>Move</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`;

    wrap.querySelectorAll("[data-status-id]").forEach((sel) => {
      sel.onchange = async () => {
        try {
          await updateTaskStatus(sel.dataset.statusSlug, sel.dataset.statusId, sel.value);
          await refresh();
          toast("Status updated");
        } catch (e) {
          toast(String(e), true);
        }
      };
    });
  }

  async function loadProviders() {
    if (mode === "live") {
      providers = await api("/api/providers");
    } else {
      providers = [
        { id: "claude", kind: "claude", enabled: true, default: true },
        { id: "cursor", kind: "cursor", enabled: true, default: false },
      ];
    }
    const sel = document.getElementById("agentProvider");
    sel.innerHTML = providers
      .filter((p) => p.enabled !== false)
      .map((p) => `<option value="${p.id}">${p.id} (${p.kind}${p.default ? ", default" : ""})</option>`)
      .join("");
  }

  function setView(view) {
    currentView = view;
    document.querySelectorAll(".view-tabs button").forEach((b) => {
      b.classList.toggle("active", b.dataset.view === view);
    });
    document.querySelectorAll(".view").forEach((v) => v.classList.add("hidden"));
    const id = view === "team" ? "viewTeam" : `view${view.charAt(0).toUpperCase()}${view.slice(1)}`;
    document.getElementById(id)?.classList.remove("hidden");
    if (view === "team") renderTeamView();
  }

  async function loadTeamProjects() {
    if (!currentUser() || mode !== "live") {
      teamProjects = [];
      return;
    }
    try {
      teamProjects = await AityAuth.saasApi("/projects");
      renderSaasProjectList();
    } catch {
      teamProjects = [];
    }
  }

  function renderSaasProjectList() {
    const list = document.getElementById("saasProjectList");
    if (!list) return;
    list.innerHTML = teamProjects
      .map(
        (p) => `
      <li><button type="button" class="${activeTeamProject?.id === p.id ? "active" : ""}" data-team-id="${p.id}" data-forge-slug="${p.forge_slug}">
        ${p.name}<span class="slug">${p.slug} · ${p.role}</span>
      </button></li>`
      )
      .join("");
    list.querySelectorAll("[data-team-id]").forEach((btn) => {
      btn.onclick = () => {
        activeTeamProject = teamProjects.find((p) => p.id === btn.dataset.teamId) || null;
        selectedSlug = btn.dataset.forgeSlug;
        renderSaasProjectList();
        refresh();
        renderTeamView();
      };
    });
  }

  async function renderTeamView() {
    const memberList = document.getElementById("memberList");
    if (!memberList) return;
    if (!activeTeamProject) {
      memberList.textContent = "Select a team project from the sidebar.";
      return;
    }
    memberList.textContent = JSON.stringify(activeTeamProject.members || [], null, 2);
    if (mode === "live" && AityAuth.getToken()) {
      try {
        const cfg = await AityAuth.saasApi(`/projects/${activeTeamProject.id}/api-config`);
        document.getElementById("teamDefaultProvider").value = cfg.default_provider || "claude";
        showOutput("outTeamApi", cfg);
      } catch (e) {
        showOutput("outTeamApi", String(e));
      }
    }
  }

  async function refresh() {
    await fetchDashboard();
    await loadTeamProjects();
    renderSummary();
    renderProjectList();
    renderKanban();
    renderTaskTable();
  }

  async function init() {
    document.querySelectorAll(".view-tabs button").forEach((btn) => {
      btn.onclick = () => setView(btn.dataset.view);
    });

    const doConnect = async (sourceInput) => {
      const el = sourceInput || document.getElementById("apiBaseInput");
      const value = el.value.trim().replace(/\/$/, "");
      if (!value) return toast("Enter API URL", true);
      document.getElementById("apiBaseInput").value = value;
      const overlayInput = document.getElementById("overlayApiInput");
      if (overlayInput) overlayInput.value = value;
      try {
        AityAuth.setApiBase(value);
        await connectLive(value);
        updateAuthUI();
        await loadProviders();
        await refresh();
        await afterBackendReady();
        toast("Connected to API");
      } catch (e) {
        toast(String(e), true);
      }
    };

    document.getElementById("btnConnect").onclick = () => doConnect();
    document.getElementById("btnCopyForgeUrl")?.addEventListener("click", async () => {
      const value = (document.getElementById("apiBaseInput")?.value || "http://127.0.0.1:8765").trim();
      try {
        await navigator.clipboard.writeText(value);
        toast("Forge URL copied");
      } catch {
        toast("Could not copy URL", true);
      }
    });
    document.getElementById("statusPill")?.addEventListener("click", async () => {
      if (mode === "live") {
        await refreshLiveHealth();
        toast("Forge health refreshed");
        return;
      }
      if (mode === "offline") {
        await doConnect();
      }
    });
    document.getElementById("btnOverlayConnect").onclick = () =>
      doConnect(document.getElementById("overlayApiInput") || document.getElementById("apiBaseInput"));

    const goDemo = async () => {
      await connectDemo();
      await loadProviders();
      await refresh();
      toast("Offline demo loaded");
    };
    document.getElementById("btnDemoMode").onclick = goDemo;
    document.getElementById("btnOverlayDemo").onclick = goDemo;
    document.getElementById("btnOverlaySignIn")?.addEventListener("click", () => openAuthDialog("login"));
    document.getElementById("btnSignIn")?.addEventListener("click", () => openAuthDialog("login"));

    document.getElementById("authToggle")?.addEventListener("click", () => {
      openAuthDialog(authMode === "login" ? "register" : "login");
    });
    document.getElementById("authForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      const errEl = document.getElementById("authError");
      errEl.style.display = "none";
      const fields = {
        email: document.getElementById("authEmail").value.trim(),
        password: document.getElementById("authPassword").value,
        name: document.getElementById("authName").value.trim(),
        plan: document.getElementById("authPlan").value,
      };
      const nextMode = authMode || "login";
      try {
        await submitAuth(nextMode, fields);
      } catch (ex) {
        errEl.textContent = String(ex.message || ex);
        errEl.style.display = "block";
      }
    });

    document.getElementById("btnAddTask").onclick = async () => {
      const title = document.getElementById("taskTitle").value.trim();
      if (!title || !selectedSlug) return toast("Enter title and select a project", true);
      try {
        requireLive();
        await api("/api/task", {
          method: "POST",
          body: JSON.stringify({ slug: selectedSlug, title, description: document.getElementById("taskDesc").value.trim() }),
        });
        document.getElementById("taskTitle").value = "";
        document.getElementById("taskDesc").value = "";
        await refresh();
        toast("Task added");
      } catch (e) {
        toast(String(e), true);
      }
    };

    document.getElementById("btnForge").onclick = async () => {
      const prompt = document.getElementById("forgePrompt").value.trim();
      if (!prompt) return toast("Enter a forge prompt", true);
      try {
        requireLive();
        showOutput("outForge", "Forging… (may take a minute)");
        const result = await api("/api/forge", {
          method: "POST",
          body: JSON.stringify({
            prompt,
            slug: document.getElementById("forgeSlug").value.trim() || null,
            scaffold: document.getElementById("forgeScaffold").checked,
            generate_backlog: document.getElementById("forgeBacklog").checked,
          }),
        });
        showOutput("outForge", result);
        selectedSlug = result.idea?.slug || selectedSlug;
        await refresh();
        toast("Forge complete");
      } catch (e) {
        showOutput("outForge", String(e));
        toast(String(e), true);
      }
    };

    document.getElementById("btnIdea")?.addEventListener("click", async () => {
      const prompt = document.getElementById("ideaPrompt").value.trim();
      if (!prompt) return toast("Enter an idea prompt", true);
      try {
        requireLive();
        showOutput("outIdea", "Generating…");
        const idea = await api("/api/idea", { method: "POST", body: JSON.stringify({ prompt }) });
        showOutput("outIdea", idea);
        selectedSlug = idea.slug;
        await refresh();
        toast("Idea created");
      } catch (e) {
        showOutput("outIdea", String(e));
        toast(String(e), true);
      }
    };

    document.getElementById("btnBacklogRefresh").onclick = async () => {
      if (!selectedSlug) return toast("Select a project", true);
      try {
        if (mode === "live") {
          showOutput("outBacklog", await api("/api/backlog/" + encodeURIComponent(selectedSlug)));
        } else {
          showOutput("outBacklog", selectedProject());
        }
      } catch (e) {
        showOutput("outBacklog", String(e));
      }
    };

    document.getElementById("btnBacklogGen").onclick = async () => {
      if (!selectedSlug) return toast("Select a project", true);
      try {
        requireLive();
        showOutput("outBacklog", "Generating backlog…");
        showOutput("outBacklog", await api("/api/backlog/generate", {
          method: "POST",
          body: JSON.stringify({ slug: selectedSlug }),
        }));
        await refresh();
        toast("Backlog generated");
      } catch (e) {
        showOutput("outBacklog", String(e));
        toast(String(e), true);
      }
    };

    document.getElementById("btnRunTests").onclick = async () => {
      if (!selectedSlug) return toast("Select a project", true);
      try {
        requireLive();
        showOutput("outBacklog", "Running tests…");
        showOutput("outBacklog", await api("/api/test/" + encodeURIComponent(selectedSlug), { method: "POST", body: "{}" }));
        await refresh();
        toast("Tests finished");
      } catch (e) {
        showOutput("outBacklog", String(e));
        toast(String(e), true);
      }
    };

    document.getElementById("btnAgentSend").onclick = async () => {
      const text = document.getElementById("agentPrompt").value.trim();
      if (!text) return toast("Enter a prompt", true);
      try {
        requireLive();
        showOutput("outAgent", "Waiting for agent…");
        const result = await api("/api/prompt", {
          method: "POST",
          body: JSON.stringify({
            text,
            provider_id: document.getElementById("agentProvider").value,
            system: document.getElementById("agentSystem").value.trim() || null,
          }),
        });
        showOutput("outAgent", result.text || result);
        toast("Agent responded");
      } catch (e) {
        showOutput("outAgent", String(e));
        toast(String(e), true);
      }
    };

    document.getElementById("btnSignOut")?.addEventListener("click", () => {
      AityAuth.clearSession();
      location.href = "landing.html";
    });

    document.getElementById("btnNewProject")?.addEventListener("click", () => {
      document.getElementById("newProjectDialog")?.showModal();
    });
    document.getElementById("btnCancelProject")?.addEventListener("click", () => {
      document.getElementById("newProjectDialog")?.close();
    });
    document.getElementById("newProjectForm")?.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        requireLive();
        const proj = await AityAuth.saasApi("/projects", {
          method: "POST",
          body: JSON.stringify({
            name: document.getElementById("newProjName").value.trim(),
            slug: document.getElementById("newProjSlug").value.trim(),
            create_demo: document.getElementById("newProjDemo").checked,
          }),
        });
        document.getElementById("newProjectDialog")?.close();
        activeTeamProject = proj;
        selectedSlug = proj.forge_slug;
        await refresh();
        toast("Project created");
      } catch (ex) {
        toast(String(ex.message || ex), true);
      }
    });

    document.getElementById("btnInvite")?.addEventListener("click", async () => {
      if (!activeTeamProject) return toast("Select a team project", true);
      const email = document.getElementById("inviteEmail").value.trim();
      if (!email) return toast("Enter email", true);
      try {
        const res = await AityAuth.saasApi(`/projects/${activeTeamProject.id}/members`, {
          method: "POST",
          body: JSON.stringify({ email, role: "member" }),
        });
        activeTeamProject.members = res.roster;
        renderTeamView();
        toast("Member invited");
      } catch (ex) {
        toast(String(ex.message || ex), true);
      }
    });

    document.getElementById("btnSaveApi")?.addEventListener("click", async () => {
      if (!activeTeamProject) return toast("Select a team project", true);
      try {
        let providersJson = JSON.parse(document.getElementById("teamApiJson").value || "[]");
        await AityAuth.saasApi(`/projects/${activeTeamProject.id}/api-config`, {
          method: "PUT",
          body: JSON.stringify({
            default_provider: document.getElementById("teamDefaultProvider").value.trim(),
            providers: providersJson,
          }),
        });
        toast("Shared API saved for team");
      } catch (ex) {
        toast(String(ex.message || ex), true);
      }
    });

    document.getElementById("btnUpgradeTeam")?.addEventListener("click", startTeamPayment);
    document.getElementById("btnCheckPayment")?.addEventListener("click", () => checkTonPayment(true));
    document.getElementById("btnCopyWallet")?.addEventListener("click", async () => {
      const v = document.getElementById("tonWallet")?.value;
      if (v) {
        await navigator.clipboard.writeText(v);
        toast("Wallet copied");
      }
    });
    document.getElementById("btnCopyComment")?.addEventListener("click", async () => {
      const v = document.getElementById("tonComment")?.value;
      if (v) {
        await navigator.clipboard.writeText(v);
        toast("Payment ID copied");
      }
    });

    updateAuthUI();
    await AitySetup.initSetupUi(AitySetup.IDS, (msg, err) => toast(msg, err));
    const demoParam = new URLSearchParams(location.search).get("demo") === "1";
    await resolveBackend(demoParam && !hasAuthIntent() && !currentUser());
    await refreshSaasStatus();
    if (mode === "offline" && hasAuthIntent()) {
      refreshSetupOverlayContext();
      document.getElementById("blockedOverlay")?.classList.remove("hidden");
    }
    await loadProviders();
    const billing = await loadBillingSettings();
    if (billing?.team_price_ton) setUpgradeButtonLabel(billing.team_price_ton);
    await refresh();
    await resumeTonPaymentIfAny();
    if (
      new URLSearchParams(location.search).get("upgrade") === "ton" &&
      currentUser()?.plan !== "team" &&
      mode === "live"
    ) {
      setView("team");
      startTeamPayment();
    }
    setView("kanban");

    document.addEventListener("keydown", async (ev) => {
      if (ev.target && ["INPUT", "TEXTAREA", "SELECT"].includes(ev.target.tagName)) return;
      if (ev.key === "r" || ev.key === "R") {
        if (mode === "live") {
          await refresh();
          await refreshLiveHealth();
          toast("Dashboard refreshed");
        }
      }
    });
  }

  init();
})();
