(() => {
  const STORAGE_API = "aityuahn-api-base";
  const STORAGE_DEMO = "aityuahn-demo-overrides";
  const DEMO_DATA_URL = new URL("demo-data.json", document.baseURI).href;

  let mode = "loading";
  let apiBase = "";
  let demoData = null;

  function assetUrl(name) {
    return new URL(name, document.baseURI).href;
  }

  function readApiBase() {
    const params = new URLSearchParams(location.search);
    const fromQuery = params.get("api");
    if (fromQuery) {
      localStorage.setItem(STORAGE_API, fromQuery.replace(/\/$/, ""));
      return fromQuery.replace(/\/$/, "");
    }
    return (localStorage.getItem(STORAGE_API) || location.origin).replace(/\/$/, "");
  }

  function setMode(next, detail) {
    mode = next;
    const el = document.getElementById("modeBanner");
    if (!el) return;
    const labels = {
      live: "Live API",
      static: "GitHub Pages demo",
      loading: "Connecting…",
    };
    el.textContent = `${labels[next] || next}${detail ? " — " + detail : ""}`;
    el.className = `mode-banner mode-${next}`;
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
    const counts = {
      idea: 0,
      backlog: 0,
      in_progress: 0,
      blocked: 0,
      review: 0,
      done: 0,
      cancelled: 0,
    };
    for (const t of tasks) {
      counts[t.status] = (counts[t.status] || 0) + 1;
    }
    const total = tasks.length;
    const done = counts.done || 0;
    return {
      total,
      done,
      percent: total ? Math.round((1000 * done) / total) / 10 : 0,
      ...counts,
    };
  }

  function applyDemoOverrides(data) {
    const overrides = loadDemoOverrides();
    const clone = structuredClone(data);
    for (const project of clone.projects) {
      const taskOverrides = overrides[project.slug] || {};
      for (const task of project.tasks) {
        if (taskOverrides[task.id]) {
          task.status = taskOverrides[task.id];
        }
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
    const r = await fetch(`${base}/api/health`, { headers: { Accept: "application/json" } });
    if (!r.ok) throw new Error(`Health check failed (${r.status})`);
    return r.json();
  }

  async function resolveBackend() {
    apiBase = readApiBase();
    document.getElementById("apiBaseInput").value = apiBase;
    document.getElementById("base").textContent = apiBase;

    try {
      const health = await probeLiveApi(apiBase);
      setMode("live", health.forge_data || apiBase);
      document.getElementById("paths").textContent = health.forge_data || "—";
      document.getElementById("apiPanels").hidden = false;
      return "live";
    } catch {
      const r = await fetch(DEMO_DATA_URL);
      if (!r.ok) throw new Error("No API and demo-data.json missing");
      demoData = await r.json();
      setMode("static", "task changes saved in this browser");
      document.getElementById("paths").textContent = demoData.forge_data;
      document.getElementById("apiPanels").hidden = true;
      return "static";
    }
  }

  async function api(path, opts = {}) {
    const r = await fetch(`${apiBase}${path}`, {
      headers: { "Content-Type": "application/json", ...opts.headers },
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

  function show(id, data, ok = true) {
    const el = document.getElementById(id);
    el.textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2);
    el.className = ok ? "ok" : "err";
  }

  function statusChip(label, count, cls) {
    if (!count) return "";
    return `<span class="chip ${cls || ""}">${label}: ${count}</span>`;
  }

  function renderDashboard(data) {
    const s = data.summary;
    document.getElementById("summaryBar").innerHTML = `
      <span><strong>${s.projects}</strong> projects</span>
      <span><strong>${s.done}</strong> / ${s.tasks} tasks done</span>
      <span><strong>${s.percent}%</strong> overall</span>
    `;

    const container = document.getElementById("projectCards");
    if (!data.projects.length) {
      container.innerHTML =
        '<p class="muted">No projects yet. Run <code>aityuahn serve</code> locally or use the static demo.</p>';
      return;
    }

    container.innerHTML = data.projects
      .map((p) => {
        const prog = p.progress;
        const chips = [
          statusChip("done", prog.done, "done"),
          statusChip("in progress", prog.in_progress, "in_progress"),
          statusChip("backlog", prog.backlog),
          statusChip("blocked", prog.blocked, "blocked"),
        ]
          .filter(Boolean)
          .join("");

        const rows = p.tasks
          .map(
            (t) => `
          <tr>
            <td><code>${t.id}</code></td>
            <td>${t.title}</td>
            <td>${t.status}</td>
            <td>${t.priority}</td>
            <td>
              <div class="task-actions">
                ${
                  t.status !== "in_progress"
                    ? `<button type="button" data-slug="${p.slug}" data-id="${t.id}" data-status="in_progress">Start</button>`
                    : ""
                }
                ${
                  t.status !== "done"
                    ? `<button type="button" data-slug="${p.slug}" data-id="${t.id}" data-status="done">Done</button>`
                    : ""
                }
              </div>
            </td>
          </tr>
        `
          )
          .join("");

        const lastTest = p.last_test
          ? `<p class="muted">Last test: ${p.last_test.status} (exit ${p.last_test.exit_code ?? "—"})</p>`
          : "";

        return `
          <article class="project-card">
            <h3>${p.title}</h3>
            <div class="slug">${p.slug}${p.registered ? " · registered" : ""}</div>
            <p class="muted">${p.summary || ""}</p>
            <div class="progress-wrap"><div class="progress-fill" style="width:${prog.percent}%"></div></div>
            <div class="row"><span>${prog.percent}% complete (${prog.done}/${prog.total})</span></div>
            <div class="status-chips">${chips}</div>
            ${lastTest}
            <table class="task-table">
              <thead><tr><th>ID</th><th>Title</th><th>Status</th><th>Pri</th><th></th></tr></thead>
              <tbody>${rows}</tbody>
            </table>
          </article>
        `;
      })
      .join("");

    container.querySelectorAll("[data-id]").forEach((btn) => {
      btn.onclick = async () => {
        try {
          if (mode === "static") {
            const overrides = loadDemoOverrides();
            const slug = btn.dataset.slug;
            overrides[slug] = overrides[slug] || {};
            overrides[slug][btn.dataset.id] = btn.dataset.status;
            saveDemoOverrides(overrides);
          } else {
            await api("/api/task/status", {
              method: "PATCH",
              body: JSON.stringify({
                slug: btn.dataset.slug,
                task_id: btn.dataset.id,
                status: btn.dataset.status,
              }),
            });
          }
          await loadDashboard();
        } catch (e) {
          alert(String(e));
        }
      };
    });
  }

  async function loadDashboard() {
    try {
      let data;
      if (mode === "static") {
        if (!demoData) {
          const r = await fetch(DEMO_DATA_URL);
          demoData = await r.json();
        }
        data = applyDemoOverrides(demoData);
      } else {
        data = await api("/api/dashboard");
        document.getElementById("paths").textContent = data.forge_data;
      }
      renderDashboard(data);
    } catch (e) {
      document.getElementById("projectCards").innerHTML = `<p class="err">${e}</p>`;
    }
  }

  async function init() {
    document.getElementById("btnDashboard").onclick = loadDashboard;

    document.getElementById("btnConnect").onclick = async () => {
      const value = document.getElementById("apiBaseInput").value.trim().replace(/\/$/, "");
      if (value) localStorage.setItem(STORAGE_API, value);
      else localStorage.removeItem(STORAGE_API);
      await resolveBackend();
      await loadDashboard();
    };

    document.getElementById("btnResetDemo").onclick = () => {
      localStorage.removeItem(STORAGE_DEMO);
      loadDashboard();
    };

    document.getElementById("btnHealth").onclick = async () => {
      if (mode === "static") {
        show("outHealth", { ok: true, mode: "static", demo: assetUrl("demo-data.json") });
        return;
      }
      try {
        const d = await api("/api/health");
        document.getElementById("paths").textContent = d.forge_data;
        show("outHealth", d);
      } catch (e) {
        show("outHealth", String(e), false);
      }
    };

    document.getElementById("btnRegistry").onclick = async () => {
      if (mode === "static") {
        show("outRegistry", applyDemoOverrides(demoData));
        return;
      }
      try {
        show("outRegistry", await api("/api/registry"));
      } catch (e) {
        show("outRegistry", String(e), false);
      }
    };

    document.getElementById("btnIdea").onclick = async () => {
      const prompt = document.getElementById("ideaPrompt").value.trim();
      if (!prompt) return alert("Enter a prompt");
      const slug = document.getElementById("ideaSlug").value.trim() || null;
      try {
        show("outIdea", await api("/api/idea", { method: "POST", body: JSON.stringify({ prompt, slug }) }));
        await loadDashboard();
      } catch (e) {
        show("outIdea", String(e), false);
      }
    };

    document.getElementById("btnForge").onclick = async () => {
      const prompt = document.getElementById("forgePrompt").value.trim();
      if (!prompt) return alert("Enter a prompt");
      try {
        show("outForge", "Working… (may take a minute)");
        show("outForge", await api("/api/forge", {
          method: "POST",
          body: JSON.stringify({
            prompt,
            scaffold: document.getElementById("forgeScaffold").checked,
            generate_backlog: document.getElementById("forgeBacklog").checked,
          }),
        }));
        await loadDashboard();
      } catch (e) {
        show("outForge", String(e), false);
      }
    };

    document.getElementById("btnBacklog").onclick = async () => {
      const slug = document.getElementById("backlogSlug").value.trim();
      if (!slug) return alert("Enter slug");
      try {
        show("outBacklog", await api("/api/backlog/" + encodeURIComponent(slug)));
      } catch (e) {
        show("outBacklog", String(e), false);
      }
    };

    document.getElementById("btnBacklogGen").onclick = async () => {
      const slug = document.getElementById("backlogSlug").value.trim();
      if (!slug) return alert("Enter slug");
      try {
        show("outBacklog", "Generating…");
        show("outBacklog", await api("/api/backlog/generate", {
          method: "POST",
          body: JSON.stringify({ slug }),
        }));
        await loadDashboard();
      } catch (e) {
        show("outBacklog", String(e), false);
      }
    };

    await resolveBackend();
    await loadDashboard();
    document.getElementById("btnHealth").click();
  }

  init();
})();
