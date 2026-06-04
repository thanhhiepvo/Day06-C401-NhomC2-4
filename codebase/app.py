"""
Quick Meal Picker — Flask API + static UI (Day 06 prototype).
Run: python app.py   (from codebase/, with .env configured)
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from openai import OpenAI

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"

load_dotenv(BASE_DIR.parent / ".env")
load_dotenv(BASE_DIR / ".env", override=True)

with open(BASE_DIR / "data" / "meals.json", encoding="utf-8") as f:
    MEALS: list[dict] = json.load(f)

MEAL_BY_ID = {m["id"]: m for m in MEALS}

APPETITE_CHIPS = {"Ăn no", "Ăn nhẹ", "Tiết kiệm"}
FOOD_KEYWORDS = [
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
]
FLOW_KEYWORDS = FOOD_KEYWORDS + [
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
]
GENERAL_QUESTION_KEYWORDS = [
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
]
ROUTE_MEAL_FLOW = "meal_flow"
ROUTE_GENERAL = "general"
ROUTE_NONSENSE = "nonsense"
ROUTE_FUTURE = "future"
ROUTE_SENSITIVE = "sensitive"
VALID_ROUTES = {
    ROUTE_MEAL_FLOW,
    ROUTE_GENERAL,
    ROUTE_NONSENSE,
    ROUTE_FUTURE,
    ROUTE_SENSITIVE,
}
SENSITIVE_KEYWORDS = [
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
]
FUTURE_KEYWORDS = [
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
]
CATEGORY_ALIASES = {
    "cơm": ["cơm", "com"],
    "bún": ["bún", "bun"],
    "phở": ["phở", "pho"],
    "bánh mì": ["bánh mì", "banh mi"],
    "mì": ["mì", "mi"],
    "salad": ["salad", "healthy"],
    "đồ uống": ["đồ uống", "do uong", "trà sữa", "tra sua"],
    "fastfood": ["burger", "fastfood"],
    "xôi": ["xôi", "xoi"],
    "lẩu": ["lẩu", "lau"],
    "pizza": ["pizza"],
    "cháo": ["cháo", "chao"],
}
MEAL_GROUPS = {
    "món nước": {
        "aliases": ["món nước", "mon nuoc"],
        "mealIds": ["m5", "m6", "m7", "m13", "m15"],
    }
}

app = Flask(__name__, static_folder=str(PUBLIC_DIR), static_url_path="")


def has_api_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def infer_budget_from_text(text: str) -> int:
    p = (text or "").lower()
    range_match = re.search(r"(\d+)\s*[-–]\s*(\d+)\s*k\b", p)
    if range_match:
        return int(range_match.group(2)) * 1000

    k_match = re.search(r"\b(\d+)\s*k\b", p)
    if k_match:
        return int(k_match.group(1)) * 1000

    num_match = re.search(r"\b(\d{5,6})\b", p)
    if num_match:
        return int(num_match.group(1))

    return 0


def contains_keyword(text: str, keyword: str) -> bool:
    return bool(
        re.search(
            rf"(^|[^0-9A-Za-zÀ-ỹ]){re.escape(keyword)}([^0-9A-Za-zÀ-ỹ]|$)",
            text,
        )
    )


def has_meal_intent(prompt: str, chips: list, clarify_answer: str | None) -> bool:
    text = " ".join([prompt or "", clarify_answer or ""]).lower()
    appetite_signals = {"ăn no", "ăn nhẹ", "tiết kiệm", "an no", "an nhe", "tiet kiem"}
    if APPETITE_CHIPS.intersection(set(chips or [])):
        return True
    if any(signal in text for signal in appetite_signals):
        return True
    return any(contains_keyword(text, keyword) for keyword in FOOD_KEYWORDS)


def extract_preferred_categories(text: str) -> list[str]:
    lowered = (text or "").lower()
    categories = []
    for category, aliases in CATEGORY_ALIASES.items():
        if any(contains_keyword(lowered, alias) for alias in aliases):
            categories.append(category)
    return categories


def extract_preferred_meal_group(text: str) -> tuple[str | None, set[str]]:
    lowered = (text or "").lower()
    for group_name, group in MEAL_GROUPS.items():
        if any(contains_keyword(lowered, alias) for alias in group["aliases"]):
            return group_name, set(group["mealIds"])
    return None, set()


def has_flow_signal(text: str) -> bool:
    lowered = (text or "").lower()
    if infer_budget_from_text(lowered):
        return True
    return any(contains_keyword(lowered, keyword) for keyword in FLOW_KEYWORDS)


def is_out_of_flow(prompt: str, clarify_answer: str | None) -> bool:
    text = " ".join([prompt or "", clarify_answer or ""]).lower().strip()
    if not text:
        return False
    has_general_question = any(keyword in text for keyword in GENERAL_QUESTION_KEYWORDS)
    if has_general_question and not has_flow_signal(text):
        return True
    return not has_flow_signal(text)


def classifier_prompt() -> str:
    return """<role>
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
</output_schema>"""


def looks_sensitive_request(text: str) -> bool:
    lowered = (text or "").lower()
    return any(keyword in lowered for keyword in SENSITIVE_KEYWORDS)


def looks_future_request(text: str) -> bool:
    lowered = (text or "").lower()
    if not any(keyword in lowered for keyword in FUTURE_KEYWORDS):
        return False
    certainty_terms = [
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
    ]
    if not has_flow_signal(lowered):
        return True
    if has_meal_intent(lowered, [], None) and not any(term in lowered for term in certainty_terms):
        return False
    return any(term in lowered for term in certainty_terms)


def looks_nonsense(text: str) -> bool:
    lowered = (text or "").lower().strip()
    if not lowered:
        return True
    if infer_budget_from_text(lowered):
        return False
    known_keywords = (
        GENERAL_QUESTION_KEYWORDS
        + FLOW_KEYWORDS
        + SENSITIVE_KEYWORDS
        + FUTURE_KEYWORDS
    )
    if any(keyword in lowered for keyword in known_keywords):
        return False

    compact = re.sub(r"\s+", "", lowered)
    if re.fullmatch(r"[\W_]+", compact or ""):
        return True

    letters = re.findall(r"[A-Za-zÀ-ỹ]", lowered)
    if not letters:
        return True

    words = re.findall(r"[0-9A-Za-zÀ-ỹ]+", lowered)
    vowels = re.findall(
        r"[aeiouyàáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹ]",
        lowered,
    )
    vowel_ratio = len(vowels) / max(len(letters), 1)
    return len(words) >= 2 and len(letters) >= 8 and vowel_ratio <= 0.27


def fallback_classify_message(text: str) -> dict:
    cleaned = (text or "").strip()
    if not cleaned:
        return {
            "route": ROUTE_NONSENSE,
            "reason": "empty-message",
            "source": "rule-router",
        }
    if looks_sensitive_request(cleaned):
        return {
            "route": ROUTE_SENSITIVE,
            "reason": "sensitive-keyword",
            "source": "rule-router",
        }
    if looks_nonsense(cleaned):
        return {
            "route": ROUTE_NONSENSE,
            "reason": "low-signal-message",
            "source": "rule-router",
        }
    if looks_future_request(cleaned):
        return {
            "route": ROUTE_FUTURE,
            "reason": "future-uncertain",
            "source": "rule-router",
        }
    if is_out_of_flow(cleaned, None):
        return {
            "route": ROUTE_GENERAL,
            "reason": "out-of-meal-flow",
            "source": "rule-router",
        }
    return {
        "route": ROUTE_MEAL_FLOW,
        "reason": "meal-flow-signal",
        "source": "rule-router",
    }


def classify_user_message(latest_message: str, user_payload: dict) -> dict:
    fallback = fallback_classify_message(latest_message)
    if not has_api_key():
        return fallback

    try:
        raw = call_llm(
            [
                {"role": "system", "content": classifier_prompt()},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "latestMessage": latest_message,
                            "currentUserState": user_payload,
                        },
                        ensure_ascii=False,
                    ),
                },
            ]
        )
        route = str(raw.get("route") or "").strip()
        if route not in VALID_ROUTES:
            return fallback
        return {
            "route": route,
            "reason": str(raw.get("reason") or fallback["reason"])[:120],
            "source": "llm-router",
        }
    except Exception:
        return fallback


def general_chat_prompt(route: str) -> str:
    return f"""<role>
Bạn là trợ lý AI của Quick Meal Picker. App này là prototype augment: giúp trò chuyện và gợi ý món, không đặt hộ, không có dữ liệu giao đồ ăn live.
</role>

<conversation_route>{route}</conversation_route>

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
{{
  "answer": string
}}
</output_schema>"""


def fallback_general_answer(route: str = ROUTE_GENERAL) -> str:
    if route == ROUTE_NONSENSE:
        return "Mình chưa hiểu rõ ý này. Bạn viết lại cụ thể hơn một chút nhé."
    if route == ROUTE_FUTURE:
        return (
            "Mình không thể dự đoán tương lai một cách chắc chắn. "
            "Nếu bạn muốn, mình có thể giúp phân tích các khả năng hoặc lên kế hoạch dựa trên dữ kiện hiện có."
        )
    if route == ROUTE_SENSITIVE:
        return (
            "Câu này có yếu tố nhạy cảm nên mình chỉ có thể hỗ trợ ở mức thông tin chung. "
            "Nếu liên quan sức khỏe, pháp lý, tài chính hoặc an toàn cá nhân, bạn nên hỏi chuyên gia phù hợp."
        )
    return (
        "Câu này nằm ngoài luồng gợi ý món, nhưng hiện mình chưa gọi được OpenAI API. "
        "Bạn thử lại sau hoặc thêm OPENAI_API_KEY để mình trả lời trực tiếp hơn."
    )


def build_general_chat_answer(
    prompt: str,
    clarify_answer: str | None,
    route: str = ROUTE_GENERAL,
) -> dict:
    text = " ".join([prompt or "", clarify_answer or ""]).strip()
    if not has_api_key():
        return {
            "answer": fallback_general_answer(route),
            "source": "needs-openai-key",
        }

    try:
        raw = call_llm(
            [
                {"role": "system", "content": general_chat_prompt(route)},
                {"role": "user", "content": text},
            ]
        )
        answer = str(raw.get("answer") or "").strip()
        return {
            "answer": answer or fallback_general_answer(route),
            "source": "llm-chat",
        }
    except Exception:
        return {
            "answer": fallback_general_answer(route),
            "source": "llm-error+safe",
        }


def missing_user_data(
    time_slot: str | None,
    budget: int,
    chips: list,
    prompt: str,
    clarify_answer: str | None,
) -> list[str]:
    missing = []
    if not time_slot:
        missing.append("time_slot")
    if not budget or budget <= 0:
        missing.append("budget")
    if not has_meal_intent(prompt, chips, clarify_answer):
        missing.append("meal_intent")
    return missing


def default_quick_replies(missing: list[str]) -> list[str]:
    missing_set = set(missing)
    if {"budget", "meal_intent"}.issubset(missing_set):
        return ["Ăn no, 50k", "Ăn nhẹ, 40k", "Tiết kiệm, 35k"]
    if "budget" in missing_set:
        return ["35k", "50k", "80k"]
    if "meal_intent" in missing_set:
        return ["Ăn no", "Ăn nhẹ", "Tiết kiệm"]
    if "time_slot" in missing_set:
        return ["Trưa", "Tối", "Khuya"]
    return ["Ăn no", "Ăn nhẹ", "Tiết kiệm"]


def fallback_followup_question(missing: list[str]) -> str:
    missing_set = set(missing)
    if {"budget", "meal_intent"}.issubset(missing_set):
        return (
            "Bạn muốn kiểu bữa nào và ngân sách khoảng bao nhiêu? "
            "Ví dụ: ăn no 50k, ăn nhẹ 40k, hoặc tiết kiệm 35k."
        )
    if "budget" in missing_set:
        return "Ngân sách tối đa cho bữa này khoảng bao nhiêu?"
    if "meal_intent" in missing_set:
        return "Bạn muốn ăn no, ăn nhẹ, tiết kiệm, hay đang thèm món cụ thể nào?"
    if "time_slot" in missing_set:
        return "Bạn định đặt cho bữa trưa, tối hay khuya?"
    return "Bạn muốn bổ sung tiêu chí nào trước khi mình gợi ý món?"


def should_use_fallback_followup(
    missing: list[str],
    question: str,
    replies: list[str],
) -> bool:
    text = f"{question} {' '.join(replies)}".lower()
    if "budget" in missing:
        asks_budget = any(word in text for word in ["ngân sách", "bao nhiêu", "budget"])
        has_budget_reply = any(infer_budget_from_text(reply) for reply in replies)
        if not asks_budget and not has_budget_reply:
            return True
    if "meal_intent" in missing:
        has_intent_reply = any(has_meal_intent(reply, [], None) for reply in replies)
        if not has_intent_reply:
            return True
    return False


def followup_prompt(missing: list[str]) -> str:
    return f"""<role>
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

<missing_slots>{", ".join(missing)}</missing_slots>

<output_schema>
{{
  "question": string,
  "quickReplies": [string, string, string]
}}
</output_schema>"""


def build_followup(
    missing: list[str],
    criteria_summary: str,
    user_payload: dict,
) -> dict:
    fallback_question = fallback_followup_question(missing)
    fallback_replies = default_quick_replies(missing)

    if not has_api_key():
        return {
            "question": fallback_question,
            "quickReplies": fallback_replies,
            "source": "rule-clarify",
        }

    try:
        raw = call_llm(
            [
                {"role": "system", "content": followup_prompt(missing)},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "criteriaSummary": criteria_summary,
                            "userPayload": user_payload,
                        },
                        ensure_ascii=False,
                    ),
                },
            ]
        )
        replies = raw.get("quickReplies") or fallback_replies
        replies = [str(r) for r in replies if str(r).strip()][:3]
        question = raw.get("question") or fallback_question
        if should_use_fallback_followup(missing, question, replies):
            question = fallback_question
            replies = fallback_replies
        return {
            "question": question,
            "quickReplies": replies or fallback_replies,
            "source": "llm-dialog",
        }
    except Exception:
        return {
            "question": fallback_question,
            "quickReplies": fallback_replies,
            "source": "rule-clarify",
        }


def build_criteria(
    time_slot: str | None,
    budget: int,
    history: list,
    chips: list,
    prompt: str,
    corrections: list,
    preferred_categories: list[str] | None = None,
    preferred_group: str | None = None,
) -> str:
    parts = []
    if time_slot:
        parts.append(f"Giờ: {time_slot}")
    if budget:
        parts.append(f"Ngân sách tối đa: {budget} VND")
    if preferred_categories:
        parts.append(f"Loại món mong muốn: {', '.join(preferred_categories)}")
    if preferred_group:
        parts.append(f"Nhóm món mong muốn: {preferred_group}")
    if history:
        parts.append(f"Lịch sử: {', '.join(history)}")
    if chips:
        parts.append(f"Ưu tiên: {', '.join(chips)}")
    if prompt:
        parts.append(f"Ghi chú: {prompt}")
    if corrections:
        parts.append(f"Đã sửa: {', '.join(corrections)}")
    return " | ".join(parts) if parts else "Chưa có tiêu chí cụ thể"


def rule_prefilter(
    meals: list[dict],
    budget: int,
    max_eta: int,
    no_spicy: bool,
    chips: list,
    preferred_categories: list[str] | None = None,
    preferred_meal_ids: set[str] | None = None,
    excluded_meal_ids: set[str] | None = None,
) -> list[dict]:
    base = list(meals)
    excluded_ids = set(excluded_meal_ids or set())
    if preferred_meal_ids:
        preferred_pool = [m for m in base if m["id"] in preferred_meal_ids]
    elif preferred_categories:
        preferred_pool = [m for m in base if m["category"] in set(preferred_categories)]
    else:
        preferred_pool = base
    hard_pool = preferred_pool if preferred_pool else base
    if no_spicy:
        hard_pool = [m for m in hard_pool if not m["spicy"]]

    lst = list(hard_pool)
    if budget:
        cap = int(budget * 1.1)
        lst = [m for m in lst if m["price"] <= cap]
    if max_eta:
        lst = [m for m in lst if m["etaMinutes"] <= max_eta]
    if "Rẻ hơn" in chips and budget:
        lst = [m for m in lst if m["price"] <= budget * 0.85]
    if "Giao nhanh hơn" in chips:
        lst = [m for m in lst if m["etaMinutes"] <= 20]
    if excluded_ids:
        alternatives = [m for m in lst if m["id"] not in excluded_ids]
        lst = alternatives if alternatives else []
    return lst


def system_prompt(
    catalog: list[dict],
    preferred_categories: list[str] | None = None,
    preferred_group: str | None = None,
) -> str:
    category_rule = (
        "- User đã nêu loại món cụ thể: "
        f"{', '.join(preferred_categories)}. Đây là ràng buộc cứng; chỉ chọn trong loại này.\n"
        if preferred_categories
        else ""
    )
    group_rule = (
        f"- User đã nêu nhóm món cụ thể: {preferred_group}. Đây là ràng buộc cứng; chỉ chọn trong nhóm này.\n"
        if preferred_group
        else ""
    )
    return f"""<role>
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
{category_rule}{group_rule}- Chỉ đa dạng category khi user KHÔNG nêu loại/nhóm món cụ thể.
- Trả JSON hợp lệ đúng output_schema.
- Không lộ chain-of-thought; reason chỉ là lý do ngắn user-facing.
</hard_rules>

<output_schema>
{{
  "mode": "clarify" | "recommend",
  "clarifyQuestion": string | null,
  "criteriaSummary": string,
  "recommendations": [
    {{ "mealId": string, "reason": string, "confidence": "cao" | "trung bình" | "thấp" }}
  ]
}}
</output_schema>

<catalog_json>
{json.dumps(catalog, ensure_ascii=False)}
</catalog_json>"""


def call_llm(messages: list[dict]) -> dict:
    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=base)
    resp = client.chat.completions.create(
        model=model,
        temperature=0.5,
        response_format={"type": "json_object"},
        messages=messages,
    )
    content = resp.choices[0].message.content
    return json.loads(content or "{}")


def validate_recommendations(raw: dict, allowed_ids: set[str]) -> dict:
    if raw.get("mode") == "clarify":
        return {
            "mode": "clarify",
            "clarifyQuestion": raw.get("clarifyQuestion")
            or "Bạn muốn ăn no, ăn nhẹ hay tiết kiệm hôm nay?",
            "criteriaSummary": raw.get("criteriaSummary", ""),
            "recommendations": [],
            "quickReplies": raw.get("quickReplies") or default_quick_replies(["meal_intent"]),
        }

    recs = []
    for r in (raw.get("recommendations") or [])[:3]:
        mid = r.get("mealId")
        if mid not in allowed_ids:
            continue
        meal = MEAL_BY_ID[mid]
        recs.append(
            {
                "mealId": mid,
                "name": meal["name"],
                "restaurant": meal["restaurant"],
                "price": meal["price"],
                "etaMinutes": meal["etaMinutes"],
                "reason": r.get("reason") or "Phù hợp tiêu chí của bạn",
                "confidence": r.get("confidence") or "trung bình",
                "spicy": meal["spicy"],
            }
        )

    return {
        "mode": "recommend",
        "clarifyQuestion": None,
        "criteriaSummary": raw.get("criteriaSummary", ""),
        "recommendations": recs,
        "quickReplies": [],
    }


def fallback_recommend(filtered: list[dict], criteria_summary: str) -> dict:
    sorted_meals = sorted(filtered, key=lambda m: m["rating"], reverse=True)
    picked: list[dict] = []
    seen_cat: set[str] = set()

    for m in sorted_meals:
        if len(picked) >= 3:
            break
        if m["category"] in seen_cat and len(picked) < 2:
            continue
        seen_cat.add(m["category"])
        picked.append(m)

    for m in sorted_meals:
        if len(picked) >= 3:
            break
        if m not in picked:
            picked.append(m)

    recommendations = []
    for i, m in enumerate(picked[:3]):
        recommendations.append(
            {
                "mealId": m["id"],
                "name": m["name"],
                "restaurant": m["restaurant"],
                "price": m["price"],
                "etaMinutes": m["etaMinutes"],
                "reason": (
                    "Phương án khác phù hợp nhất trong catalog hiện có (rule fallback)"
                    if i == 0
                    else "Món thay thế trong catalog mock"
                ),
                "confidence": "cao" if i == 0 else "trung bình",
                "spicy": m["spicy"],
            }
        )

    return {
        "mode": "recommend",
        "clarifyQuestion": None,
        "criteriaSummary": criteria_summary,
        "recommendations": recommendations,
        "quickReplies": [],
    }


@app.route("/")
def index():
    return send_from_directory(PUBLIC_DIR, "index.html")


@app.get("/api/health")
def health():
    return jsonify(
        ok=True,
        aiConfigured=has_api_key(),
        mealCount=len(MEALS),
        runtime="python",
    )


@app.post("/api/recommend")
def recommend():
    try:
        body = request.get_json(silent=True) or {}
        time_slot = body.get("timeSlot")
        history = body.get("history") or []
        chips = list(body.get("chips") or [])
        prompt = body.get("prompt") or ""
        corrections = list(body.get("corrections") or [])
        excluded_meal_ids = set(body.get("excludedMealIds") or [])
        max_eta = int(body.get("maxEta") or 25)
        clarify_answer = body.get("clarifyAnswer") or ""
        latest_message = body.get("latestMessage") or clarify_answer or prompt
        combined_text = " ".join([prompt, clarify_answer, latest_message])
        budget = int(body.get("budget") or 0) or infer_budget_from_text(combined_text)
        preferred_categories = extract_preferred_categories(combined_text)
        preferred_group, preferred_meal_ids = extract_preferred_meal_group(combined_text)

        criteria_summary = build_criteria(
            time_slot,
            budget,
            history,
            chips + corrections,
            prompt,
            corrections,
            preferred_categories,
            preferred_group,
        )

        user_payload = {
            "timeSlot": time_slot,
            "budget": budget,
            "history": history,
            "chips": chips,
            "prompt": prompt,
            "corrections": corrections,
            "excludedMealIds": list(excluded_meal_ids),
            "clarifyAnswer": clarify_answer,
            "latestMessage": latest_message,
            "preferredCategories": preferred_categories,
            "preferredGroup": preferred_group,
            "maxEtaMinutes": max_eta,
        }

        classification = classify_user_message(latest_message, user_payload)
        user_payload["route"] = classification["route"]
        user_payload["routeReason"] = classification["reason"]

        if classification["route"] != ROUTE_MEAL_FLOW:
            chat = build_general_chat_answer(
                latest_message,
                None,
                classification["route"],
            )
            return jsonify(
                mode="chat",
                answer=chat["answer"],
                route=classification["route"],
                routeReason=classification["reason"],
                recommendations=[],
                quickReplies=[],
                aiSource=chat["source"],
                routerSource=classification["source"],
            )

        missing = missing_user_data(
            time_slot,
            budget,
            chips + corrections,
            prompt,
            clarify_answer,
        )
        if missing:
            followup = build_followup(missing, criteria_summary, user_payload)
            return jsonify(
                mode="clarify",
                clarifyQuestion=followup["question"],
                criteriaSummary=criteria_summary,
                recommendations=[],
                quickReplies=followup["quickReplies"],
                missingSlots=missing,
                aiSource=followup["source"],
            )

        no_spicy = (
            "Không cay" in chips
            or "Không cay" in corrections
            or bool(re.search(r"không cay|ko cay", prompt, re.I))
        )

        filtered = rule_prefilter(
            MEALS,
            budget,
            max_eta,
            no_spicy,
            chips + corrections,
            preferred_categories,
            preferred_meal_ids,
            excluded_meal_ids,
        )
        allowed_ids = {m["id"] for m in filtered}

        if not has_api_key():
            out = fallback_recommend(filtered, criteria_summary)
            out["aiSource"] = "rule-fallback"
            return jsonify(out)

        user_payload["catalogIds"] = list(allowed_ids)

        try:
            raw = call_llm(
                [
                    {
                        "role": "system",
                        "content": system_prompt(
                            filtered,
                            preferred_categories,
                            preferred_group,
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Hãy gợi ý cho user:\n{json.dumps(user_payload, ensure_ascii=False, indent=2)}",
                    },
                ]
            )
        except Exception:
            out = fallback_recommend(filtered, criteria_summary)
            out["aiSource"] = "llm-error+rule"
            return jsonify(out)

        validated = validate_recommendations(raw, allowed_ids)
        if (
            validated["mode"] == "recommend"
            and len(validated["recommendations"]) < 3
        ):
            merged = fallback_recommend(filtered, validated["criteriaSummary"])
            merged["aiSource"] = "llm+rule"
            return jsonify(merged)

        validated["aiSource"] = "llm"
        return jsonify(validated)

    except Exception as err:
        app.logger.exception(err)
        return (
            jsonify(
                error=str(err),
                hint="Kiểm tra OPENAI_API_KEY trong .env",
            ),
            500,
        )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "3000"))
    print(f"Quick Meal Picker → http://localhost:{port}")
    print(f"AI: {'enabled (LLM)' if has_api_key() else 'rule fallback only'}")
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_DEBUG") == "1")
