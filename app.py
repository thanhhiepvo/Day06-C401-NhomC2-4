import csv
import json
import os
import re
import unicodedata
from pathlib import Path
from urllib.parse import quote_plus

import streamlit as st
from openai import OpenAI


def load_env_files() -> None:
    for env_file in (Path(".env"), Path(".evn")):
        if not env_file.exists():
            continue

        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            key = key.strip().removeprefix("export ").strip()
            value = value.strip().strip('"').strip("'")

            if key and key not in os.environ:
                os.environ[key] = value


def get_ai_client() -> tuple[OpenAI, str]:
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if openai_api_key:
        return OpenAI(api_key=openai_api_key), os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    openrouter_api_key = os.environ.get("OPENROUTER_API_KEY")
    if openrouter_api_key:
        return (
            OpenAI(
                api_key=openrouter_api_key,
                base_url="https://openrouter.ai/api/v1",
            ),
            os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
        )

    raise ValueError("Missing API key")


def load_app_config() -> dict[str, object]:
    config_path = Path(__file__).parent / "data" / "app_config.json"
    if config_path.exists():
        return json.loads(config_path.read_text(encoding="utf-8"))

    return {
        "max_recommendations": 3,
        "default_max_eta_minutes": 30,
        "budget_tolerance_percent": 15,
        "supported_constraints": [
            "cheaper",
            "not_spicy",
            "faster",
            "lighter",
            "more_filling",
            "different_from_history",
        ],
    }


def load_meals_dataset() -> list[dict[str, object]]:
    menu_path = Path(__file__).parent / "data" / "menu_items.json"
    if menu_path.exists():
        menu_items = json.loads(menu_path.read_text(encoding="utf-8"))
        return [
            {
                "id": item["id"],
                "name": item["dish"],
                "store": item["store"],
                "time_tags": item["meal_time"],
                "price": int(item["price"]),
                "min_price": int(item["price"]),
                "max_price": int(item["price"]),
                "eta_minutes": int(item["eta_minutes"]),
                "rating": float(item["rating"]),
                "category": item["category"],
                "cuisine": item.get("cuisine", "vietnamese"),
                "spicy": bool(item["spicy"]),
                "available": bool(item["available"]),
                "available_locations": item.get(
                    "available_locations",
                    ["ho-chi-minh", "ha-noi", "da-nang"],
                ),
                "tags": " ".join(item["reason_tags"]),
                "reason_tags": item["reason_tags"],
                "description": f"{item['store']}, giao khoảng {item['eta_minutes']} phút",
                "shopeefood_search_url": item["shopeefood_search_url"],
            }
            for item in menu_items
        ]

    dataset_path = Path(__file__).with_name("meals_dataset.csv")
    meals = []

    with dataset_path.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            min_price = int(row["min_price"])
            max_price = int(row["max_price"])
            meals.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "store": "ShopeeFood",
                    "time_tags": row["time_tags"].split(),
                    "price": min_price,
                    "min_price": min_price,
                    "max_price": max_price,
                    "eta_minutes": 30,
                    "rating": 4.5,
                    "category": "food",
                    "cuisine": "vietnamese",
                    "spicy": "spicy" in row["tags"],
                    "available": True,
                    "available_locations": ["ho-chi-minh", "ha-noi", "da-nang"],
                    "tags": row["tags"],
                    "reason_tags": row["tags"].split(),
                    "description": row["description"],
                    "shopeefood_search_url": shopeefood_search_url(row["name"]),
                }
            )

    return meals


def normalize_text(text: str) -> str:
    lowered = text.lower().replace("đ", "d")
    without_accents = unicodedata.normalize("NFD", lowered)
    return "".join(char for char in without_accents if unicodedata.category(char) != "Mn")


def extract_budget(text: str) -> int | None:
    lowered = normalize_text(text)
    match = re.search(r"(\d+)\s*k\b", lowered)
    if match:
        return int(match.group(1)) * 1000

    match = re.search(r"(\d+)\s*(nghin|ngan|k vnd)", lowered)
    if match:
        return int(match.group(1)) * 1000

    numbers = [int(value.replace(".", "").replace(",", "")) for value in re.findall(r"\d[\d.,]*", lowered)]
    likely_budgets = [number for number in numbers if number >= 10000]
    if likely_budgets:
        return likely_budgets[0]

    return None


def parse_budget(text: str) -> int:
    return extract_budget(text) or 50000


def extract_time_of_day(text: str) -> str | None:
    lowered = normalize_text(text)
    if any(keyword in lowered for keyword in ("sang", "morning", "breakfast", "an sang", "bua sang")):
        return "morning"
    if any(keyword in lowered for keyword in ("trua", "lunch", "noon", "an trua", "bua trua")):
        return "lunch"
    if any(keyword in lowered for keyword in ("toi", "dinner", "evening", "an toi", "bua toi")):
        return "dinner"
    return None


def parse_time_of_day(text: str) -> str:
    return extract_time_of_day(text) or "lunch"


def extract_location(text: str) -> str | None:
    lowered = normalize_text(text)

    location_patterns = [
        ("VinUni/Gia Lâm, Hà Nội", ("vinuni", "vin uni", "gia lam", "vincity ocean park", "ocean park")),
        ("Hà Nội", ("ha noi", "hanoi", "hn", "cau giay", "dong da", "hoan kiem", "ba dinh", "tay ho")),
        (
            "TP.HCM",
            (
                "tp hcm",
                "tphcm",
                "ho chi minh",
                "sai gon",
                "saigon",
                "quan 1",
                "quan 3",
                "quan 4",
                "quan 5",
                "quan 7",
                "quan 10",
                "binh thanh",
                "phu nhuan",
                "thu duc",
                "tan binh",
            ),
        ),
        ("Đà Nẵng", ("da nang", "danang", "hai chau", "son tra")),
    ]

    for location, patterns in location_patterns:
        if any(pattern in lowered for pattern in patterns):
            return location

    if re.search(r"\bq\s*\d+\b", lowered):
        return "TP.HCM"

    return None


def city_slug_from_location(location: str | None) -> str:
    if not location:
        return os.environ.get("SHOPEEFOOD_CITY_SLUG", "ho-chi-minh").strip() or "ho-chi-minh"

    normalized_location = normalize_text(location)
    if "ha noi" in normalized_location or "vinuni" in normalized_location or "gia lam" in normalized_location:
        return "ha-noi"
    if "da nang" in normalized_location:
        return "da-nang"
    if "tp.hcm" in location.lower() or "hcm" in normalized_location or "sai gon" in normalized_location:
        return "ho-chi-minh"

    return os.environ.get("SHOPEEFOOD_CITY_SLUG", "ho-chi-minh").strip() or "ho-chi-minh"


def extract_cuisine_preference(text: str) -> str | None:
    lowered = normalize_text(text)
    cuisine_aliases = {
        "korean": ("mon han", "do han", "han quoc", "korean", "kimchi", "kimbap", "tokbokki", "tteokbokki"),
        "japanese": ("mon nhat", "do nhat", "nhat ban", "japanese", "sushi", "ramen", "udon"),
        "thai": ("mon thai", "do thai", "thai lan", "thai food", "tom yum", "pad thai"),
        "western": ("mon au", "do au", "western", "pasta", "pizza", "burger"),
        "vietnamese": ("mon viet", "do viet", "viet nam", "vietnamese"),
        "vegetarian": ("mon chay", "do chay", "vegetarian", "vegan"),
    }

    for cuisine, aliases in cuisine_aliases.items():
        if any(alias in lowered for alias in aliases):
            return cuisine

    return None


def cuisine_label(cuisine: str | None) -> str:
    labels = {
        "korean": "món Hàn",
        "japanese": "món Nhật",
        "thai": "món Thái",
        "western": "món Âu",
        "vietnamese": "món Việt",
        "vegetarian": "món chay",
    }
    return labels.get(cuisine or "", cuisine or "không rõ")


def extract_eta_limit(text: str) -> int | None:
    lowered = normalize_text(text)
    match = re.search(r"(?:duoi|trong|toi da|max|<=|<)\s*(\d+)\s*(?:phut|p|min)", lowered)
    if match:
        return int(match.group(1))

    match = re.search(r"(\d+)\s*(?:phut|p|min)\s*(?:tro lai|thoi|do lai)", lowered)
    if match:
        return int(match.group(1))

    match = re.fullmatch(r"\s*(\d+)\s*(?:phut|p|min)\s*", lowered)
    if match:
        return int(match.group(1))

    return None


def eta_is_optional(text: str) -> bool:
    lowered = normalize_text(text)
    return any(
        phrase in lowered
        for phrase in (
            "khong voi",
            "khong can nhanh",
            "giao luc nao cung duoc",
            "eta nao cung duoc",
            "thoi gian giao khong quan trong",
        )
    )


def extract_short_eta_answer(text: str) -> int | None:
    lowered = normalize_text(text).strip()
    match = re.search(r"(\d+)\s*(?:phut|p|min)?", lowered)
    if not match:
        return None

    value = int(match.group(1))
    if 1 <= value <= 180:
        return value

    return None


def parse_avoid_terms(text: str) -> set[str]:
    lowered = normalize_text(text)
    avoid_terms = set()
    stopwords = {
        "mon",
        "do",
        "an",
        "qua",
        "nhieu",
        "nua",
        "va",
        "voi",
        "giao",
        "duoi",
        "phut",
        "ngan",
        "sach",
    }

    for pattern in (
        r"(?:khong an|khong thich|khong muon|ne|tranh)\s+([^,.]+)",
        r"(?:avoid|dislike)\s+([^,.]+)",
    ):
        for match in re.finditer(pattern, lowered):
            phrase = match.group(1)
            for token in re.findall(r"\w+", phrase):
                if len(token) >= 3 and token not in stopwords:
                    avoid_terms.add(token)

    if any(phrase in lowered for phrase in ("khong cay", "ko cay", "it cay", "ne cay", "not spicy")):
        avoid_terms.add("cay")

    return avoid_terms


def has_avoid_info(text: str) -> bool:
    lowered = normalize_text(text)
    if parse_avoid_terms(text):
        return True

    return any(
        phrase in lowered
        for phrase in (
            "khong co mon tranh",
            "khong can tranh",
            "khong co gi can tranh",
            "khong co",
            "khong gi",
            "khong can",
            "none",
            "no avoid",
            "gi cung duoc",
        )
    )


def parse_constraints(text: str) -> set[str]:
    lowered = normalize_text(text)
    constraints = set()

    if any(keyword in lowered for keyword in ("re hon", "gia re", "tiet kiem", "duoi ngan sach", "cheap")) or re.search(
        r"\bre\b", lowered
    ):
        constraints.add("cheaper")
    if any(keyword in lowered for keyword in ("khong cay", "ko cay", "it cay", "ne cay", "not spicy")):
        constraints.add("not_spicy")
    if any(keyword in lowered for keyword in ("giao nhanh", "nhanh hon", "ship nhanh", "eta", "faster")):
        constraints.add("faster")
    if any(keyword in lowered for keyword in ("nhe bung", "an nhe", "healthy", "it dau", "lighter")):
        constraints.add("lighter")
    if any(keyword in lowered for keyword in ("no hon", "an no", "chac bung", "more filling")):
        constraints.add("more_filling")
    if any(keyword in lowered for keyword in ("doi mon", "khac di", "dung giong", "khong giong", "different")):
        constraints.add("different_from_history")

    return constraints


def parse_eta_limit(text: str, constraints: set[str], app_config: dict[str, object]) -> int:
    default_eta = int(app_config.get("default_max_eta_minutes", 30))
    explicit_eta = extract_eta_limit(text)
    if explicit_eta is not None:
        return explicit_eta
    if eta_is_optional(text):
        return 45
    if "faster" in constraints:
        return min(default_eta, 22)
    return default_eta


def has_food_preference_or_history(
    text: str,
    meals: list[dict[str, object]],
    constraints: set[str],
) -> bool:
    lowered = normalize_text(text)
    if extract_cuisine_preference(text):
        return True
    if constraints - {"cheaper", "faster"}:
        return True

    preference_phrases = (
        "thich",
        "hay an",
        "gan day",
        "history",
        "mon quen",
        "gi cung duoc",
        "an gi cung duoc",
        "khong thich",
        "ne",
        "tranh",
    )
    food_terms = {
        "com",
        "bun",
        "pho",
        "banh",
        "mi",
        "chao",
        "xoi",
        "goi",
        "sup",
        "ga",
        "bo",
        "chay",
        "ca",
        "tom",
    }
    if any(keyword in lowered for keyword in preference_phrases):
        return True

    words = set(re.findall(r"\w+", lowered))
    if words & food_terms:
        return True

    for meal in meals:
        searchable_text = normalize_text(f"{meal['name']} {meal['category']} {meal['tags']}")
        if any(token in lowered for token in searchable_text.split() if len(token) >= 4):
            return True

    return False


def get_missing_context(user_context: str, meals: list[dict[str, object]]) -> list[str]:
    constraints = parse_constraints(user_context)
    missing = []

    if extract_location(user_context) is None:
        missing.append("location")
    if extract_time_of_day(user_context) is None:
        missing.append("time")
    if extract_budget(user_context) is None:
        missing.append("budget")
    if not has_food_preference_or_history(user_context, meals, constraints):
        missing.append("preference")
    if not has_avoid_info(user_context):
        missing.append("avoid")
    if extract_eta_limit(user_context) is None and not eta_is_optional(user_context) and "faster" not in constraints:
        missing.append("eta")

    return missing


def build_clarifying_question(missing_context: list[str]) -> str:
    if not missing_context:
        return ""

    questions = {
        "location": "Bạn đang ở khu vực/thành phố nào? Ví dụ: VinUni/Gia Lâm, Cầu Giấy, Quận 1.",
        "time": "Bạn muốn ăn bữa nào: sáng, trưa hay tối?",
        "budget": "Ngân sách khoảng bao nhiêu VND? Ví dụ: 50k.",
        "preference": "Bạn muốn ăn kiểu/món gì? Ví dụ: món Hàn, cơm, bún, ăn nhẹ.",
        "avoid": "Có món/vị nào cần tránh không? Ví dụ: không cay, không bò, hoặc không có.",
        "eta": "Bạn muốn giao tối đa bao lâu? Ví dụ: dưới 25 phút, hoặc không vội.",
    }
    return questions[missing_context[0]]


def empty_collected_context() -> dict[str, object]:
    return {
        "location": None,
        "time": None,
        "budget": None,
        "preference": None,
        "avoid": None,
        "eta": None,
    }


def infer_pending_field_from_assistant(message: str) -> str | None:
    lowered = normalize_text(message)
    if "khu vuc" in lowered or "thanh pho" in lowered or "dang o dau" in lowered:
        return "location"
    if "bua nao" in lowered or "sang, trua hay toi" in lowered:
        return "time"
    if "ngan sach" in lowered:
        return "budget"
    if "kieu/mon" in lowered or "muon an kieu" in lowered:
        return "preference"
    if "can tranh" in lowered or "mon/vi" in lowered:
        return "avoid"
    if "giao toi da" in lowered:
        return "eta"

    return None


def update_collected_context(
    context: dict[str, object],
    text: str,
    meals: list[dict[str, object]],
    pending_field: str | None = None,
) -> bool:
    before = dict(context)
    lowered = normalize_text(text).strip()
    constraints = parse_constraints(text)

    location = extract_location(text)
    if location:
        context["location"] = location

    time_of_day = extract_time_of_day(text)
    if time_of_day:
        context["time"] = time_of_day

    budget = extract_budget(text)
    if budget is None and pending_field == "budget":
        match = re.fullmatch(r"\s*(\d+)\s*", lowered)
        if match:
            short_budget = int(match.group(1))
            if 1 <= short_budget < 1000:
                budget = short_budget * 1000
    if budget is not None:
        context["budget"] = budget

    cuisine = extract_cuisine_preference(text)
    if cuisine:
        context["preference"] = cuisine_label(cuisine)
    elif pending_field == "preference" and text.strip():
        context["preference"] = text.strip()
    elif pending_field != "avoid" and not (constraints and constraints <= {"not_spicy"}):
        if has_food_preference_or_history(text, meals, constraints):
            context["preference"] = text.strip()

    if has_avoid_info(text):
        context["avoid"] = text.strip() or "không có món tránh"
    elif pending_field == "avoid" and lowered in {"khong", "khong gi", "none", "no"}:
        context["avoid"] = "không có món tránh"
    elif pending_field == "avoid" and text.strip():
        context["avoid"] = text.strip()

    eta_limit = extract_eta_limit(text)
    if eta_limit is None and pending_field == "eta":
        eta_limit = extract_short_eta_answer(text)
    if eta_limit is not None:
        context["eta"] = f"dưới {eta_limit} phút"
    elif eta_is_optional(text):
        context["eta"] = "không vội"
    elif "faster" in constraints:
        context["eta"] = "giao nhanh hơn"

    return before != context


def hydrate_context_from_messages(messages: list[dict[str, str]], meals: list[dict[str, object]]) -> dict[str, object]:
    context = empty_collected_context()
    pending_field = None

    for message in messages:
        if message["role"] == "assistant":
            inferred_field = infer_pending_field_from_assistant(message["content"])
            if inferred_field:
                pending_field = inferred_field
            continue

        if message["role"] == "user":
            update_collected_context(context, message["content"], meals, pending_field)
            pending_field = None

    return context


def collected_context_to_text(context: dict[str, object]) -> str:
    parts = []
    if context.get("location"):
        parts.append(f"Vị trí: {context['location']}")
    if context.get("time"):
        parts.append(f"Bữa ăn: {context['time']}")
    if context.get("budget"):
        parts.append(f"Ngân sách: {context['budget']} VND")
    if context.get("preference"):
        parts.append(f"Sở thích/cuisine: {context['preference']}")
    if context.get("avoid"):
        parts.append(f"Cần tránh: {context['avoid']}")
    if context.get("eta"):
        parts.append(f"ETA: {context['eta']}")

    return "\n".join(parts)


def try_ai_update_collected_context(
    context: dict[str, object],
    messages: list[dict[str, str]],
    pending_field: str | None,
) -> bool:
    if not pending_field or context.get(pending_field):
        return False

    try:
        client, model = get_ai_client()
        conversation = "\n".join(f"{message['role']}: {message['content']}" for message in messages[-8:])
        response = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract only the requested missing field for a meal recommendation chat. "
                        "Return strict JSON only. Use null if unknown. Keys: "
                        "location, time, budget, preference, avoid, eta."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Missing field: {pending_field}\n"
                        f"Conversation:\n{conversation}\n\n"
                        "Return JSON like {\"location\": null, \"time\": null, "
                        "\"budget\": null, \"preference\": null, \"avoid\": null, \"eta\": null}."
                    ),
                },
            ],
            temperature=0,
            max_tokens=120,
        )
        raw_content = response.choices[0].message.content or "{}"
        json_match = re.search(r"\{.*\}", raw_content, flags=re.DOTALL)
        if not json_match:
            return False

        extracted = json.loads(json_match.group(0))
        value = extracted.get(pending_field)
        if value in (None, "", [], {}):
            return False

        context[pending_field] = value
        return True
    except Exception:
        return False


def build_requirements(user_message: str, app_config: dict[str, object]) -> dict[str, object]:
    constraints = parse_constraints(user_message)
    location = extract_location(user_message)
    eta_optional = eta_is_optional(user_message)

    return {
        "location": location,
        "city_slug": city_slug_from_location(location),
        "budget": parse_budget(user_message),
        "time_of_day": parse_time_of_day(user_message),
        "cuisine": extract_cuisine_preference(user_message),
        "constraints": constraints,
        "avoid_terms": parse_avoid_terms(user_message),
        "max_eta_minutes": parse_eta_limit(user_message, constraints, app_config),
        "eta_optional": eta_optional,
        "budget_tolerance_percent": int(app_config.get("budget_tolerance_percent", 15)),
    }


def meal_matches_cuisine(meal: dict[str, object], cuisine: str | None) -> bool:
    if not cuisine:
        return True

    if cuisine == "vegetarian":
        searchable_text = normalize_text(f"{meal['name']} {meal['category']} {meal['tags']}")
        return meal["category"] == "vegetarian" or "chay" in searchable_text or "vegetarian" in searchable_text

    return str(meal.get("cuisine", "vietnamese")) == cuisine


def meal_matches_avoid_preferences(
    meal: dict[str, object],
    constraints: set[str],
    avoid_terms: set[str],
) -> bool:
    if "not_spicy" in constraints and meal["spicy"]:
        return False

    searchable_text = normalize_text(f"{meal['name']} {meal['category']} {meal['tags']}")
    for term in avoid_terms:
        if term == "cay":
            if meal["spicy"]:
                return False
            continue
        if term in searchable_text:
            return False

    return True


def get_constraint_issues(meal: dict[str, object], requirements: dict[str, object]) -> list[str]:
    issues = []
    budget = int(requirements["budget"])
    max_eta_minutes = int(requirements["max_eta_minutes"])
    city_slug = str(requirements["city_slug"])

    if not meal["available"]:
        issues.append("availability")
    if city_slug not in meal.get("available_locations", []):
        issues.append("location")
    if requirements["time_of_day"] not in meal["time_tags"]:
        issues.append("time")
    if not meal_matches_cuisine(meal, requirements["cuisine"]):
        issues.append("cuisine")
    if int(meal["price"]) > budget:
        issues.append("budget")
    if not requirements["eta_optional"] and int(meal["eta_minutes"]) > max_eta_minutes:
        issues.append("eta")
    if not meal_matches_avoid_preferences(
        meal,
        requirements["constraints"],
        requirements["avoid_terms"],
    ):
        issues.append("avoid")

    return issues


def relaxed_constraint_labels(constraints: list[str]) -> str:
    labels = {
        "cuisine": "cuisine preference",
        "budget": "budget",
        "eta": "delivery time limit",
        "time": "meal time",
    }
    return ", ".join(labels.get(constraint, constraint) for constraint in constraints)


def score_meal(
    meal: dict[str, object],
    user_message: str,
    requirements: dict[str, object],
) -> float:
    lowered = normalize_text(user_message)
    score = 0.0
    time_of_day = str(requirements["time_of_day"])
    budget = int(requirements["budget"])
    constraints = requirements["constraints"]
    max_eta_minutes = int(requirements["max_eta_minutes"])

    if time_of_day in meal["time_tags"]:
        score += 8
    if meal_matches_cuisine(meal, requirements["cuisine"]):
        score += 12

    price = int(meal["price"])
    if price <= budget:
        score += 6
    elif price <= int(budget * 1.15):
        score += 3
    if "cheaper" in constraints and price <= int(budget * 0.9):
        score += 4

    eta_minutes = int(meal["eta_minutes"])
    if eta_minutes <= max_eta_minutes:
        score += 4
    if "faster" in constraints:
        score += max(0, max_eta_minutes - eta_minutes) / 4

    if "not_spicy" in constraints and meal["spicy"]:
        score -= 20
    if "lighter" in constraints and (
        meal["category"] in ("light", "soup", "vegetarian") or "lighter" in meal["reason_tags"]
    ):
        score += 6
    if "more_filling" in constraints and (
        meal["category"] in ("rice", "office_rice", "noodle_soup", "noodle_dry")
        or "filling" in meal["reason_tags"]
    ):
        score += 6

    searchable_text = normalize_text(f"{meal['name']} {meal['category']} {meal['tags']}")
    exact_history_match = normalize_text(str(meal["name"])) in lowered
    if exact_history_match and "different_from_history" not in constraints:
        score += 16
    if exact_history_match and "different_from_history" in constraints:
        score -= 12

    for token in re.findall(r"[\wÀ-ỹ]+", lowered):
        if len(token) >= 3 and token in searchable_text:
            score += 5

    score += float(meal["rating"]) / 2
    score -= len(meal.get("relaxed_constraints", [])) * 4

    return score


def filter_meals(
    meals: list[dict[str, object]],
    user_message: str,
    app_config: dict[str, object],
) -> tuple[list[dict[str, object]], int]:
    requirements = build_requirements(user_message, app_config)
    budget = int(requirements["budget"])
    budget_tolerance = int(requirements["budget_tolerance_percent"])
    max_eta_minutes = int(requirements["max_eta_minutes"])
    close_budget = int(budget * (1 + budget_tolerance / 100))
    relaxed_eta_limit = max_eta_minutes + 10

    exact_candidates = []
    relaxed_candidates = []

    for meal in meals:
        issues = get_constraint_issues(meal, requirements)
        candidate = {**meal, "relaxed_constraints": []}

        if not issues:
            exact_candidates.append(candidate)
            continue

        non_relaxable_issues = {"availability", "location", "avoid"}
        if any(issue in non_relaxable_issues for issue in issues):
            continue
        if "budget" in issues and int(meal["price"]) > close_budget:
            continue
        if "eta" in issues and int(meal["eta_minutes"]) > relaxed_eta_limit:
            continue

        candidate["relaxed_constraints"] = [
            issue for issue in issues if issue in {"cuisine", "budget", "eta", "time"}
        ]
        relaxed_candidates.append(candidate)

    exact_candidates = sorted(
        exact_candidates,
        key=lambda meal: score_meal(meal, user_message, requirements),
        reverse=True,
    )
    relaxed_candidates = sorted(
        relaxed_candidates,
        key=lambda meal: score_meal(meal, user_message, requirements),
        reverse=True,
    )

    if len(exact_candidates) >= 10:
        return exact_candidates[:10], len(exact_candidates)

    candidates = (exact_candidates + relaxed_candidates)[:10]
    return candidates, len(exact_candidates)


def shopeefood_search_url(dish_name: str, city_slug: str | None = None) -> str:
    keyword = quote_plus(dish_name)
    resolved_city_slug = city_slug or os.environ.get("SHOPEEFOOD_CITY_SLUG", "ho-chi-minh").strip() or "ho-chi-minh"
    return f"https://shopeefood.vn/{resolved_city_slug}/danh-sach-dia-diem-giao-tan-noi?keyword={keyword}"


def google_places_search_url(query: str, location: str | None) -> str:
    location_text = f" gần {location}" if location else ""
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query + location_text)}"


def extract_requested_dish_query(text: str, meals: list[dict[str, object]]) -> str | None:
    lowered = normalize_text(text)

    for meal in meals:
        meal_name = str(meal["name"])
        if normalize_text(meal_name) in lowered:
            return meal_name

    known_queries = {
        "tokbokki": ("tokbokki", "tteokbokki"),
        "kimbap": ("kimbap",),
        "bibimbap": ("bibimbap", "com tron han"),
        "kimchi": ("kimchi",),
        "ramen": ("ramen",),
        "sushi": ("sushi",),
        "pizza": ("pizza",),
        "burger": ("burger", "hamburger"),
        "pad thai": ("pad thai",),
        "tom yum": ("tom yum",),
    }

    for query, aliases in known_queries.items():
        if any(alias in lowered for alias in aliases):
            return query

    return None


def build_external_search_query(
    user_context: str,
    requirements: dict[str, object],
    meals: list[dict[str, object]],
) -> str:
    requested_dish = extract_requested_dish_query(user_context, meals)
    if requested_dish:
        return requested_dish

    cuisine = requirements["cuisine"]
    if cuisine:
        return cuisine_label(str(cuisine))

    return "món ăn phù hợp"


def format_external_search_fallback(
    user_context: str,
    requirements: dict[str, object],
    meals: list[dict[str, object]],
    reason: str,
) -> str:
    query = build_external_search_query(user_context, requirements, meals)
    shopeefood_link = shopeefood_search_url(query, str(requirements["city_slug"]))
    google_places_link = google_places_search_url(query, str(requirements["location"]))

    return (
        f"{reason}\n\n"
        f"- ShopeeFood search: [Tìm {query}]({shopeefood_link})\n"
        f"- Google Places fallback: [Tìm {query} gần {requirements['location']}]({google_places_link})"
    )


def parse_selected_items(text: str, candidates: list[dict[str, object]]) -> list[tuple[str, str]]:
    candidate_ids = {str(meal["id"]) for meal in candidates}
    selected_items = []

    for line in text.splitlines():
        id_match = re.search(r"\bM\d{2,3}\b", line.upper())
        if not id_match:
            continue

        meal_id = id_match.group(0)
        if meal_id not in candidate_ids or any(selected_id == meal_id for selected_id, _ in selected_items):
            continue

        reason = re.sub(r"\bM\d{2,3}\b", "", line, count=1, flags=re.IGNORECASE)
        reason = reason.strip(" |:-–—.\t")
        if reason.lower().startswith("vì "):
            reason = reason[3:].strip()
        selected_items.append((meal_id, reason))

        if len(selected_items) == 3:
            break

    return selected_items


def fallback_selected_items(candidates: list[dict[str, object]]) -> list[tuple[str, str]]:
    selected_items = []
    seen_tags = set()

    for meal in candidates:
        main_tag = str(meal["tags"]).split()[0]
        if main_tag not in seen_tags:
            selected_items.append((str(meal["id"]), "hợp nhu cầu hiện tại và giúp đổi vị nhanh."))
            seen_tags.add(main_tag)
        if len(selected_items) == 3:
            break

    for meal in candidates:
        meal_id = str(meal["id"])
        if not any(selected_id == meal_id for selected_id, _ in selected_items):
            selected_items.append((meal_id, "nằm gần ngân sách và dễ đặt trên app giao đồ ăn."))
        if len(selected_items) == 3:
            break

    return selected_items


def format_meal_links(
    selected_items: list[tuple[str, str]],
    candidates: list[dict[str, object]],
    user_location: str | None,
    exact_match_count: int,
    user_context: str,
    requirements: dict[str, object],
    meals: list[dict[str, object]],
) -> str:
    meal_by_id = {str(meal["id"]): meal for meal in candidates}
    lines = []
    city_slug = city_slug_from_location(user_location)
    selected_relaxed_constraints = sorted(
        {
            constraint
            for meal_id, _ in selected_items[:3]
            for constraint in meal_by_id[meal_id].get("relaxed_constraints", [])
        }
    )

    if exact_match_count == 0:
        external_query = build_external_search_query(user_context, requirements, meals)
        lines.append(
            "Không có món nào khớp tuyệt đối trong mock dataset. "
            "Mình đưa các lựa chọn gần nhất và link tìm ngoài để kiểm tra nhanh."
        )
        lines.append(f"ShopeeFood search: [Tìm {external_query}]({shopeefood_search_url(external_query, city_slug)})")
        lines.append(
            "Google Places fallback: "
            f"[Tìm {external_query} gần {user_location}]({google_places_search_url(external_query, user_location)})"
        )
    elif exact_match_count < 3 and selected_relaxed_constraints:
        lines.append(
            "Không đủ 3 món khớp tuyệt đối. Mình thêm lựa chọn gần nhất và đã nới: "
            f"{relaxed_constraint_labels(selected_relaxed_constraints)}."
        )

    for index, (meal_id, reason) in enumerate(selected_items[:3], start=1):
        meal = meal_by_id[meal_id]
        price = f"{int(meal['price']):,} VND"
        link = shopeefood_search_url(str(meal["name"]), city_slug)
        reason_text = reason or "hợp khẩu vị và ngân sách hiện tại."
        relaxed_constraints = meal.get("relaxed_constraints", [])
        if relaxed_constraints:
            reason_text += f" Lưu ý: đã nới {relaxed_constraint_labels(relaxed_constraints)}."

        lines.append(
            f"{index}. {meal['name']} - {meal['store']} - {price} - ~{meal['eta_minutes']} phút\n"
            f"   Reason: {reason_text}\n"
            f"   ShopeeFood link: [Open search]({link})"
        )

    return "\n".join(lines)


def build_user_context(messages: list[dict[str, str]]) -> str:
    return " ".join(message["content"] for message in messages if message["role"] == "user")


def load_system_prompt() -> str:
    prompt_path = Path(__file__).with_name("system_prompt.md")
    return prompt_path.read_text(encoding="utf-8").strip()


load_env_files()
SYSTEM_PROMPT = load_system_prompt()
APP_CONFIG = load_app_config()
MEALS_DATASET = load_meals_dataset()

st.title("AI Quick Meal Picker")

CHAT_VERSION = "ask_one_missing_field_v1"

if st.session_state.get("chat_version") != CHAT_VERSION:
    st.session_state.chat_version = CHAT_VERSION
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Bạn đang ở khu vực/thành phố nào? Ví dụ: VinUni/Gia Lâm, Cầu Giấy, Quận 1.",
        }
    ]

if "collected_context" not in st.session_state:
    st.session_state.collected_context = hydrate_context_from_messages(
        st.session_state.messages,
        MEALS_DATASET,
    )

if "pending_field" not in st.session_state:
    last_assistant_message = next(
        (
            message["content"]
            for message in reversed(st.session_state.messages)
            if message["role"] == "assistant"
        ),
        "",
    )
    st.session_state.pending_field = infer_pending_field_from_assistant(last_assistant_message)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

user_message = st.chat_input("Ví dụ: đang ở VinUni, trưa 50k, muốn món Hàn, không cay, giao dưới 25 phút")

if user_message:
    st.session_state.messages.append({"role": "user", "content": user_message})
    with st.chat_message("user"):
        st.markdown(user_message)

    with st.chat_message("assistant"):
        try:
            pending_field = st.session_state.get("pending_field")
            update_collected_context(
                st.session_state.collected_context,
                user_message,
                MEALS_DATASET,
                pending_field,
            )
            chat_history = [
                {"role": message["role"], "content": message["content"]}
                for message in st.session_state.messages[-8:]
            ]
            try_ai_update_collected_context(
                st.session_state.collected_context,
                chat_history,
                pending_field,
            )
            raw_user_context = build_user_context(chat_history)
            stored_context = collected_context_to_text(st.session_state.collected_context)
            user_context = "\n".join(part for part in (raw_user_context, stored_context) if part)
            missing_context = get_missing_context(user_context, MEALS_DATASET)

            if missing_context:
                clarification = build_clarifying_question(missing_context)
                st.markdown(clarification)
                st.session_state.pending_field = missing_context[0]
                st.session_state.messages.append({"role": "assistant", "content": clarification})
            else:
                st.session_state.pending_field = None
                user_location = extract_location(user_context)
                requirements = build_requirements(user_context, APP_CONFIG)
                candidates, exact_match_count = filter_meals(MEALS_DATASET, user_context, APP_CONFIG)

                if not candidates:
                    suggestions = format_external_search_fallback(
                        user_context,
                        requirements,
                        MEALS_DATASET,
                        "Không có món nào trong mock dataset phù hợp với các ràng buộc hiện tại.",
                    )
                    st.markdown(suggestions)
                    st.session_state.messages.append({"role": "assistant", "content": suggestions})
                else:
                    client, model = get_ai_client()
                    candidate_text = "\n".join(
                        (
                            f"{meal['id']}: {meal['name']} | store={meal['store']} | "
                            f"time={','.join(meal['time_tags'])} | price={meal['price']} VND | "
                            f"eta={meal['eta_minutes']} minutes | rating={meal['rating']} | "
                            f"category={meal['category']} | cuisine={meal['cuisine']} | spicy={meal['spicy']} | "
                            f"relaxed_constraints={','.join(meal.get('relaxed_constraints', [])) or 'none'} | "
                            f"tags={meal['tags']} | description={meal['description']}"
                        )
                        for meal in candidates
                    )
                    ranking_prompt = f"""
Nhu cầu mới nhất của user:
{user_message}

Vị trí hiện tại của user:
{user_location}

Hard constraints extracted:
- city_slug: {requirements["city_slug"]}
- budget: {requirements["budget"]} VND
- preferred_cuisine: {cuisine_label(requirements["cuisine"])}
- avoid_terms: {", ".join(sorted(requirements["avoid_terms"])) or "none"}
- max_delivery_time: {requirements["max_eta_minutes"]} minutes
- exact_matches_before_relaxation: {exact_match_count}

History/preference từ các tin nhắn user gần đây:
{user_context}

Filtered meal dataset candidates:
{candidate_text}

Hãy chọn đúng 3 candidate ID từ dataset đã lọc.
Nếu exact_matches_before_relaxation < 3, được chọn closest alternatives nhưng lý do phải nói rõ constraint đã nới.
Không được bỏ qua preferred_cuisine nếu vẫn còn đủ 3 exact matches.
Ưu tiên theo thứ tự: cuisine match, budget fit, ETA fit, rating, history/preference.
Trả đúng 3 dòng, mỗi dòng gồm ID và lý do tiếng Việt ngắn gắn với constraint của user.
Ví dụ:
M001 | Vì hợp thói quen ăn cơm tấm và nằm trong ngân sách.
M005 | Vì đổi vị nhẹ hơn nhưng vẫn no cho bữa trưa.
M011 | Vì tươi, dễ ăn và cân bằng với các món nhiều đạm.
"""

                    response = client.chat.completions.create(
                        model=model,
                        messages=[
                            {"role": "system", "content": SYSTEM_PROMPT},
                            *chat_history,
                            {"role": "user", "content": ranking_prompt},
                        ],
                        temperature=0.7,
                        max_tokens=80,
                    )

                    selected_items = parse_selected_items(response.choices[0].message.content, candidates)
                    if len(selected_items) < 3:
                        fallback_items = fallback_selected_items(candidates)
                        selected_ids = {meal_id for meal_id, _ in selected_items}
                        selected_items.extend(
                            (meal_id, reason) for meal_id, reason in fallback_items if meal_id not in selected_ids
                        )
                        selected_items = selected_items[:3]

                    suggestions = format_meal_links(
                        selected_items,
                        candidates,
                        user_location,
                        exact_match_count,
                        user_context,
                        requirements,
                        MEALS_DATASET,
                    )
                    st.markdown(suggestions)
                    st.session_state.messages.append({"role": "assistant", "content": suggestions})
        except Exception:
            error_message = "Mình chưa gợi ý được lúc này, bạn thử nhắn lại giúp mình nhé."
            st.error(error_message)
            st.session_state.messages.append({"role": "assistant", "content": error_message})
