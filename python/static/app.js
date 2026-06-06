(() => {
  const STORAGE_API = "aityuahn-api-base";
  const STORAGE_DEMO = "aityuahn-demo-overrides";
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
    const newProj = document.getElementById("btnNewProject");
    const teamList = document.getElementById("teamProjectList");
    const upgrade = document.getElementById("btnUpgradeTeam");
    if (!badge) return;
    if (user) {
      badge.textContent = `${user.name} · ${user.plan}`;
      badge.classList.remove("hidden");
      signOut?.classList.remove("hidden");
      newProj?.classList.remove("hidden");
      teamList?.classList.remove("hidden");
      upgrade?.classList.toggle("hidden", user.plan === "team");
    } else {
      badge.classList.add("hidden");
      signOut?.classList.add("hidden");
      newProj?.classList.add("hidden");
      teamList?.classList.add("hidden");
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

  function setMode(next, detail = "") {
    mode = next;
    const pill = document.getElementById("statusPill");
    const labels = { live: "Live API", static: "Offline demo", offline: "Not connected", loading: "Connecting…" };
    pill.textContent = `${labels[next] || next}${detail ? " · " + detail : ""}`;
    pill.className = `status-pill ${next}`;
    document.getElementById("blockedOverlay").classList.toggle("hidden", next === "live" || next === "static");
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
    setMode("live", health.forge_data || apiBase);
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
    apiBase = readApiBase(config);
    document.getElementById("apiBaseInput").value = apiBase;

    if (preferDemo || new URLSearchParams(location.search).get("demo") === "1") {
      await connectDemo();
      return;
    }
    if (apiBase) {
      try {
        await connectLive(apiBase);
        return;
      } catch (e) {
        toast(`API unreachable: ${e.message}`, true);
      }
    }
    if (location.hostname.endsWith("github.io")) {
      setMode("offline");
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

  function renderSummary() {
    const s = dashboard?.summary || { projects: 0, tasks: 0, done: 0, percent: 0 };
    document.getElementById("summaryRow").innerHTML = `
      <div class="stat-card"><span class="muted">Projects</span><strong>${s.projects}</strong></div>
      <div class="stat-card"><span class="muted">Tasks done</span><strong>${s.done}/${s.tasks}</strong></div>
      <div class="stat-card"><span class="muted">Progress</span><strong>${s.percent}%</strong></div>
    `;
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

    const doConnect = async () => {
      const value = document.getElementById("apiBaseInput").value.trim().replace(/\/$/, "");
      if (!value) return toast("Enter API URL", true);
      try {
        await connectLive(value);
        await loadProviders();
        await refresh();
        toast("Connected to API");
      } catch (e) {
        toast(String(e), true);
      }
    };

    document.getElementById("btnConnect").onclick = doConnect;
    document.getElementById("btnOverlayConnect").onclick = doConnect;

    const goDemo = async () => {
      await connectDemo();
      await loadProviders();
      await refresh();
      toast("Offline demo loaded");
    };
    document.getElementById("btnDemoMode").onclick = goDemo;
    document.getElementById("btnOverlayDemo").onclick = goDemo;

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

    document.getElementById("btnUpgradeTeam")?.addEventListener("click", async () => {
      try {
        const res = await AityAuth.saasApi("/billing/upgrade-team", { method: "POST", body: "{}" });
        AityAuth.setSession(AityAuth.getToken(), { ...currentUser(), plan: res.plan });
        updateAuthUI();
        toast(res.message || "Upgraded");
      } catch (ex) {
        toast(String(ex.message || ex), true);
      }
    });

    updateAuthUI();
    await resolveBackend(new URLSearchParams(location.search).get("demo") === "1");
    await loadProviders();
    await refresh();
    setView("kanban");
  }

  init();
})();
