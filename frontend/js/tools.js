const TOOL_DEFINITIONS = [
  { key: "WebSearchTools", label: "Web Search", icon: "🌐", kind: "toolkit" },
  { key: "PandasTools", label: "Pandas", icon: "📊", kind: "toolkit" },
  { key: "ShellTools", label: "Shell", icon: "🖥️", kind: "toolkit" },
  { key: "LocalFileSystemTools", label: "Local File System", icon: "📁", kind: "toolkit" },
  { key: "SleepTools", label: "Sleep", icon: "😴", kind: "toolkit" },
  { key: "PythonTools", label: "Python", icon: "🐍", kind: "toolkit" },
  { key: "NanoBananaTools", label: "Nano Banana", icon: "🍌", kind: "toolkit" },
  { key: "SalesforceTools", label: "Salesforce", icon: "☁️", kind: "toolkit" },
  { key: "WebBrowserTools", label: "Web Browser Tools", icon: "🌍", kind: "toolkit" },
  { key: "GitLabTools", label: "GitLab", icon: "🦊", kind: "toolkit" },
];

function renderToolsList() {
  const container = document.getElementById("tools-list");
  if (!container) return;

  container.innerHTML = "";
  TOOL_DEFINITIONS.forEach((tool) => {
    const item = document.createElement("div");
    item.className = "list-item";
    item.innerHTML = `
      <div class="list-item-icon" aria-hidden="true">${escapeHtml(tool.icon)}</div>
      <div class="list-item-body">
        <div class="list-item-title">${escapeHtml(tool.label)}</div>
        <div class="list-item-meta">${escapeHtml(tool.key)}</div>
      </div>
    `;
    container.appendChild(item);
  });
}

function buildToolToggleList(containerId, selectedKeys = []) {
  const container = document.getElementById(containerId);
  if (!container) return;

  container.innerHTML = "";
  TOOL_DEFINITIONS.forEach((tool) => {
    const row = document.createElement("label");
    row.className = "tool-toggle-item";
    row.innerHTML = `
      <span aria-hidden="true">${escapeHtml(tool.icon)}</span>
      <span>${escapeHtml(tool.label)}</span>
      <span class="switch">
        <input type="checkbox" value="${escapeHtml(tool.key)}" ${selectedKeys.includes(tool.key) ? 'checked' : ''}>
        <span class="switch-track"></span>
      </span>
    `;
    container.appendChild(row);
  });
}

function readToolToggleList(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return [];
  return Array.from(container.querySelectorAll('input[type="checkbox"]:checked')).map((input) => input.value);
}

function buildToolModalList(containerId, selectedKeys = []) {
  const container = document.getElementById(containerId);
  if (!container) return;

  container.innerHTML = "";
  TOOL_DEFINITIONS.forEach((tool) => {
    const row = document.createElement("label");
    row.className = "modal-item";
    row.innerHTML = `
      <div class="switch">
        <input type="checkbox" value="${escapeHtml(tool.key)}" ${selectedKeys.includes(tool.key) ? "checked" : ""}>
        <span class="switch-track"></span>
      </div>
      <div>
        <div class="modal-item-title">${escapeHtml(tool.icon)} ${escapeHtml(tool.label)}</div>
        <div class="modal-item-desc">${escapeHtml(tool.key)}</div>
      </div>
    `;
    container.appendChild(row);
  });
}
