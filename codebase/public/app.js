const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

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
  el.textContent = `Tiêu chí: ${text}`;
  el.classList.remove("hidden");
}

function confClass(c) {
  const v = (c || "").toLowerCase();
  if (v.includes("cao")) return "conf-high";
  if (v.includes("thấp")) return "conf-low";
  return "conf-mid";
}

function renderCards(recommendations, aiSource) {
  const container = $("#cards");
  container.innerHTML = "";
  if (!recommendations?.length) return;

  recommendations.forEach((r, i) => {
    const card = document.createElement("article");
    card.className = "card";
    card.innerHTML = `
      <h3>${i + 1}. ${r.name}</h3>
      <p class="meta">${r.restaurant} · ${r.price.toLocaleString("vi-VN")}đ · ~${r.etaMinutes} phút</p>
      <span class="badge ${confClass(r.confidence)}">${r.confidence}</span>
      ${r.spicy ? '<span class="badge spicy">Cay</span>' : ""}
      <p class="reason">${r.reason}</p>
      <button type="button" class="btn primary pick" data-name="${r.name}">Chọn món này</button>
    `;
    container.appendChild(card);
  });

  const sourceNote = document.createElement("p");
  sourceNote.className = "hint";
  sourceNote.textContent =
    aiSource === "llm"
      ? "Nguồn: gọi LLM thật (OpenAI-compatible)."
      : aiSource === "llm+rule"
        ? "Nguồn: LLM + bổ sung rule khi thiếu món."
        : "Nguồn: rule (chưa có API key — thêm OPENAI_API_KEY vào .env).";
  container.appendChild(sourceNote);

  $$(".pick").forEach((btn) => {
    btn.addEventListener("click", () => {
      $("#checkout-text").textContent = `Bạn chọn: ${btn.dataset.name}. Chuyển sang app giao đồ ăn để đặt và thanh toán.`;
      $("#checkout-modal").classList.remove("hidden");
    });
  });

  $("#refine-bar").classList.remove("hidden");
}

function showClarify(question) {
  $("#clarify-box").classList.remove("hidden");
  $("#clarify-question").textContent = question;
  $("#cards").innerHTML = "";
  $("#refine-bar").classList.add("hidden");
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
}

async function initHealth() {
  try {
    const res = await fetch("/api/health");
    const h = await res.json();
    const pill = $("#ai-status");
    if (h.aiConfigured) {
      pill.textContent = "AI thật: đã cấu hình API key";
      pill.classList.remove("off");
    } else {
      pill.textContent =
        "Chưa có API key — chạy rule fallback (thêm .env để đủ điểm AI)";
      pill.classList.add("off");
    }
  } catch {
    $("#ai-status").textContent = "Không kết nối server";
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
  if (! $("#budget").value.trim()) {
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

$("#prompt").value = "Trưa nay 50k, ăn no, không cay";
["Ăn no", "Không cay", "Giao < 25 phút"].forEach((label) => {
  const btn = [...$$("#pref-chips .chip")].find((b) => b.dataset.chip === label);
  if (btn) {
    state.selectedPrefs.add(label);
    btn.classList.add("active");
  }
});

initHealth();
