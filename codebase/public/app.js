const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

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

const state = {
  selectedPrefs: new Set(),
  corrections: [],
  clarifyAnswer: null,
  lastPayload: null,
};

function parseHistory() {
  const raw = $("#history").value.trim();
  if (!raw) return [];
  return raw.split(/[,;]/).map((s) => s.trim()).filter(Boolean);
}

function getPayload(extra = {}) {
  const budgetVal = $("#budget").value.trim();
  return {
    timeSlot: $("#time-slot").value,
    budget: budgetVal ? Number(budgetVal) : 0,
    history: parseHistory(),
    chips: [...state.selectedPrefs],
    prompt: $("#prompt").value.trim(),
    corrections: [...state.corrections],
    clarifyAnswer: state.clarifyAnswer,
    maxEta: 25,
    ...extra,
  };
}

function setCriteria(text) {
  const el = $("#criteria-line");
  if (!text) {
    el.classList.add("hidden");
    return;
  }
  el.textContent = text;
  el.classList.remove("hidden");
}

function confClass(c) {
  const v = (c || "").toLowerCase();
  if (v.includes("cao")) return "conf-high";
  if (v.includes("thấp")) return "conf-low";
  return "conf-mid";
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

function setResultsMode(hasCards) {
  const results = $(".sf-results");
  const empty = $("#empty-state");
  if (hasCards) {
    results.classList.add("has-cards");
    empty.classList.add("hidden");
  } else {
    results.classList.remove("has-cards");
    empty.classList.remove("hidden");
  }
}

function renderCards(recommendations, aiSource) {
  const container = $("#cards");
  container.innerHTML = "";
  if (!recommendations?.length) {
    setResultsMode(false);
    return;
  }

  setResultsMode(true);

  recommendations.forEach((r, i) => {
    const rating = (4.2 + (i * 0.1)).toFixed(1);
    const card = document.createElement("article");
    card.className = "sf-dish-card";
    card.dataset.rank = `#${i + 1}`;
    card.innerHTML = `
      <div class="sf-dish-thumb" aria-hidden="true">${thumbEmoji(r.name)}</div>
      <div class="sf-dish-body">
        <h3 class="sf-dish-name">${escapeHtml(r.name)}</h3>
        <p class="sf-dish-shop">${escapeHtml(r.restaurant)}</p>
        <div class="sf-dish-stats">
          <span class="sf-stat-star">★ ${rating}</span>
          <span>🕐 ${r.etaMinutes} phút</span>
          <span>🛵 15.000₫</span>
          <span><strong style="color:#ee4d2d">${formatPrice(r.price)}</strong></span>
        </div>
        <div class="sf-dish-tags">
          <span class="badge ${confClass(r.confidence)}">AI ${escapeHtml(r.confidence)}</span>
          ${r.spicy ? '<span class="badge spicy">Cay</span>' : ""}
          <span class="badge sf-voucher">Freeship</span>
        </div>
        <p class="sf-dish-reason"><em>Vì sao:</em> ${escapeHtml(r.reason)}</p>
        <button type="button" class="btn btn-primary pick" data-name="${escapeAttr(r.name)}">
          Thêm vào giỏ
        </button>
      </div>
    `;
    container.appendChild(card);
  });

  const sourceNote = document.createElement("p");
  sourceNote.className = "sf-source-note";
  sourceNote.textContent =
    aiSource === "llm"
      ? "Gợi ý từ AI thật · OpenAI-compatible"
      : aiSource === "llm+rule"
        ? "AI + bổ sung rule"
        : "Rule fallback · thêm OPENAI_API_KEY vào .env";
  container.appendChild(sourceNote);

  $$(".pick").forEach((btn) => {
    btn.addEventListener("click", () => {
      $("#checkout-text").innerHTML = `Bạn đã chọn <strong>${escapeHtml(btn.dataset.name)}</strong>. Tiếp theo mở ShopeeFood để thanh toán.`;
      $("#checkout-modal").classList.remove("hidden");
    });
  });

  $("#refine-bar").classList.remove("hidden");
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function escapeAttr(s) {
  return escapeHtml(s).replace(/"/g, "&quot;");
}

function showClarify(question) {
  $("#clarify-box").classList.remove("hidden");
  $("#clarify-question").textContent = question;
  $("#cards").innerHTML = "";
  $("#refine-bar").classList.add("hidden");
  setResultsMode(false);
}

function hideClarify() {
  $("#clarify-box").classList.add("hidden");
}

async function fetchRecommend(payload) {
  $("#loading").classList.remove("hidden");
  $("#error").classList.add("hidden");
  state.lastPayload = payload;

  const res = await fetch("/api/recommend", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await res.json();
  $("#loading").classList.add("hidden");

  if (!res.ok) {
    $("#error").textContent = data.error || "Lỗi gọi API";
    $("#error").classList.remove("hidden");
    return null;
  }
  return data;
}

async function runSuggest() {
  hideClarify();
  const payload = getPayload();
  const data = await fetchRecommend(payload);
  if (!data) return;

  setCriteria(data.criteriaSummary);

  if (data.mode === "clarify") {
    showClarify(data.clarifyQuestion);
    return;
  }

  renderCards(data.recommendations, data.aiSource);
}

async function runRefine(chip) {
  if (!state.corrections.includes(chip)) {
    state.corrections.push(chip);
  }
  const payload = getPayload();
  const data = await fetchRecommend(payload);
  if (!data) return;

  const update =
    data.criteriaSummary ||
    `Đã cập nhật: ${state.corrections.join(", ")}`;
  setCriteria(update);

  if (data.mode === "clarify") {
    showClarify(data.clarifyQuestion);
    return;
  }
  hideClarify();
  renderCards(data.recommendations, data.aiSource);
}

function resetSession() {
  state.selectedPrefs.clear();
  state.corrections = [];
  state.clarifyAnswer = null;
  $$("#pref-chips .chip").forEach((c) => c.classList.remove("active"));
  $("#prompt").value = "";
  $("#budget").value = "50000";
  $("#cards").innerHTML = "";
  $("#criteria-line").classList.add("hidden");
  $("#refine-bar").classList.add("hidden");
  hideClarify();
  $("#error").classList.add("hidden");
  setResultsMode(false);
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
      pill.textContent = "AI fallback";
      pill.classList.add("off");
    }
  } catch {
    $("#ai-status").textContent = "Offline";
    $("#ai-status").classList.add("off");
  }
}

$("#pref-chips").addEventListener("click", (e) => {
  const chip = e.target.closest(".chip[data-chip]");
  if (!chip) return;
  const val = chip.dataset.chip;
  if (state.selectedPrefs.has(val)) {
    state.selectedPrefs.delete(val);
    chip.classList.remove("active");
  } else {
    state.selectedPrefs.add(val);
    chip.classList.add("active");
  }
});

$("#clarify-chips").addEventListener("click", async (e) => {
  const chip = e.target.closest(".chip[data-answer]");
  if (!chip) return;
  state.clarifyAnswer = chip.dataset.answer;
  if (!state.selectedPrefs.has(state.clarifyAnswer)) {
    state.selectedPrefs.add(state.clarifyAnswer);
  }
  if (!$("#budget").value.trim()) {
    $("#budget").value = "50000";
  }
  hideClarify();
  await runSuggest();
});

$("#refine-chips").addEventListener("click", (e) => {
  const chip = e.target.closest(".chip[data-refine]");
  if (!chip) return;
  runRefine(chip.dataset.refine);
});

$("#btn-suggest").addEventListener("click", runSuggest);
$("#btn-reset").addEventListener("click", resetSession);
$("#btn-close-modal").addEventListener("click", () => {
  $("#checkout-modal").classList.add("hidden");
});
$("#sheet-backdrop")?.addEventListener("click", () => {
  $("#checkout-modal").classList.add("hidden");
});

$$(".sf-cat").forEach((btn) => {
  btn.addEventListener("click", () => {
    $$(".sf-cat").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
  });
});

$("#prompt").value = "Trưa nay 50k, ăn no, không cay";
["Ăn no", "Không cay", "Giao < 25 phút"].forEach((label) => {
  const btn = [...$$("#pref-chips .chip")].find((b) => b.dataset.chip === label);
  if (btn) {
    state.selectedPrefs.add(label);
    btn.classList.add("active");
  }
});

initHealth();
