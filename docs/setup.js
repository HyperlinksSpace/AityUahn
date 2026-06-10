(() => {
  const DEFAULT_LOCAL = "http://127.0.0.1:8765";

  const IDS = {
    zip: "overlayBackendZip",
    repo: "overlayBackendRepo",
    defaultApi: "overlayDefaultApi",
    healthUrl: "overlayHealthUrl",
    apiInput: "overlayApiInput",
    title: "setupTitle",
    lead: "setupLead",
    note: "setupNote",
    authBtn: "btnOverlaySignIn",
  };

  async function loadConfig() {
    try {
      const r = await fetch(new URL("config.json", document.baseURI).href);
      return r.ok ? await r.json() : {};
    } catch {
      return {};
    }
  }

  function localDefault(config) {
    return (config?.defaultApiLocal || DEFAULT_LOCAL).replace(/\/$/, "");
  }

  function applyBackendLinks(config, ids = IDS) {
    const local = localDefault(config);
    const setHref = (key, href) => {
      const el = document.getElementById(ids[key]);
      if (el && href) el.href = href;
    };
    const setText = (key, value) => {
      const el = document.getElementById(ids[key]);
      if (el && value) el.textContent = value;
    };
    setHref("zip", config?.backendZip);
    setHref("repo", config?.backendRepo);
    setText("defaultApi", local);
    setText("healthUrl", `${local}/api/health`);
    const input = document.getElementById(ids.apiInput);
    if (input && !input.value.trim()) input.placeholder = local;
    return local;
  }

  function updateSetupContext(options = {}, ids = IDS) {
    const { pendingAuth, loggedIn, authIntent } = options;
    const title = document.getElementById(ids.title);
    const lead = document.getElementById(ids.lead);
    const note = document.getElementById(ids.note);
    const authBtn = document.getElementById(ids.authBtn);

    if (pendingAuth || authIntent) {
      if (title) {
        title.textContent =
          pendingAuth?.mode === "register" || authIntent === "register"
            ? "Connect backend to create your account"
            : "Connect backend to sign in";
      }
      if (lead) {
        lead.textContent =
          "Sign-in and registration run on aityuahn serve — not on GitHub Pages. Download the backend, run it locally (or deploy it), then paste the API URL below.";
      }
      if (note) {
        note.textContent =
          "After you connect, your sign-in form opens automatically with the details you already entered.";
      }
      if (authBtn) authBtn.textContent = "Continue sign-in after connect";
    } else if (loggedIn) {
      if (title) title.textContent = "Reconnect your backend";
      if (lead) {
        lead.textContent =
          "You are signed in, but the app cannot reach your API. Start aityuahn serve (or your deployed instance) and connect again.";
      }
      if (note) {
        note.textContent = "Your session is saved locally. Team projects and forge features return once the API is live.";
      }
      if (authBtn) authBtn.textContent = "Open sign-in";
    } else {
      if (title) title.textContent = "First run — download & start the backend";
      if (lead) {
        lead.textContent =
          "The controller UI can run on GitHub Pages, but forge, agents, and accounts need the Python API (aityuahn serve) on your machine or a deployed host.";
      }
      if (note) {
        note.textContent =
          "After connecting, complete sign-in or registration in the dialog. Team features require an account.";
      }
      if (authBtn) authBtn.textContent = "Sign in / Register";
    }
  }

  async function connectFromOverlay(inputId, onSuccess, onError) {
    const el = document.getElementById(inputId);
    const value = (el?.value || "").trim().replace(/\/$/, "");
    if (!value) {
      onError?.("Enter API URL");
      return false;
    }
    try {
      await window.AityAuth.probeApi(value);
      window.AityAuth.setApiBase(value);
      onSuccess?.(value);
      return true;
    } catch (ex) {
      onError?.(String(ex.message || ex));
      return false;
    }
  }

  window.AitySetup = {
    IDS,
    DEFAULT_LOCAL,
    loadConfig,
    localDefault,
    applyBackendLinks,
    updateSetupContext,
    connectFromOverlay,
  };
})();
