(() => {
  const dialog = document.getElementById("authDialog");
  const form = document.getElementById("authForm");
  const title = document.getElementById("authTitle");
  const planWrap = document.getElementById("authPlanWrap");
  const errEl = document.getElementById("authError");
  const apiInput = document.getElementById("authApiBase");
  let mode = "login";

  async function initApiField() {
    await AityAuth.loadConfig();
    const base = AityAuth.readApiBase();
    if (base) apiInput.value = base;
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
    if (!apiInput.value && AityAuth.isLocalHost()) {
      apiInput.value = location.origin;
    }
    dialog.showModal();
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
        <article class="lp-plan featured"><h3>Team</h3><div class="lp-price">$49/seat/mo</div><ul><li>Shared codebase &amp; API</li><li>Invite members</li></ul><button type="button" class="lp-btn primary" id="planTeam">Get Team access</button></article>`;
      document.getElementById("planPersonal").onclick = () => openAuth("register");
      document.getElementById("planTeam").onclick = () => {
        document.getElementById("authPlan").value = "team";
        openAuth("register");
      };
    }
  }

  document.getElementById("btnSignIn").onclick = () => openAuth("login");
  document.getElementById("btnHeroSignUp").onclick = () => openAuth("register");
  document.getElementById("authToggle").onclick = () => openAuth(mode === "login" ? "register" : "login");

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errEl.classList.add("hidden");
    const apiBase = AityAuth.setApiBase(apiInput.value);
    if (!apiBase) {
      errEl.textContent = "Enter your aityuahn serve URL (e.g. http://127.0.0.1:8765)";
      errEl.classList.remove("hidden");
      return;
    }
    try {
      await AityAuth.probeApi(apiBase);
    } catch (ex) {
      errEl.textContent = String(ex.message || ex);
      errEl.classList.remove("hidden");
      return;
    }
    const email = document.getElementById("authEmail").value.trim();
    const password = document.getElementById("authPassword").value;
    const name = document.getElementById("authName").value.trim();
    const plan = document.getElementById("authPlan").value;
    try {
      const path = mode === "login" ? "/auth/login" : "/auth/register";
      const body =
        mode === "login"
          ? { email, password }
          : { email, password, name, plan };
      const data = await AityAuth.saasApi(path, { method: "POST", body: JSON.stringify(body) });
      AityAuth.setSession(data.access_token, data.user);
      dialog.close();
      location.href = "controller.html";
    } catch (ex) {
      errEl.textContent = String(ex.message || ex);
      errEl.classList.remove("hidden");
    }
  });

  if (AityAuth.getUser()) {
    document.getElementById("btnSignIn").textContent = "Open app";
    document.getElementById("btnSignIn").onclick = () => {
      location.href = "controller.html";
    };
  }

  initApiField();
  loadPricing();
})();
