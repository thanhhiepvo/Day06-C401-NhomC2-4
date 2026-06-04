const $ = (sel) => document.querySelector(sel);

const FOOD_EMOJI = {
  cơm: "🍚",
  bún: "🍜",
  phở: "🍲",
  "bánh mì": "🥖",
  mì: "🍝",
  salad: "🥗",
  "đồ uống": "🧋",
  fastfood: "🍔",
  xôi: "🍚",
  lẩu: "🫕",
  pizza: "🍕",
  cháo: "🥣",
  default: "🍱",
};

const STARTER_CHIPS = [
  "Trưa 50k, ăn no, không cay",
  "Ăn gì cũng được",
  "Tối 80k, giao nhanh",
];

const CLARIFY_CHIPS = ["Ăn no", "Ăn nhẹ", "Tiết kiệm"];

const REFINE_CHIPS = ["Không cay", "Rẻ hơn", "Giao nhanh hơn", "Đổi món"];

const state = {
  selectedPrefs: new Set(),
  corrections: [],
  clarifyAnswer: null,
  prompt: "",
  busy: false,
};

function parseHistory() {
  const raw = $("#history").value.trim();
  if (!raw) return [];
  return raw.split(/[,;]/).map((s) => s.trim()).filter(Boolean);
}

function parseUserMessage(text) {
  const t = text.toLowerCase();
  const prefs = new Set(state.selectedPrefs);

  if (/không cay|ko cay|khong cay/.test(t)) prefs.add("Không cay");
  if (/ăn no|an no/.test(t)) prefs.add("Ăn no");
  if (/ăn nhẹ|an nhe/.test(t)) prefs.add("Ăn nhẹ");
  if (/tiết kiệm|tiet kiem|re hon|rẻ/.test(t)) prefs.add("Tiết kiệm");
  if (/giao nhanh|nhanh hon|<\s*25/.test(t)) prefs.add("Giao < 25 phút");

  if (/trưa|trua/.test(t)) $("#time-slot").value = "trưa";
  if (/\btối\b|toi\b/.test(t)) $("#time-slot").value = "tối";
  if (/khuya|đêm|dem/.test(t)) $("#time-slot").value = "khuya";

  const budgetMatch = t.match(/(\d+)\s*k\b/);
  if (budgetMatch) {
    $("#budget").value = String(Number(budgetMatch[1]) * 1000);
  } else {
    const numMatch = t.match(/\b(\d{5,6})\b/);
    if (numMatch) $("#budget").value = numMatch[1];
  }

  if (/ăn gì cũng được|gì cũng được|không biết|tùy/.test(t)) {
    $("#budget").value = "";
  }

  state.selectedPrefs = prefs;
  state.prompt = text.trim();
}

function getPayload(extra = {}) {
  const budgetVal = $("#budget").value.trim();
  return {
    timeSlot: $("#time-slot").value,
    budget: budgetVal ? Number(budgetVal) : 0,
    history: parseHistory(),
    chips: [...state.selectedPrefs],
    prompt: state.prompt,
    corrections: [...state.corrections],
    clarifyAnswer: state.clarifyAnswer,
    maxEta: 25,
    ...extra,
  };
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function escapeAttr(s) {
  return escapeHtml(s).replace(/"/g, "&quot;");
}

function thumbEmoji(name) {
  const n = (name || "").toLowerCase();
  if (n.includes("cơm")) return FOOD_EMOJI.cơm;
  if (n.includes("bún") || n.includes("phở")) return FOOD_EMOJI.bún;
  if (n.includes("bánh mì")) return FOOD_EMOJI["bánh mì"];
  if (n.includes("trà") || n.includes("sữa")) return FOOD_EMOJI["đồ uống"];
  if (n.includes("burger")) return FOOD_EMOJI.fastfood;
  if (n.includes("pizza")) return FOOD_EMOJI.pizza;
  if (n.includes("lẩu")) return FOOD_EMOJI.lẩu;
  if (n.includes("cháo")) return FOOD_EMOJI.cháo;
  if (n.includes("salad")) return FOOD_EMOJI.salad;
  return FOOD_EMOJI.default;
}

function formatPrice(price) {
  return `${price.toLocaleString("vi-VN")}₫`;
}

function confClass(c) {
  const v = (c || "").toLowerCase();
  if (v.includes("cao")) return "conf-high";
  if (v.includes("thấp")) return "conf-low";
  return "conf-mid";
}

function scrollToBottom() {
  const el = $("#chat-messages");
  el.scrollTop = el.scrollHeight;
}

function appendMessage(role, html, meta = "") {
  const row = document.createElement("div");
  row.className = `msg-row ${role}`;
  const avatar = role === "user" ? "🧑" : "🤖";
  row.innerHTML = `
    <span class="msg-avatar" aria-hidden="true">${avatar}</span>
    <div>
      <div class="msg-bubble">${html}</div>
      ${meta ? `<div class="msg-meta">${escapeHtml(meta)}</div>` : ""}
    </div>
  `;
  $("#chat-messages").appendChild(row);
  scrollToBottom();
  return row;
}

function showTyping() {
  const row = document.createElement("div");
  row.className = "msg-row bot msg-typing";
  row.id = "typing-indicator";
  row.innerHTML = `
    <span class="msg-avatar" aria-hidden="true">🤖</span>
    <div class="msg-bubble">
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
      <span class="typing-dot"></span>
    </div>
  `;
  $("#chat-messages").appendChild(row);
  scrollToBottom();
}

function hideTyping() {
  $("#typing-indicator")?.remove();
}

function setQuickReplies(chips, handler) {
  const bar = $("#quick-replies");
  bar.innerHTML = "";
  if (!chips?.length) {
    bar.classList.add("hidden");
    return;
  }
  bar.classList.remove("hidden");
  chips.forEach((label) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "quick-chip";
    btn.textContent = label;
    btn.addEventListener("click", () => handler(label, btn));
    bar.appendChild(btn);
  });
}

function clearQuickReplies() {
  $("#quick-replies").classList.add("hidden");
  $("#quick-replies").innerHTML = "";
}

function buildMealsHtml(recommendations, aiSource) {
  if (!recommendations?.length) return "<p>Không có gợi ý phù hợp.</p>";

  const cards = recommendations
    .map((r, i) => {
      const rating = (4.2 + i * 0.1).toFixed(1);
      return `
        <article class="meal-card">
          <div class="meal-thumb">${thumbEmoji(r.name)}</div>
          <div>
            <h3 class="meal-name">${escapeHtml(r.name)}</h3>
            <p class="meal-shop">${escapeHtml(r.restaurant)}</p>
            <div class="meal-stats">
              <span>★ ${rating}</span>
              <span>🕐 ${r.etaMinutes}p</span>
              <span class="meal-price">${formatPrice(r.price)}</span>
            </div>
            <div class="meal-tags">
              <span class="badge ${confClass(r.confidence)}">AI ${escapeHtml(r.confidence)}</span>
              ${r.spicy ? '<span class="badge spicy">Cay</span>' : ""}
            </div>
            <p class="meal-reason"><em>Vì sao:</em> ${escapeHtml(r.reason)}</p>
            <button type="button" class="btn-pick" data-name="${escapeAttr(r.name)}">Chọn món này</button>
          </div>
        </article>
      `;
    })
    .join("");

  const source =
    aiSource === "llm"
      ? "Gợi ý từ AI thật"
      : aiSource === "llm+rule"
        ? "AI + rule bổ sung"
        : "Rule fallback (thêm OPENAI_API_KEY)";

  return `<div class="meal-cards">${cards}</div><p class="msg-source">${escapeHtml(source)}</p>`;
}

function wirePickButtons(container) {
  container.querySelectorAll(".btn-pick").forEach((btn) => {
    btn.addEventListener("click", () => {
      const name = btn.dataset.name;
      appendMessage(
        "user",
        `Mình chọn <strong>${escapeHtml(name)}</strong> nhé!`,
        "Vừa xong"
      );
      appendMessage(
        "bot",
        `<p>Đã ghi nhận <strong>${escapeHtml(name)}</strong>. Mở ShopeeFood thật để thanh toán nhé — prototype không đặt hộ.</p>`,
        "Giỏ hàng mock"
      );
      clearQuickReplies();
      setQuickReplies(REFINE_CHIPS, handleRefineChip);
    });
  });
}

async function fetchRecommend(payload) {
  const res = await fetch("/api/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || data.hint || "Lỗi gọi API");
  }
  return data;
}

function handleBotResponse(data) {
  const criteria = data.criteriaSummary
    ? `<p class="msg-criteria"><strong>Tiêu chí:</strong> ${escapeHtml(data.criteriaSummary)}</p>`
    : "";

  if (data.mode === "clarify") {
    appendMessage(
      "bot",
      `<p>${escapeHtml(data.clarifyQuestion || "Bạn muốn ăn no, ăn nhẹ hay tiết kiệm?")}</p>${criteria}`,
      "Cần thêm thông tin"
    );
    setQuickReplies(CLARIFY_CHIPS, handleClarifyChip);
    return;
  }

  const intro =
    "<p>Mình gợi ý <strong>3 món</strong> phù hợp với bạn:</p>";
  const row = appendMessage(
    "bot",
    `${intro}${buildMealsHtml(data.recommendations, data.aiSource)}${criteria}`,
    "Gợi ý xong"
  );
  wirePickButtons(row);
  setQuickReplies(REFINE_CHIPS, handleRefineChip);
}

async function sendUserText(text, { skipParse = false } = {}) {
  if (!text.trim() || state.busy) return;

  state.busy = true;
  $("#btn-send").disabled = true;
  clearQuickReplies();

  appendMessage("user", `<p>${escapeHtml(text)}</p>`);
  if (!skipParse) parseUserMessage(text);

  showTyping();
  try {
    const data = await fetchRecommend(getPayload());
    hideTyping();
    handleBotResponse(data);
  } catch (err) {
    hideTyping();
    appendMessage("bot", `<p class="msg-error">${escapeHtml(err.message)}</p>`, "Lỗi");
    setQuickReplies(STARTER_CHIPS, (label) => sendUserText(label));
  } finally {
    state.busy = false;
    $("#btn-send").disabled = false;
    $("#chat-input").focus();
  }
}

function handleClarifyChip(label) {
  state.clarifyAnswer = label;
  if (!state.selectedPrefs.has(label)) state.selectedPrefs.add(label);
  if (!$("#budget").value.trim()) $("#budget").value = "50000";
  sendUserText(label, { skipParse: true });
}

function handleRefineChip(label) {
  if (!state.corrections.includes(label)) state.corrections.push(label);
  if (label === "Không cay" && !state.selectedPrefs.has("Không cay")) {
    state.selectedPrefs.add("Không cay");
  }
  sendUserText(label, { skipParse: true });
}

function resetChat() {
  state.selectedPrefs.clear();
  state.corrections = [];
  state.clarifyAnswer = null;
  state.prompt = "";
  state.busy = false;
  $("#budget").value = "50000";
  $("#time-slot").value = "trưa";
  $("#chat-messages").innerHTML = "";
  clearQuickReplies();
  showWelcome();
}

function showWelcome() {
  appendMessage(
    "bot",
    `<p>Xin chào! Mình là trợ lý <strong>gợi ý món</strong> — bạn nói giờ ăn, ngân sách và sở thích, mình chọn tối đa 3 món.</p>
     <p>Ví dụ: <em>Trưa 50k, ăn no, không cay</em> hoặc thử <em>Ăn gì cũng được</em> để xem AI hỏi lại.</p>`,
    "Quick Meal Picker"
  );
  setQuickReplies(STARTER_CHIPS, (label) => sendUserText(label));
}

async function initHealth() {
  try {
    const res = await fetch("/api/health");
    const h = await res.json();
    const pill = $("#ai-status");
    if (h.aiConfigured) {
      pill.textContent = "AI ON";
      pill.classList.remove("off");
    } else {
      pill.textContent = "Fallback";
      pill.classList.add("off");
    }
  } catch {
    $("#ai-status").textContent = "Offline";
    $("#ai-status").classList.add("off");
  }
}

$("#chat-form").addEventListener("submit", (e) => {
  e.preventDefault();
  const input = $("#chat-input");
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  sendUserText(text);
});

$("#btn-reset").addEventListener("click", resetChat);

initHealth();
showWelcome();
