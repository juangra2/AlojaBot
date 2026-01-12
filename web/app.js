// web/app.js
const API_URL = "http://localhost:8000/chat";
const API_BASE = API_URL.replace(/\/chat\/?$/, "");

const SESSION_ID = crypto.randomUUID();

const chatEl = document.getElementById("chat");
const formEl = document.getElementById("composer");
const inputEl = document.getElementById("msg");

// =======================
// Markdown light + helpers
// =======================
function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderMarkdownLight(s) {
  const safe = escapeHtml(String(s));
  const withBold = safe.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  return withBold.replace(/\n/g, "<br>");
}

function addBubble(role, text) {
  const tpl = document.getElementById(role === "user" ? "tpl-user" : "tpl-bot");
  const node = tpl.content.firstElementChild.cloneNode(true);
  node.querySelector(".content").innerHTML = renderMarkdownLight(text);
  chatEl.appendChild(node);
  chatEl.scrollTop = chatEl.scrollHeight;
}

// =======================
// Envío al backend
// =======================
let isSending = false;

async function sendMessage(text) {
  if (isSending) return;
  isSending = true;

  const sendBtn = document.getElementById("send");
  if (sendBtn) sendBtn.disabled = true;

  addBubble("user", text);

  try {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, session_id: SESSION_ID }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    addBubble("bot", data.answer || "(sin respuesta)");
  } catch (err) {
    addBubble(
      "bot",
      `⚠️ Ups, no puedo conectar con la API.\nRevisa API_URL en app.js.\nDetalle: ${err.message}`
    );
  } finally {
    isSending = false;
    if (sendBtn) sendBtn.disabled = false;
  }
}

// =======================
// Eventos chat
// =======================
formEl.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;
  inputEl.value = "";
  sendMessage(text);
});

// =====================================================
// Modal: detalle alojamiento (CLICK -> abrir en grande)
// =====================================================
const modal = document.getElementById("alojModal");
const modalMainImg = document.getElementById("modalMainImg");
const modalThumbs = document.getElementById("modalThumbs");
const modalTitle = document.getElementById("modalTitle");
const modalMeta = document.getElementById("modalMeta");
const modalPrice = document.getElementById("modalPrice");
const modalDesc = document.getElementById("modalDesc");
const modalAmenities = document.getElementById("modalAmenities");
const modalReserveBtn = document.getElementById("modalReserveBtn");

// --- Detalles para el modal (descripción + amenities) ---
const ALOJ_DETAILS = {
  "Apartamento Mercedes": {
    desc:
      "Apartamento entero e independiente en el centro de Cobisa, ideal para hasta 4 personas. " +
      "Tiene balcón/terraza con vistas, wifi gratis y aparcamiento gratuito muy cerca. " +
      "Vivienda familiar reformada, perfecta para escapadas a Toledo y Puy du Fou.",
    amenities: [
      "Wifi gratis",
      "Aire acondicionado",
      "Calefacción (según temporada)",
      "Baño privado con ducha y secador",
      "Ropa de cama y toallas incluidas",
      "Cocina equipada (placa, nevera, cafetera, menaje)",
      "Sala de estar independiente con sofá cama",
      "Mesa de comedor / zona de estar familiar",
    ],
  },

  "Apartamento los arcos": {
    desc:
      "Casa entera independiente de una planta en el centro de Cobisa, con jardín, terraza, patio privado " +
      "y una cueva típica rehabilitada. Ideal para familias o grupos de hasta 6 personas cerca de Toledo y Puy du Fou.",
    amenities: [
      "Wifi gratis",
      "Aire acondicionado",
      "Calefacción (según temporada)",
      "Casa completa de uso exclusivo",
      "Habitaciones sin humo",
      "Baño privado con ducha y secador",
      "Ropa de cama y toallas incluidas",
      "Cueva privada rehabilitada",
      "Cocina equipada (placa, nevera, cafetera, menaje)",
      "Sala de estar independiente con sofá cama",
      "Mesa de comedor / zona de estar familiar",
    ],
  },

  "Casa Bruna": {
    desc:
      "Casa entera independiente de una planta en Cobisa, con patio privado, terraza y jardín. " +
      "Ideal para hasta 6 personas en una casa tradicional reformada, con wifi y aparcamiento gratuito junto al alojamiento.",
    amenities: [
      "Wifi gratis",
      "Aire acondicionado",
      "Calefacción (según temporada)",
      "Baño privado con ducha y secador",
      "Ropa de cama y toallas incluidas",
      "Habitaciones sin humo",
      "Lavadora",
      "Cocina equipada (placa, nevera, cafetera, menaje)",
      "Sala de estar con sofá cama",
      "Mesa de comedor / zona de estar familiar",
    ],
  },

  "Casa La Calera": {
    desc:
      "Casa entera independiente de una planta en Cobisa, con patio privado, jardín y terraza solárium. " +
      "Entorno tranquilo cerca de Toledo y Puy du Fou, con wifi y aparcamiento gratuito en la misma calle.",
    amenities: [
      "Wifi gratis",
      "Aire acondicionado",
      "Calefacción (según temporada)",
      "Baño privado con ducha y artículos de aseo",
      "Ropa de cama y toallas incluidas",
      "Habitaciones sin humo",
      "Lavadora",
      "Cocina equipada (placa, nevera, cafetera, menaje)",
      "Sala de estar con sofá cama",
      "Mesa de comedor / zona de estar familiar",
    ],
  },
};

let lastFocusedEl = null;

function openModal() {
  if (!modal) return;
  lastFocusedEl = document.activeElement;

  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
}

function closeModal() {
  if (!modal) return;

  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");

  // limpiar
  if (modalThumbs) modalThumbs.innerHTML = "";
  if (modalMainImg) modalMainImg.src = "";

  if (lastFocusedEl && typeof lastFocusedEl.focus === "function") {
    lastFocusedEl.focus();
  }
}

function setActiveThumb(imgEl) {
  if (!modalThumbs) return;
  [...modalThumbs.querySelectorAll("img")].forEach((i) => i.classList.remove("active"));
  imgEl.classList.add("active");
}

function fillModalFromCard(card) {
  if (!card || !modal) return;

  const alojName = (card.dataset.alojNombre || "").trim();

  const h3 = card.querySelector("h3");
  const priceEl = card.querySelector(".aloj-price");
  const metaEl = card.querySelector(".aloj-meta");
  const chipEl = card.querySelector(".aloj-chip");

  // 👉 Descripción / amenities desde el “catálogo” en JS
  const info = ALOJ_DETAILS[alojName] || null;

  if (modalTitle) modalTitle.textContent = (h3?.textContent || alojName || "Alojamiento").trim();

  const metaTxt = [chipEl?.textContent?.trim(), metaEl?.textContent?.trim()]
    .filter(Boolean)
    .join(" · ");
  if (modalMeta) modalMeta.textContent = metaTxt || "Cobisa";

  if (modalPrice) modalPrice.textContent = (priceEl?.textContent || "").trim();

  if (modalDesc) modalDesc.textContent = info?.desc || "—";
  if (modalAmenities) {
    modalAmenities.textContent = info?.amenities?.length
      ? "• " + info.amenities.join("\n• ")
      : "—";
  }

  // 👉 Imágenes:
  // - Elegimos como principal la miniatura activa (si existe) o la principal de la tarjeta
  // - En las miniaturas del modal NO repetimos la principal
  const main = card.querySelector(".aloj-main");
  const activeThumb = card.querySelector(".aloj-thumbs img.active");
  const mainSrc = (activeThumb?.dataset.src || activeThumb?.src || main?.src || "").trim();

  const thumbs = [...card.querySelectorAll(".aloj-thumbs img")].map((t) => (t.dataset.src || t.src || "").trim());
  const unique = [...new Set(thumbs.filter(Boolean))];

  // Asegurar que la principal esté en la lista (por si acaso)
  if (mainSrc && !unique.includes(mainSrc)) unique.unshift(mainSrc);

  if (modalMainImg) {
    modalMainImg.src = mainSrc || unique[0] || "";
    modalMainImg.alt = `Foto de ${modalTitle?.textContent || alojName || "alojamiento"}`;
  }

  if (modalThumbs) {
    modalThumbs.innerHTML = "";

    // ✅ Aquí está la “solución a la duplicación”:
    // renderizamos miniaturas EXCEPTO la que ya está como principal
    const thumbList = unique.filter((src) => src !== (modalMainImg?.src || ""));

    thumbList.forEach((src, idx) => {
      const im = document.createElement("img");
      im.src = src;
      im.alt = `Miniatura ${idx + 1}`;
      im.addEventListener("click", () => {
        if (modalMainImg) modalMainImg.src = src;
        // marcar activa en el modal
        [...modalThumbs.querySelectorAll("img")].forEach((i) => i.classList.remove("active"));
        im.classList.add("active");
      });
      modalThumbs.appendChild(im);
    });
    
  }

  if (modalReserveBtn) {
    modalReserveBtn.onclick = () => {
      const name = (modalTitle?.textContent || alojName || "").trim();
      if (!name) return;

      const base = `Quiero reservar ${name}`;
      inputEl.value = base;
      inputEl.focus();
      inputEl.setSelectionRange(base.length, base.length);

      closeModal();
    };
  }
  // Cargar calendario del mes actual cuando se abre el modal
  const now = new Date();
  loadAndRenderCalendarFor(alojName, now.getFullYear(), now.getMonth() + 1);
}


// Cerrar modal: overlay / botón con data-close="1"
if (modal) {
  modal.addEventListener("click", (e) => {
    const t = e.target;
    if (t && t.dataset && t.dataset.close === "1") closeModal();
  });
}

// Cerrar con ESC
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && modal && modal.classList.contains("is-open")) {
    closeModal();
  }
});

// =======================
// Calendario disponibilidad (modal)
// =======================
const calTitleEl = document.getElementById("calTitle");
const calGridEl = document.getElementById("calGrid");
const calMsgEl = document.getElementById("calMsg");
const calPrevBtn = document.getElementById("calPrev");
const calNextBtn = document.getElementById("calNext");

const MONTHS_ES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"];

// cache nombre->id
const alojIdCache = new Map();

let calState = { alojName: null, year: null, month: null, days: null };

async function fetchAlojIdByName(name) {
  if (alojIdCache.has(name)) return alojIdCache.get(name);

  const url = `${API_BASE}/aloj_id?name=${encodeURIComponent(name)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const data = await res.json();
  if (!data.ok || !data.id) throw new Error("No se pudo resolver el id del alojamiento");
  alojIdCache.set(name, data.id);
  return data.id;
}

async function fetchMonthAvailability(idAloj, year, month) {
  const url = `${API_BASE}/availability?id_aloj=${encodeURIComponent(idAloj)}&year=${encodeURIComponent(year)}&month=${encodeURIComponent(month)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

function renderCalendarGrid(year, month, daysMap) {
  if (!calGridEl) return;

  // month: 1..12 en backend, JS usa 0..11
  const jsMonth = month - 1;
  const first = new Date(year, jsMonth, 1);

  // queremos semana empezando en Lunes:
  // JS: 0 Domingo..6 Sábado -> convertimos a 0 Lunes..6 Domingo
  const jsDow = first.getDay(); // 0..6
  const offset = (jsDow + 6) % 7; // Lunes=0

  const lastDay = new Date(year, jsMonth + 1, 0).getDate();

  if (calTitleEl) calTitleEl.textContent = `${MONTHS_ES[jsMonth]} ${year}`;

  calGridEl.innerHTML = "";

  // celdas vacías iniciales
  for (let i = 0; i < offset; i++) {
    const cell = document.createElement("div");
    cell.className = "cal__day is-empty";
    cell.textContent = "";
    calGridEl.appendChild(cell);
  }

  for (let d = 1; d <= lastDay; d++) {
    const cell = document.createElement("div");
    const iso = `${year}-${String(month).padStart(2,"0")}-${String(d).padStart(2,"0")}`;
    const estado = (daysMap && daysMap[iso]) ? String(daysMap[iso]).toLowerCase() : "libre";

    cell.className = "cal__day " + (estado === "ocupado" ? "is-busy" : "is-free");
    cell.title = `${iso} · ${estado}`;
    cell.textContent = String(d);

    calGridEl.appendChild(cell);
  }
}

async function loadAndRenderCalendarFor(name, year, month) {
  if (!name || !year || !month) return;
  if (calMsgEl) { calMsgEl.style.display = "none"; calMsgEl.textContent = ""; }

  try {
    const idAloj = await fetchAlojIdByName(name);
    const data = await fetchMonthAvailability(idAloj, year, month);

    calState = {
      alojName: name,
      year,
      month,
      days: data.days || {},
    };

    renderCalendarGrid(year, month, calState.days);
  } catch (e) {
    if (calGridEl) calGridEl.innerHTML = "";
    if (calMsgEl) {
      calMsgEl.style.display = "block";
      calMsgEl.textContent = `No puedo cargar la disponibilidad ahora mismo. (${e.message})`;
    }
  }
}

// Navegación prev/next mes
function shiftMonth(year, month, delta) {
  // month 1..12
  const m = month + delta;
  if (m < 1) return { year: year - 1, month: 12 };
  if (m > 12) return { year: year + 1, month: 1 };
  return { year, month: m };
}

if (calPrevBtn) {
  calPrevBtn.addEventListener("click", async (ev) => {
    ev.stopPropagation();
    if (!calState.alojName) return;
    const next = shiftMonth(calState.year, calState.month, -1);
    await loadAndRenderCalendarFor(calState.alojName, next.year, next.month);
  });
}

if (calNextBtn) {
  calNextBtn.addEventListener("click", async (ev) => {
    ev.stopPropagation();
    if (!calState.alojName) return;
    const next = shiftMonth(calState.year, calState.month, +1);
    await loadAndRenderCalendarFor(calState.alojName, next.year, next.month);
  });
}


// =====================================================
// Alojamientos: click tarjeta -> abre modal + (opcional) prefil
// =====================================================

const alojCards = document.querySelectorAll("[data-aloj-nombre]");

alojCards.forEach((card) => {
  card.addEventListener("click", () => {
    // Si no hay modal en el DOM, mantenemos el comportamiento antiguo (prefill)
    if (!modal) {
      const nombre = card.dataset.alojNombre;
      if (!nombre) return;

      const base = `Quiero reservar ${nombre}`;
      inputEl.value = base;
      inputEl.focus();
      inputEl.setSelectionRange(base.length, base.length);
      return;
    }

    // Modal: llenar datos y abrir
    fillModalFromCard(card);
    openModal();
  });
});

// =====================================================
// Galerías de fotos en las tarjetas 
// =====================================================
document.querySelectorAll(".aloj-thumbs img").forEach((thumb) => {
  thumb.addEventListener("click", (ev) => {
    // Evita abrir modal / prefill por el click de la tarjeta
    ev.stopPropagation();

    const newSrc = thumb.dataset.src || thumb.src;
    const gallery = thumb.closest(".aloj-gallery");
    const mainImg = gallery?.querySelector(".aloj-main");
    if (!mainImg) return;

    mainImg.src = newSrc;

    // Marcar miniatura activa
    gallery.querySelectorAll(".aloj-thumbs img").forEach((t) => {
      t.classList.remove("active");
    });
    thumb.classList.add("active");
  });
});

// =======================
// Mensaje de bienvenida
// =======================
addBubble(
  "bot",
  "¡Hola! Soy AlojaBot. Puedo buscar, informar y reservar. ¿Qué necesitas? 😊"
);
