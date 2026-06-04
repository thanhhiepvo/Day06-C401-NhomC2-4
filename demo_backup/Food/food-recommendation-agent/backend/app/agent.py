from __future__ import annotations

import json
import os
import re
import unicodedata
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from .data_loader import DATASET_MISSING_MESSAGE
from .schemas import ExtractedFilters
from .tools import get_food_detail, recommend_top_foods


SYSTEM_PROMPT = """
Bạn là bộ trích xuất điều kiện lọc món ăn từ câu tiếng Việt ngắn.
Chỉ trả về JSON hợp lệ, không giải thích.

Schema:
{
  "intent": "recommend_food | filter_food | ask_food_detail | new_chat | small_talk | unknown",
  "rating_min": number|null,
  "price_min": number|null,
  "price_max": number|null,
  "category": string|string[]|null,
  "max_wait_minutes": number|null,
  "randomize": boolean|null,
  "detail_target": string|null,
  "detail_fields": string[],
  "keyword": string|null
}

Quy tắc:
- "trên 3 sao" => rating_min = 3
- "từ 3 sao" => rating_min = 3
- "rating trên 4" => rating_min = 4
- "dưới 60k" => price_max = 60000
- "dưới 60.000" => price_max = 60000
- "từ 30k đến 70k" => price_min = 30000, price_max = 70000
- "30k-70k" => price_min = 30000, price_max = 70000
- "giao nhanh" => max_wait_minutes = 30
- "không muốn chờ lâu" => max_wait_minutes = 30
- "đang vội" => max_wait_minutes = 25
- "nhanh nhất có thể" => max_wait_minutes = 25
- "giao dưới 20 phút" => max_wait_minutes = 20
- "tối đa 25 phút" => max_wait_minutes = 25
- "dưới 30 phút" => max_wait_minutes = 30
- "ít hơn 30 phút" => max_wait_minutes = 30
- "nhỏ hơn 30 phút" => max_wait_minutes = 30
- "30 phút đổ lại" => max_wait_minutes = 30
- "ngẫu nhiên", "random", "bất kỳ", "món khác" => randomize = true
- Nếu user nhắc category như "BÁNH & ĐỒ ĂN VẶT", "BÚN TRỨNG ĐẬU DƯA CÀ", "Bò, bê", "Cá", "Củ quả", "Gia Vị, Sốt, Chấm", "Gia cầm", "Gia vị", "Gia vị tươi", "Gà, gia cầm", "Gạo, mỳ, miến", "Hải sản", "Khác", "Lương thực", "Lợn", "MÂM CỖ RẰM LỄ", "MÓN ĂN NẤU CHÍN SẴN", "Món Canh", "Món Chiên Xào", "Món Hấp, Hầm", "Món Kho, Rang", "Món Nướng", "Món Sốt", "Nấm/Măng", "Nộm", "RAU, CỦ, QUẢ", "Rau Củ Quả", "Rau xanh", "Rau, Củ Gia Vị", "Rau, Củ Sơ Chế Sẵn", "RẰM & LỄ", "Salad", "Set món ăn", "TRÁI CÂY", "Thịt bê", "Thịt bò", "Thịt gà", "Thịt heo/lợn", "Thủy, Hải Sản", "Thực phẩm chế biến", "Thực phẩm khác", "Thực phẩm khô", "Thực phẩm tươi sống", "ĐỒ CÚNG", "Đồ Khô, Hạt, Măng, Nấm", "Ếch" thì đưa vào category.
- Nếu user nhắc category không đầy đủ như "ăn vặt", "bún", "trứng", "đậu", "dưa cà", "bò", "bê", "cá", "củ quả", "gia vị", "sốt", "chấm", "gia cầm", "gà", "gạo", "mỳ", "miến", "hải sản", "lương thực", "lợn", "heo", "mâm cỗ", "rằm lễ", "nấu chín", "canh", "chiên xào", "hấp", "hầm", "kho", "rang", "nướng", "món sốt", "nấm", "măng", "nộm", "rau xanh", "rau sơ chế", "salad", "set món", "trái cây", "thực phẩm chế biến", "thực phẩm khô", "tươi sống", "đồ cúng", "đồ khô", "ếch" thì vẫn đưa vào category theo text người dùng.
- Nếu user nhắc nhiều category bằng "và", "hoặc", "thêm", "cả", "kèm" thì category là mảng string.
- Nếu câu nối tiếp chỉ có điều kiện mới như "ít hơn 30 phút cơ", "rẻ hơn", "rating cao hơn", vẫn extract điều kiện mới; hệ thống sẽ tự ghép với filter cũ ở bước context.
- Nếu user nói "đổi sang", "thay bằng", "chuyển qua" category mới thì chỉ extract category mới; hệ thống sẽ ghi đè category cũ.
- Nếu user hỏi "món số 1", detail_target = "1".
- Nếu user hỏi "món số 2", detail_target = "2".
- Nếu user hỏi "món số 3", detail_target = "3".
- Nếu user hỏi nguyên liệu, thêm "ingredients" vào detail_fields.
- Nếu user hỏi mô tả, thêm "description" vào detail_fields.
- Nếu user hỏi url/link, thêm "url" vào detail_fields.
- Nếu user hỏi giá, thêm "price" và "new_price" vào detail_fields.
- Nếu user hỏi thời gian giao/chờ bao lâu, thêm "estimated_time_minutes" vào detail_fields.
- Nếu user hỏi rating/đánh giá, thêm "rating" vào detail_fields.
- Nếu user hỏi lượt bán, thêm "sold_count" vào detail_fields.
- Nếu user hỏi thông tin chung, detail_fields gồm ["name","brand","category","price","new_price","voucher","rating","sold_count","estimated_time_minutes","ingredients","product_info","description","url"].
- Nếu không rõ field chi tiết, detail_fields = [].
- Nếu có từ khóa tên món cụ thể, đưa vào keyword.
- Nếu user hỏi chuyện ngoài phạm vi đặt món/gợi ý món như "bạn là ai", "tao là gì của mày", "tôi muốn ăn bạn", hỏi thời tiết, bóng đá, người nổi tiếng, crypto, lập trình, học tập... thì intent = "small_talk" và mọi filter = null.
""".strip()


SMALL_TALK_PROMPT = """
Bạn là chatbot gợi ý món ăn trong một app demo.
Người dùng vừa hỏi một câu ngoài phạm vi đặt món/gợi ý món.

Hãy trả lời bằng tiếng Việt, ngắn gọn, hơi trả treo dí dỏm nhưng không xúc phạm.
Không trả lời kiến thức ngoài phạm vi như thời tiết, crypto, người nổi tiếng, chính trị, lập trình.
Không nhận lời các câu gây hấn, tình cảm, khiêu khích, hoặc kiểu "tôi muốn ăn bạn"; hãy né nhẹ và kéo người dùng về chuyện chọn món.
Nhắc rõ bạn chỉ hỗ trợ gợi ý/lọc món theo danh mục, giá, rating, thời gian giao và hỏi chi tiết món trong dataset.
Cuối câu đưa 2-3 gợi ý người dùng có thể hỏi tiếp.
""".strip()


def _configured_openai_model() -> str:
    model = (os.getenv("OPENAI_MODEL") or "gpt-4o-mini").strip()
    aliases = {
        "gpt-4-o-mini": "gpt-4o-mini",
    }
    return aliases.get(model, model) or "gpt-4o-mini"


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def _plain(text: str) -> str:
    return _strip_accents(text).casefold()


def _parse_money_token(token: str | None) -> int | None:
    if not token:
        return None
    text = token.strip().lower().replace(" ", "")
    if not text:
        return None
    has_k = text.endswith("k")
    if has_k:
        number_text = text[:-1].replace(",", ".")
        try:
            return int(round(float(number_text) * 1000))
        except ValueError:
            return None

    digits = re.sub(r"\D", "", text)
    if not digits:
        return None
    value = int(digits)
    if value < 1000 and ("." not in text and "," not in text):
        value *= 1000
    return value


def _extract_price_filters(message: str, plain_message: str) -> tuple[int | None, int | None]:
    price_min: int | None = None
    price_max: int | None = None

    range_match = re.search(
        r"(?:tu\s+)?(\d+(?:[\.,]\d+)?\s*k?)\s*(?:den|toi|-)\s*(\d+(?:[\.,]\d+)?\s*k?)",
        plain_message,
    )
    if range_match and "phut" not in range_match.group(0):
        price_min = _parse_money_token(range_match.group(1))
        price_max = _parse_money_token(range_match.group(2))

    under_matches = list(
        re.finditer(
            r"(?:gia\s*)?(?:duoi|toi da|khong qua|it hon|nho hon|be hon)\s*(\d+(?:[\.,]\d+)?\s*k?)",
            plain_message,
        )
    )
    for match in under_matches:
        tail = plain_message[match.end() : match.end() + 12]
        token = match.group(1)
        if "phut" in tail:
            continue
        if "k" in token or "." in token or "," in token or "gia" in match.group(0):
            parsed = _parse_money_token(token)
            if parsed is not None:
                price_max = parsed

    over_match = re.search(r"gia\s*(?:tren|tu)\s*(\d+(?:[\.,]\d+)?\s*k?)", plain_message)
    if over_match:
        price_min = _parse_money_token(over_match.group(1))

    return price_min, price_max


def _extract_wait_time(plain_message: str) -> int | None:
    explicit_match = re.search(
        r"(?:giao\s*)?(?:duoi|toi da|khong qua|trong|trong vong|it hon|nho hon|be hon)\s*(\d+)\s*(?:phut|p)\b",
        plain_message,
    )
    if explicit_match:
        return int(explicit_match.group(1))

    reverse_match = re.search(r"(\d+)\s*(?:phut|p)\s*(?:do lai|tro lai|thoi|la cung)", plain_message)
    if reverse_match:
        return int(reverse_match.group(1))

    if "nhanh nhat co the" in plain_message or "dang voi" in plain_message:
        return 25

    if "giao nhanh" in plain_message or "khong muon cho lau" in plain_message:
        return 30

    return None


def _extract_rating_min(plain_message: str) -> float | None:
    match = re.search(
        r"(?:rating|danh gia)?\s*(?:tren|tu)\s*(\d+(?:[\.,]\d+)?)\s*sao",
        plain_message,
    )
    if not match:
        match = re.search(r"rating\s*(?:tren|tu)?\s*(\d+(?:[\.,]\d+)?)", plain_message)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _phrase_in_plain(pattern: str, plain_message: str) -> bool:
    normalized_pattern = re.sub(r"[^\w\s-]", " ", pattern)
    normalized_message = re.sub(r"[^\w\s-]", " ", plain_message)
    normalized_pattern = re.sub(r"\s+", " ", normalized_pattern).strip()
    normalized_message = re.sub(r"\s+", " ", normalized_message).strip()
    return re.search(rf"(?<!\w){re.escape(normalized_pattern)}(?!\w)", normalized_message) is not None


def _extract_category(message: str, plain_message: str) -> str | list[str] | None:
    category_patterns = [
        ("banh do an vat", "BÁNH & ĐỒ ĂN VẶT"),
        ("banh", "BÁNH & ĐỒ ĂN VẶT"),
        ("do an vat", "BÁNH & ĐỒ ĂN VẶT"),
        ("an vat", "BÁNH & ĐỒ ĂN VẶT"),
        ("bun trung dau dua ca", "BÚN TRỨNG ĐẬU DƯA CÀ"),
        ("bun", "BÚN TRỨNG ĐẬU DƯA CÀ"),
        ("trung", "BÚN TRỨNG ĐẬU DƯA CÀ"),
        ("dau", "BÚN TRỨNG ĐẬU DƯA CÀ"),
        ("dua ca", "BÚN TRỨNG ĐẬU DƯA CÀ"),
        ("thit heo lon", "Thịt heo/lợn"),
        ("thit heo", "Thịt heo/lợn"),
        ("thit lon", "Thịt heo/lợn"),
        ("heo", "Thịt heo/lợn"),
        ("thit bo", "Thịt bò"),
        ("thit be", "Thịt bê"),
        ("thit ga", "Thịt gà"),
        ("thuc pham tuoi song", "Thực phẩm tươi sống"),
        ("tuoi song", "Thực phẩm tươi sống"),
        ("thuc pham che bien", "Thực phẩm chế biến"),
        ("che bien", "Thực phẩm chế biến"),
        ("thuc pham kho", "Thực phẩm khô"),
        ("thuc pham khac", "Thực phẩm khác"),
        ("set mon an", "Set món ăn"),
        ("set mon", "Set món ăn"),
        ("mam co ram le", "MÂM CỖ RẰM LỄ"),
        ("mam co", "MÂM CỖ RẰM LỄ"),
        ("mon an nau chin san", "MÓN ĂN NẤU CHÍN SẴN"),
        ("nau chin", "MÓN ĂN NẤU CHÍN SẴN"),
        ("rau cu so che san", "Rau, Củ Sơ Chế Sẵn"),
        ("rau so che", "Rau, Củ Sơ Chế Sẵn"),
        ("so che", "Rau, Củ Sơ Chế Sẵn"),
        ("rau cu gia vi", "Rau, Củ Gia Vị"),
        ("gia vi tuoi", "Gia vị tươi"),
        ("do kho hat mang nam", "Đồ Khô, Hạt, Măng, Nấm"),
        ("do kho", "Đồ Khô, Hạt, Măng, Nấm"),
        ("hat", "Đồ Khô, Hạt, Măng, Nấm"),
        ("nam mang", "Nấm/Măng"),
        ("nam/mang", "Nấm/Măng"),
        ("gia vi sot cham", "Gia Vị, Sốt, Chấm"),
        ("sot cham", "Gia Vị, Sốt, Chấm"),
        ("sot", "Gia Vị, Sốt, Chấm"),
        ("cham", "Gia Vị, Sốt, Chấm"),
        ("gia vi", "Gia vị"),
        ("gao my mien", "Gạo, mỳ, miến"),
        ("gao", "Gạo, mỳ, miến"),
        ("my", "Gạo, mỳ, miến"),
        ("mien", "Gạo, mỳ, miến"),
        ("luong thuc", "Lương thực"),
        ("thuy hai san", "Thủy, Hải Sản"),
        ("thuy san", "Thủy, Hải Sản"),
        ("hai san", "Hải sản"),
        ("rau cu qua", "Rau Củ Quả"),
        ("cu qua", "Củ quả"),
        ("rau xanh", "Rau xanh"),
        ("trai cay", "TRÁI CÂY"),
        ("do cung", "ĐỒ CÚNG"),
        ("ram le", "RẰM & LỄ"),
        ("ram", "RẰM & LỄ"),
        ("le ram", "RẰM & LỄ"),
        ("bo be", "Bò, bê"),
        ("bo", "Bò, bê"),
        ("ga gia cam", "Gà, gia cầm"),
        ("ga", "Gà, gia cầm"),
        ("gia cam", "Gia cầm"),
        ("lon", "Lợn"),
        ("mon kho rang", "Món Kho, Rang"),
        ("mon kho", "Món Kho, Rang"),
        ("kho rang", "Món Kho, Rang"),
        ("rang", "Món Kho, Rang"),
        ("hap ham", "Món Hấp, Hầm"),
        ("hap", "Món Hấp, Hầm"),
        ("ham", "Món Hấp, Hầm"),
        ("nuong", "Món Nướng"),
        ("mon sot", "Món Sốt"),
        ("nam", "Nấm/Măng"),
        ("mang", "Nấm/Măng"),
        ("nom", "Nộm"),
        ("ech", "Ếch"),
        ("ca", "Cá"),
        ("khac", "Khác"),
        ("chien xao", "Món Chiên Xào"),
        ("canh", "Món Canh"),
        ("rau cu qua", "Rau Củ Quả"),
        ("rau", "RAU, CỦ, QUẢ"),
        ("salad", "Salad"),
    ]
    categories: list[str] = []
    for pattern, category in category_patterns:
        if _phrase_in_plain(pattern, plain_message) and category not in categories:
            categories.append(category)
    categories = _normalize_extracted_categories(categories)
    if not categories:
        return None
    return categories[0] if len(categories) == 1 else categories


def _normalize_extracted_categories(categories: list[str]) -> list[str]:
    remove_when_present = {
        "Bò, bê": {"Thịt bò", "Thịt bê"},
        "Gà, gia cầm": {"Thịt gà"},
        "Gia cầm": {"Gà, gia cầm", "Thịt gà"},
        "Gia vị": {"Gia vị tươi", "Gia Vị, Sốt, Chấm"},
        "Hải sản": {"Thủy, Hải Sản"},
        "Món Kho, Rang": {"Đồ Khô, Hạt, Măng, Nấm"},
        "Nấm/Măng": {"Đồ Khô, Hạt, Măng, Nấm"},
        "RAU, CỦ, QUẢ": {
            "Rau xanh",
            "Rau Củ Quả",
            "Củ quả",
            "Rau, Củ Gia Vị",
            "Rau, Củ Sơ Chế Sẵn",
        },
        "Cá": {"BÚN TRỨNG ĐẬU DƯA CÀ"},
    }
    present = set(categories)
    normalized: list[str] = []
    for category in categories:
        blockers = remove_when_present.get(category, set())
        if blockers & present:
            continue
        normalized.append(category)
    return normalized


def _extract_randomize(plain_message: str) -> bool | None:
    if any(
        phrase in plain_message
        for phrase in (
            "ngau nhien",
            "random",
            "bat ky",
            "bat ki",
            "mon khac",
            "doi mon",
            "chon dai",
        )
    ):
        return True
    return None


def _extract_detail_fields(plain_message: str) -> list[str]:
    fields: list[str] = []
    if "nguyen lieu" in plain_message:
        fields.append("ingredients")
    if "mo ta" in plain_message:
        fields.append("description")
    if "url" in plain_message or "link" in plain_message:
        fields.append("url")
    if re.search(r"\bgia\b", plain_message):
        fields.extend(["price", "new_price"])
    if "thoi gian" in plain_message or "giao" in plain_message or "cho bao lau" in plain_message:
        fields.append("estimated_time_minutes")
    if "rating" in plain_message or "danh gia" in plain_message or "sao" in plain_message:
        fields.append("rating")
    if "luot ban" in plain_message or "sold" in plain_message:
        fields.append("sold_count")
    if "xuat xu" in plain_message or "nguon goc" in plain_message:
        fields.append("origin")
    if "thong tin" in plain_message or "gioi thieu" in plain_message:
        fields.extend(
            [
                "name",
                "brand",
                "category",
                "price",
                "new_price",
                "voucher",
                "rating",
                "sold_count",
                "estimated_time_minutes",
                "ingredients",
                "product_info",
                "description",
                "url",
            ]
        )

    unique_fields: list[str] = []
    for field in fields:
        if field not in unique_fields:
            unique_fields.append(field)
    return unique_fields


def _extract_detail_target(plain_message: str) -> str | None:
    match = re.search(r"mon\s*(?:so|#)?\s*(\d+)", plain_message)
    if match:
        return match.group(1)
    if "mon nay" in plain_message:
        return "1"
    return None


def _is_small_talk_message(plain_message: str) -> bool:
    relationship_phrases = (
        "ban la ai",
        "may la ai",
        "m la ai",
        "bot la ai",
        "chatbot la ai",
        "ban ten gi",
        "may ten gi",
        "ten ban la gi",
        "ai tao ra ban",
        "ai tao ra may",
        "ai tao ra bot",
        "ban bao nhieu tuoi",
        "may bao nhieu tuoi",
        "ban o dau",
        "may o dau",
        "m la gi",
        "may la gi",
        "ban la gi",
        "tao la gi cua may",
        "tao la gi cua m",
        "toi la gi cua ban",
        "minh la gi cua ban",
        "ban co nguoi yeu",
        "may co nguoi yeu",
        "ban thich gi",
        "may thich gi",
        "ban an gi",
        "may an gi",
        "ban lam duoc gi",
        "may lam duoc gi",
        "yeu toi khong",
        "yeu tao khong",
        "lam nguoi yeu",
        "cuoi toi khong",
        "ngu voi toi",
        "di choi voi toi",
        "noi chuyen voi toi",
        "hello",
        "hi ",
        "xin chao",
        "chao ban",
    )
    provocative_phrases = (
        "toi muon an ban",
        "tao muon an may",
        "muon an ban",
        "muon an may",
        "an ban",
        "an may",
        "an bot",
        "an chatbot",
        "ban co an duoc khong",
        "may co an duoc khong",
    )
    off_topic_keywords = (
        "thoi tiet",
        "bitcoin",
        "crypto",
        "coin",
        "chung khoan",
        "ronaldo",
        "messi",
        "bong da",
        "google",
        "facebook",
        "youtube",
        "chinh tri",
        "tong thong",
        "chien tranh",
        "tin tuc",
        "thoi su",
        "gia vang",
        "ty gia",
        "usd",
        "du lich",
        "phim",
        "nhac",
        "game",
        "bai hat",
        "lap trinh",
        "code python",
        "code javascript",
        "viet code",
        "giai bai",
        "lam bai tap",
        "lich su",
        "dia ly",
        "toan hoc",
        "ke chuyen",
        "hat cho toi",
        "viet tho",
        "dich cau",
    )

    if any(phrase in plain_message for phrase in relationship_phrases):
        return True
    if re.fullmatch(r"\s*(?:hi|hello|alo|xin chao|chao|chao ban)[!\.\s]*", plain_message):
        return True
    if any(phrase in plain_message for phrase in provocative_phrases):
        return True
    if any(keyword in plain_message for keyword in off_topic_keywords):
        return True
    if re.search(r"\b(?:tao|toi|minh|tui)\s+la\s+gi\s+cua\s+(?:may|m|ban)\b", plain_message):
        return True
    return False


def _detect_intent(plain_message: str, has_filters: bool, has_category: bool) -> str:
    if any(keyword in plain_message for keyword in ("chat moi", "doan chat moi", "reset")):
        return "new_chat"

    if has_category:
        return "recommend_food"

    if has_filters:
        return "filter_food"

    if any(
        keyword in plain_message
        for keyword in (
            "mon so",
            "mon nay",
        )
    ):
        return "ask_food_detail"

    if _is_small_talk_message(plain_message):
        return "small_talk"

    if any(
        keyword in plain_message
        for keyword in (
            "goi y",
            "an gi",
            "mon nao",
            "recommend",
            "de xuat",
            "co mon",
            "do an",
            "thuc pham",
            "bua an",
            "an trua",
            "an toi",
            "an sang",
            "dat mon",
            "dat hang",
        )
    ):
        return "recommend_food"

    if any(
        keyword in plain_message
        for keyword in ("loc mon", "loc do an", "category", "danh muc mon", "danh muc do an")
    ):
        return "filter_food"

    return "unknown"


def fallback_extract_filters(message: str) -> ExtractedFilters:
    plain_message = _plain(message)
    rating_min = _extract_rating_min(plain_message)
    price_min, price_max = _extract_price_filters(message, plain_message)
    category = _extract_category(message, plain_message)
    max_wait_minutes = _extract_wait_time(plain_message)
    randomize = _extract_randomize(plain_message)
    detail_target = _extract_detail_target(plain_message)
    detail_fields = _extract_detail_fields(plain_message)
    has_filters = any(
        value is not None
        for value in (rating_min, price_min, price_max, max_wait_minutes, randomize)
    )
    intent = _detect_intent(plain_message, has_filters, category is not None)

    keyword = None
    if intent == "ask_food_detail" and not detail_target:
        cleaned = re.sub(
            r"(cho toi|toi muon|mon nay|co|gi|link|url|nguyen lieu|mo ta|thong tin|gioi thieu|xuat xu|la)",
            " ",
            plain_message,
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        keyword = cleaned or None

    return ExtractedFilters(
        intent=intent,
        rating_min=rating_min,
        price_min=price_min,
        price_max=price_max,
        category=category,
        max_wait_minutes=max_wait_minutes,
        randomize=randomize,
        detail_target=detail_target,
        detail_fields=detail_fields,
        keyword=keyword,
    )


def _coerce_extracted_filters(payload: dict[str, Any], fallback: ExtractedFilters) -> ExtractedFilters:
    try:
        extracted = ExtractedFilters(**payload)
    except Exception:
        return fallback

    fallback_data = fallback.model_dump()
    extracted_data = extracted.model_dump()
    actionable_keys = (
        "rating_min",
        "price_min",
        "price_max",
        "category",
        "max_wait_minutes",
        "randomize",
        "detail_target",
    )
    if fallback.intent == "small_talk" and not any(extracted_data.get(key) for key in actionable_keys):
        return fallback

    if fallback.intent == "unknown" and not any(extracted_data.get(key) for key in actionable_keys):
        return fallback

    for key, value in fallback_data.items():
        if key == "intent":
            continue
        if extracted_data.get(key) in (None, [], "") and value not in (None, [], ""):
            extracted_data[key] = value

    if extracted.intent == "unknown" and fallback.intent != "unknown":
        extracted_data["intent"] = fallback.intent

    return ExtractedFilters(**extracted_data)


def extract_filters_with_llm(message: str) -> ExtractedFilters:
    fallback = fallback_extract_filters(message)
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return fallback

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=_configured_openai_model(),
            response_format={"type": "json_object"},
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f'Câu người dùng: "{message}"\nHãy trích xuất JSON theo schema đã yêu cầu.',
                },
            ],
        )
        content = response.choices[0].message.content or "{}"
        return _coerce_extracted_filters(json.loads(content), fallback)
    except Exception:
        return fallback


FILTER_KEYS = (
    "rating_min",
    "price_min",
    "price_max",
    "category",
    "max_wait_minutes",
    "keyword",
    "randomize",
)


def _is_filter_value(value: Any) -> bool:
    return value not in (None, [], "", False)


def _compact_filters(data: dict[str, Any]) -> dict[str, Any]:
    return {key: data.get(key) for key in FILTER_KEYS if _is_filter_value(data.get(key))}


def _category_values(category: Any) -> list[str]:
    if not category:
        return []
    if isinstance(category, list):
        return [str(item) for item in category if item not in (None, "")]
    return [str(category)]


def _merge_category_values(old_category: Any, new_category: Any) -> str | list[str] | None:
    merged: list[str] = []
    for category in [*_category_values(old_category), *_category_values(new_category)]:
        if category not in merged:
            merged.append(category)
    if not merged:
        return None
    return merged[0] if len(merged) == 1 else merged


def _is_category_append_message(plain_message: str) -> bool:
    return any(
        phrase in plain_message
        for phrase in (
            "them",
            "ca ",
            "voi ",
            "kem",
            "cung",
            "hoac",
            " va ",
            "lan",
        )
    )


def _is_category_override_message(plain_message: str) -> bool:
    return any(
        phrase in plain_message
        for phrase in (
            "doi sang",
            "chuyen sang",
            "chuyen qua",
            "thay bang",
            "thay thanh",
            "khong phai",
        )
    )


def _is_context_followup(plain_message: str) -> bool:
    return any(
        phrase in plain_message
        for phrase in (
            "co",
            "nua",
            "them",
            "hon",
            "it hon",
            "nho hon",
            "be hon",
            "re hon",
            "cao hon",
            "nhanh hon",
            "loc tiep",
            "bo sung",
            "van",
            "giu",
            "cung",
            "do lai",
            "tro lai",
            "ngau nhien",
            "random",
            "mon khac",
        )
    )


def _apply_contextual_filters(extracted: ExtractedFilters, message: str, session: dict[str, Any]) -> ExtractedFilters:
    plain_message = _plain(message)
    old_filters = _compact_filters(session.get("last_filters") or {})
    last_recommendations = session.get("last_recommendations") or []

    data = extracted.model_dump()
    if "re hon" in plain_message or "gia re hon" in plain_message:
        prices = [item.get("new_price", 0) for item in last_recommendations if item.get("new_price")]
        if prices:
            data["price_max"] = max(0, int(min(prices)) - 1)
            data["intent"] = "filter_food"
        elif old_filters.get("price_max"):
            data["price_max"] = max(0, int(old_filters["price_max"]) - 5000)
            data["intent"] = "filter_food"

    if "giao nhanh hon" in plain_message or "nhanh hon" in plain_message:
        times = [
            item.get("estimated_time_minutes", 0)
            for item in last_recommendations
            if item.get("estimated_time_minutes")
        ]
        if times:
            data["max_wait_minutes"] = max(0, int(min(times)) - 1)
            data["intent"] = "filter_food"
        elif old_filters.get("max_wait_minutes"):
            data["max_wait_minutes"] = max(0, int(old_filters["max_wait_minutes"]) - 5)
            data["intent"] = "filter_food"

    if "rating cao hon" in plain_message or "danh gia cao hon" in plain_message:
        ratings = [float(item.get("rating", 0)) for item in last_recommendations]
        if ratings:
            data["rating_min"] = min(5, round(max(ratings) + 0.1, 1))
            data["intent"] = "filter_food"
        elif old_filters.get("rating_min"):
            data["rating_min"] = min(5, round(float(old_filters["rating_min"]) + 0.1, 1))
            data["intent"] = "filter_food"

    current_filters = _compact_filters(data)
    should_merge = (
        bool(old_filters)
        and data.get("intent") in ("recommend_food", "filter_food", "unknown")
        and (bool(current_filters) or _is_context_followup(plain_message))
    )

    active_filters = dict(old_filters) if should_merge else {}

    for key, value in current_filters.items():
        if key == "category":
            continue
        active_filters[key] = value

    if "category" in current_filters:
        if (
            should_merge
            and active_filters.get("category")
            and _is_category_append_message(plain_message)
            and not _is_category_override_message(plain_message)
        ):
            active_filters["category"] = _merge_category_values(
                active_filters.get("category"),
                current_filters.get("category"),
            )
        else:
            active_filters["category"] = current_filters["category"]

    if not active_filters and current_filters:
        active_filters = current_filters

    for key in FILTER_KEYS:
        data[key] = active_filters.get(key)

    if data["intent"] == "unknown" and active_filters:
        data["intent"] = "filter_food"
    elif data["intent"] == "unknown" and session.get("old_intent") in ("recommend_food", "filter_food"):
        data["intent"] = "filter_food"

    return ExtractedFilters(**data)


def _recommendation_filters(extracted: ExtractedFilters) -> dict[str, Any]:
    filters = extracted.model_dump(
        exclude={"intent", "detail_target", "detail_fields"},
    )
    return _compact_filters(filters)


def _format_vnd(value: Any) -> str:
    try:
        amount = int(round(float(value)))
        return f"{amount:,}".replace(",", ".") + "đ"
    except (TypeError, ValueError):
        return "Chưa có thông tin trong dataset."


def _format_original_price(value: Any) -> str:
    if value is None or value == "":
        return "Chưa có thông tin trong dataset."
    if isinstance(value, (int, float)):
        return _format_vnd(value)
    return str(value)


def _format_list(value: Any) -> str:
    if not value:
        return "Chưa có thông tin trong dataset."
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if item not in (None, "")) or "Chưa có thông tin trong dataset."
    return str(value)


def _field_value(item: dict[str, Any], field: str) -> str:
    value = item.get(field)
    if field == "category":
        return _format_list(value)
    if field in ("new_price", "parsed_price"):
        return _format_vnd(value)
    if field == "price":
        return _format_original_price(value)
    if field in ("ingredients", "image_urls"):
        return _format_list(value)
    if value is None or value == "" or value == []:
        return "Chưa có thông tin trong dataset."
    return str(value)


def build_recommendation_answer(recommendations: list[dict[str, Any]]) -> str:
    lines = ["Mình gợi ý 3 món phù hợp nhất:"]
    for index, item in enumerate(recommendations, start=1):
        url = item.get("url") or "Chưa có link món ăn trong dataset."
        lines.extend(
            [
                "",
                f"{index}. {item.get('name', 'Không rõ tên món')} - {item.get('brand') or 'Chưa rõ quán/brand'}",
                f"- Danh mục: {_format_list(item.get('category', ['Khác']))}",
                f"- Giá gốc: {_format_original_price(item.get('price'))}",
                f"- Voucher: {item.get('voucher', 0)}%",
                f"- Giá sau voucher: {_format_vnd(item.get('new_price'))}",
                f"- Rating: {item.get('rating', 0)}",
                f"- Thời gian dự kiến: {item.get('estimated_time_minutes', 0)} phút",
                f"- Lý do: {item.get('reason', '')}",
                f"- Link món: {url}",
            ]
        )

    lines.extend(
        [
            "",
            "Bạn có thể hỏi tiếp:",
            '- "giới thiệu món số 1"',
            '- "món số 2 có nguyên liệu gì?"',
            '- "cho tôi link món số 3"',
            '- "lọc rẻ hơn"',
            '- "giao nhanh hơn"',
        ]
    )
    return "\n".join(lines)


def build_no_result_answer() -> str:
    return (
        "Mình chưa tìm thấy món phù hợp với điều kiện này. "
        "Bạn có thể nới khoảng giá, giảm yêu cầu rating hoặc tăng thời gian chờ."
    )


def build_dataset_missing_answer() -> str:
    return "Hiện chưa có dataset. Vui lòng đặt file JSON vào backend/data/foods.json rồi khởi động lại backend."


def build_suggested_questions(session: dict[str, Any] | None = None) -> list[str]:
    session = session or {}
    last_filters = session.get("last_filters") or {}
    last_recommendations = session.get("last_recommendations") or []

    if last_filters or last_recommendations:
        return [
            "Giao dưới 30 phút",
            "Tôi muốn món giá rẻ hơn",
            "Tôi muốn món rating cao hơn",
            "Thêm Món Canh nữa",
            "Đổi sang TRÁI CÂY",
            "Cho tôi link món số 1",
        ]

    return [
        "Gợi ý món ăn dưới 60k",
        "Tôi muốn Món Canh giao dưới 30 phút",
        "Tôi muốn TRÁI CÂY",
        "Gợi ý BÁNH & ĐỒ ĂN VẶT",
        "Tôi muốn món trên 3 sao",
        "List ngẫu nhiên",
    ]


def build_small_talk_fallback_answer(message: str, session: dict[str, Any] | None = None) -> str:
    plain_message = _plain(message)
    suggestions = build_suggested_questions(session)

    if "an ban" in plain_message or "an may" in plain_message or "an chatbot" in plain_message:
        opener = "Mình không nằm trong menu hôm nay đâu, ăn mình là app treo trước khi no đó."
    elif "ban la ai" in plain_message or "may la ai" in plain_message or "bot la ai" in plain_message:
        opener = "Mình là trợ lý gợi ý món ăn, không phải nhân vật bí ẩn trong phim trinh thám."
    elif "la gi cua" in plain_message:
        opener = "Mình là người canh menu cho bạn, quan hệ hiện tại là: bạn hỏi món, mình lọc món."
    else:
        opener = "Câu này vui đấy, nhưng nó đang chạy khỏi khu đồ ăn của mình rồi."

    lines = [
        opener,
        "Mình chỉ hỗ trợ gợi ý/lọc món theo danh mục, giá, rating, thời gian giao và hỏi chi tiết món trong dataset.",
        "",
        "Thử hỏi một câu như:",
    ]
    lines.extend(f"- {question}" for question in suggestions[:3])
    return "\n".join(lines)


def generate_small_talk_answer(message: str, session: dict[str, Any] | None = None) -> str:
    fallback_answer = build_small_talk_fallback_answer(message, session)
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return fallback_answer

    try:
        client = OpenAI(api_key=api_key)
        suggestions = build_suggested_questions(session)[:4]
        response = client.chat.completions.create(
            model=_configured_openai_model(),
            temperature=0.75,
            max_tokens=220,
            messages=[
                {"role": "system", "content": SMALL_TALK_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f'Câu người dùng: "{message}"\n'
                        f"Các câu gợi ý hợp lệ có thể dùng: {json.dumps(suggestions, ensure_ascii=False)}"
                    ),
                },
            ],
        )
        content = (response.choices[0].message.content or "").strip()
        return content or fallback_answer
    except Exception:
        return fallback_answer


def build_unknown_answer(session: dict[str, Any] | None = None) -> str:
    suggestions = build_suggested_questions(session)
    lines = [
        "Mình chưa có đủ thông tin để trả lời câu này vì nó nằm ngoài phạm vi gợi ý/tra cứu món ăn từ dataset local.",
        "Mình chỉ hỗ trợ các yêu cầu như lọc món theo giá, rating, danh mục, thời gian giao và hỏi chi tiết các món đã gợi ý.",
        "",
        "Bạn có thể chọn một câu hỏi phù hợp:",
    ]
    lines.extend(f"- {question}" for question in suggestions[:4])
    return "\n".join(lines)


def build_detail_answer(
    item: dict[str, Any] | None,
    detail_fields: list[str],
    detail_target: str | None = None,
) -> str:
    target_label = f"món số {detail_target}" if detail_target and detail_target.isdigit() else "món này"
    if not item:
        return f"Mình chưa tìm thấy {target_label} trong dataset hoặc lịch sử gợi ý hiện tại."

    if detail_fields == ["url"] or ("url" in detail_fields and len(detail_fields) == 1):
        url = item.get("url")
        if url:
            return f"Link {target_label}: {url}"
        return f"{target_label.capitalize()} chưa có link trong dataset."

    fields = detail_fields or [
        "name",
        "brand",
        "category",
        "price",
        "new_price",
        "voucher",
        "rating",
        "sold_count",
        "estimated_time_minutes",
        "ingredients",
        "product_info",
        "description",
        "url",
    ]

    label_map = {
        "name": "Tên món",
        "brand": "Quán/brand",
        "category": "Danh mục",
        "price": "Giá gốc",
        "new_price": "Giá sau voucher",
        "voucher": "Voucher",
        "rating": "Rating",
        "sold_count": "Lượt bán",
        "estimated_time_minutes": "Thời gian dự kiến",
        "ingredients": "Nguyên liệu",
        "origin": "Xuất xứ",
        "product_info": "Thông tin sản phẩm",
        "description": "Mô tả",
        "url": "Link món",
    }

    title = f"Thông tin {target_label}:"
    lines = [title, ""]
    for field in fields:
        label = label_map.get(field, field)
        value = _field_value(item, field)
        if field == "new_price" and value != "Chưa có thông tin trong dataset.":
            lines.append(f"- {label}: {value}")
        elif field == "estimated_time_minutes" and value != "Chưa có thông tin trong dataset.":
            lines.append(f"- {label}: {value} phút")
        elif field == "voucher" and value != "Chưa có thông tin trong dataset.":
            lines.append(f"- {label}: {value}%")
        else:
            lines.append(f"- {label}: {value}")

    return "\n".join(lines)


def run_react_agent(
    message: str,
    session: dict[str, Any],
    food_items: list[dict[str, Any]],
    data_loaded: bool,
) -> dict[str, Any]:
    trace: list[dict[str, Any]] = [
        {
            "step": "Thought",
            "content": "Người dùng gửi yêu cầu bằng tiếng Việt, cần trích xuất intent và điều kiện lọc ngắn gọn.",
        },
        {
            "step": "Action",
            "tool": "extract_filters",
            "input": message,
        },
    ]

    raw_extracted = extract_filters_with_llm(message)
    trace.append({"step": "Observation", "content": raw_extracted.model_dump()})

    old_filters = _compact_filters(session.get("last_filters") or {})
    trace.append(
        {
            "step": "Action",
            "tool": "merge_context_filters",
            "input": {
                "old_filters": old_filters,
                "new_filters": _recommendation_filters(raw_extracted),
                "old_intent": session.get("old_intent"),
            },
        }
    )
    extracted = _apply_contextual_filters(raw_extracted, message, session)
    active_filters = _recommendation_filters(extracted)
    trace.append(
        {
            "step": "Observation",
            "content": {
                "intent": extracted.intent,
                "active_filters": active_filters,
            },
        }
    )

    old_intent = session.get("old_intent")
    intent = extracted.intent

    if intent == "new_chat":
        return {
            "intent": "new_chat",
            "old_intent": old_intent,
            "answer": "Mình đã tạo đoạn chat mới.",
            "recommendations": [],
            "suggested_questions": build_suggested_questions({}),
            "react_trace": trace,
        }

    if intent == "small_talk":
        trace.append(
            {
                "step": "Action",
                "tool": "generate_small_talk_answer",
                "input": {
                    "model": _configured_openai_model(),
                    "message": message,
                },
            }
        )
        answer = generate_small_talk_answer(message, session)
        trace.append(
            {
                "step": "Observation",
                "content": "Đã trả lời ngoài phạm vi theo kiểu trả treo và kéo người dùng về đặt món.",
            }
        )
        return {
            "intent": "small_talk",
            "old_intent": old_intent,
            "answer": answer,
            "recommendations": [],
            "suggested_questions": build_suggested_questions(session),
            "react_trace": trace,
        }

    if not data_loaded:
        trace.append({"step": "Observation", "content": DATASET_MISSING_MESSAGE})
        return {
            "intent": intent,
            "old_intent": old_intent,
            "answer": build_dataset_missing_answer(),
            "recommendations": [],
            "suggested_questions": build_suggested_questions(session),
            "active_filters": active_filters,
            "react_trace": trace,
        }

    if intent in ("recommend_food", "filter_food"):
        filters = active_filters
        trace.append({"step": "Action", "tool": "filter_food_items", "input": filters})

        if extracted.max_wait_minutes is not None:
            trace.append(
                {
                    "step": "Observation",
                    "content": (
                        "Đã dùng check_wait_time_match để loại các món vượt quá "
                        f"{extracted.max_wait_minutes} phút."
                    ),
                }
            )

        trace.append({"step": "Action", "tool": "recommend_top_foods", "input": {"top_k": 3}})
        recommendations = recommend_top_foods(food_items, filters, top_k=3)
        trace.append(
            {
                "step": "Observation",
                "content": f"Tìm được {len(recommendations)} món phù hợp.",
            }
        )

        answer = build_recommendation_answer(recommendations) if recommendations else build_no_result_answer()
        return {
            "intent": intent,
            "old_intent": old_intent,
            "answer": answer,
            "recommendations": recommendations,
            "suggested_questions": build_suggested_questions(
                {
                    "last_filters": filters,
                    "last_recommendations": recommendations,
                }
            ),
            "active_filters": filters,
            "react_trace": trace,
        }

    if intent == "ask_food_detail":
        target = extracted.detail_target
        if not target and session.get("last_recommendations"):
            target = "1"
        trace.append(
            {
                "step": "Action",
                "tool": "get_food_detail",
                "input": {
                    "detail_target": target,
                    "detail_fields": extracted.detail_fields,
                    "keyword": extracted.keyword,
                },
            }
        )
        item = get_food_detail(
            food_items,
            detail_target=target,
            last_recommendations=session.get("last_recommendations", []),
            keyword=extracted.keyword,
        )
        trace.append(
            {
                "step": "Observation",
                "content": "Đã tìm thấy món trong dataset." if item else "Không tìm thấy món phù hợp.",
            }
        )
        return {
            "intent": intent,
            "old_intent": old_intent,
            "answer": build_detail_answer(item, extracted.detail_fields, target),
            "recommendations": [],
            "suggested_questions": build_suggested_questions(session),
            "react_trace": trace,
        }

    trace.append(
        {
            "step": "Observation",
            "content": "Yêu cầu nằm ngoài phạm vi gợi ý món ăn nên agent không trả lời nội dung đó.",
        }
    )
    return {
        "intent": "unknown",
        "old_intent": old_intent,
        "answer": build_unknown_answer(session),
        "recommendations": [],
        "suggested_questions": build_suggested_questions(session),
        "react_trace": trace,
    }
