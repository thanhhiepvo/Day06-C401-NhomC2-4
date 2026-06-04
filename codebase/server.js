import { config } from "dotenv";
import express from "express";
import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __dirname = dirname(fileURLToPath(import.meta.url));

config({ path: join(__dirname, "..", ".env") });
config({ path: join(__dirname, ".env"), override: true });

const MEALS = JSON.parse(
  readFileSync(join(__dirname, "data", "meals.json"), "utf8")
);
const MEAL_BY_ID = Object.fromEntries(MEALS.map((m) => [m.id, m]));

const APPETITE_CHIPS = new Set(["Ăn no", "Ăn nhẹ", "Tiết kiệm"]);
const FOOD_KEYWORDS = [
  "cơm",
  "com",
  "bún",
  "bun",
  "phở",
  "pho",
  "bánh mì",
  "banh mi",
  "mì",
  "mi",
  "salad",
  "trà sữa",
  "tra sua",
  "burger",
  "xôi",
  "xoi",
  "lẩu",
  "lau",
  "pizza",
  "cháo",
  "chao",
  "gà",
  "ga",
  "bò",
  "bo",
  "heo",
  "thịt",
  "thit",
  "healthy",
  "đồ uống",
  "do uong",
];
const FLOW_KEYWORDS = [
  ...FOOD_KEYWORDS,
  "ăn",
  "an",
  "món",
  "mon",
  "bữa",
  "bua",
  "đói",
  "doi",
  "thèm",
  "them",
  "trưa",
  "trua",
  "tối",
  "toi",
  "khuya",
  "đêm",
  "dem",
  "đặt",
  "dat",
  "giao",
  "ship",
  "quán",
  "quan",
  "ngân sách",
  "budget",
  "cay",
  "no",
  "nhẹ",
  "nhe",
  "tiết kiệm",
  "tiet kiem",
];
const GENERAL_QUESTION_KEYWORDS = [
  "là gì",
  "la gi",
  "giải thích",
  "giai thich",
  "dịch",
  "dich",
  "viết",
  "viet",
  "tóm tắt",
  "tom tat",
  "code",
  "python",
  "javascript",
  "thời tiết",
  "thoi tiet",
  "mấy giờ",
  "may gio",
  "tin tức",
  "tin tuc",
  "bài thơ",
  "bai tho",
  "kể chuyện",
  "ke chuyen",
  "tính",
  "tinh",
];
const ROUTE_MEAL_FLOW = "meal_flow";
const ROUTE_GENERAL = "general";
const ROUTE_NONSENSE = "nonsense";
const ROUTE_FUTURE = "future";
const ROUTE_SENSITIVE = "sensitive";
const VALID_ROUTES = new Set([
  ROUTE_MEAL_FLOW,
  ROUTE_GENERAL,
  ROUTE_NONSENSE,
  ROUTE_FUTURE,
  ROUTE_SENSITIVE,
]);
const SENSITIVE_KEYWORDS = [
  "tự tử",
  "tu tu",
  "muốn chết",
  "muon chet",
  "giết",
  "giet",
  "bạo lực",
  "bao luc",
  "hack",
  "mật khẩu",
  "mat khau",
  "ma túy",
  "ma tuy",
  "thuốc gì",
  "thuoc gi",
  "uống thuốc",
  "uong thuoc",
  "đau",
  "dau",
  "triệu chứng",
  "trieu chung",
  "dị ứng",
  "di ung",
  "bệnh",
  "benh",
  "chẩn đoán",
  "chan doan",
  "đầu tư",
  "dau tu",
  "all-in",
  "pháp lý",
  "phap ly",
  "kiện",
  "kien",
  "cá cược",
  "ca cuoc",
];
const FUTURE_KEYWORDS = [
  "tương lai",
  "tuong lai",
  "dự đoán",
  "du doan",
  "tiên tri",
  "tien tri",
  "chắc chắn",
  "chac chan",
  "bảo đảm",
  "bao dam",
  "chính xác",
  "chinh xac",
  "ngày mai",
  "ngay mai",
  "năm sau",
  "nam sau",
  "tháng sau",
  "thang sau",
  "xổ số",
  "xo so",
];
const CATEGORY_ALIASES = {
  "cơm": ["cơm", "com"],
  "bún": ["bún", "bun"],
  "phở": ["phở", "pho"],
  "bánh mì": ["bánh mì", "banh mi"],
  "mì": ["mì", "mi"],
  salad: ["salad", "healthy"],
  "đồ uống": ["đồ uống", "do uong", "trà sữa", "tra sua"],
  fastfood: ["burger", "fastfood"],
  "xôi": ["xôi", "xoi"],
  "lẩu": ["lẩu", "lau"],
  pizza: ["pizza"],
  "cháo": ["cháo", "chao"],
};
const MEAL_GROUPS = {
  "món nước": {
    aliases: ["món nước", "mon nuoc"],
    mealIds: ["m5", "m6", "m7", "m13", "m15"],
  },
};

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json({ limit: "32kb" }));
app.use(express.static(join(__dirname, "public")));

function hasApiKey() {
  return Boolean(process.env.OPENAI_API_KEY?.trim());
}

function inferBudgetFromText(text) {
  const p = (text || "").toLowerCase();
  const range = p.match(/(\d+)\s*[-–]\s*(\d+)\s*k\b/);
  if (range) return Number(range[2]) * 1000;

  const k = p.match(/\b(\d+)\s*k\b/);
  if (k) return Number(k[1]) * 1000;

  const raw = p.match(/\b(\d{5,6})\b/);
  if (raw) return Number(raw[1]);

  return 0;
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function containsFoodKeyword(text) {
  return FOOD_KEYWORDS.some((keyword) => {
    const pattern = new RegExp(
      `(^|[^\\p{L}\\p{N}])${escapeRegExp(keyword)}([^\\p{L}\\p{N}]|$)`,
      "iu"
    );
    return pattern.test(text);
  });
}

function containsFlowKeyword(text) {
  return FLOW_KEYWORDS.some((keyword) => {
    const pattern = new RegExp(
      `(^|[^\\p{L}\\p{N}])${escapeRegExp(keyword)}([^\\p{L}\\p{N}]|$)`,
      "iu"
    );
    return pattern.test(text);
  });
}

function hasFlowSignal(text) {
  const lowered = (text || "").toLowerCase();
  if (inferBudgetFromText(lowered)) return true;
  return containsFlowKeyword(lowered);
}

function isOutOfFlow({ prompt, clarifyAnswer }) {
  const text = `${prompt || ""} ${clarifyAnswer || ""}`.toLowerCase().trim();
  if (!text) return false;
  const hasGeneralQuestion = GENERAL_QUESTION_KEYWORDS.some((keyword) =>
    text.includes(keyword)
  );
  if (hasGeneralQuestion && !hasFlowSignal(text)) return true;
  return !hasFlowSignal(text);
}

function classifierPrompt() {
  return `<role>
Bạn là router hội thoại cho prototype Quick Meal Picker. Nhiệm vụ của bạn là phân loại tin nhắn mới nhất trước khi hệ thống quyết định có gợi ý món hay trả lời chat thường.
</role>

<routes>
- meal_flow: User muốn chọn/gợi ý/đổi món ăn hoặc đồ uống, cung cấp tiêu chí bữa ăn, budget, giờ ăn, khẩu vị, hoặc phản hồi refine như "đổi món", "không cay". Câu "ngày mai ăn gì?" vẫn là meal_flow nếu user đang nhờ gợi ý bữa ăn, không phải đòi dự đoán số phận.
- general: Câu hỏi bình thường ngoài đồ ăn và không thuộc nhóm rủi ro.
- nonsense: Nội dung quá ngắn, rời rạc, ký tự ngẫu nhiên, hoặc không đủ nghĩa để trả lời.
- future: User yêu cầu dự đoán chắc chắn về tương lai, kết quả chưa biết, xổ số, giá cả, thời tiết xa, hoặc điều không thể biết chính xác. Không dùng route này cho kế hoạch ăn uống thông thường.
- sensitive: Y tế, thuốc men, triệu chứng, dị ứng, tự hại, bạo lực, pháp lý, tài chính/đầu tư rủi ro, bảo mật, hành vi bất hợp pháp, hoặc dữ liệu riêng tư.
</routes>

<priority>
Ưu tiên nhãn an toàn hơn khi mơ hồ: sensitive > future > nonsense > meal_flow > general.
</priority>

<style>
Không giải thích dài. Không lộ chain-of-thought. Chỉ trả JSON hợp lệ.
</style>

<output_schema>
{
  "route": "meal_flow" | "general" | "nonsense" | "future" | "sensitive",
  "reason": string
}
</output_schema>`;
}

function looksSensitiveRequest(text) {
  const lowered = (text || "").toLowerCase();
  return SENSITIVE_KEYWORDS.some((keyword) => lowered.includes(keyword));
}

function looksFutureRequest(text) {
  const lowered = (text || "").toLowerCase();
  if (!FUTURE_KEYWORDS.some((keyword) => lowered.includes(keyword))) {
    return false;
  }
  const certaintyTerms = [
    "chắc chắn",
    "chac chan",
    "bảo đảm",
    "bao dam",
    "chính xác",
    "chinh xac",
    "xổ số",
    "xo so",
    "tiên tri",
    "tien tri",
  ];
  if (!hasFlowSignal(lowered)) return true;
  if (
    hasMealIntent({ prompt: lowered, chips: [], clarifyAnswer: "" }) &&
    !certaintyTerms.some((term) => lowered.includes(term))
  ) {
    return false;
  }
  return certaintyTerms.some((term) => lowered.includes(term));
}

function looksNonsense(text) {
  const lowered = (text || "").toLowerCase().trim();
  if (!lowered) return true;
  if (inferBudgetFromText(lowered)) return false;
  const knownKeywords = [
    ...GENERAL_QUESTION_KEYWORDS,
    ...FLOW_KEYWORDS,
    ...SENSITIVE_KEYWORDS,
    ...FUTURE_KEYWORDS,
  ];
  if (knownKeywords.some((keyword) => lowered.includes(keyword))) return false;

  const compact = lowered.replace(/\s+/g, "");
  if (/^[\W_]+$/u.test(compact)) return true;

  const letters = lowered.match(/\p{L}/gu) || [];
  if (!letters.length) return true;

  const words = lowered.match(/[\p{L}\p{N}]+/gu) || [];
  const vowels =
    lowered.match(
      /[aeiouyàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹ]/giu
    ) || [];
  const vowelRatio = vowels.length / Math.max(letters.length, 1);
  return words.length >= 2 && letters.length >= 8 && vowelRatio <= 0.27;
}

function fallbackClassifyMessage(text) {
  const cleaned = (text || "").trim();
  if (!cleaned) {
    return {
      route: ROUTE_NONSENSE,
      reason: "empty-message",
      source: "rule-router",
    };
  }
  if (looksSensitiveRequest(cleaned)) {
    return {
      route: ROUTE_SENSITIVE,
      reason: "sensitive-keyword",
      source: "rule-router",
    };
  }
  if (looksNonsense(cleaned)) {
    return {
      route: ROUTE_NONSENSE,
      reason: "low-signal-message",
      source: "rule-router",
    };
  }
  if (looksFutureRequest(cleaned)) {
    return {
      route: ROUTE_FUTURE,
      reason: "future-uncertain",
      source: "rule-router",
    };
  }
  if (isOutOfFlow({ prompt: cleaned, clarifyAnswer: "" })) {
    return {
      route: ROUTE_GENERAL,
      reason: "out-of-meal-flow",
      source: "rule-router",
    };
  }
  return {
    route: ROUTE_MEAL_FLOW,
    reason: "meal-flow-signal",
    source: "rule-router",
  };
}

async function classifyUserMessage({ latestMessage, userPayload }) {
  const fallback = fallbackClassifyMessage(latestMessage);
  if (!hasApiKey()) return fallback;

  try {
    const raw = await callLLM([
      { role: "system", content: classifierPrompt() },
      {
        role: "user",
        content: JSON.stringify({
          latestMessage,
          currentUserState: userPayload,
        }),
      },
    ]);
    const route = String(raw.route || "").trim();
    if (!VALID_ROUTES.has(route)) return fallback;
    return {
      route,
      reason: String(raw.reason || fallback.reason).slice(0, 120),
      source: "llm-router",
    };
  } catch {
    return fallback;
  }
}

function generalChatPrompt(route) {
  return `<role>
Bạn là trợ lý AI của Quick Meal Picker. App này là prototype augment: giúp trò chuyện và gợi ý món, không đặt hộ, không có dữ liệu giao đồ ăn live.
</role>

<conversation_route>${route}</conversation_route>

<response_policy>
- Trả lời bằng tiếng Việt, trực tiếp, tự nhiên, 1-4 câu.
- Không tự nhận đã đặt món, không bịa dữ liệu thật ngoài catalog/app.
- Trả JSON hợp lệ đúng output_schema.
- Không lộ chain-of-thought; nếu cần, chỉ nêu kết luận và 1 lý do ngắn.
- general: trả lời đúng câu hỏi ngoài luồng.
- nonsense: nói rằng bạn chưa hiểu đủ ý và mời user viết lại rõ hơn.
- future: không dự đoán chắc chắn; nêu bất định và có thể đưa cách suy nghĩ/kịch bản nếu hữu ích.
- sensitive: đưa hỗ trợ an toàn ở mức khái quát; không kê thuốc, không chẩn đoán, không tư vấn pháp lý/tài chính chắc chắn; khuyến nghị gặp chuyên gia/cấp cứu khi có dấu hiệu nguy hiểm.
</response_policy>

<output_schema>
{
  "answer": string
}
</output_schema>`;
}

function fallbackGeneralAnswer(route = ROUTE_GENERAL) {
  if (route === ROUTE_NONSENSE) {
    return "Mình chưa hiểu rõ ý này. Bạn viết lại cụ thể hơn một chút nhé.";
  }
  if (route === ROUTE_FUTURE) {
    return "Mình không thể dự đoán tương lai một cách chắc chắn. Nếu bạn muốn, mình có thể giúp phân tích các khả năng hoặc lên kế hoạch dựa trên dữ kiện hiện có.";
  }
  if (route === ROUTE_SENSITIVE) {
    return "Câu này có yếu tố nhạy cảm nên mình chỉ có thể hỗ trợ ở mức thông tin chung. Nếu liên quan sức khỏe, pháp lý, tài chính hoặc an toàn cá nhân, bạn nên hỏi chuyên gia phù hợp.";
  }
  return "Câu này nằm ngoài luồng gợi ý món, nhưng hiện mình chưa gọi được OpenAI API. Bạn thử lại sau hoặc thêm OPENAI_API_KEY để mình trả lời trực tiếp hơn.";
}

async function buildGeneralChatAnswer({
  prompt,
  clarifyAnswer,
  route = ROUTE_GENERAL,
}) {
  const text = `${prompt || ""} ${clarifyAnswer || ""}`.trim();
  if (!hasApiKey()) {
    return {
      answer: fallbackGeneralAnswer(route),
      source: "needs-openai-key",
    };
  }

  try {
    const raw = await callLLM([
      { role: "system", content: generalChatPrompt(route) },
      { role: "user", content: text },
    ]);
    const answer = String(raw.answer || "").trim();
    return {
      answer: answer || fallbackGeneralAnswer(route),
      source: "llm-chat",
    };
  } catch {
    return {
      answer: fallbackGeneralAnswer(route),
      source: "llm-error+safe",
    };
  }
}

function hasMealIntent({ prompt, chips, clarifyAnswer }) {
  const text = `${prompt || ""} ${clarifyAnswer || ""}`.toLowerCase();
  const appetiteSignals = [
    "ăn no",
    "ăn nhẹ",
    "tiết kiệm",
    "an no",
    "an nhe",
    "tiet kiem",
  ];
  if ((chips || []).some((chip) => APPETITE_CHIPS.has(chip))) return true;
  if (appetiteSignals.some((signal) => text.includes(signal))) return true;
  return containsFoodKeyword(text);
}

function extractPreferredCategories(text) {
  const lowered = (text || "").toLowerCase();
  return Object.entries(CATEGORY_ALIASES)
    .filter(([_category, aliases]) =>
      aliases.some((alias) => {
        const pattern = new RegExp(
          `(^|[^\\p{L}\\p{N}])${escapeRegExp(alias)}([^\\p{L}\\p{N}]|$)`,
          "iu"
        );
        return pattern.test(lowered);
      })
    )
    .map(([category]) => category);
}

function extractPreferredMealGroup(text) {
  const lowered = (text || "").toLowerCase();
  for (const [groupName, group] of Object.entries(MEAL_GROUPS)) {
    const matched = group.aliases.some((alias) => {
      const pattern = new RegExp(
        `(^|[^\\p{L}\\p{N}])${escapeRegExp(alias)}([^\\p{L}\\p{N}]|$)`,
        "iu"
      );
      return pattern.test(lowered);
    });
    if (matched) return { groupName, mealIds: new Set(group.mealIds) };
  }
  return { groupName: null, mealIds: new Set() };
}

function missingUserData({ timeSlot, budget, chips, prompt, clarifyAnswer }) {
  const missing = [];
  if (!timeSlot) missing.push("time_slot");
  if (!budget || budget <= 0) missing.push("budget");
  if (!hasMealIntent({ prompt, chips, clarifyAnswer })) {
    missing.push("meal_intent");
  }
  return missing;
}

function defaultQuickReplies(missing) {
  const set = new Set(missing);
  if (set.has("budget") && set.has("meal_intent")) {
    return ["Ăn no, 50k", "Ăn nhẹ, 40k", "Tiết kiệm, 35k"];
  }
  if (set.has("budget")) return ["35k", "50k", "80k"];
  if (set.has("meal_intent")) return ["Ăn no", "Ăn nhẹ", "Tiết kiệm"];
  if (set.has("time_slot")) return ["Trưa", "Tối", "Khuya"];
  return ["Ăn no", "Ăn nhẹ", "Tiết kiệm"];
}

function fallbackFollowupQuestion(missing) {
  const set = new Set(missing);
  if (set.has("budget") && set.has("meal_intent")) {
    return "Bạn muốn kiểu bữa nào và ngân sách khoảng bao nhiêu? Ví dụ: ăn no 50k, ăn nhẹ 40k, hoặc tiết kiệm 35k.";
  }
  if (set.has("budget")) {
    return "Ngân sách tối đa cho bữa này khoảng bao nhiêu?";
  }
  if (set.has("meal_intent")) {
    return "Bạn muốn ăn no, ăn nhẹ, tiết kiệm, hay đang thèm món cụ thể nào?";
  }
  if (set.has("time_slot")) return "Bạn định đặt cho bữa trưa, tối hay khuya?";
  return "Bạn muốn bổ sung tiêu chí nào trước khi mình gợi ý món?";
}

function shouldUseFallbackFollowup({ missing, question, replies }) {
  const text = `${question} ${replies.join(" ")}`.toLowerCase();
  if (missing.includes("budget")) {
    const asksBudget =
      text.includes("ngân sách") ||
      text.includes("bao nhiêu") ||
      text.includes("budget");
    const hasBudgetReply = replies.some((reply) => inferBudgetFromText(reply));
    if (!asksBudget && !hasBudgetReply) return true;
  }
  if (missing.includes("meal_intent")) {
    const hasIntentReply = replies.some((reply) =>
      hasMealIntent({ prompt: reply, chips: [], clarifyAnswer: "" })
    );
    if (!hasIntentReply) return true;
  }
  return false;
}

function followupPrompt(missing) {
  return `<role>
Bạn là trợ lý hội thoại cho Quick Meal Picker.
</role>

<task>
Trước khi gợi ý món, hỏi đúng MỘT câu ngắn để thu thập dữ liệu còn thiếu từ user.
</task>

<rules>
- Không gợi ý tên món ở bước này.
- Không nói đã đặt món.
- Câu hỏi phải tự nhiên, dễ trả lời bằng một tin nhắn ngắn.
- quickReplies phải là 3 lựa chọn có thể bấm ngay.
- Trả JSON hợp lệ đúng output_schema.
- Không lộ chain-of-thought.
</rules>

<missing_slots>${missing.join(", ")}</missing_slots>

<output_schema>
{
  "question": string,
  "quickReplies": [string, string, string]
}
</output_schema>`;
}

async function buildFollowup({ missing, criteriaSummary, userPayload }) {
  const fallbackQuestion = fallbackFollowupQuestion(missing);
  const fallbackReplies = defaultQuickReplies(missing);

  if (!hasApiKey()) {
    return {
      question: fallbackQuestion,
      quickReplies: fallbackReplies,
      source: "rule-clarify",
    };
  }

  try {
    const raw = await callLLM([
      { role: "system", content: followupPrompt(missing) },
      {
        role: "user",
        content: JSON.stringify({
          criteriaSummary,
          userPayload,
        }),
      },
    ]);
    const replies = (raw.quickReplies || [])
      .map((reply) => String(reply))
      .filter((reply) => reply.trim())
      .slice(0, 3);
    let question = raw.question || fallbackQuestion;
    let quickReplies = replies.length ? replies : fallbackReplies;
    if (
      shouldUseFallbackFollowup({
        missing,
        question,
        replies: quickReplies,
      })
    ) {
      question = fallbackQuestion;
      quickReplies = fallbackReplies;
    }
    return {
      question,
      quickReplies,
      source: "llm-dialog",
    };
  } catch {
    return {
      question: fallbackQuestion,
      quickReplies: fallbackReplies,
      source: "rule-clarify",
    };
  }
}

function buildCriteria({
  timeSlot,
  budget,
  history,
  chips,
  prompt,
  corrections,
  preferredCategories = [],
  preferredGroup = null,
}) {
  const parts = [];
  if (timeSlot) parts.push(`Giờ: ${timeSlot}`);
  if (budget) parts.push(`Ngân sách tối đa: ${budget} VND`);
  if (preferredCategories.length) {
    parts.push(`Loại món mong muốn: ${preferredCategories.join(", ")}`);
  }
  if (preferredGroup) parts.push(`Nhóm món mong muốn: ${preferredGroup}`);
  if (history?.length) parts.push(`Lịch sử: ${history.join(", ")}`);
  if (chips?.length) parts.push(`Ưu tiên: ${chips.join(", ")}`);
  if (prompt) parts.push(`Ghi chú: ${prompt}`);
  if (corrections?.length) parts.push(`Đã sửa: ${corrections.join(", ")}`);
  return parts.join(" | ") || "Chưa có tiêu chí cụ thể";
}

function rulePrefilter(
  meals,
  {
    budget,
    maxEta,
    noSpicy,
    chips,
    preferredCategories = [],
    preferredMealIds = new Set(),
    excludedMealIds = [],
  }
) {
  const preferredSet = new Set(preferredCategories);
  const excludedSet = new Set(excludedMealIds);
  const preferredPool = preferredMealIds.size
    ? meals.filter((m) => preferredMealIds.has(m.id))
    : preferredSet.size
    ? meals.filter((m) => preferredSet.has(m.category))
    : [...meals];
  let hardPool = preferredPool.length ? [...preferredPool] : [...meals];
  if (noSpicy) hardPool = hardPool.filter((m) => !m.spicy);

  let list = [...hardPool];
  if (budget) {
    const cap = Math.round(budget * 1.1);
    list = list.filter((m) => m.price <= cap);
  }
  if (maxEta) list = list.filter((m) => m.etaMinutes <= maxEta);
  if (chips?.includes("Rẻ hơn") && budget) {
    list = list.filter((m) => m.price <= budget * 0.85);
  }
  if (chips?.includes("Giao nhanh hơn")) {
    list = list.filter((m) => m.etaMinutes <= 20);
  }
  if (excludedSet.size) {
    const alternatives = list.filter((m) => !excludedSet.has(m.id));
    list = alternatives.length ? alternatives : [];
  }
  return list;
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
      temperature: 0.5,
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

function systemPrompt(catalog, preferredCategories = [], preferredGroup = null) {
  const categoryRule = preferredCategories.length
    ? `- User đã nêu loại món cụ thể: ${preferredCategories.join(", ")}. Đây là ràng buộc cứng; chỉ chọn trong loại này.\n`
    : "";
  const groupRule = preferredGroup
    ? `- User đã nêu nhóm món cụ thể: ${preferredGroup}. Đây là ràng buộc cứng; chỉ chọn trong nhóm này.\n`
    : "";
  return `<role>
Bạn là AI gợi ý món ăn cho prototype "Quick Meal Picker" (augment, không đặt hộ).
</role>

<task>
Chọn món phù hợp nhất từ catalog JSON theo id. Dữ liệu user đã được thu thập trước bước này nên mặc định ưu tiên recommend.
</task>

<hard_rules>
- Chỉ chọn món từ catalog, không bịa món ngoài catalog.
- Không nói đã đặt món hoặc có đơn hàng thật.
- mode=clarify chỉ dùng khi vẫn thiếu dữ liệu rất quan trọng; hỏi MỘT câu ngắn.
- mode=recommend: trả đúng 3 mealId khác nhau nếu catalog đủ món.
- Tôn trọng ràng buộc user nêu: loại món, nhóm món, không cay, budget, ETA.
${categoryRule}${groupRule}- Chỉ đa dạng category khi user KHÔNG nêu loại/nhóm món cụ thể.
- Trả JSON hợp lệ đúng output_schema.
- Không lộ chain-of-thought; reason chỉ là lý do ngắn user-facing.
</hard_rules>

<output_schema>
{
  "mode": "clarify" | "recommend",
  "clarifyQuestion": string | null,
  "criteriaSummary": string,
  "recommendations": [
    { "mealId": string, "reason": string, "confidence": "cao" | "trung bình" | "thấp" }
  ]
}
</output_schema>

<catalog_json>
${JSON.stringify(catalog)}
</catalog_json>`;
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
      quickReplies: raw.quickReplies || defaultQuickReplies(["meal_intent"]),
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
    quickReplies: [],
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
          ? "Phương án khác phù hợp nhất trong catalog hiện có (rule fallback)"
          : "Món thay thế trong catalog mock",
      confidence: i === 0 ? "cao" : "trung bình",
      spicy: m.spicy,
    })),
    quickReplies: [],
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
      budget: rawBudget,
      history = [],
      chips = [],
      prompt = "",
      corrections = [],
      excludedMealIds = [],
      maxEta = 25,
      clarifyAnswer = "",
      latestMessage = "",
    } = body;
    const currentMessage = latestMessage || clarifyAnswer || prompt;
    const combinedText = `${prompt} ${clarifyAnswer} ${currentMessage}`;
    const budget = Number(rawBudget || 0) || inferBudgetFromText(combinedText);
    const preferredCategories = extractPreferredCategories(combinedText);
    const preferredGroup = extractPreferredMealGroup(combinedText);

    const criteriaSummary = buildCriteria({
      timeSlot,
      budget,
      history,
      chips: [...chips, ...corrections],
      prompt,
      corrections,
      preferredCategories,
      preferredGroup: preferredGroup.groupName,
    });

    const userPayload = {
      timeSlot,
      budget,
      history,
      chips,
      prompt,
      corrections,
      excludedMealIds,
      clarifyAnswer,
      latestMessage: currentMessage,
      preferredCategories,
      preferredGroup: preferredGroup.groupName,
      maxEtaMinutes: maxEta,
    };

    const classification = await classifyUserMessage({
      latestMessage: currentMessage,
      userPayload,
    });
    userPayload.route = classification.route;
    userPayload.routeReason = classification.reason;

    if (classification.route !== ROUTE_MEAL_FLOW) {
      const chat = await buildGeneralChatAnswer({
        prompt: currentMessage,
        clarifyAnswer: "",
        route: classification.route,
      });
      return res.json({
        mode: "chat",
        answer: chat.answer,
        route: classification.route,
        routeReason: classification.reason,
        recommendations: [],
        quickReplies: [],
        aiSource: chat.source,
        routerSource: classification.source,
      });
    }

    const missing = missingUserData({
      timeSlot,
      budget,
      chips: [...chips, ...corrections],
      prompt,
      clarifyAnswer,
    });
    if (missing.length) {
      const followup = await buildFollowup({
        missing,
        criteriaSummary,
        userPayload,
      });
      return res.json({
        mode: "clarify",
        clarifyQuestion: followup.question,
        criteriaSummary,
        recommendations: [],
        quickReplies: followup.quickReplies,
        missingSlots: missing,
        aiSource: followup.source,
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
      preferredCategories,
      preferredMealIds: preferredGroup.mealIds,
      excludedMealIds,
    });
    const allowedIds = new Set(filtered.map((m) => m.id));

    if (!hasApiKey()) {
      const out = fallbackRecommend(filtered, criteriaSummary);
      return res.json({ ...out, aiSource: "rule-fallback" });
    }

    userPayload.catalogIds = [...allowedIds];

    let raw;
    try {
      raw = await callLLM([
        {
          role: "system",
          content: systemPrompt(
            filtered,
            preferredCategories,
            preferredGroup.groupName
          ),
        },
        {
          role: "user",
          content: `Hãy gợi ý cho user:\n${JSON.stringify(userPayload, null, 2)}`,
        },
      ]);
    } catch {
      const out = fallbackRecommend(filtered, criteriaSummary);
      return res.json({ ...out, aiSource: "llm-error+rule" });
    }

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
