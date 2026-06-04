from __future__ import annotations

import copy
import math
import random
import re
import unicodedata
from typing import Any


DEFAULT_FOOD_ITEM: dict[str, Any] = {
    "url": "",
    "name": "Không rõ tên món",
    "price": 0,
    "ingredients": [],
    "origin": "",
    "product_info": "",
    "description": "",
    "category": ["Khác"],
    "product_code": "",
    "brand": "",
    "sold_count": 0,
    "image_urls": [],
    "error": None,
    "voucher": 0,
    "distance_km": 3,
    "prep_time_minutes": 15,
    "rating": 0,
}


def _is_missing(value: Any) -> bool:
    if value is None or value == "":
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if str(value).strip().casefold() == "nan":
        return True
    return False


def parse_price(price: Any) -> int:
    """Normalize a mixed price value to an integer VND amount."""
    if _is_missing(price):
        return 0

    if isinstance(price, bool):
        return 0

    if isinstance(price, (int, float)):
        try:
            return max(0, int(round(float(price))))
        except (TypeError, ValueError, OverflowError):
            return 0

    text = str(price).strip()
    if not text:
        return 0

    candidates: list[int] = []
    for match in re.finditer(r"\d+(?:[\.,]\d+)*(?:\s*[kK])?", text):
        raw = match.group(0).replace(" ", "").lower()
        if not raw:
            continue

        if raw.endswith("k"):
            number_text = raw[:-1].replace(",", ".")
            try:
                candidates.append(max(0, int(round(float(number_text) * 1000))))
                continue
            except ValueError:
                raw = raw[:-1]

        digits = re.sub(r"\D", "", raw)
        if digits:
            candidates.append(max(0, int(digits)))

    return min(candidates) if candidates else 0


def _to_number(value: Any, default: float = 0) -> float:
    if _is_missing(value):
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        try:
            return float(value)
        except (TypeError, ValueError, OverflowError):
            return default

    text = str(value).strip()
    if not text:
        return default

    match = re.search(r"-?\d+(?:[\.,]\d+)?", text)
    if not match:
        return default
    try:
        return float(match.group(0).replace(",", "."))
    except ValueError:
        return default


def _to_int(value: Any, default: int = 0) -> int:
    return int(round(_to_number(value, default)))


def _to_string(value: Any, default: str = "") -> str:
    if _is_missing(value):
        return default
    text = str(value).strip()
    return text if text else default


def _to_list(value: Any) -> list[Any]:
    if _is_missing(value):
        return []
    if isinstance(value, list):
        return [item for item in value if not _is_missing(item)]
    return [value]


def _to_string_list(value: Any, default: str = "Khác") -> list[str]:
    items = [str(item).strip() for item in _to_list(value)]
    cleaned = [item for item in items if item and item.casefold() != "nan"]
    return cleaned or [default]


def normalize_food_item(item: Any) -> dict[str, Any]:
    """Return a safe food item with defaults while preserving unknown fields."""
    source = item if isinstance(item, dict) else {}
    normalized = copy.deepcopy(source)

    for key, default_value in DEFAULT_FOOD_ITEM.items():
        if key not in normalized or _is_missing(normalized[key]):
            normalized[key] = copy.deepcopy(default_value)

    normalized["url"] = _to_string(normalized.get("url"), "")
    normalized["name"] = _to_string(normalized.get("name"), "Không rõ tên món")
    normalized["origin"] = _to_string(normalized.get("origin"), "")
    normalized["product_info"] = _to_string(normalized.get("product_info"), "")
    normalized["description"] = _to_string(normalized.get("description"), "")
    normalized["category"] = _to_string_list(normalized.get("category"), "Khác")
    normalized["product_code"] = _to_string(normalized.get("product_code"), "")
    normalized["brand"] = _to_string(normalized.get("brand"), "")
    normalized["ingredients"] = _to_list(normalized.get("ingredients"))
    normalized["image_urls"] = [str(url) for url in _to_list(normalized.get("image_urls"))]
    normalized["sold_count"] = max(0, _to_int(normalized.get("sold_count"), 0))
    normalized["voucher"] = _to_number(normalized.get("voucher"), 0)
    normalized["distance_km"] = _to_number(normalized.get("distance_km"), 3)
    normalized["prep_time_minutes"] = _to_number(normalized.get("prep_time_minutes"), 15)
    normalized["rating"] = _to_number(normalized.get("rating"), 0)

    return normalized


def calculate_new_price(price: Any, voucher: Any = 0) -> dict[str, int]:
    price_value = max(0, parse_price(price))
    voucher_value = _to_number(voucher, 0)
    voucher_value = min(100, max(0, voucher_value))
    new_price = int(round(price_value * (1 - voucher_value / 100)))
    return {"new_price": max(0, new_price)}


def calculate_estimated_time(
    distance_km: Any = 3,
    prep_time_minutes: Any = 15,
) -> dict[str, int]:
    distance_value = max(0, _to_number(distance_km, 3))
    prep_value = max(0, _to_number(prep_time_minutes, 15))
    estimated_time = int(round(prep_value + (distance_value / 30) * 60))
    return {"estimated_time_minutes": estimated_time}


def check_wait_time_match(
    estimated_time_minutes: Any,
    max_wait_minutes: Any,
) -> dict[str, Any]:
    if max_wait_minutes is None:
        return {
            "is_match": True,
            "message": "Không có điều kiện thời gian chờ.",
        }

    estimated = max(0, _to_number(estimated_time_minutes, 0))
    max_wait = max(0, _to_number(max_wait_minutes, 0))
    is_match = estimated <= max_wait
    return {
        "is_match": is_match,
        "message": (
            "Món này nằm trong thời gian chờ mong muốn."
            if is_match
            else "Món này vượt thời gian chờ mong muốn."
        ),
    }


def enrich_food_items_with_tools(items: list[Any]) -> list[dict[str, Any]]:
    enriched_items: list[dict[str, Any]] = []
    for raw_item in items:
        normalized = normalize_food_item(raw_item)
        parsed_price = parse_price(normalized.get("price"))
        new_price = calculate_new_price(parsed_price, normalized.get("voucher"))["new_price"]
        estimated_time = calculate_estimated_time(
            normalized.get("distance_km"),
            normalized.get("prep_time_minutes"),
        )["estimated_time_minutes"]

        normalized["parsed_price"] = parsed_price
        normalized["new_price"] = new_price
        normalized["estimated_time_minutes"] = estimated_time
        enriched_items.append(normalized)

    return enriched_items


def _filters_to_dict(filters: Any) -> dict[str, Any]:
    if filters is None:
        return {}
    if isinstance(filters, dict):
        return filters
    if hasattr(filters, "model_dump"):
        return filters.model_dump()
    if hasattr(filters, "dict"):
        return filters.dict()
    return {}


def _contains_casefold(haystack: Any, needle: Any) -> bool:
    haystack_text = _plain_text(haystack)
    needle_text = _plain_text(needle).strip()
    return bool(needle_text and needle_text in haystack_text)


def _category_texts(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if not _is_missing(item)]
    if _is_missing(value):
        return []
    return [str(value)]


def _category_matches(item_category: Any, category_filter: Any) -> bool:
    if not category_filter:
        return True
    item_categories = _category_texts(item_category)
    filter_categories = _category_texts(category_filter)
    return any(
        _contains_casefold(item_text, filter_text)
        or _contains_casefold(filter_text, item_text)
        for item_text in item_categories
        for filter_text in filter_categories
    )


def _plain_text(value: Any) -> str:
    text = str(value or "")
    normalized = unicodedata.normalize("NFD", text)
    no_accent = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return no_accent.casefold()


def _searchable_text(item: dict[str, Any]) -> str:
    values = [
        item.get("name"),
        item.get("brand"),
        " ".join(_category_texts(item.get("category"))),
        item.get("origin"),
        item.get("product_info"),
        item.get("description"),
        " ".join(str(value) for value in item.get("ingredients", [])),
    ]
    return _plain_text(" ".join(str(value or "") for value in values))


def filter_food_items(items: list[dict[str, Any]], filters: Any) -> list[dict[str, Any]]:
    filter_data = _filters_to_dict(filters)
    rating_min = filter_data.get("rating_min")
    price_min = filter_data.get("price_min")
    price_max = filter_data.get("price_max")
    category = filter_data.get("category")
    max_wait_minutes = filter_data.get("max_wait_minutes")
    keyword = filter_data.get("keyword")

    results: list[dict[str, Any]] = []
    for item in items:
        if rating_min is not None and _to_number(item.get("rating"), 0) < _to_number(rating_min, 0):
            continue
        if price_min is not None and _to_number(item.get("new_price"), 0) < _to_number(price_min, 0):
            continue
        if price_max is not None and _to_number(item.get("new_price"), 0) > _to_number(price_max, 0):
            continue
        if category and not _category_matches(item.get("category"), category):
            continue
        if max_wait_minutes is not None:
            wait_result = check_wait_time_match(
                item.get("estimated_time_minutes"),
                max_wait_minutes,
            )
            if not wait_result["is_match"]:
                continue
        if keyword and _plain_text(keyword).strip() not in _searchable_text(item):
            continue

        results.append(item)

    return results


def _has_error(item: dict[str, Any]) -> bool:
    error = item.get("error")
    if error is None:
        return False
    if isinstance(error, str) and not error.strip():
        return False
    return True


def rank_food_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked_items: list[dict[str, Any]] = []
    for item in items:
        score = 0.0
        score += _to_number(item.get("rating"), 0) * 20
        score += min(_to_number(item.get("sold_count"), 0) / 100, 20)
        score += _to_number(item.get("voucher"), 0) * 0.5
        score -= _to_number(item.get("estimated_time_minutes"), 0) * 0.5
        score -= _to_number(item.get("new_price"), 0) / 10000

        if _has_error(item):
            score -= 20
        if item.get("url"):
            score += 2
        if item.get("image_urls"):
            score += 2

        ranked_item = copy.deepcopy(item)
        ranked_item["_score"] = round(score, 3)
        ranked_items.append(ranked_item)

    return sorted(ranked_items, key=lambda food: food.get("_score", 0), reverse=True)


def _build_reason(item: dict[str, Any], filters: dict[str, Any]) -> str:
    pieces = [
        f"rating {item.get('rating', 0)}",
        f"giá sau voucher {item.get('new_price', 0)}đ",
        f"dự kiến {item.get('estimated_time_minutes', 0)} phút",
    ]
    if item.get("sold_count"):
        pieces.append(f"đã bán {item.get('sold_count')}")
    if item.get("voucher"):
        pieces.append(f"voucher {item.get('voucher')}%")
    if filters.get("category"):
        pieces.append(f"phù hợp danh mục {', '.join(_category_texts(filters.get('category')))}")
    if filters.get("max_wait_minutes") is not None:
        pieces.append(f"không vượt {filters.get('max_wait_minutes')} phút")
    if filters.get("randomize"):
        pieces.append("được chọn ngẫu nhiên trong nhóm phù hợp")
    if _has_error(item):
        pieces.append("có cảnh báo crawl nên đã bị trừ điểm")
    return "Món này nổi bật vì " + ", ".join(pieces) + "."


def _recommendation_shape(item: dict[str, Any], reason: str) -> dict[str, Any]:
    keys = [
        "url",
        "name",
        "brand",
        "category",
        "price",
        "parsed_price",
        "new_price",
        "voucher",
        "rating",
        "distance_km",
        "prep_time_minutes",
        "estimated_time_minutes",
        "sold_count",
        "image_urls",
        "ingredients",
        "origin",
        "product_info",
        "description",
        "product_code",
        "error",
    ]
    recommendation = {key: item.get(key, copy.deepcopy(DEFAULT_FOOD_ITEM.get(key))) for key in keys}
    recommendation["reason"] = reason
    return recommendation


def recommend_top_foods(
    items: list[dict[str, Any]],
    filters: Any | None = None,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    filter_data = _filters_to_dict(filters)
    filtered = filter_food_items(items, filter_data)
    ranked = rank_food_items(filtered)
    if filter_data.get("randomize"):
        random_pool = ranked[: min(len(ranked), max(top_k * 6, 12))]
        random.shuffle(random_pool)
        ranked = random_pool + ranked[len(random_pool) :]
    return [
        _recommendation_shape(item, _build_reason(item, filter_data))
        for item in ranked[: max(0, top_k)]
    ]


def _matches_name(item: dict[str, Any], query: str) -> bool:
    name = str(item.get("name") or "").casefold()
    query_text = query.casefold().strip()
    return bool(query_text and (query_text in name or name in query_text))


def get_food_detail(
    items: list[dict[str, Any]],
    detail_target: str | None = None,
    last_recommendations: list[dict[str, Any]] | None = None,
    keyword: str | None = None,
) -> dict[str, Any] | None:
    last_recommendations = last_recommendations or []

    if detail_target and str(detail_target).isdigit():
        index = int(detail_target) - 1
        if 0 <= index < len(last_recommendations):
            return last_recommendations[index]
        return None

    query = (detail_target or keyword or "").strip()
    if query:
        for item in last_recommendations:
            if _matches_name(item, query):
                return item
        for item in items:
            if _matches_name(item, query):
                return item

    return None
