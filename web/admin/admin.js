const API_BASE = "http://localhost:8000/admin";

let token = localStorage.getItem("ADMIN_TOKEN") || null;
let chart = null;

const el = (id) => document.getElementById(id);

function show(elm, yes) {
  elm.style.display = yes ? "" : "none";
}

function fmtEUR(x) {
  if (x === null || x === undefined || Number.isNaN(Number(x))) return "—";
  return `${Number(x).toFixed(2)} €`;
}
function fmtPct(x) {
  if (x === null || x === undefined || Number.isNaN(Number(x))) return "—";
  return `${(Number(x) * 100).toFixed(2)}%`;
}

function cleanCell(v) {
  if (v === null || v === undefined) return "";
  const s = String(v).trim();
  if (!s) return "";
  const low = s.toLowerCase();
  if (low === "nan" || low === "none" || low === "null" || low === "undefined") return "";
  return s;
}

// Quita el .0 final típico de Excel (ej: "609298323.0" -> "609298323")
function fmtPhone(v) {
  const s = cleanCell(v);
  if (!s) return "";
  return s.replace(/\.0+$/, "");
}

function nightsBetween(a, b) {
  const d1 = new Date(a);
  const d2 = new Date(b);
  const ms = d2 - d1;
  return Math.max(0, Math.round(ms / 86400000));
}

async function api(path, opts = {}) {
  const headers = opts.headers || {};
  headers["Content-Type"] = "application/json";
  if (token) headers["X-Admin-Token"] = token;

  const res = await fetch(`${API_BASE}${path}`, { ...opts, headers });

  const ct = res.headers.get("content-type") || "";
  const payload = ct.includes("application/json")
    ? await res.json().catch(() => null)
    : await res.text().catch(() => "");

  if (!res.ok) {
    const msg = typeof payload === "string" ? payload : (payload?.detail || payload?.message || "");
    throw new Error(`HTTP ${res.status} ${msg}`.trim());
  }
  return payload;
}

function fillYears(selectId) {
  const y = new Date().getFullYear();
  const sel = el(selectId);
  sel.innerHTML = "";
  for (let k = y - 2; k <= y + 2; k++) {
    const opt = document.createElement("option");
    opt.value = String(k);
    opt.textContent = String(k);
    if (k === y) opt.selected = true;
    sel.appendChild(opt);
  }
}

function fillMonths(selectId) {
  const sel = el(selectId);
  sel.innerHTML = "";
  const names = ["1","2","3","4","5","6","7","8","9","10","11","12"];
  const m = new Date().getMonth() + 1;
  names.forEach((n) => {
    const opt = document.createElement("option");
    opt.value = n;
    opt.textContent = n;
    if (Number(n) === m) opt.selected = true;
    sel.appendChild(opt);
  });
}

/**
 * ✅ NUEVO: rellena los selects de alojamientos (metricsAloj y resAloj)
 * desde /alojamientos.
 */
async function loadAlojamientosSelects() {
  const selMetrics = el("metricsAloj");
  const selRes = el("resAloj");

  // Si no existen en el DOM, no hacemos nada.
  if (!selMetrics && !selRes) return;

  const prevMetrics = selMetrics ? (selMetrics.value || "all") : "all";
  const prevRes = selRes ? (selRes.value || "all") : "all";

  if (selMetrics) selMetrics.innerHTML = `<option value="all">todos</option>`;
  if (selRes) selRes.innerHTML = `<option value="all">todos</option>`;

  try {
    const out = await api("/alojamientos");
    (out.items || []).forEach((it) => {
      const id = String(it.id);
      const name = it.nombre;

      if (selMetrics) {
        const opt = document.createElement("option");
        opt.value = id;
        opt.textContent = name;
        selMetrics.appendChild(opt);
      }
      if (selRes) {
        const opt = document.createElement("option");
        opt.value = id;
        opt.textContent = name;
        selRes.appendChild(opt);
      }
    });

    // Restaurar selección previa si sigue existiendo
    if (selMetrics) {
      const ok = [...selMetrics.options].some(o => o.value === prevMetrics);
      selMetrics.value = ok ? prevMetrics : "all";
    }
    if (selRes) {
      const ok = [...selRes.options].some(o => o.value === prevRes);
      selRes.value = ok ? prevRes : "all";
    }
  } catch (e) {
    // no bloqueamos el panel si falla
  }
}

function setScopeUI(scope, yearEl, monthEl) {
  if (scope === "all") {
    yearEl.style.display = "none";
    monthEl.style.display = "none";
    return;
  }
  yearEl.style.display = "";
  monthEl.style.display = (scope === "month") ? "" : "none";
}

function renderChart(labels, data, title) {
  const ctx = el("chartCanvas");
  if (!ctx) return;

  const cleanLabels = (labels || []).map(x => String(x));
  const cleanData = (data || []).map(v => {
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  });

  if (chart) { chart.destroy(); chart = null; }

  chart = new Chart(ctx, {
    type: "line",
    data: { labels: cleanLabels, datasets: [{ label: title, data: cleanData, tension: 0.25 }] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: { legend: { display: true }, tooltip: { enabled: true } },
      scales: { y: { beginAtZero: true } }
    }
  });
}

// =======================
// LOGIN
// =======================
async function doLogin(user, pass) {
  const out = await api("/login", {
    method: "POST",
    body: JSON.stringify({ username: user, password: pass })
  });

  if (!out || !out.ok || !out.token) {
    throw new Error(out?.message || "Usuario o contraseña incorrectos.");
  }

  token = out.token;
  localStorage.setItem("ADMIN_TOKEN", token);
}

function enterDash() {
  show(el("loginView"), false);
  show(el("dashView"), true);
  show(el("btnLogout"), true);
}

function enterLogin() {
  show(el("loginView"), true);
  show(el("dashView"), false);
  show(el("btnLogout"), false);
}

el("btnLogout").addEventListener("click", () => {
  token = null;
  localStorage.removeItem("ADMIN_TOKEN");
  enterLogin();
});

// =======================
// MÉTRICAS
// =======================
async function loadMetrics() {
  const scope = el("metricsScope").value;
  const year = Number(el("metricsYear").value);
  const month = Number(el("metricsMonth").value);

  const alojVal = el("metricsAloj") ? (el("metricsAloj").value || "all") : "all";

  const qObj = { scope, year: String(year), month: String(month) };
  if (alojVal && alojVal !== "all") qObj.aloj_id = String(alojVal);

  const q = new URLSearchParams(qObj);
  const m = await api(`/metrics?${q.toString()}`);

  el("kpiRevenue").textContent = fmtEUR(m.revenue);
  el("kpiOcc").textContent = fmtPct(m.occupancy);
  el("kpiRes").textContent = String(m.reservas_checkin ?? 0);
  el("kpiAdr").textContent = fmtEUR(m.adr);
  el("kpiRevpar").textContent = fmtEUR(m.revpar);
  el("kpiTop").textContent = m.top_alojamiento ? `${m.top_alojamiento} (${fmtEUR(m.top_revenue)})` : "—";

  const chartKind = el("chartType").value;
  const chartYear = (scope === "all") ? new Date().getFullYear() : year;

  const qsObj = { year: String(chartYear), kind: chartKind };
  if (alojVal && alojVal !== "all") qsObj.aloj_id = String(alojVal);

  const qs = new URLSearchParams(qsObj);
  const series = await api(`/series?${qs.toString()}`);

  renderChart(series.labels, series.values, series.title);
}

// el("btnRefreshMetrics").addEventListener("click", loadMetrics);
el("chartType").addEventListener("change", loadMetrics);
el("metricsScope").addEventListener("change", () => {
  setScopeUI(el("metricsScope").value, el("metricsYear"), el("metricsMonth"));
});
// ✅ Auto-refresh métricas al cambiar cualquier filtro
const metricsIds = ["metricsScope", "metricsYear", "metricsMonth", "metricsAloj", "chartType"];
metricsIds.forEach((id) => {
  const node = el(id);
  if (!node) return;
  node.addEventListener("change", loadMetrics);
});

// Si cambias scope, además de refrescar, ajusta visibilidad year/month
el("metricsScope").addEventListener("change", () => {
  setScopeUI(el("metricsScope").value, el("metricsYear"), el("metricsMonth"));
  loadMetrics();
});


/* ✅ NUEVO: al cambiar alojamiento en métricas, refresca */
if (el("metricsAloj")) {
  el("metricsAloj").addEventListener("change", loadMetrics);
}

// =======================
// RESERVAS
// =======================
function resScopeUI() {
  const scope = el("resScope").value;

  const showYear = (scope === "month" || scope === "year");
  const showMonth = (scope === "month");
  const showRange = (scope === "range");

  show(el("resYear"), showYear);
  show(el("resMonth"), showMonth);
  show(el("resFrom"), showRange);
  show(el("resTo"), showRange);
}
el("resScope").addEventListener("change", resScopeUI);

function badgeEstado(x){
  return `<span class="badge">${x}</span>`;
}
function actionButtons(row){
  const id = row.id;
  const disabled = (row.estado !== "creada") ? "disabled" : "";
  return `
    <div class="actions">
      <button class="btn btn-xs btn-secondary" data-act="edit" data-id="${id}">Modificar</button>
      <button class="btn btn-xs btn-ghost" data-act="cancel" data-id="${id}" ${disabled}>Cancelar</button>
    </div>
  `;
}

async function loadReservas() {
  const scope = el("resScope").value;
  const estado = el("resEstado").value;
  const year = Number(el("resYear").value);
  const month = Number(el("resMonth").value);

  const params = { scope, estado, year: String(year), month: String(month) };

  // ✅ NUEVO: filtro alojamiento en RESERVAS
  const alojId = el("resAloj") ? (el("resAloj").value || "all") : "all";
  if (alojId !== "all") params.aloj_id = String(alojId);

  if (scope === "range") {
    params.from = el("resFrom").value || "";
    params.to = el("resTo").value || "";
  }

  const q = new URLSearchParams(params);
  const out = await api(`/reservas?${q.toString()}`);
  (out.items || []).sort((a,b) => (Number(a.id)||0) - (Number(b.id)||0));

  const tbody = el("resTable").querySelector("tbody");
  tbody.innerHTML = "";

  out.items.forEach((r) => {
    const tr = document.createElement("tr");
    const noches = nightsBetween(r.check_in, r.check_out);

    tr.innerHTML = `
      <td>${r.id}</td>
      <td>${r.alojamiento_nombre || r.id_alojamiento}</td>
      <td>${r.check_in}</td>
      <td>${r.check_out}</td>
      <td>${noches}</td>
      <td>${r.huespedes ?? ""}</td>
      <td>${(r.precio_total ?? "").toString()}</td>
      <td>${badgeEstado(r.estado)}</td>
      <td>${r.cliente_nombre ?? ""}</td>
      <td>${r.cliente_email ?? ""}</td>
      <td>${fmtPhone(r.cliente_tel)}</td>
      <td>${cleanCell(r.cliente_dni)}</td>
      <td>${(r.created_at ?? "").toString().slice(0, 19)}</td>
      <td>${actionButtons(r)}</td>
    `;
    tbody.appendChild(tr);
  });
}

el("btnLoadRes").addEventListener("click", loadReservas);
if (el("resAloj")) el("resAloj").addEventListener("change", loadReservas);

// Export CSV
el("btnExportCsv").addEventListener("click", async () => {
  const scope = el("resScope").value;
  const estado = el("resEstado").value;
  const year = Number(el("resYear").value);
  const month = Number(el("resMonth").value);

  const params = { scope, estado, year: String(year), month: String(month) };

  const alojId = (el("resAloj")?.value || "all");
  if (alojId !== "all") params.aloj_id = String(alojId);

  if (scope === "range") {
    params.from = el("resFrom").value || "";
    params.to = el("resTo").value || "";
  }
  const q = new URLSearchParams(params);

  const url = `${API_BASE}/export?${q.toString()}`;
  const res = await fetch(url, {
    headers: { "X-Admin-Token": token }
  });

  if (!res.ok) {
    alert("No se pudo exportar CSV");
    return;
  }

  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `reservas_${Date.now()}.csv`;
  a.click();
});

// =======================
// MODAL cancelar
// =======================
const cancelModal = el("cancelModal");
const cancelSub = el("cancelSub");
const cancelErr = el("cancelErr");
let cancellingId = null;

function openCancelModal(row){
  cancellingId = row.id;
  cancelErr.style.display = "none";
  cancelErr.textContent = "";
  cancelSub.textContent = `${row.alojamiento_nombre || row.id_alojamiento} · ${row.check_in} → ${row.check_out}`;

  cancelModal.classList.add("is-open");
  cancelModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
}

function closeCancelModal(){
  cancelModal.classList.remove("is-open");
  cancelModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");
  cancellingId = null;
}

cancelModal.addEventListener("click", (e) => {
  const t = e.target;
  if (t && t.dataset && t.dataset.close === "1") closeCancelModal();
});

el("btnCancelYes").addEventListener("click", async () => {
  if (!cancellingId) return;
  try{
    const out = await api(`/reserva/${cancellingId}/cancel`, { method: "POST" });
    closeCancelModal();
    await loadReservas();
    await loadMetrics();
    addChatMsg("bot", out.message || `✅ Reserva ${cancellingId} cancelada.`);
  }catch(err){
    cancelErr.style.display = "";
    cancelErr.textContent = `⚠️ ${err.message}`;
  }
});

// =======================
// MODAL editar
// =======================
const editModal = el("editModal");
const editIn = el("editIn");
const editOut = el("editOut");
const editGuests = el("editGuests");
const editErr = el("editErr");
let editingId = null;

function openEditModal(row) {
  editingId = row.id;
  el("editTitle").textContent = `Modificar reserva ${row.id}`;
  el("editSub").textContent = `${row.alojamiento_nombre || row.id_alojamiento} · ${row.check_in} → ${row.check_out}`;
  editIn.value = row.check_in;
  editOut.value = row.check_out;
  editGuests.value = row.huespedes || 1;

  editErr.style.display = "none";
  editErr.textContent = "";

  editModal.classList.add("is-open");
  editModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
}

function closeEditModal() {
  editModal.classList.remove("is-open");
  editModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");
  editingId = null;
}

editModal.addEventListener("click", (e) => {
  const t = e.target;
  if (t && t.dataset && t.dataset.close === "1") closeEditModal();
});
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && editModal.classList.contains("is-open")) closeEditModal();
});

el("btnEditSave").addEventListener("click", async () => {
  if (!editingId) return;
  try {
    const body = {
      new_check_in: editIn.value,
      new_check_out: editOut.value,
      new_huespedes: Number(editGuests.value || 1),
    };
    const out = await api(`/reserva/${editingId}/modify`, {
      method: "POST",
      body: JSON.stringify(body),
    });

    closeEditModal();
    await loadReservas();
    await loadMetrics();
    addChatMsg("bot", out.message || "✅ Reserva modificada.");
  } catch (err) {
    editErr.style.display = "";
    editErr.textContent = `⚠️ ${err.message}`;
  }
});

el("resTable").addEventListener("click", async (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;

  const act = btn.dataset.act;
  const id = btn.dataset.id;
  if (!act || !id) return;

  if (act === "cancel") {
    const out = await api(`/reserva/${id}`);
    openCancelModal(out.item);
  }

  if (act === "edit") {
    const out = await api(`/reserva/${id}`);
    openEditModal(out.item);
  }
});

// =======================
// CHAT ADMIN
// =======================
function addChatMsg(role, text) {
  const box = el("adminChat");
  const div = document.createElement("div");
  div.className = `msg ${role === "user" ? "user" : "bot"}`;
  div.textContent = text;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}

el("adminComposer").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = el("adminMsg").value.trim();
  if (!msg) return;
  el("adminMsg").value = "";
  addChatMsg("user", msg);

  try {
    const out = await api("/chat", {
      method: "POST",
      body: JSON.stringify({
        message: msg,
        context: {
          year: Number(el("metricsYear").value),
          month: Number(el("metricsMonth").value),
          scope: el("metricsScope").value,
        }
      })
    });

    addChatMsg("bot", out.answer || "(sin respuesta)");

    if (out.chart && out.chart.labels && out.chart.values) {
      renderChart(out.chart.labels, out.chart.values, out.chart.title || "Serie");
    }
  } catch (err) {
    addChatMsg("bot", `⚠️ Error: ${err.message}`);
  }
});

// =======================
// INIT
// =======================
function initSelects() {
  fillYears("metricsYear");
  fillMonths("metricsMonth");
  fillYears("resYear");
  fillMonths("resMonth");

  setScopeUI(el("metricsScope").value, el("metricsYear"), el("metricsMonth"));
  resScopeUI();
}

async function boot() {
  initSelects();

  el("loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const user = el("loginUser").value.trim();
    const pass = el("loginPass").value.trim();

    el("loginErr").style.display = "none";
    el("loginErr").textContent = "";

    try {
      await doLogin(user, pass);
      await loadAlojamientosSelects();
      await loadMetrics();
      await loadReservas();
      enterDash();
      addChatMsg("bot", "👋 Listo. Pregúntame por facturación, ocupación, ADR/RevPAR, días libres, top alojamiento o gráficas.");
    } catch (err) {
      el("loginErr").style.display = "";
      el("loginErr").textContent = err.message || "Usuario o contraseña incorrectos.";
      token = null;
      localStorage.removeItem("ADMIN_TOKEN");
    }
  });

  // autologin
  if (token) {
    try {
      await api("/me");
      enterDash();
      await loadAlojamientosSelects(); // ✅ primero rellena selects
      await loadMetrics();
      await loadReservas();
      addChatMsg("bot", "✅ Sesión admin restaurada.");
    } catch (e) {
      token = null;
      localStorage.removeItem("ADMIN_TOKEN");
      enterLogin();
    }
  } else {
    enterLogin();
  }
}

boot();
