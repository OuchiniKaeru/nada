async function loadSquads() {
  const list = document.getElementById("squads-list");
  if (!list) return;
  list.innerHTML = "";

  try {
    const squads = await api("/squads");
    if (!squads.length) {
      list.innerHTML = `<p class="empty">スクワッドがありません。</p>`;
      return;
    }

    squads.forEach((squad) => {
      const item = document.createElement("div");
      item.className = "list-item";
      const iconHtml = squad.icon ? `<div class="list-item-icon" aria-hidden="true">${escapeHtml(squad.icon)}</div>` : "";
      item.innerHTML = `
        ${iconHtml}
        <div class="list-item-body">
          <div class="list-item-title">${escapeHtml(squad.name)}</div>
          <div class="list-item-meta">${escapeHtml(squad.description || "")}</div>
        </div>
      `;
      item.addEventListener("click", () => openSquadChat(squad.id, squad.name, squad));
      list.appendChild(item);
    });
  } catch (error) {
    list.innerHTML = `<p class="empty">スクワッドの取得に失敗しました: ${escapeHtml(error.message)}</p>`;
  }
}

async function loadSquadCreateModal() {
  const leaderSelect = document.getElementById("squad-leader-select");
  const teamModalList = document.getElementById("team-modal-list");
  const teamList = document.getElementById("squad-team-list");
  if (!leaderSelect || !teamModalList || !teamList) return;

  leaderSelect.innerHTML = '<option value="">リーダーエージェントを選択</option>';
  teamList.innerHTML = "";

  try {
    const agents = await api("/agents");
    agents.forEach((agent) => {
      const leaderOption = document.createElement("option");
      leaderOption.value = agent.id;
      leaderOption.textContent = agent.title;
      leaderSelect.appendChild(leaderOption);
    });

    teamModalList.innerHTML = "";
    agents.forEach((agent) => {
      const row = document.createElement("label");
      row.className = "modal-item";
      row.innerHTML = `
        <div class="switch">
          <input type="checkbox" name="team_agent_ids" value="${agent.id}" form="squad-create-form">
          <span class="switch-track"></span>
        </div>
        <div>
          <div class="modal-item-title">${escapeHtml(agent.title)}</div>
          <div class="modal-item-desc">${escapeHtml(agent.model_provider || "")} / ${escapeHtml(agent.model_id || "")}</div>
        </div>
      `;
      teamModalList.appendChild(row);
    });
  } catch (error) {
    console.error("エージェント取得失敗", error);
  }
}

function openCreateSquadModal() {
  const modal = document.getElementById("squad-create-modal");
  if (!modal) return;
  loadSquadCreateModal();
  modal.classList.remove("hidden");
}

function bindSquadEvents() {
  document.getElementById("open-team-modal-btn")?.addEventListener("click", () => {
    document.getElementById("team-select-modal")?.classList.remove("hidden");
  });

  const teamSearch = document.getElementById("team-modal-search");
  teamSearch?.addEventListener("input", (e) => filterModalList("team-modal-list", e.target.value));

  document.querySelectorAll("#team-select-modal [data-modal-close]")?.forEach((el) => {
    el.addEventListener("click", () => {
      document.getElementById("team-select-modal")?.classList.add("hidden");
      updateTeamSelectionLabels();
    });
  });

  document.getElementById("team-modal-save")?.addEventListener("click", () => {
    document.getElementById("team-select-modal")?.classList.add("hidden");
    updateTeamSelectionLabels();
  });

  // Close the squad-create modal from its cancel / X buttons. The nested
  // team-select-modal lives INSIDE squad-create-modal, so its own close
  // buttons must not close the outer modal too.
  document.querySelectorAll("#squad-create-modal [data-modal-close]")?.forEach((el) => {
    el.addEventListener("click", (e) => {
      if (e.target.closest("#team-select-modal")) return;
      document.getElementById("squad-create-modal")?.classList.add("hidden");
    });
  });
}

function updateTeamSelectionLabels() {
  const selected = Array.from(document.querySelectorAll('input[name="team_agent_ids"]:checked'));
  const teamList = document.getElementById("squad-team-list");
  if (!teamList) return;

  teamList.innerHTML = "";
  selected.forEach((input) => {
    const chip = document.createElement("div");
    chip.className = "selection-chip";
    chip.textContent = input.closest(".modal-item")?.querySelector(".modal-item-title")?.textContent || input.value;
    teamList.appendChild(chip);
  });
}

function bindSquadForm() {
  const form = document.getElementById("squad-create-form");
  const error = document.getElementById("squad-create-error");
  if (!form || !error) return;

  const descriptionInput = form.querySelector('textarea[name="description"]');
  const countEl = document.getElementById("squad-description-count");
  descriptionInput?.addEventListener("input", () => {
    countEl.textContent = `${descriptionInput.value.length} / 255`;
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    error.classList.add("hidden");

    try {
      const formData = new FormData(form);
      const teamAgentIds = Array.from(
        form.querySelectorAll('input[name="team_agent_ids"]:checked')
      ).map((input) => input.value);

      await api("/squads", {
        method: "POST",
        body: JSON.stringify({
          name: String(formData.get("name") || "").trim(),
          description: String(formData.get("description") || "").trim(),
          system_prompt: String(formData.get("system_prompt") || "").trim(),
          model_provider: String(formData.get("model_provider") || "openai").trim(),
          model_id: String(formData.get("model_id") || "gpt-4o").trim(),
          leader_agent_id: String(formData.get("leader_agent_id") || "").trim() || null,
          team_agent_ids: teamAgentIds,
          visibility: String(formData.get("visibility") || "private").trim(),
        }),
      });

      form.reset();
      document.getElementById("squad-description-count").textContent = "0 / 255";
      document.querySelector("#squad-create-modal [data-modal-close]")?.click();
      loadSquads();
    } catch (err) {
      error.textContent = err.message;
      error.classList.remove("hidden");
    }
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bindSquadForm);
} else {
  bindSquadForm();
}
