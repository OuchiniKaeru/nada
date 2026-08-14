let currentAgentId = null;
let currentSessionId = null;
let currentAgentTitle = "";
let pendingAttachments = [];
let currentAgent = null;

let currentSquadId = null;
let currentSquadSessionId = null;
let currentSquadTitle = "";
let currentSquad = null;
let pendingSquadAttachments = [];

async function openChat(agentId, agentTitle, agent) {
  currentAgentId = agentId;
  currentAgentTitle = agentTitle || "エージェント";
  pendingAttachments = [];
  renderAttachmentPreview();
  currentAgent = agent || null;

  document.getElementById("chat-agent-title").textContent = currentAgentTitle;
  document.getElementById("chat-messages").innerHTML = "";

  await loadSessions(agentId);
  const sessionList = document.getElementById("sessions-list");
  const firstSession = sessionList ? sessionList.querySelector(".session-item") : null;
  if (firstSession) {
    firstSession.click();
  } else {
    currentSessionId = null;
  }

  window.location.hash = "#chat";
}

function openSquadChat(squadId, squadTitle, squad) {
  currentSquadId = squadId;
  currentSquadTitle = squadTitle || "スクワッド";
  currentSquadSessionId = null;
  currentSquad = squad || null;
  pendingSquadAttachments = [];
  renderSquadAttachmentPreview();

  document.getElementById("squad-chat-title").textContent = currentSquadTitle;
  document.getElementById("squad-chat-messages").innerHTML = "";

  window.location.hash = "#squad-chat";
  loadSquadSessions(squadId);
}

function navigateToAgents() {
  currentAgentId = null;
  currentSessionId = null;
  currentAgentTitle = "";
  pendingAttachments = [];
  currentAgent = null;
  window.location.hash = "#agents";
}

function navigateToSquads() {
  currentSquadId = null;
  currentSquadSessionId = null;
  currentSquadTitle = "";
  currentSquad = null;
  window.location.hash = "#squads";
}

function escapeHtml(text = "") {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/* ---------- Markdown -> HTML (safe) ---------- */
function renderMarkdown(src) {
  if (!src) return "";
  const text = String(src);
  const blocks = [];

  // Extract fenced code blocks first (keep them verbatim).
  let body = text.replace(/```([^\n]*)\n([\s\S]*?)(?:```|$)/g, (m, lang, code) => {
    const id = blocks.length;
    const langAttr = escapeHtml(String(lang || "").trim());
    const codeHtml = escapeHtml(String(code).replace(/\n$/, ""));
    blocks.push(`<pre><code class="language-${langAttr}">${codeHtml}</code></pre>`);
    return `\u0000B${id}\u0000`;
  });

  // Extract pipe markdown tables (header + separator + rows) into a pre-built
  // <table>. Cells are already escaped so they survive the pass below.
  body = body.replace(/^((?:\|.*\|\s*\n)+)/gm, (matchBlock, block) => {
    const lines = block.trim().split("\n").map((l) => l.trim());
    if (lines.length < 2) return matchBlock;
    if (!/^\|?[\s\-:|]+\|?$/.test(lines[1])) return matchBlock;
    const cells = (line) =>
      line.replace(/^\|/, "").replace(/\|$/, "").split("|").map((c) => escapeHtml(c.trim()));
    const header = cells(lines[0]);
    const rows = lines.slice(2).map(cells);
    const tid = blocks.length;
    let html = `<table><thead><tr>${header.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>`;
    html += rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("");
    html += "</tbody></table>";
    blocks.push(html);
    return `\u0000B${tid}\u0000`;
  });

  // Escape the remainder.
  body = escapeHtml(body);

  // Restore code blocks.
  body = body.replace(/\u0000B(\d+)\u0000/g, (m, i) => blocks[+i]);

  // Inline transforms.
  body = body.replace(/`([^`\n]+)`/g, (m, c) => `<code>${c}</code>`);
  body = body.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  body = body.replace(/\*([^*\n]+)\*/g, "<em>$1</em>");
  body = body.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');

  const lines = body.split("\n");
  const out = [];
  let paragraph = [];

  const flushParagraph = () => {
    if (paragraph.length) {
      out.push(`<p>${paragraph.join("<br/>")}</p>`);
      paragraph = [];
    }
  };

  for (let line of lines) {
    const trimmed = line.trim();
    if (/^#{1,6}\s/.test(trimmed)) {
      flushParagraph();
      const level = trimmed.match(/^#+/)[0].length;
      out.push(`<h${level}>${trimmed.replace(/^#+\s*/, "")}</h${level}>`);
    } else if (/^---+$/.test(trimmed)) {
      flushParagraph();
      out.push("<hr>");
    } else if (/^&gt;\s?/.test(trimmed)) {
      flushParagraph();
      out.push(`<blockquote>${trimmed.replace(/^&gt;\s?/, "")}</blockquote>`);
    } else if (/^[-*]\s+/.test(trimmed) || /^\d+\.\s+/.test(trimmed)) {
      flushParagraph();
      out.push(`<li>${trimmed.replace(/^([-*]|\d+\.)\s+/, "")}</li>`);
    } else if (trimmed === "") {
      flushParagraph();
    } else {
      paragraph.push(line);
    }
  }
  flushParagraph();

  // Group consecutive <li> into lists.
  let html = out.join("\n");
  html = html.replace(/(<li>[\s\S]*?<\/li>)(?:\n?<li>[\s\S]*?<\/li>)*/g, (group) => {
    const items = group.match(/<li>[\s\S]*?<\/li>/g).join("");
    return `<ul>${items}</ul>`;
  });
  return html;
}

/* ---------- message rendering ---------- */
function appendUserMessage(text) {
  const container = document.getElementById("chat-messages");
  const el = document.createElement("div");
  el.className = "message user";
  const md = document.createElement("div");
  md.className = "md";
  md.innerHTML = renderMarkdown(text);
  el.appendChild(md);
  container.appendChild(el);
  smartScroll(container);
}

function appendAgentMessage(text) {
  const container = document.getElementById("chat-messages");
  const el = document.createElement("div");
  el.className = "message agent";
  const md = document.createElement("div");
  md.className = "md";
  md.innerHTML = renderMarkdown(text);
  el.appendChild(md);
  container.appendChild(el);
  smartScroll(container);
  return { el, md };
}

function appendSquadUserMessage(text) {
  const container = document.getElementById("squad-chat-messages");
  const el = document.createElement("div");
  el.className = "message user";
  const md = document.createElement("div");
  md.className = "md";
  md.innerHTML = renderMarkdown(text);
  el.appendChild(md);
  container.appendChild(el);
  smartScroll(container);
}

function appendSquadAgentMessage(text) {
  const container = document.getElementById("squad-chat-messages");
  const el = document.createElement("div");
  el.className = "message agent";
  const md = document.createElement("div");
  md.className = "md";
  md.innerHTML = renderMarkdown(text);
  el.appendChild(md);
  container.appendChild(el);
  smartScroll(container);
  return { el, md };
}

/* ---------- smart scroll ---------- */
function bindSmartScroll(container) {
  if (!container || container.dataset.smartBound) return;
  container.dataset.smartBound = "1";
  container.addEventListener("scroll", () => {
    const nearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 120;
    container.dataset.smartPin = nearBottom ? "1" : "0";
  });
}

function smartScroll(container) {
  if (!container) return;
  if (container.dataset.smartPin === "0") return; // user is scrolled up — don't yank them
  container.scrollTop = container.scrollHeight;
}

function sessionTitleLabel(session) {
  const t = (session.title && String(session.title).trim()) || "新しいセッション";
  return t.length > 20 ? t.slice(0, 20) + "…" : t;
}

function formatDateTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/* ---------- SSE streaming over fetch (POST) ---------- */
async function streamChat(url, payload, onDelta, onError) {
  const token = getToken();
  const response = await fetch(`${API_BASE}${url}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: token ? `Bearer ${token}` : "",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok || !response.body) {
    const text = await response.text();
    let detail = `HTTP ${response.status}`;
    try { detail = JSON.parse(text).detail || detail; } catch { detail = text || detail; }
    throw new Error(detail);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const readAll = async () => {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buffer.indexOf("\n\n")) !== -1) {
        const chunk = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);
        const match = chunk.match(/^data:\s?(.*)$/m);
        if (!match) continue;
        let data;
        try { data = JSON.parse(match[1]); } catch { continue; }
        if (data.type === "delta") onDelta(data.content || "");
        else if (data.type === "done") { onDelta(data.content || ""); return data; }
        else if (data.type === "error") { onError(data.content || "エラーが発生しました。"); return data; }
      }
    }
    return null;
  };

  return await readAll();
}

function addPendingAttachment(attachment) {
  pendingAttachments.push(attachment);
  renderAttachmentPreview();
}

function addSquadPendingAttachment(attachment) {
  pendingSquadAttachments.push(attachment);
  renderSquadAttachmentPreview();
}

function removeSquadPendingAttachment(id) {
  pendingSquadAttachments = pendingSquadAttachments.filter((attachment) => attachment.id !== id);
  renderSquadAttachmentPreview();
}

function removePendingAttachment(id) {
  pendingAttachments = pendingAttachments.filter((attachment) => attachment.id !== id);
  renderAttachmentPreview();
}

function renderPendingAttachmentChips(containerId, attachments, onRemove) {
  const preview = document.getElementById(containerId);
  if (!preview) return;
  preview.innerHTML = "";
  if (!attachments.length) {
    preview.classList.add("hidden");
    return;
  }
  preview.classList.remove("hidden");
  attachments.forEach((attachment) => {
    const chip = document.createElement("div");
    chip.className = "attachment-chip";
    const name = document.createElement("span");
    name.textContent = attachment.filename || attachment.url || "ファイル";
    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.textContent = "✕";
    removeButton.title = "削除";
    removeButton.addEventListener("click", () => onRemove(attachment.id));
    chip.appendChild(name);
    chip.appendChild(removeButton);
    preview.appendChild(chip);
  });
}

function renderAttachmentPreview() {
  renderPendingAttachmentChips("attachment-preview", pendingAttachments, removePendingAttachment);
}

function renderSquadAttachmentPreview() {
  renderPendingAttachmentChips("squad-attachment-preview", pendingSquadAttachments, removeSquadPendingAttachment);
}

async function sendMessage(agentId, text) {
  if (!text.trim()) return;

  appendUserMessage(text);
  showTypingIndicator(true);

  const container = document.getElementById("chat-messages");
  const live = appendAgentMessage("生成中...");
  let acc = "";

  try {
    const payload = {
      message: text,
      session_id: currentSessionId,
      attachment_ids: pendingAttachments.map((attachment) => attachment.id),
    };

    const done = await streamChat(
      `/agents/${encodeURIComponent(agentId)}/chat`,
      payload,
      (chunk) => {
        acc += chunk;
        live.md.innerHTML = renderMarkdown(acc || "生成中...");
        smartScroll(container);
      },
      (err) => {
        acc = err;
        live.md.innerHTML = renderMarkdown(err);
      }
    );

    if (done && done.session_id) currentSessionId = done.session_id;
    if (!acc.trim() && done && done.content) acc = done.content;
    live.el.classList.remove("streaming");
    live.md.innerHTML = renderMarkdown(acc.trim() || "(応答がありません)");
    smartScroll(container);

    pendingAttachments = [];
    renderAttachmentPreview();
    if (done && done.session_id && document.getElementById("sessions-list").children.length === 0) {
      loadSessions(agentId);
    }
  } catch (error) {
    live.el.classList.remove("streaming");
    live.md.innerHTML = renderMarkdown("送信中にエラーが発生しました。" + (error.message ? ` ${error.message}` : ""));
  } finally {
    showTypingIndicator(false);
  }
}

async function sendSquadMessage(squadId, text) {
  if (!text.trim()) return;

  appendSquadUserMessage(text);
  showSquadTypingIndicator(true);

  const container = document.getElementById("squad-chat-messages");
  const live = appendSquadAgentMessage("生成中...");
  let acc = "";

  try {
    const payload = {
      message: text,
      session_id: currentSquadSessionId,
      attachment_ids: pendingSquadAttachments.map((attachment) => attachment.id),
    };

    const done = await streamChat(
      `/squads/${encodeURIComponent(squadId)}/chat`,
      payload,
      (chunk) => {
        acc += chunk;
        live.md.innerHTML = renderMarkdown(acc || "生成中...");
        smartScroll(container);
      },
      (err) => {
        acc = err;
        live.md.innerHTML = renderMarkdown(err);
      }
    );

    if (done && done.session_id) currentSquadSessionId = done.session_id;
    if (!acc.trim() && done && done.content) acc = done.content;
    live.el.classList.remove("streaming");
    live.md.innerHTML = renderMarkdown(acc.trim() || "(応答がありません)");
    smartScroll(container);

    pendingSquadAttachments = [];
    renderSquadAttachmentPreview();
    if (done && done.session_id && document.getElementById("squad-sessions-list").children.length === 0) {
      loadSquadSessions(squadId);
    }
  } catch (error) {
    live.el.classList.remove("streaming");
    live.md.innerHTML = renderMarkdown("送信中にエラーが発生しました。" + (error.message ? ` ${error.message}` : ""));
  } finally {
    showSquadTypingIndicator(false);
  }
}

function showTypingIndicator(show) {
  const indicator = document.getElementById("typing-indicator");
  if (!indicator) return;
  indicator.classList.toggle("hidden", !show);
}

function showSquadTypingIndicator(show) {
  const indicator = document.getElementById("squad-typing-indicator");
  if (!indicator) return;
  indicator.classList.toggle("hidden", !show);
}

async function loadSessions(agentId) {
  const list = document.getElementById("sessions-list");
  if (!list) return;
  list.innerHTML = "";

  try {
    const sessions = await api(`/agents/${encodeURIComponent(agentId)}/sessions`);

    if (!sessions.length) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "セッションがありません。";
      list.appendChild(empty);
      return;
    }

    sessions.forEach((session) => {
      const el = document.createElement("div");
      el.className = "session-item";
      el.dataset.sessionId = session.id;

      const titleEl = document.createElement("div");
      titleEl.className = "session-item-title";
      titleEl.textContent = sessionTitleLabel(session);

      const timeEl = document.createElement("div");
      timeEl.className = "session-item-time";
      timeEl.textContent = formatDateTime(session.updated_at || session.created_at);

      el.appendChild(titleEl);
      el.appendChild(timeEl);

      el.addEventListener("click", async () => {
        currentSessionId = session.id;
        const active = list.querySelector(".session-item.active");
        if (active) active.classList.remove("active");
        el.classList.add("active");
        await loadSessionMessages(agentId, session.id);
      });
      list.appendChild(el);
    });
  } catch {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "セッションの取得に失敗しました。";
    list.appendChild(empty);
  }
}

async function loadSessionMessages(agentId, sessionId) {
  const container = document.getElementById("chat-messages");
  if (!container || !sessionId) return;
  container.innerHTML = "";

  try {
    const messages = await api(`/agents/${encodeURIComponent(agentId)}/sessions/${encodeURIComponent(sessionId)}/messages`);
    messages.forEach((message) => {
      if (message.role === "user") {
        appendUserMessage(message.content);
      } else {
        appendAgentMessage(message.content);
      }
    });
  } catch {
    appendAgentMessage("セッションの読み込みに失敗しました。");
  }
}

async function loadSquadSessionMessages(sessionId) {
  const container = document.getElementById("squad-chat-messages");
  if (!container || !sessionId || !currentSquadId) return;
  container.innerHTML = "";

  try {
    const messages = await api(`/squads/${encodeURIComponent(currentSquadId)}/sessions/${encodeURIComponent(sessionId)}/messages`);
    messages.forEach((message) => {
      if (message.role === "user") {
        appendSquadUserMessage(message.content);
      } else {
        appendSquadAgentMessage(message.content);
      }
    });
  } catch {
    appendSquadAgentMessage("セッションの読み込みに失敗しました。");
  }
}

async function loadSquadSessions(squadId) {
  const list = document.getElementById("squad-sessions-list");
  if (!list) return;
  list.innerHTML = "";

  try {
    const sessions = await api(`/squads/${encodeURIComponent(squadId)}/sessions`);

    if (!sessions.length) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = "セッションがありません。";
      list.appendChild(empty);
      return;
    }

    sessions.forEach((session) => {
      const el = document.createElement("div");
      el.className = "session-item";
      el.dataset.sessionId = session.id;

      const titleEl = document.createElement("div");
      titleEl.className = "session-item-title";
      titleEl.textContent = sessionTitleLabel(session);

      const timeEl = document.createElement("div");
      timeEl.className = "session-item-time";
      timeEl.textContent = formatDateTime(session.updated_at || session.created_at);

      el.appendChild(titleEl);
      el.appendChild(timeEl);

      el.addEventListener("click", () => {
        currentSquadSessionId = session.id;
        const active = list.querySelector(".session-item.active");
        if (active) active.classList.remove("active");
        el.classList.add("active");
        loadSquadSessionMessages(session.id);
      });
      list.appendChild(el);
    });
  } catch {
    const empty = document.createElement("p");
    empty.className = "empty";
    empty.textContent = "セッションの取得に失敗しました。";
    list.appendChild(empty);
  }
}

async function openAgentSettingsModal(agent) {
  currentAgent = agent || currentAgent;
  const modal = document.getElementById("agent-settings-modal");
  if (!modal) return;

  await loadAgentSettingsModals();

  if (currentAgent) {
    const form = document.getElementById("agent-settings-form");
    form.title.value = currentAgent.title || "";
    form.description.value = currentAgent.description || "";
    form.model_provider.value = currentAgent.model_provider || "openai";
    form.model_id.value = currentAgent.model_id || "";
    form.visibility.value = currentAgent.visibility || "private";
    form.system_prompt.value = currentAgent.system_prompt || "";
    form.workspace.value = currentAgent.workspace_config ? JSON.stringify(currentAgent.workspace_config, null, 2) : "";
    form.icon.value = currentAgent.icon || "";

    buildToolModalList("agent-settings-tools-list", (currentAgent.tools_config?.tools || []).map(String));
    updateAgentSettingsToolsLabel();

    const skillsModal = document.getElementById("agent-settings-skills-modal");
    const mcpsModal = document.getElementById("agent-settings-mcps-modal");
    const skillCheckboxes = skillsModal ? skillsModal.querySelectorAll('input[name="agent_skill_ids"]') : [];
    const mcpCheckboxes = mcpsModal ? mcpsModal.querySelectorAll('input[name="agent_mcp_server_ids"]') : [];

    skillCheckboxes.forEach((checkbox) => {
      checkbox.checked = (currentAgent.skill_ids || []).includes(checkbox.value);
    });

    mcpCheckboxes.forEach((checkbox) => {
      checkbox.checked = (currentAgent.mcp_server_ids || []).includes(checkbox.value);
    });

    updateAgentSettingsSelectionLabels();
  }

  modal.classList.remove("hidden");
}

function bindAgentSettingsEvents() {
  document.getElementById("open-agent-settings-skills-btn")?.addEventListener("click", () => {
    document.getElementById("agent-settings-skills-modal")?.classList.remove("hidden");
  });

  document.getElementById("open-agent-settings-mcps-btn")?.addEventListener("click", () => {
    document.getElementById("agent-settings-mcps-modal")?.classList.remove("hidden");
  });

  document.getElementById("open-agent-settings-tools-btn")?.addEventListener("click", () => {
    buildToolModalList("agent-settings-tools-list", (currentAgent?.tools_config?.tools || []).map(String));
    updateAgentSettingsToolsLabel();
    document.getElementById("agent-settings-tools-modal")?.classList.remove("hidden");
  });

  const skillsSearch = document.getElementById("agent-settings-skills-search");
  const mcpsSearch = document.getElementById("agent-settings-mcps-search");
  const toolsSearch = document.getElementById("agent-settings-tools-search");
  skillsSearch?.addEventListener("input", (e) => filterModalList("agent-settings-skills-list", e.target.value));
  mcpsSearch?.addEventListener("input", (e) => filterModalList("agent-settings-mcps-list", e.target.value));
  toolsSearch?.addEventListener("input", (e) => filterModalList("agent-settings-tools-list", e.target.value));

  document.querySelectorAll("#agent-settings-modal [data-modal-close]")?.forEach((el) => {
    el.addEventListener("click", () => {
      document.getElementById("agent-settings-modal")?.classList.add("hidden");
    });
  });

  document.querySelectorAll("#agent-settings-skills-modal [data-modal-close]")?.forEach((el) => {
    el.addEventListener("click", () => {
      document.getElementById("agent-settings-skills-modal")?.classList.add("hidden");
      updateAgentSettingsSelectionLabels();
    });
  });

  document.querySelectorAll("#agent-settings-mcps-modal [data-modal-close]")?.forEach((el) => {
    el.addEventListener("click", () => {
      document.getElementById("agent-settings-mcps-modal")?.classList.add("hidden");
      updateAgentSettingsSelectionLabels();
    });
  });

  document.querySelectorAll("#agent-settings-tools-modal [data-modal-close]")?.forEach((el) => {
    el.addEventListener("click", () => {
      document.getElementById("agent-settings-tools-modal")?.classList.add("hidden");
      updateAgentSettingsToolsLabel();
    });
  });

  document.getElementById("agent-settings-tools-save")?.addEventListener("click", () => {
    document.getElementById("agent-settings-tools-modal")?.classList.add("hidden");
    updateAgentSettingsToolsLabel();
  });

  document.getElementById("agent-settings-save")?.addEventListener("click", async () => {
    if (!currentAgent) return;

    const form = document.getElementById("agent-settings-form");
    const skillIds = Array.from(document.querySelectorAll('input[name="agent_skill_ids"]:checked')).map((i) => i.value);
    const mcpServerIds = Array.from(document.querySelectorAll('input[name="agent_mcp_server_ids"]:checked')).map((i) => i.value);
    const toolKeys = readToolToggleList("agent-settings-tools-list");

    const workspaceRaw = String(form.workspace?.value || "").trim();
    let workspaceConfig = {};
    try { workspaceConfig = workspaceRaw ? JSON.parse(workspaceRaw) : {}; } catch { workspaceConfig = { raw: workspaceRaw }; }
    if (!Object.keys(workspaceConfig).length) workspaceConfig = { target_directory: "./output" };

    try {
      await api(`/agents/${encodeURIComponent(currentAgent.id)}`, {
        method: "PATCH",
        body: JSON.stringify({
          title: String(form.title.value || "").trim(),
          description: String(form.description.value || "").trim(),
          system_prompt: String(form.system_prompt.value || "").trim(),
          model_provider: String(form.model_provider.value || "openai").trim(),
          model_id: String(form.model_id.value || "").trim(),
          visibility: String(form.visibility.value || "private").trim(),
          skill_ids: skillIds,
          mcp_server_id: mcpServerIds.length ? mcpServerIds[0] : (currentAgent.mcp_server_id || null),
          mcp_server_ids: mcpServerIds,
          tools_config: { tools: toolKeys },
          workspace_config: workspaceConfig,
          icon: String(form.icon?.value || "").trim() || null,
        }),
      });

      currentAgent.icon = String(form.icon?.value || "").trim() || null;
      applyIcon(currentAgent.icon);

      document.getElementById("agent-settings-modal")?.classList.add("hidden");
      document.getElementById("agent-settings-skills-modal")?.classList.add("hidden");
      document.getElementById("agent-settings-mcps-modal")?.classList.add("hidden");
      await loadAgents();
    } catch (err) {
      console.error("Failed to save agent settings", err);
    }
  });

  document.getElementById("delete-agent-btn")?.addEventListener("click", async () => {
    if (!currentAgentId) return;
    if (!confirm("このエージェントを削除しますか？")) return;

    try {
      await api(`/agents/${encodeURIComponent(currentAgentId)}`, { method: "DELETE" });
      navigateToAgents();
    } catch (err) {
      alert("エージェントの削除に失敗しました。");
    }
  });
}

async function openSquadSettingsModal(squad) {
  currentSquad = squad || currentSquad;
  const modal = document.getElementById("squad-settings-modal");
  if (!modal) return;

  if (!currentSquad || !Array.isArray(currentSquad.members)) {
    try {
      currentSquad = await api(`/squads/${encodeURIComponent(currentSquadId || currentSquad?.id)}`);
    } catch {
      currentSquad = { id: currentSquadId || currentSquad?.id, members: [] };
    }
  }
  if (!currentSquad) return;

  const form = document.getElementById("squad-settings-form");
  form.name.value = currentSquad.name || "";
  form.description.value = currentSquad.description || "";
  modal.dataset.squadId = currentSquad.id;

  const leaderSelect = document.getElementById("squad-settings-leader-select");
  const teamList = document.getElementById("squad-settings-team-list");
  teamList.innerHTML = "";

  try {
    const agents = await api("/agents");
    leaderSelect.innerHTML = '<option value="">リーダーエージェントを選択</option>';
    agents.forEach((agent) => {
      const option = document.createElement("option");
      option.value = agent.id;
      option.textContent = agent.title;
      leaderSelect.appendChild(option);
    });
    leaderSelect.value = currentSquad.leader_agent_id || "";

    const teamModalList = document.getElementById("squad-settings-team-modal-list");
    teamModalList.innerHTML = "";
    agents.forEach((agent) => {
      const row = document.createElement("label");
      row.className = "modal-item";
      row.innerHTML = `
        <div class="switch">
          <input type="checkbox" name="squad_settings_team_agent_ids" value="${agent.id}" form="squad-settings-form">
          <span class="switch-track"></span>
        </div>
        <div>
          <div class="modal-item-title">${escapeHtml(agent.title)}</div>
          <div class="modal-item-desc">${escapeHtml(agent.model_provider || "")} / ${escapeHtml(agent.model_id || "")}</div>
        </div>
      `;
      teamModalList.appendChild(row);
    });

    const memberAgentIds = (currentSquad.members || []).map((member) => member.agent_id).filter(Boolean);
    memberAgentIds.forEach((agentId) => {
      const checkbox = teamModalList.querySelector(`input[name="squad_settings_team_agent_ids"][value="${agentId}"]`);
      if (checkbox) checkbox.checked = true;
    });
    updateSquadSettingsTeamChips();
  } catch {
    // ignore
  }

  modal.classList.remove("hidden");
}

function updateSquadSettingsSelectionLabels() {}

function loadSquadSettingsModals() {}

function bindSquadSettingsEvents() {
  const form = document.getElementById("squad-settings-form");
  const saveBtn = document.getElementById("squad-settings-save");

  // The cancel button, the X button, and the overlay all carry data-modal-close.
  const squadSettingsModal = document.getElementById("squad-settings-modal");
  squadSettingsModal?.querySelectorAll("[data-modal-close]").forEach((el) => {
    el.addEventListener("click", (e) => {
      if (e.target.closest("#squad-settings-team-select-modal")) return;
      squadSettingsModal.classList.add("hidden");
    });
  });

  form?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!currentSquad) return;

    const teamAgentIds = Array.from(document.querySelectorAll('input[name="squad_settings_team_agent_ids"]:checked')).map((i) => i.value);
    const squadId = document.getElementById("squad-settings-modal")?.dataset?.squadId || currentSquad?.id || currentSquadId;

    try {
      await api(`/squads/${encodeURIComponent(squadId)}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: String(form.name.value || "").trim(),
          description: String(form.description.value || "").trim(),
          leader_agent_id: String(form.leader_agent_id.value || "").trim() || null,
          team_agent_ids: teamAgentIds,
        }),
      });

      currentSquad = null;
      document.getElementById("squad-settings-modal")?.classList.add("hidden");
      document.getElementById("squad-settings-team-select-modal")?.classList.add("hidden");
      await loadSquads();
    } catch (err) {
      console.error("Failed to save squad settings", err);
    }
  });

  saveBtn?.addEventListener("click", () => {
    form?.requestSubmit();
  });

  document.getElementById("open-squad-settings-team-modal-btn")?.addEventListener("click", () => {
    document.getElementById("squad-settings-team-select-modal")?.classList.remove("hidden");
  });

  const teamSearch = document.getElementById("squad-settings-team-modal-search");
  teamSearch?.addEventListener("input", (e) => filterModalList("squad-settings-team-modal-list", e.target.value));

  document.querySelectorAll("#squad-settings-team-select-modal [data-modal-close]")?.forEach((el) => {
    el.addEventListener("click", () => {
      document.getElementById("squad-settings-team-select-modal")?.classList.add("hidden");
      updateSquadSettingsTeamChips();
    });
  });

  document.getElementById("squad-settings-team-modal-save")?.addEventListener("click", () => {
    document.getElementById("squad-settings-team-select-modal")?.classList.add("hidden");
    updateSquadSettingsTeamChips();
  });

  document.getElementById("delete-squad-btn")?.addEventListener("click", async () => {
    if (!currentSquadId) return;
    if (!confirm("このスクワッドを削除しますか？")) return;
    try {
      await api(`/squads/${encodeURIComponent(currentSquadId)}`, { method: "DELETE" });
      navigateToSquads();
    } catch (err) {
      alert("スクワッドの削除に失敗しました。");
    }
  });
}

function updateSquadSettingsTeamChips() {
  const selected = Array.from(document.querySelectorAll('input[name="squad_settings_team_agent_ids"]:checked'));
  const teamList = document.getElementById("squad-settings-team-list");
  if (!teamList) return;

  teamList.innerHTML = "";
  selected.forEach((input) => {
    const chip = document.createElement("div");
    chip.className = "selection-chip";
    chip.textContent = input.closest(".modal-item")?.querySelector(".modal-item-title")?.textContent || input.value;
    teamList.appendChild(chip);
  });
}

function updateAgentSettingsToolsLabel() {
  const btn = document.getElementById("open-agent-settings-tools-btn");
  if (!btn) return;
  const selected = readToolToggleList("agent-settings-tools-list");
  btn.textContent = selected.length ? `選択済み: ${selected.length}` : "Toolsを選択";
}

function updateAgentSettingsSelectionLabels() {
  const modal = document.getElementById("agent-settings-modal");
  if (!modal) return;
  const skillBtn = document.getElementById("open-agent-settings-skills-btn");
  const mcpBtn = document.getElementById("open-agent-settings-mcps-btn");
  const selectedSkills = Array.from(modal.querySelectorAll('input[name="agent_skill_ids"]:checked')).map((i) => i.closest('.modal-item')?.querySelector('.modal-item-title')?.textContent || i.value);
  const selectedMcps = Array.from(modal.querySelectorAll('input[name="agent_mcp_server_ids"]:checked')).map((i) => i.closest('.modal-item')?.querySelector('.modal-item-title')?.textContent || i.value);

  if (skillBtn) {
    skillBtn.textContent = selectedSkills.length ? `選択済み: ${selectedSkills.length}` : "Skillsを選択";
  }
  if (mcpBtn) {
    mcpBtn.textContent = selectedMcps.length ? `選択済み: ${selectedMcps.length}` : "MCPを選択";
  }
}

async function loadAgentSettingsModals() {
  const modal = document.getElementById("agent-settings-modal");
  if (!modal) return;

  const skillsListContainer = document.getElementById("agent-settings-skills-list");
  const mcpsListContainer = document.getElementById("agent-settings-mcps-list");

  if (skillsListContainer) {
    skillsListContainer.innerHTML = "";
    const skills = await api("/skills");
    skills.forEach((skill) => {
      const id = String(skill.id);
      const row = document.createElement("label");
      row.className = "modal-item";
      row.innerHTML = `
        <div class="switch">
          <input type="checkbox" name="agent_skill_ids" value="${id}" form="agent-settings-form">
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
          <input type="checkbox" name="agent_mcp_server_ids" value="${id}" form="agent-settings-form">
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
}
