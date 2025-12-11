// web/app.js
const API_URL = "http://localhost:8000/chat";
const SESSION_ID = crypto.randomUUID();

const chatEl = document.getElementById("chat");
const formEl = document.getElementById("composer");
const inputEl = document.getElementById("msg");

// --- Render ligero de Markdown (negritas) + saltos de línea ---
function escapeHtml(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderMarkdownLight(s) {
  const safe = escapeHtml(String(s));
  // **texto** -> <strong>texto</strong>
  const withBold = safe.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  return withBold.replace(/\n/g, "<br>");
}

// ---- UI helpers ----
function addBubble(role, text) {
  const tpl = document.getElementById(
    role === "user" ? "tpl-user" : "tpl-bot"
  );
  const node = tpl.content.firstElementChild.cloneNode(true);
  node.querySelector(".content").innerHTML = renderMarkdownLight(text);
  chatEl.appendChild(node);
  chatEl.scrollTop = chatEl.scrollHeight;
}

// ---- Envío al backend (con sesión e anti-doble envío) ----
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

    // El backend devuelve answer, evidence, candidatos, weather…
    // pero ahora solo usamos answer porque todo se muestra en el chat.
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

// ---- Eventos ----
formEl.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;
  inputEl.value = "";
  sendMessage(text);
});

// Alojamientos: al hacer clic, pre-rellena el mensaje
const alojCards = document.querySelectorAll("[data-aloj-nombre]");
alojCards.forEach((card) => {
  card.addEventListener("click", () => {
    const nombre = card.dataset.alojNombre;
    if (!nombre) return;

    const base = `Quiero reservar ${nombre}`;
    // Siempre sobreescribimos el input con el nuevo alojamiento
    inputEl.value = base;

    inputEl.focus();
    inputEl.setSelectionRange(base.length, base.length);
  });
});

// --- Galerías de fotos en las tarjetas ---
document.querySelectorAll(".aloj-thumbs img").forEach((thumb) => {
  thumb.addEventListener("click", (ev) => {
    // Evita que el clic cambie también el mensaje (click de la tarjeta)
    ev.stopPropagation();

    const newSrc = thumb.dataset.src || thumb.src;
    const gallery = thumb.closest(".aloj-gallery");
    const mainImg = gallery.querySelector(".aloj-main");
    if (!mainImg) return;

    mainImg.src = newSrc;

    // Marcar miniatura activa
    gallery.querySelectorAll(".aloj-thumbs img").forEach((t) => {
      t.classList.remove("active");
    });
    thumb.classList.add("active");
  });
});

// Mensaje de bienvenida
addBubble(
  "bot",
  "¡Hola! Soy AlojaBot. Puedo buscar, informar y reservar. ¿Qué necesitas? 😊"
);
