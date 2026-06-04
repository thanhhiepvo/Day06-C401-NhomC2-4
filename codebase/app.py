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

load_dotenv(Path(__file__).resolve().parent / ".env")

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"

with open(BASE_DIR / "data" / "meals.json", encoding="utf-8") as f:
    MEALS: list[dict] = json.load(f)

MEAL_BY_ID = {m["id"]: m for m in MEALS}

app = Flask(__name__, static_folder=str(PUBLIC_DIR), static_url_path="")


def has_api_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def is_vague_input(budget: int, prompt: str, chips: list) -> bool:
    p = (prompt or "").lower().strip()
    vague = ["ăn gì cũng được", "gì cũng được", "không biết", "tùy", "anything"]
    looks_vague = any(v in p for v in vague)
    no_budget = not budget or budget <= 0
    few_signals = len(chips or []) == 0 and (not p or len(p) < 8)
    return looks_vague and no_budget and few_signals


def build_criteria(
    time_slot: str | None,
    budget: int,
    history: list,
    chips: list,
    prompt: str,
    corrections: list,
) -> str:
    parts = []
    if time_slot:
        parts.append(f"Giờ: {time_slot}")
    if budget:
        parts.append(f"Ngân sách tối đa: {budget} VND")
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
) -> list[dict]:
    lst = list(meals)
    if budget:
        cap = int(budget * 1.1)
        lst = [m for m in lst if m["price"] <= cap]
    if max_eta:
        lst = [m for m in lst if m["etaMinutes"] <= max_eta]
    if no_spicy:
        lst = [m for m in lst if not m["spicy"]]
    if "Rẻ hơn" in chips and budget:
        lst = [m for m in lst if m["price"] <= budget * 0.85]
    if "Giao nhanh hơn" in chips:
        lst = [m for m in lst if m["etaMinutes"] <= 20]
    return lst if lst else meals


def system_prompt(catalog: list[dict]) -> str:
    return f"""Bạn là AI gợi ý món ăn cho prototype "Quick Meal Picker" (augment, không đặt hộ).
Chỉ chọn món từ catalog JSON (theo id). Trả về JSON đúng schema:
{{
  "mode": "clarify" | "recommend",
  "clarifyQuestion": string | null,
  "criteriaSummary": string,
  "recommendations": [
    {{ "mealId": string, "reason": string, "confidence": "cao" | "trung bình" | "thấp" }}
  ]
}}
Quy tắc:
- mode=clarify khi thiếu budget VÀ input quá mơ hồ; chỉ hỏi MỘT câu ngắn (ăn no / nhẹ / tiết kiệm).
- mode=recommend: đúng 3 mealId khác nhau, đa dạng category, tôn trọng không cay / budget / ETA.
- Không bịa món ngoài catalog. Không nói đã đặt món.
Catalog: {json.dumps(catalog, ensure_ascii=False)}"""


def call_llm(messages: list[dict]) -> dict:
    base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url=base)
    resp = client.chat.completions.create(
        model=model,
        temperature=0.4,
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
                    "Hợp ngân sách và rating cao (rule fallback)"
                    if i == 0
                    else "Đa dạng món trong catalog mock"
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
        budget = int(body.get("budget") or 0)
        history = body.get("history") or []
        chips = list(body.get("chips") or [])
        prompt = body.get("prompt") or ""
        corrections = list(body.get("corrections") or [])
        max_eta = int(body.get("maxEta") or 25)
        clarify_answer = body.get("clarifyAnswer")

        criteria_summary = build_criteria(
            time_slot,
            budget,
            history,
            chips + corrections,
            prompt,
            corrections,
        )

        if (
            is_vague_input(budget, prompt, chips)
            and not clarify_answer
            and not corrections
        ):
            return jsonify(
                mode="clarify",
                clarifyQuestion="Bạn muốn ăn no, ăn nhẹ hay tiết kiệm hôm nay?",
                criteriaSummary=criteria_summary,
                recommendations=[],
                aiSource="rule",
            )

        no_spicy = (
            "Không cay" in chips
            or "Không cay" in corrections
            or bool(re.search(r"không cay|ko cay", prompt, re.I))
        )

        filtered = rule_prefilter(
            MEALS, budget, max_eta, no_spicy, chips + corrections
        )
        allowed_ids = {m["id"] for m in filtered}

        if not has_api_key():
            out = fallback_recommend(filtered, criteria_summary)
            out["aiSource"] = "rule-fallback"
            return jsonify(out)

        user_payload = {
            "timeSlot": time_slot,
            "budget": budget,
            "history": history,
            "chips": chips,
            "prompt": prompt,
            "corrections": corrections,
            "clarifyAnswer": clarify_answer,
            "maxEtaMinutes": max_eta,
            "catalogIds": list(allowed_ids),
        }

        raw = call_llm(
            [
                {"role": "system", "content": system_prompt(filtered)},
                {
                    "role": "user",
                    "content": f"Hãy gợi ý cho user:\n{json.dumps(user_payload, ensure_ascii=False, indent=2)}",
                },
            ]
        )

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
