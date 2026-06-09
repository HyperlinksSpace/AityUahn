(() => {
  const PENDING_AUTH_KEY = "aityuahn-pending-auth";
  const dialog = document.getElementById("authDialog");
  const form = document.getElementById("authForm");
  const title = document.getElementById("authTitle");
  const planWrap = document.getElementById("authPlanWrap");
  const errEl = document.getElementById("authError");
  let mode = "login";

  async function initBanner() {
    await AityAuth.loadConfig();
    if (location.hostname.endsWith("github.io")) {
      document.getElementById("apiBanner")?.classList.remove("hidden");
    }
  }

  function openAuth(nextMode = "login") {
    mode = nextMode;
    title.textContent = mode === "login" ? "Sign in" : "Create account";
    document.getElementById("authToggle").textContent = mode === "login" ? "Create account" : "Sign in instead";
    planWrap.classList.toggle("hidden", mode === "login");
    errEl.classList.add("hidden");
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

  document.getElementById("btnSignIn").onclick = () => openAuth("login");
  document.getElementById("btnHeroSignUp").onclick = () => openAuth("register");
  document.getElementById("btnCtaSignUp")?.addEventListener("click", () => openAuth("register"));
  document.getElementById("authToggle").onclick = () => openAuth(mode === "login" ? "register" : "login");

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
        const path = payload.mode === "login" ? "/auth/login" : "/auth/register";
        const body =
          payload.mode === "login"
            ? { email: payload.email, password: payload.password }
            : { email: payload.email, password: payload.password, name: payload.name, plan: payload.plan };
        const data = await AityAuth.saasApi(path, { method: "POST", body: JSON.stringify(body) });
        AityAuth.setSession(data.access_token, data.user);
        dialog.close();
        const params = new URLSearchParams();
        if (data.requires_ton_payment || (payload.mode === "register" && payload.plan === "team")) {
          params.set("upgrade", "ton");
        }
        location.href = params.toString() ? `controller.html?${params}` : "controller.html";
        return;
      } catch (ex) {
        /* fall through — open controller setup */
      }
    }

    dialog.close();
    redirectToController(payload);
  });

  if (AityAuth.getUser()) {
    document.getElementById("btnSignIn").textContent = "Open app";
    document.getElementById("btnSignIn").onclick = () => {
      location.href = "controller.html";
    };
  }

  initBanner();
  loadPricing();
})();
