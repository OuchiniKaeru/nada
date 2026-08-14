async function loadSkills() {
  const list = document.getElementById("skills-list");
  if (!list) return;
  list.innerHTML = "";

  try {
    const skills = await api("/skills");
    if (!skills.length) {
      list.innerHTML = `<p class="empty">Skillがありません。</p>`;
      return;
    }

    skills.forEach((skill) => {
      const item = document.createElement("div");
      item.className = "list-item";
      const iconHtml = skill.icon ? `<div class="list-item-icon" aria-hidden="true">${escapeHtml(skill.icon)}</div>` : "";
      item.innerHTML = `
        ${iconHtml}
        <div class="list-item-body">
          <div class="list-item-title">${escapeHtml(skill.name)}</div>
          <div class="list-item-meta">${escapeHtml(skill.description)}</div>
        </div>
      `;
      item.addEventListener("click", () => {
        window.location.hash = `#skills-detail/${skill.id}`;
      });
      list.appendChild(item);
    });
  } catch (error) {
    list.innerHTML = `<p class="empty">Skillの取得に失敗しました: ${escapeHtml(error.message)}</p>`;
  }
}

async function loadSkillDetail() {
  const container = document.getElementById("skill-detail-content");
  const form = document.getElementById("skill-edit-form");
  const error = document.getElementById("skill-error");
  if (!container || !form) return;

  const id = getRouteId("skills-detail");
  if (!id) {
    container.innerHTML = `<p class="empty">Skill IDが指定されていません。</p>`;
    return;
  }

  try {
    const skill = await api(`/skills/${encodeURIComponent(id)}`);
    form.classList.add("hidden");
    error.classList.add("hidden");
    container.innerHTML = `
      <h3>${escapeHtml(skill.name)}</h3>
      <p>${escapeHtml(skill.description)}</p>
      <pre class="detail-code">${escapeHtml(skill.content)}</pre>
    `;
  } catch (error) {
    container.innerHTML = `<p class="empty">Skillの取得に失敗しました: ${escapeHtml(error.message)}</p>`;
  }
}

function bindSkillForm() {
  const form = document.getElementById("skill-edit-form");
  const error = document.getElementById("skill-error");
  if (!form || !error) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.classList.add("hidden");

    const id = getRouteId("skills-detail");
    if (!id) return;

    try {
      const data = new FormData(form);
      await api(`/skills/${encodeURIComponent(id)}`, {
        method: "PATCH",
        body: JSON.stringify({
          name: String(data.get("name") || "").trim(),
          description: String(data.get("description") || "").trim(),
          content: String(data.get("content") || "").trim(),
          visibility: String(data.get("visibility") || "private").trim(),
        }),
      });

      form.classList.add("hidden");
      await loadSkillDetail();
    } catch (err) {
      error.textContent = err.message;
      error.classList.remove("hidden");
    }
  });
}

function bindSkillCreateForm() {
  const form = document.getElementById("skill-create-form");
  const error = document.getElementById("skill-create-error");
  if (!form || !error) return;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.classList.add("hidden");

    try {
      const data = new FormData(form);
      await api("/skills", {
        method: "POST",
        body: JSON.stringify({
          name: String(data.get("name") || "").trim(),
          description: String(data.get("description") || "").trim(),
          content: String(data.get("content") || "").trim(),
          visibility: String(data.get("visibility") || "private").trim(),
        }),
      });

      form.reset();
      window.location.hash = "#skills-list";
    } catch (err) {
      error.textContent = err.message;
      error.classList.remove("hidden");
    }
  });
}

async function deleteCurrentSkill() {
  const id = getRouteId("skills-detail");
  if (!id) return;

  if (!confirm("このSkillを削除しますか？")) return;

  try {
    await api(`/skills/${encodeURIComponent(id)}`, { method: "DELETE" });
    window.location.hash = "#skills-list";
  } catch (err) {
    const error = document.getElementById("skill-error");
    if (error) {
      error.textContent = err.message;
      error.classList.remove("hidden");
    }
  }
}

function bindSkillDetailEvents() {
  const editBtn = document.getElementById("edit-skill-btn");
  const deleteBtn = document.getElementById("delete-skill-btn");
  const cancelBtn = document.getElementById("cancel-skill-edit");
  const form = document.getElementById("skill-edit-form");
  const container = document.getElementById("skill-detail-content");
  const error = document.getElementById("skill-error");
  if (!editBtn || !deleteBtn || !cancelBtn || !form || !container || !error) return;

  editBtn.addEventListener("click", async () => {
    const id = getRouteId("skills-detail");
    if (!id) return;

    try {
      const skill = await api(`/skills/${encodeURIComponent(id)}`);
      form.name.value = skill.name || "";
      form.description.value = skill.description || "";
      form.content.value = skill.content || "";
      form.visibility.value = skill.visibility || "private";
      form.classList.remove("hidden");
      container.classList.add("hidden");
      error.classList.add("hidden");
    } catch (err) {
      error.textContent = err.message;
      error.classList.remove("hidden");
    }
  });

  deleteBtn.addEventListener("click", deleteCurrentSkill);

  cancelBtn.addEventListener("click", () => {
    form.classList.add("hidden");
    container.classList.remove("hidden");
    error.classList.add("hidden");
  });
}
