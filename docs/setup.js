(() => {
  const DEFAULT_LOCAL = "http://127.0.0.1:8765";

  const IDS = {
    zip: "overlayBackendZip",
    repo: "overlayBackendRepo",
    exe: "overlayBackendExe",
    release: "overlayBackendRelease",
    defaultApi: "overlayDefaultApi",
    healthUrl: "overlayHealthUrl",
    apiInput: "overlayApiInput",
    title: "setupTitle",
    lead: "setupLead",
    note: "setupNote",
    authBtn: "btnOverlaySignIn",
    cmdPs1: "installCmdPs1",
    cmdSh: "installCmdSh",
  };

  let copyBound = false;

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

  function installOneLiners(config) {
    const sh = config?.backendInstallerSh;
    const ps1 = config?.backendInstallerPs1;
    return {
      powershell: ps1 ? `irm ${ps1} | iex` : "",
      gitBash: sh ? `curl -LsSf ${sh} | sh` : "",
    };
  }

  function setVisible(id, show) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.toggle("hidden", !show);
  }

  function applyBackendLinks(config, ids = IDS) {
    const local = localDefault(config);
    const lines = installOneLiners(config);
    const setHref = (key, href) => {
      const el = document.getElementById(ids[key]);
      if (el && href) el.href = href;
    };
    const setText = (key, value) => {
      const el = document.getElementById(ids[key]);
      if (el && value != null && value !== "") el.textContent = value;
    };
    setHref("zip", config?.backendZip);
    setHref("repo", config?.backendRepo);
    setHref("release", config?.backendRelease);
    setHref("exe", config?.backendExe);
    ["linkBackendZip", "linkBackendRepo", "linkBackendExe"].forEach((id, i) => {
      const key = ["zip", "repo", "exe"][i];
      const el = document.getElementById(id);
      const href = key === "zip" ? config?.backendZip : key === "repo" ? config?.backendRepo : config?.backendExe;
      if (el && href) el.href = href;
      if (id === "linkBackendExe") setVisible(id, Boolean(config?.backendExe));
    });
    setText("defaultApi", local);
    setText("healthUrl", `${local}/api/health`);
    setText("cmdPs1", lines.powershell);
    setText("cmdSh", lines.gitBash);
    if (ids.exe) setVisible(ids.exe, Boolean(config?.backendExe));
    if (ids.release) setVisible(ids.release, Boolean(config?.backendRelease));
    const input = document.getElementById(ids.apiInput);
    if (input && !input.value.trim()) input.placeholder = local;
    return local;
  }

  async function copyText(text) {
    if (!text) return false;
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.left = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      ta.remove();
      return ok;
    }
  }

  function bindCopyButtons(root = document, onCopied) {
    if (copyBound) return;
    copyBound = true;
    root.addEventListener("click", async (ev) => {
      const btn = ev.target.closest("[data-copy-target]");
      if (!btn) return;
      const targetId = btn.getAttribute("data-copy-target");
      const el = document.getElementById(targetId);
      const text = el?.textContent?.trim();
      if (!text) return;
      const ok = await copyText(text);
      onCopied?.(ok ? "Install command copied" : "Could not copy", !ok);
    });
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
          "Sign-in runs on aityuahn serve. Install the backend with the one-line command below (PowerShell on Windows), start it, then paste the API URL.";
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
          "You are signed in, but the app cannot reach your API. Run serve.bat in your install folder or aityuahn serve, then connect again.";
      }
      if (note) {
        note.textContent = "Your session is saved locally. Team projects and forge features return once the API is live.";
      }
      if (authBtn) authBtn.textContent = "Open sign-in";
    } else {
      if (title) title.textContent = "First run — install & start the backend";
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

  async function initSetupUi(ids = IDS, onCopied) {
    const config = await loadConfig();
    applyBackendLinks(config, ids);
    bindCopyButtons(document, onCopied);
    return config;
  }

  window.AitySetup = {
    IDS,
    DEFAULT_LOCAL,
    loadConfig,
    localDefault,
    installOneLiners,
    applyBackendLinks,
    updateSetupContext,
    connectFromOverlay,
    initSetupUi,
    bindCopyButtons,
    copyText,
  };
})();
