async function loadAgents() {
  const container = document.getElementById("agents-list");
  const empty = document.getElementById("agents-empty");

  container.innerHTML = "";

  try {
    const agents = await api("/agents");

    if (!agents.length) {
      empty.classList.remove("hidden");
      return;
    }

    empty.classList.add("hidden");

    agents.forEach((agent) => {
      const el = document.createElement("div");
      el.className = "list-item";

      const iconHtml = agent.icon
        ? `<div class="list-item-icon" aria-hidden="true">${escapeHtml(agent.icon)}</div>`
        : "";

      el.innerHTML = `
        ${iconHtml}
        <div class="list-item-body">
          <div class="list-item-title">${escapeHtml(agent.title)}</div>
          <div class="list-item-meta">
            ${escapeHtml(agent.model_provider || "")}
            /
            ${escapeHtml(agent.model_id || "")}
            ·
            ${escapeHtml(agent.visibility || "")}
          </div>
        </div>
      `;

      el.addEventListener("click", () => {
        openChat(agent.id, agent.title, agent);
      });

      container.appendChild(el);
    });
  } catch (error) {
    empty.classList.remove("hidden");
    empty.textContent =
      `エージェント一覧の取得に失敗しました: ${error.message}`;
  }
}

async function loadBuilder() {
  buildToolModalList("builder-tools-modal-list", []);
  updateBuilderToolsLabel();

  // Tools modal (chat-style ON/OFF selection)
  document.getElementById("open-builder-tools-btn")?.addEventListener("click", () => {
    buildToolModalList("builder-tools-modal-list", readBuilderTools());
    document.getElementById("builder-tools-modal")?.classList.remove("hidden");
  });
  document.getElementById("builder-tools-modal-save")?.addEventListener("click", () => {
    document.getElementById("builder-tools-modal")?.classList.add("hidden");
    updateBuilderToolsLabel();
  });
  document.getElementById("builder-tools-modal-search")?.addEventListener("input", (e) =>
    filterModalList("builder-tools-modal-list", e.target.value)
  );

  // Populate skills modal and mcps modal (inputs use form="agent-form" so they are included in FormData)
  const skillsListContainer = document.getElementById("skills-modal-list");
  const mcpsListContainer = document.getElementById("mcps-modal-list");

  if (skillsListContainer) {
    skillsListContainer.innerHTML = "";
    const skills = await api("/skills");
    skills.forEach((skill) => {
      const id = String(skill.id);
      const row = document.createElement("label");
      row.className = "modal-item";
      row.innerHTML = `
        <div class="switch">
          <input type="checkbox" name="skill_ids" value="${id}" id="skill-checkbox-${id}" form="agent-form">
          <span class="switch-track"></span>
        </div>
        <div>
          <div class="modal-item-title">${escapeHtml(skill.name)}</div>
          <div class="modal-item-desc">${escapeHtml(skill.description || "")}</div>
        </div>
      `;
      skillsListContainer.appendChild(row);
    });
  }

  if (mcpsListContainer) {
    mcpsListContainer.innerHTML = "";
    // allow multiple MCP selection via checkboxes
    const mcps = await api("/mcps");
    if (!mcps.length) {
      mcpsListContainer.innerHTML = `<p class="empty">MCPがありません。</p>`;
    }
    mcps.forEach((mcp) => {
      const id = String(mcp.id);
      const row = document.createElement("label");
      row.className = "modal-item";
      row.innerHTML = `
        <div class="switch">
          <input type="checkbox" name="mcp_server_ids" value="${id}" id="mcp-checkbox-${id}" form="agent-form">
          <span class="switch-track"></span>
        </div>
        <div>
          <div class="modal-item-title">${escapeHtml(mcp.name)}</div>
          <div class="modal-item-desc">${escapeHtml(mcp.url || "")}</div>
        </div>
      `;
      mcpsListContainer.appendChild(row);
    });
  }

  // wire modal open/close buttons
  document.getElementById("open-skills-modal-btn")?.addEventListener("click", () => {
    document.getElementById("skills-modal")?.classList.remove("hidden");
  });
  document.getElementById("open-mcps-modal-btn")?.addEventListener("click", () => {
    document.getElementById("mcps-modal")?.classList.remove("hidden");
  });

  // search/filter in modals
  const skillsSearch = document.getElementById("skills-modal-search");
  const mcpsSearch = document.getElementById("mcps-modal-search");
  skillsSearch?.addEventListener("input", (e) => filterModalList("skills-modal-list", e.target.value));
  mcpsSearch?.addEventListener("input", (e) => filterModalList("mcps-modal-list", e.target.value));

  // close handlers
  document.querySelectorAll("[data-modal-close]")?.forEach((el) => {
    el.addEventListener("click", (e) => {
      let node = e.target;
      while (node && !node.classList?.contains("modal")) node = node.parentElement;
      if (node && node.id) document.getElementById(node.id)?.classList.add("hidden");
      // update button labels to reflect selections
      updateSelectionLabels();
    });
  });

  document.getElementById("skills-modal-save")?.addEventListener("click", () => {
    document.getElementById("skills-modal")?.classList.add("hidden");
    updateSelectionLabels();
  });
  document.getElementById("mcps-modal-save")?.addEventListener("click", () => {
    document.getElementById("mcps-modal")?.classList.add("hidden");
    updateSelectionLabels();
  });
}

function updateSelectionLabels() {
  const skillBtn = document.getElementById("open-skills-modal-btn");
  const mcpsBtn = document.getElementById("open-mcps-modal-btn");
  const selectedSkills = Array.from(document.querySelectorAll('input[name="skill_ids"]:checked')).map(i => i.closest('.modal-item')?.querySelector('.modal-item-title')?.textContent || i.value);
  const selectedMcps = Array.from(document.querySelectorAll('input[name="mcp_server_ids"]:checked')).map(i => i.closest('.modal-item')?.querySelector('.modal-item-title')?.textContent || i.value);

  if (skillBtn) {
    if (selectedSkills.length === 0) skillBtn.textContent = "Skillsを選択";
    else skillBtn.textContent = `選択済み: ${selectedSkills.length}`;
  }
  if (mcpsBtn) {
    if (selectedMcps.length === 0) mcpsBtn.textContent = "MCPを選択";
    else mcpsBtn.textContent = `選択済み: ${selectedMcps.length}`;
  }
  updateBuilderToolsLabel();
}

function readBuilderTools() {
  return Array.from(
    document.querySelectorAll("#builder-tools-modal-list input[type='checkbox']:checked")
  ).map((input) => input.value);
}

function updateBuilderToolsLabel() {
  const btn = document.getElementById("open-builder-tools-btn");
  if (!btn) return;
  const count = readBuilderTools().length;
  btn.textContent = count ? `選択済み: ${count}` : "Toolsを選択";
}

function filterModalList(listId, query) {
  const q = String(query || "").trim().toLowerCase();
  const container = document.getElementById(listId);
  if (!container) return;
  Array.from(container.querySelectorAll('.modal-item')).forEach((item) => {
    const title = (item.querySelector('.modal-item-title')?.textContent || '').toLowerCase();
    const desc = (item.querySelector('.modal-item-desc')?.textContent || '').toLowerCase();
    const match = !q || title.includes(q) || desc.includes(q);
    item.style.display = match ? '' : 'none';
  });
}

async function createAgent(formData) {
  const skillIds = formData.getAll("skill_ids").filter(Boolean).map(String);
  const mcpServerIds = formData.getAll("mcp_server_ids").filter(Boolean).map(String);
  const mcpServerId = mcpServerIds.length ? mcpServerIds[0] : (String(formData.get("mcp_server_id") || "").trim() || null);
  const toolKeys = readBuilderTools();

  const workspaceRaw = String(formData.get("workspace") || "").trim();
  let workspaceConfig = {};
  try {
    workspaceConfig = workspaceRaw ? JSON.parse(workspaceRaw) : {};
  } catch {
    workspaceConfig = { raw: workspaceRaw };
  }
  if (!Object.keys(workspaceConfig).length) {
    workspaceConfig = { target_directory: "./output" };
  }

  const payload = {
    title: String(formData.get("title") || "").trim(),
    description: String(formData.get("description") || "").trim(),
    system_prompt: String(formData.get("system_prompt") || "").trim(),
    model_provider: String(formData.get("model_provider") || "").trim(),
    model_id: String(formData.get("model_id") || "").trim(),
    visibility: String(formData.get("visibility") || "private").trim(),
    ad_group: String(formData.get("ad_group") || "").trim() || null,
    skill_ids: skillIds,
    mcp_server_id: mcpServerId,
    mcp_server_ids: mcpServerIds,
    tools_config: { tools: toolKeys },
    workspace_config: workspaceConfig,
    icon: String(formData.get("icon") || "").trim() || null,
  };

  if (
    !payload.title ||
    !payload.description ||
    !payload.system_prompt ||
    !payload.model_provider ||
    !payload.model_id
  ) {
    throw new Error("必須項目を入力してください。");
  }

  return await api("/agents", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

function bindAgentForm() {
  const form = document.getElementById("agent-form");
  const error = document.getElementById("builder-error");
  if (!form || !error) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.classList.add("hidden");

    try {
      const formData = new FormData(form);
      await createAgent(formData);
      form.reset();
      alert("エージェントを作成しました。");
      window.location.hash = "#agents";
    } catch (err) {
      error.textContent = err.message;
      error.classList.remove("hidden");
    }
  });
}

function escapeHtml(text = "") {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
