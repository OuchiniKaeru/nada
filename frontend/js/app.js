const VALID_VIEWS = [
  "login",
  "agents",
  "chat",
  "squad-chat",
  "builder",
  "squads",
  "skills-list",
  "skills-create",
  "skills-detail",
  "mcps-list",
  "mcps-create",
  "mcps-detail",
  "tools-list",
  "dashboard",
];

function showView(viewName) {
  VALID_VIEWS.forEach((name) => {
    const section = document.getElementById(`${name}-view`);
    if (!section) return;
    section.classList.toggle("hidden", name !== viewName);
  });

  const sidebar = document.getElementById("sidebar");
  if (sidebar) {
    sidebar.classList.toggle("hidden", viewName === "login");
  }

  // Lock page scroll in chat views so the composer/input stay fixed at the bottom.
  document.body.classList.toggle("view-chat", viewName === "chat" || viewName === "squad-chat");
}

function requireAuth() {
  if (!getToken()) {
    showView("login");
    return false;
  }
  return true;
}

async function initAuthUI() {
  const token = getToken();

  if (!token) {
    showView("login");
    return;
  }

  try {
    await api("/auth/me");
    showView("agents");
    await loadAgents();
  } catch {
    clearToken();
    showView("login");
  }
}

function bindLoginForms() {
  const token = getToken();
  if (token) {
    showView("agents");
    return;
  }

  showView("login");

  const loginForm = document.getElementById("login-form");
  const registerForm = document.getElementById("register-form");
  const tabs = document.querySelectorAll(".tab");
  const errorEl = document.getElementById("login-error");

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.toggle("active", true);
      const mode = tab.dataset.tab;
      loginForm.classList.toggle("hidden", mode !== "login");
      registerForm.classList.toggle("hidden", mode !== "register");
      errorEl.classList.add("hidden");
    });
  });

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorEl.classList.add("hidden");

    const formData = new FormData(loginForm);
    const params = new URLSearchParams();
    params.set("username", String(formData.get("username") || "").trim());
    params.set("password", String(formData.get("password") || "").trim());

    try {
      const data = await api("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: params.toString(),
      });

      setToken(data.access_token);
      loginForm.reset();
      showView("agents");
      await loadAgents();
      await loadAgentSettingsModals();
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.classList.remove("hidden");
    }
  });

  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    errorEl.classList.add("hidden");

    const formData = new FormData(registerForm);

    try {
      await api("/auth/register", {
        method: "POST",
        body: formData,
      });

      alert("登録が完了しました。ログインしてください。");
      tabs[0].click();
    } catch (err) {
      errorEl.textContent = err.message;
      errorEl.classList.remove("hidden");
    }
  });
}

function uploadSelectedFiles(input, onAdd) {
  return async () => {
    const files = Array.from(input.files || []);
    for (const file of files) {
      const formData = new FormData();
      formData.append("file", file);
      try {
        const attachment = await api("/attachments", {
          method: "POST",
          body: formData,
        });
        onAdd(attachment);
      } catch (err) {
        console.error("Attachment upload failed", err);
      }
    }
    input.value = "";
  };
}

function bindPageSearches() {
  const pairs = [
    ["agents-search", "agents-list"],
    ["squads-search", "squads-list"],
    ["skills-search", "skills-list"],
    ["mcps-search", "mcps-list"],
    ["tools-search", "tools-list"],
  ];
  pairs.forEach(([inputId, listId]) => {
    const input = document.getElementById(inputId);
    const list = document.getElementById(listId);
    if (!input || !list) return;
    input.addEventListener("input", () => {
      const q = input.value.trim().toLowerCase();
      Array.from(list.querySelectorAll(".list-item")).forEach((item) => {
        const text = (item.textContent || "").toLowerCase();
        item.style.display = !q || text.includes(q) ? "" : "none";
      });
    });
  });
}

function setupChatTextarea(textareaId, formId) {
  const ta = document.getElementById(textareaId);
  const form = document.getElementById(formId);
  if (!ta || !form) return;
  const autoresize = () => {
    ta.style.height = "auto";
    ta.style.height = Math.min(ta.scrollHeight, 160) + "px";
  };
  ta.addEventListener("input", autoresize);
  ta.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    } else {
      setTimeout(autoresize, 0);
    }
  });
  autoresize();
}

function bindNavigation() {
  document.getElementById("logout-btn").addEventListener("click", () => {
    clearToken();
    showView("login");
  });

  document.getElementById("settings-btn")?.addEventListener("click", () => {
    document.getElementById("settings-modal")?.classList.remove("hidden");
  });

  document.getElementById("settings-save")?.addEventListener("click", () => {
    const form = document.getElementById("settings-form");
    const theme = String(form?.theme?.value || "dark-emerald").trim();
    const icon = String(form?.icon?.value || "").trim();
    applyTheme(theme);
    applyIcon(icon);
    document.getElementById("settings-modal")?.classList.add("hidden");
  });

  document.getElementById("new-session-btn")?.addEventListener("click", () => {
    currentSessionId = null;
    document.getElementById("chat-messages").innerHTML = "";
    loadSessions(currentAgentId);
  });

  document.getElementById("new-squad-session-btn")?.addEventListener("click", () => {
    currentSquadSessionId = null;
    document.getElementById("squad-chat-messages").innerHTML = "";
    loadSquadSessions(currentSquadId);
  });

  document.getElementById("chat-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const input = document.getElementById("chat-text");
    const text = String(input.value || "").trim();
    if (!text || !currentAgentId) return;
    input.value = "";
    sendMessage(currentAgentId, text);
  });

  document.getElementById("squad-chat-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const input = document.getElementById("squad-chat-text");
    const text = String(input.value || "").trim();
    if (!text || !currentSquadId) return;
    input.value = "";
    sendSquadMessage(currentSquadId, text);
  });

  const attachButton = document.getElementById("attach-file-btn");
  const attachmentInput = document.getElementById("chat-attachment-input");
  if (attachButton && attachmentInput) {
    attachButton.addEventListener("click", () => attachmentInput.click());
    attachmentInput.addEventListener("change", uploadSelectedFiles(attachmentInput, addPendingAttachment));
  }

  const squadAttachButton = document.getElementById("squad-attach-file-btn");
  const squadAttachmentInput = document.getElementById("squad-chat-attachment-input");
  if (squadAttachButton && squadAttachmentInput) {
    squadAttachButton.addEventListener("click", () => squadAttachmentInput.click());
    squadAttachmentInput.addEventListener("change", uploadSelectedFiles(squadAttachmentInput, addSquadPendingAttachment));
  }
}

function handleRoute() {
  const hash = window.location.hash.replace("#", "") || "";

  if (hash === "") {
    initAuthUI();
    return;
  }

  const exactView = VALID_VIEWS.includes(hash);
  const skillDetail = hash.startsWith("skills-detail/");
  const mcpDetail = hash.startsWith("mcps-detail/");
  if (exactView || skillDetail || mcpDetail) {
    if (!requireAuth()) return;
    showView(exactView ? hash : hash.split("/")[0]);
    if (hash === "agents") loadAgents();
    if (hash === "builder") loadBuilder();
    if (hash === "squads") loadSquads();
    if (hash === "skills-list") loadSkills();
    if (hash === "skills-create") bindSkillForm();
    if (skillDetail) loadSkillDetail();
    if (hash === "mcps-list") loadMcps();
    if (hash === "mcps-create") bindMcpForm();
    if (mcpDetail) loadMcpDetail();
    if (hash === "dashboard") loadDashboard();
    if (hash === "tools-list") renderToolsList();
    if (hash === "chat" && !currentAgentId) {
      window.location.hash = "#agents";
    }
    return;
  }

  initAuthUI();
}

function init() {
  const settings = currentSettings();
  applyTheme(settings.theme);
  applyIcon(settings.icon);

  bindLoginForms();
  bindNavigation();
  bindAgentForm();
  bindSkillForm();
  bindSkillCreateForm();
  bindMcpForm();
  bindMcpEditForm();
  bindMcpDetailEvents();
  document.getElementById("chat-back-link")?.addEventListener("click", navigateToAgents);
  document.getElementById("squad-chat-back-link")?.addEventListener("click", navigateToSquads);
  document.querySelector('a[data-link="agents"]')?.addEventListener("click", () => {
    if (currentAgentId) {
      navigateToAgents();
    }
  });
  document.getElementById("open-create-squad-btn")?.addEventListener("click", openCreateSquadModal);
  bindSquadEvents();
  document.getElementById("open-agent-settings")?.addEventListener("click", () => {
    if (currentAgentId) openAgentSettingsModal(currentAgent);
  });
  document.getElementById("open-squad-settings")?.addEventListener("click", () => {
    if (currentSquadId) openSquadSettingsModal(currentSquad);
  });
  bindSquadSettingsEvents();
  bindAgentSettingsEvents();
  bindSkillDetailEvents();
  bindSettingsEvents();
  bindPageSearches();
  setupChatTextarea("chat-text", "chat-form");
  setupChatTextarea("squad-chat-text", "squad-chat-form");
  bindSmartScroll(document.getElementById("chat-messages"));
  bindSmartScroll(document.getElementById("squad-chat-messages"));
  window.addEventListener("hashchange", handleRoute);
  handleRoute();
}

document.addEventListener("DOMContentLoaded", init);

function applyTheme(theme) {
  if (!theme) return;
  document.documentElement.setAttribute("data-theme", theme);
  try {
    localStorage.setItem("nada_theme", theme);
  } catch {
    // ignore
  }
}

function applyIcon(icon) {
  if (!icon) return;
  try {
    localStorage.setItem("nada_icon", icon);
  } catch {
    // ignore
  }
}

function currentSettings() {
  try {
    return {
      theme: localStorage.getItem("nada_theme") || "dark-emerald",
      icon: localStorage.getItem("nada_icon") || "",
    };
  } catch {
    return { theme: "dark-emerald", icon: "" };
  }
}

function bindSettingsEvents() {
  const openBtn = document.getElementById("settings-btn");
  const saveBtn = document.getElementById("settings-save");
  const form = document.getElementById("settings-form");
  const modal = document.getElementById("settings-modal");
  if (!openBtn || !saveBtn || !form || !modal) return;

  const settings = currentSettings();
  applyTheme(settings.theme);
  applyIcon(settings.icon);
  if (form.theme) form.theme.value = settings.theme;
  if (form.icon) form.icon.value = settings.icon;

  const closeModal = () => modal.classList.add("hidden");

  openBtn.addEventListener("click", () => modal.classList.remove("hidden"));

  // The cancel button, the X button, and the overlay all carry
  // data-modal-close. Bind them so the modal actually closes.
  modal.querySelectorAll("[data-modal-close]").forEach((el) => {
    el.addEventListener("click", (e) => {
      e.preventDefault();
      closeModal();
    });
  });

  saveBtn.addEventListener("click", () => {
    const theme = String(form.theme?.value || "dark-emerald").trim();
    const icon = String(form.icon?.value || "").trim();
    applyTheme(theme);
    applyIcon(icon);
    closeModal();
  });
}
