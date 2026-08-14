let chartMode = "tokens";
let dailyCache = [];

function fmtDuration(ms) {
  if (ms === null || ms === undefined || isNaN(ms)) return "00:00:00";
  const total = Math.max(0, Math.floor(Number(ms) / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(h)}:${pad(m)}:${pad(s)}`;
}

function fmtNumber(n) {
  n = Number(n) || 0;
  if (n >= 1e9) return (n / 1e9).toFixed(2) + "B";
  if (n >= 1e6) return (n / 1e6).toFixed(2) + "M";
  if (n >= 1e3) return (n / 1e3).toFixed(1) + "K";
  return String(Math.round(n));
}

function fmtMoney(x) {
  return "$" + Number(x || 0).toFixed(4);
}

async function loadDashboard() {
  try {
    const [overview, daily, models, prices] = await Promise.all([
      api("/metrics/overview"),
      api("/metrics/daily"),
      api("/metrics/models"),
      api("/metrics/prices"),
    ]);

    document.getElementById("metric-cost").textContent = fmtMoney(overview.cost_total);
    document.getElementById("metric-tokens").textContent = fmtNumber(overview.tokens_total);
    document.getElementById("metric-duration").textContent = fmtDuration(overview.duration_total);
    document.getElementById("metric-count").textContent = String(overview.executions_count);

    dailyCache = Array.isArray(daily) ? daily : [];
    renderUsageTable(Array.isArray(models) ? models : []);
    renderPricesTable(Array.isArray(prices) ? prices : []);
    bindChartTabs();
    drawChart();
  } catch (err) {
    console.error("Dashboard load failed", err);
  }
}

function renderUsageTable(models) {
  const tbody = document.querySelector("#models-usage-table tbody");
  if (!tbody) return;
  tbody.innerHTML = "";
  if (!models.length) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty">データがありません。</td></tr>`;
    return;
  }
  models.forEach((m) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(m.model || "-")}</td>
      <td class="num">${fmtNumber(m.input_tokens)}</td>
      <td class="num">${fmtNumber(m.output_tokens)}</td>
      <td class="num">${fmtNumber(m.total_tokens)}</td>
      <td class="num">${fmtMoney(m.cost)}</td>
      <td class="num">${fmtNumber(m.count)}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderPricesTable(prices) {
  const tbody = document.querySelector("#model-prices-table tbody");
  if (!tbody) return;
  tbody.innerHTML = "";
  if (!prices.length) {
    tbody.innerHTML = `<tr><td colspan="4" class="empty">価格マスターがありません。</td></tr>`;
    return;
  }
  prices.forEach((p) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(p.provider || "-")}</td>
      <td>${escapeHtml(p.model_id || "-")}</td>
      <td class="num">$${Number(p.input_price || 0).toFixed(4)}</td>
      <td class="num">$${Number(p.output_price || 0).toFixed(4)}</td>
    `;
    tbody.appendChild(tr);
  });
}

function bindChartTabs() {
  const tokensBtn = document.getElementById("chart-mode-tokens");
  const costBtn = document.getElementById("chart-mode-cost");
  if (!tokensBtn || !costBtn) return;
  const setActive = () => {
    tokensBtn.classList.toggle("active", chartMode === "tokens");
    costBtn.classList.toggle("active", chartMode === "cost");
  };
  tokensBtn.onclick = () => { chartMode = "tokens"; setActive(); drawChart(); };
  costBtn.onclick = () => { chartMode = "cost"; setActive(); drawChart(); };
}

function drawChart() {
  const canvas = document.getElementById("usage-chart");
  if (!canvas) return;
  const container = canvas.parentElement;
  const cssW = Math.max(280, container.clientWidth - 24);
  const cssH = 280;
  const dpr = window.devicePixelRatio || 1;
  canvas.width = cssW * dpr;
  canvas.height = cssH * dpr;
  canvas.style.width = cssW + "px";
  canvas.style.height = cssH + "px";

  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, cssW, cssH);

  const data = Array.isArray(dailyCache) ? dailyCache : [];
  const accent = "#66fcf1";
  const muted = "#45a29e";

  ctx.font = "11px sans-serif";

  if (!data.length) {
    ctx.fillStyle = "#7a7d83";
    ctx.textAlign = "center";
    ctx.fillText("データがありません", cssW / 2, cssH / 2);
    return;
  }

  const values = data.map((d) =>
    chartMode === "tokens" ? Number(d.tokens || 0) : Number(d.cost || 0)
  );
  const max = Math.max(1, ...values);

  const padL = 46;
  const padB = 26;
  const padT = 14;
  const plotW = cssW - padL - 12;
  const plotH = cssH - padT - padB;
  const step = plotW / data.length;

  // grid + y labels
  ctx.strokeStyle = "#1f2833";
  ctx.fillStyle = "#7a7d83";
  ctx.textAlign = "right";
  const gridLines = 4;
  for (let i = 0; i <= gridLines; i++) {
    const val = (max / gridLines) * i;
    const y = padT + plotH - (plotH * i) / gridLines;
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(cssW - 8, y);
    ctx.stroke();
    ctx.fillText(chartMode === "cost" ? "$" + val.toFixed(4) : fmtNumber(val), padL - 6, y + 4);
  }

  // bars
  data.forEach((d, i) => {
    const v = values[i];
    const h = (v / max) * (plotH - 6);
    const x = padL + i * step + 4;
    const barW = Math.max(4, step - 8);
    const y = padT + plotH - h;
    ctx.fillStyle = accent;
    ctx.fillRect(x, y, barW, h);
    ctx.fillStyle = muted;
    ctx.textAlign = "center";
    ctx.font = "10px sans-serif";
    ctx.fillText(shortDate(d.date), x + barW / 2, cssH - 8);
  });

  // baseline
  ctx.strokeStyle = accent;
  ctx.beginPath();
  ctx.moveTo(padL, padT + plotH);
  ctx.lineTo(cssW - 8, padT + plotH);
  ctx.stroke();

  ctx.font = "11px sans-serif";
  ctx.fillStyle = "#a0a1a6";
  ctx.textAlign = "center";
  ctx.fillText(
    chartMode === "tokens" ? "日毎のトークン数" : "日毎のコスト (USD)",
    cssW / 2,
    padT - 2
  );
}

function shortDate(iso) {
  if (!iso) return "";
  const d = new Date(iso + "T00:00:00");
  if (isNaN(d.getTime())) return iso;
  return `${d.getMonth() + 1}/${d.getDate()}`;
}