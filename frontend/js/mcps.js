async function loadMcps() {
  const list = document.getElementById("mcps-list");
  if (!list) return;
  list.innerHTML = "";

  try {
    const mcps = await api("/mcps");
    if (!mcps.length) {
      list.innerHTML = `<p class="empty">MCPがありません。</p>`;
      return;
    }

    mcps.forEach((mcp) => {
      const item = document.createElement("div");
      item.className = "list-item";
      const iconHtml = mcp.icon ? `<div class="list-item-icon" aria-hidden="true">${escapeHtml(mcp.icon)}</div>` : "";
      item.innerHTML = `
        ${iconHtml}
        <div class="list-item-body">
          <div class="list-item-title">${escapeHtml(mcp.name)}</div>
          <div class="list-item-meta">${escapeHtml(mcp.description || "")}</div>
        </div>
      `;
      item.addEventListener("click", () => {
        window.location.hash = `#mcps-detail/${mcp.id}`;
      });
      list.appendChild(item);
    });
  } catch (error) {
    list.innerHTML = `<p class="empty">MCPの取得に失敗しました: ${escapeHtml(error.message)}</p>`;
  }
}

async function loadMcpDetail() {
  const container = document.getElementById("mcp-detail-content");
  const form = document.getElementById("mcp-edit-form");
  const error = document.getElementById("mcp-error");
  if (!container || !form) return;

  const id = getRouteId("mcps-detail");
  if (!id) {
    container.innerHTML = `<p class="empty">MCP IDが指定されていません。</p>`;
    return;
  }

  try {
    const mcp = await api(`/mcps/${encodeURIComponent(id)}`);
    form.classList.add("hidden");
    error.classList.add("hidden");
    container.classList.remove("hidden");
    container.innerHTML = `
      <h3>${escapeHtml(mcp.name)}</h3>
      <p>${escapeHtml(mcp.description || "")}</p>
      <pre class="detail-code">${escapeHtml(typeof mcp.config === "object" ? JSON.stringify(mcp.config, null, 2) : (mcp.config || "{}"))}</pre>
    `;
  } catch (error) {
    container.innerHTML = `<p class="empty">MCPの取得に失敗しました: ${escapeHtml(error.message)}</p>`;
  }
}

function bindMcpForm() {
  const form = document.getElementById("mcp-create-form");
  const error = document.getElementById("mcp-create-error");
  if (!form || !error) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.classList.add("hidden");

    try {
      const data = new FormData(form);
      const configText = String(data.get("config") || "{}").trim();
      let config = {};
      try {
        config = JSON.parse(configText);
      } catch (e) {
        error.textContent = "設定 JSON の形式が不正です。";
        error.classList.remove("hidden");
        return;
      }

      await api("/mcps", {
        method: "POST",
        body: JSON.stringify({
          name: String(data.get("name") || "").trim(),
          description: String(data.get("description") || "").trim(),
          config: config,
        }),
      });
      form.reset();
      window.location.hash = "#mcps-list";
    } catch (err) {
      error.textContent = err.message;
      error.classList.remove("hidden");
    }
  });
}

function bindMcpEditForm() {
  const form = document.getElementById("mcp-edit-form");
  const error = document.getElementById("mcp-error");
  if (!form || !error) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.classList.add("hidden");

    const id = getRouteId("mcps-detail");
    if (!id) return;

    try {
      const data = new FormData(form);
      const configText = String(data.get("config") || "{}").trim();
      let config = {};
      try {
        config = JSON.parse(configText);
      } catch (e) {
        error.textContent = "設定 JSON の形式が不正です。";
        error.classList.remove("hidden");
        return;
      }

      await api(`/mcps/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: String(data.get("name") || "").trim(),
          description: String(data.get("description") || "").trim(),
          config: config,
        }),
      });

      form.classList.add("hidden");
      await loadMcpDetail();
    } catch (err) {
      error.textContent = err.message;
      error.classList.remove("hidden");
    }
  });
}

async function deleteCurrentMcp() {
  const id = getRouteId("mcps-detail");
  if (!id) return;

  if (!confirm("このMCPを削除しますか？")) return;

  try {
    await api(`/mcps/${encodeURIComponent(id)}`, { method: "DELETE" });
    window.location.hash = "#mcps-list";
  } catch (err) {
    const error = document.getElementById("mcp-error");
    if (error) {
      error.textContent = err.message;
      error.classList.remove("hidden");
    }
  }
}

function bindMcpDetailEvents() {
  const editBtn = document.getElementById("edit-mcp-btn");
  const deleteBtn = document.getElementById("delete-mcp-btn");
  const cancelBtn = document.getElementById("cancel-mcp-edit");
  const form = document.getElementById("mcp-edit-form");
  const container = document.getElementById("mcp-detail-content");
  const error = document.getElementById("mcp-error");
  if (!editBtn || !deleteBtn || !cancelBtn || !form || !container || !error) return;

  editBtn.addEventListener("click", async () => {
    const id = getRouteId("mcps-detail");
    if (!id) return;

    try {
      const mcp = await api(`/mcps/${encodeURIComponent(id)}`);
      form.name.value = mcp.name || "";
      form.description.value = mcp.description || "";
      form.config.value = typeof mcp.config === "object" ? JSON.stringify(mcp.config, null, 2) : (mcp.config || "{}");
      form.classList.remove("hidden");
      container.classList.add("hidden");
      error.classList.add("hidden");
    } catch (err) {
      error.textContent = err.message;
      error.classList.remove("hidden");
    }
  });

  deleteBtn.addEventListener("click", deleteCurrentMcp);

  cancelBtn.addEventListener("click", () => {
    form.classList.add("hidden");
    container.classList.remove("hidden");
    error.classList.add("hidden");
  });
}
