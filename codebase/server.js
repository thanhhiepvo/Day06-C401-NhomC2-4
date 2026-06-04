import "dotenv/config";
import express from "express";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));
const MEALS = JSON.parse(
  readFileSync(join(__dirname, "data", "meals.json"), "utf8")
);
const MEAL_BY_ID = Object.fromEntries(MEALS.map((m) => [m.id, m]));

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json({ limit: "32kb" }));
app.use(express.static(join(__dirname, "public")));

function hasApiKey() {
  return Boolean(process.env.OPENAI_API_KEY?.trim());
}

function isVagueInput({ budget, prompt, chips }) {
  const p = (prompt || "").toLowerCase().trim();
  const vaguePhrases = [
    "ăn gì cũng được",
    "gì cũng được",
    "không biết",
    "tùy",
    "anything",
  ];
  const looksVague = vaguePhrases.some((v) => p.includes(v));
  const noBudget = !budget || budget <= 0;
  const fewSignals =
    (chips?.length || 0) === 0 && (!p || p.length < 8);
  return looksVague && noBudget && fewSignals;
}

function buildCriteria({ timeSlot, budget, history, chips, prompt, corrections }) {
  const parts = [];
  if (timeSlot) parts.push(`Giờ: ${timeSlot}`);
  if (budget) parts.push(`Ngân sách tối đa: ${budget} VND`);
  if (history?.length) parts.push(`Lịch sử: ${history.join(", ")}`);
  if (chips?.length) parts.push(`Ưu tiên: ${chips.join(", ")}`);
  if (prompt) parts.push(`Ghi chú: ${prompt}`);
  if (corrections?.length) parts.push(`Đã sửa: ${corrections.join(", ")}`);
  return parts.join(" | ") || "Chưa có tiêu chí cụ thể";
}

function rulePrefilter(meals, { budget, maxEta, noSpicy, chips }) {
  let list = [...meals];
  if (budget) {
    const cap = Math.round(budget * 1.1);
    list = list.filter((m) => m.price <= cap);
  }
  if (maxEta) list = list.filter((m) => m.etaMinutes <= maxEta);
  if (noSpicy) list = list.filter((m) => !m.spicy);
  if (chips?.includes("Rẻ hơn") && budget) {
    list = list.filter((m) => m.price <= budget * 0.85);
  }
  if (chips?.includes("Giao nhanh hơn")) {
    list = list.filter((m) => m.etaMinutes <= 20);
  }
  return list.length ? list : meals;
}

async function callLLM(messages) {
  const base = process.env.OPENAI_BASE_URL || "https://api.openai.com/v1";
  const model = process.env.OPENAI_MODEL || "gpt-4o-mini";
  const res = await fetch(`${base.replace(/\/$/, "")}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
    },
    body: JSON.stringify({
      model,
      temperature: 0.4,
      response_format: { type: "json_object" },
      messages,
    }),
  });
  if (!res.ok) {
    const errText = await res.text();
    throw new Error(`LLM ${res.status}: ${errText.slice(0, 200)}`);
  }
  const data = await res.json();
  const content = data.choices?.[0]?.message?.content;
  return JSON.parse(content);
}

function systemPrompt(catalog) {
  return `Bạn là AI gợi ý món ăn cho prototype "Quick Meal Picker" (augment, không đặt hộ).
Chỉ chọn món từ catalog JSON (theo id). Trả về JSON đúng schema:
{
  "mode": "clarify" | "recommend",
  "clarifyQuestion": string | null,
  "criteriaSummary": string,
  "recommendations": [
    { "mealId": string, "reason": string, "confidence": "cao" | "trung bình" | "thấp" }
  ]
}
Quy tắc:
- mode=clarify khi thiếu budget VÀ input quá mơ hồ; chỉ hỏi MỘT câu ngắn (ăn no / nhẹ / tiết kiệm).
- mode=recommend: đúng 3 mealId khác nhau, đa dạng category, tôn trọng không cay / budget / ETA.
- Không bịa món ngoài catalog. Không nói đã đặt món.
Catalog: ${JSON.stringify(catalog)}`;
}

function validateRecommendations(raw, allowedIds) {
  if (raw.mode === "clarify") {
    return {
      mode: "clarify",
      clarifyQuestion:
        raw.clarifyQuestion ||
        "Bạn muốn ăn no, ăn nhẹ hay tiết kiệm hôm nay?",
      criteriaSummary: raw.criteriaSummary || "",
      recommendations: [],
    };
  }
  const recs = (raw.recommendations || [])
    .filter((r) => allowedIds.has(r.mealId))
    .slice(0, 3)
    .map((r) => {
      const meal = MEAL_BY_ID[r.mealId];
      return {
        mealId: r.mealId,
        name: meal.name,
        restaurant: meal.restaurant,
        price: meal.price,
        etaMinutes: meal.etaMinutes,
        reason: r.reason || "Phù hợp tiêu chí của bạn",
        confidence: r.confidence || "trung bình",
        spicy: meal.spicy,
      };
    });
  return {
    mode: "recommend",
    clarifyQuestion: null,
    criteriaSummary: raw.criteriaSummary || "",
    recommendations: recs,
  };
}

function fallbackRecommend(filtered, criteriaSummary) {
  const sorted = [...filtered].sort((a, b) => b.rating - a.rating);
  const picked = [];
  const seenCat = new Set();
  for (const m of sorted) {
    if (picked.length >= 3) break;
    if (seenCat.has(m.category) && picked.length < 2) continue;
    seenCat.add(m.category);
    picked.push(m);
  }
  while (picked.length < 3 && sorted[picked.length]) {
    const next = sorted.find((x) => !picked.includes(x));
    if (next) picked.push(next);
    else break;
  }
  return {
    mode: "recommend",
    clarifyQuestion: null,
    criteriaSummary,
    recommendations: picked.map((m, i) => ({
      mealId: m.id,
      name: m.name,
      restaurant: m.restaurant,
      price: m.price,
      etaMinutes: m.etaMinutes,
      reason:
        i === 0
          ? "Hợp ngân sách và rating cao (rule fallback)"
          : "Đa dạng món trong catalog mock",
      confidence: i === 0 ? "cao" : "trung bình",
      spicy: m.spicy,
    })),
    usedFallback: true,
  };
}

app.get("/api/health", (_req, res) => {
  res.json({
    ok: true,
    aiConfigured: hasApiKey(),
    mealCount: MEALS.length,
  });
});

app.post("/api/recommend", async (req, res) => {
  try {
    const body = req.body || {};
    const {
      timeSlot,
      budget,
      history = [],
      chips = [],
      prompt = "",
      corrections = [],
      maxEta = 25,
      clarifyAnswer = null,
    } = body;

    const criteriaSummary = buildCriteria({
      timeSlot,
      budget,
      history,
      chips: [...chips, ...corrections],
      prompt,
      corrections,
    });

    if (
      isVagueInput({ budget, prompt, chips }) &&
      !clarifyAnswer &&
      !corrections.length
    ) {
      return res.json({
        mode: "clarify",
        clarifyQuestion:
          "Bạn muốn ăn no, ăn nhẹ hay tiết kiệm hôm nay?",
        criteriaSummary,
        recommendations: [],
        aiSource: "rule",
      });
    }

    const noSpicy =
      chips.includes("Không cay") ||
      corrections.includes("Không cay") ||
      /không cay|ko cay/i.test(prompt);

    const filtered = rulePrefilter(MEALS, {
      budget,
      maxEta,
      noSpicy,
      chips: [...chips, ...corrections],
    });
    const allowedIds = new Set(filtered.map((m) => m.id));

    if (!hasApiKey()) {
      const out = fallbackRecommend(filtered, criteriaSummary);
      return res.json({ ...out, aiSource: "rule-fallback" });
    }

    const userPayload = {
      timeSlot,
      budget,
      history,
      chips,
      prompt,
      corrections,
      clarifyAnswer,
      maxEtaMinutes: maxEta,
      catalogIds: [...allowedIds],
    };

    const raw = await callLLM([
      { role: "system", content: systemPrompt(filtered) },
      {
        role: "user",
        content: `Hãy gợi ý cho user:\n${JSON.stringify(userPayload, null, 2)}`,
      },
    ]);

    const validated = validateRecommendations(raw, allowedIds);
    if (
      validated.mode === "recommend" &&
      validated.recommendations.length < 3
    ) {
      const merged = fallbackRecommend(filtered, validated.criteriaSummary);
      merged.aiSource = "llm+rule";
      return res.json(merged);
    }

    res.json({ ...validated, aiSource: "llm" });
  } catch (err) {
    console.error(err);
    res.status(500).json({
      error: err.message || "Recommend failed",
      hint: "Kiểm tra OPENAI_API_KEY trong .env",
    });
  }
});

app.listen(PORT, () => {
  console.log(`Quick Meal Picker → http://localhost:${PORT}`);
  console.log(`AI: ${hasApiKey() ? "enabled (LLM)" : "rule fallback only"}`);
});
