(() => {
  const PENDING_AUTH_KEY = "aityuahn-pending-auth";
  const dialog = document.getElementById("authDialog");
  const form = document.getElementById("authForm");
  const title = document.getElementById("authTitle");
  const planWrap = document.getElementById("authPlanWrap");
  const errEl = document.getElementById("authError");
  const setupOverlay = document.getElementById("lpSetupOverlay");
  const setupError = document.getElementById("lpSetupError");
  const LP_IDS = {
    zip: "lpSetupBackendZip",
    repo: "lpSetupBackendRepo",
    exe: "lpSetupBackendExe",
    release: "lpSetupBackendRelease",
    defaultApi: "lpSetupDefaultApi",
    healthUrl: "lpSetupHealthUrl",
    apiInput: "lpSetupApiInput",
    title: "lpSetupTitle",
    lead: "lpSetupLead",
    note: "lpSetupNote",
    cmdPs1: "lpInstallCmdPs1",
    cmdSh: "lpInstallCmdSh",
  };
  let mode = "login";
  let pendingAfterConnect = null;
  let setupConfig = null;

  async function initSetup() {
    setupConfig = await AitySetup.initSetupUi(LP_IDS, (msg) => {
      const note = document.getElementById("lpSetupNote");
      if (note) {
        const prev = note.textContent;
        note.textContent = msg;
        setTimeout(() => {
          if (note.textContent === msg) note.textContent = prev;
        }, 2500);
      }
    });
    const input = document.getElementById("lpSetupApiInput");
    const stored = AityAuth.readApiBase();
    if (input) input.value = stored || AitySetup.localDefault(setupConfig);
  }

  function needsBackendSetup() {
    return !AityAuth.readApiBase() || location.hostname.endsWith("github.io");
  }

  function showSetupOverlay(options = {}) {
    AitySetup.updateSetupContext(options, {
      ...LP_IDS,
      authBtn: "lpSetupConnect",
    });
    setupError?.classList.add("hidden");
    setupOverlay?.classList.remove("hidden");
    document.body.style.overflow = "hidden";
  }

  function hideSetupOverlay() {
    setupOverlay?.classList.add("hidden");
    document.body.style.overflow = "";
  }

  async function initBanner() {
    await AityAuth.loadConfig();
    if (location.hostname.endsWith("github.io")) {
      document.getElementById("apiBanner")?.classList.remove("hidden");
      document.getElementById("authBackendHint")?.classList.remove("hidden");
    }
  }

  function openAuth(nextMode = "login") {
    mode = nextMode;
    title.textContent = mode === "login" ? "Sign in" : "Create account";
    document.getElementById("authToggle").textContent = mode === "login" ? "Create account" : "Sign in instead";
    planWrap.classList.toggle("hidden", mode === "login");
    errEl.classList.add("hidden");
    if (needsBackendSetup()) {
      document.getElementById("authBackendHint")?.classList.remove("hidden");
    }
    dialog.showModal();
  }

  function authPayload() {
    return {
      mode,
      email: document.getElementById("authEmail").value.trim(),
      password: document.getElementById("authPassword").value,
      name: document.getElementById("authName").value.trim(),
      plan: document.getElementById("authPlan").value,
    };
  }

  async function completeAuthOnLanding(payload) {
    const path = payload.mode === "login" ? "/auth/login" : "/auth/register";
    const body =
      payload.mode === "login"
        ? { email: payload.email, password: payload.password }
        : { email: payload.email, password: payload.password, name: payload.name, plan: payload.plan };
    const data = await AityAuth.saasApi(path, { method: "POST", body: JSON.stringify(body) });
    AityAuth.setSession(data.access_token, data.user);
    hideSetupOverlay();
    dialog.close();
    const params = new URLSearchParams();
    if (data.requires_ton_payment || (payload.mode === "register" && payload.plan === "team")) {
      params.set("upgrade", "ton");
    }
    location.href = params.toString() ? `controller.html?${params}` : "controller.html";
  }

  async function openAuthAfterConnect(payload) {
    hideSetupOverlay();
    if (payload) {
      try {
        await completeAuthOnLanding(payload);
        return;
      } catch (ex) {
        fillAuthForm(payload);
        errEl.textContent = String(ex.message || ex);
        errEl.classList.remove("hidden");
      }
    }
    dialog.showModal();
  }

  function fillAuthForm(payload) {
    if (!payload) return;
    if (payload.email) document.getElementById("authEmail").value = payload.email;
    if (payload.name) document.getElementById("authName").value = payload.name;
    if (payload.plan) document.getElementById("authPlan").value = payload.plan;
    mode = payload.mode || mode;
    title.textContent = mode === "login" ? "Sign in" : "Create account";
    planWrap.classList.toggle("hidden", mode === "login");
  }

  function redirectToController(payload) {
    sessionStorage.setItem(PENDING_AUTH_KEY, JSON.stringify(payload));
    const params = new URLSearchParams({ auth: payload.mode });
    if (payload.mode === "register" && payload.plan === "team") params.set("upgrade", "ton");
    location.href = `controller.html?${params}`;
  }

  async function loadPricing() {
    const wrap = document.getElementById("pricingCards");
    try {
      await AityAuth.loadConfig();
      const base = AityAuth.readApiBase();
      if (!base) throw new Error("offline");
      await AityAuth.probeApi(base);
      const r = await fetch(`${base}/api/saas/pricing`);
      const plans = r.ok ? await r.json() : null;
      if (!plans) throw new Error("offline");
      wrap.innerHTML = plans
        .map(
          (p) => `
        <article class="lp-plan ${p.id === "team" ? "featured" : ""}">
          <h3>${p.name}</h3>
          <div class="lp-price">${p.price_label}</div>
          <ul>${p.features.map((f) => `<li>${f}</li>`).join("")}</ul>
          <button type="button" class="lp-btn ${p.id === "team" ? "primary" : ""}" data-plan="${p.id}">
            ${p.id === "team" ? "Get Team access" : "Start free"}
          </button>
        </article>`
        )
        .join("");
      wrap.querySelectorAll("[data-plan]").forEach((btn) => {
        btn.onclick = () => {
          if (btn.dataset.plan === "team") {
            document.getElementById("authPlan").value = "team";
          }
          openAuth("register");
        };
      });
    } catch {
      wrap.innerHTML = `
        <article class="lp-plan"><h3>Personal</h3><div class="lp-price">Free</div><ul><li>1 project</li><li>Bring your own API keys</li></ul><button type="button" class="lp-btn" id="planPersonal">Start free</button></article>
        <article class="lp-plan featured"><h3>Team</h3><div class="lp-price">10 TON</div><ul><li>Shared codebase &amp; API</li><li>Invite members</li><li>Pay with TON wallet</li></ul><button type="button" class="lp-btn primary" id="planTeam">Get Team access</button></article>`;
      document.getElementById("planPersonal").onclick = () => openAuth("register");
      document.getElementById("planTeam").onclick = () => {
        document.getElementById("authPlan").value = "team";
        openAuth("register");
      };
    }
  }

  async function tryResumeLoggedInSession() {
    if (!AityAuth.getUser()) return;
    const base = AityAuth.readApiBase();
    if (!base) {
      showSetupOverlay({ loggedIn: true });
      return;
    }
    try {
      await AityAuth.probeApi(base);
    } catch {
      showSetupOverlay({ loggedIn: true });
    }
  }

  document.getElementById("btnSignIn").onclick = () => openAuth("login");
  document.getElementById("btnHeroSignUp").onclick = () => openAuth("register");
  document.getElementById("btnCtaSignUp")?.addEventListener("click", () => openAuth("register"));
  document.getElementById("authToggle").onclick = () => openAuth(mode === "login" ? "register" : "login");

  document.getElementById("lpSetupConnect")?.addEventListener("click", async () => {
    setupError?.classList.add("hidden");
    await AitySetup.connectFromOverlay(
      "lpSetupApiInput",
      async () => {
        if (pendingAfterConnect) {
          await openAuthAfterConnect(pendingAfterConnect);
          pendingAfterConnect = null;
          return;
        }
        if (AityAuth.getUser()) {
          hideSetupOverlay();
          location.href = "controller.html";
          return;
        }
        hideSetupOverlay();
        dialog.showModal();
      },
      (msg) => {
        if (setupError) {
          setupError.textContent = msg;
          setupError.classList.remove("hidden");
        }
      }
    );
  });

  document.getElementById("lpSetupDemo")?.addEventListener("click", () => {
    hideSetupOverlay();
    location.href = "controller.html?demo=1";
  });

  const nav = document.getElementById("lpNav");
  const navToggle = document.getElementById("navToggle");
  navToggle?.addEventListener("click", () => {
    const open = nav.classList.toggle("open");
    navToggle.setAttribute("aria-expanded", open ? "true" : "false");
  });
  nav?.querySelectorAll('a[href^="#"]').forEach((link) => {
    link.addEventListener("click", () => {
      nav.classList.remove("open");
      navToggle?.setAttribute("aria-expanded", "false");
    });
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errEl.classList.add("hidden");
    const payload = authPayload();
    if (!payload.email || !payload.password) {
      errEl.textContent = "Enter email and password";
      errEl.classList.remove("hidden");
      return;
    }

    await AityAuth.loadConfig();
    const base = AityAuth.readApiBase();
    if (base) {
      try {
        await AityAuth.probeApi(base);
        AityAuth.setApiBase(base);
        await completeAuthOnLanding(payload);
        return;
      } catch {
        /* fall through — show setup on landing */
      }
    }

    if (needsBackendSetup()) {
      pendingAfterConnect = payload;
      dialog.close();
      showSetupOverlay({ pendingAuth: payload, authIntent: payload.mode });
      return;
    }

    dialog.close();
    redirectToController(payload);
  });

  if (AityAuth.getUser()) {
    document.getElementById("btnSignIn").textContent = "Open app";
    document.getElementById("btnSignIn").onclick = async () => {
      const base = AityAuth.readApiBase();
      if (!base) {
        showSetupOverlay({ loggedIn: true });
        return;
      }
      try {
        await AityAuth.probeApi(base);
        location.href = "controller.html";
      } catch {
        showSetupOverlay({ loggedIn: true });
      }
    };
  }

  (async () => {
    await initSetup();
    initBanner();
    loadPricing();
    await tryResumeLoggedInSession();
  })();
})();
