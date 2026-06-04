from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


Intent = Literal[
    "recommend_food",
    "filter_food",
    "ask_food_detail",
    "new_chat",
    "small_talk",
    "unknown",
]


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str


class ReactTraceStep(BaseModel):
    step: Literal["Thought", "Action", "Observation"]
    content: Any | None = None
    tool: str | None = None
    input: Any | None = None


class ExtractedFilters(BaseModel):
    intent: Intent = "unknown"
    rating_min: float | None = None
    price_min: int | None = None
    price_max: int | None = None
    category: str | list[str] | None = None
    max_wait_minutes: int | None = None
    randomize: bool | None = None
    detail_target: str | None = None
    detail_fields: list[str] = Field(default_factory=list)
    keyword: str | None = None


class FoodItem(BaseModel):
    url: str = ""
    name: str = "Không rõ tên món"
    price: Any = 0
    parsed_price: int = 0
    new_price: int = 0
    ingredients: list[Any] = Field(default_factory=list)
    origin: str = ""
    product_info: str = ""
    description: str = ""
    category: str | list[str] = Field(default_factory=lambda: ["Khác"])
    product_code: str = ""
    brand: str = ""
    sold_count: int = 0
    image_urls: list[str] = Field(default_factory=list)
    error: Any | None = None
    voucher: float = 0
    distance_km: float = 3
    prep_time_minutes: float = 15
    estimated_time_minutes: int = 0
    rating: float = 0


class RecommendationItem(FoodItem):
    reason: str = ""


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class SessionData(BaseModel):
    session_id: str
    old_intent: str | None = None
    messages: list[ChatMessage] = Field(default_factory=list)
    last_recommendations: list[RecommendationItem] = Field(default_factory=list)
    last_filters: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    session_id: str
    intent: Intent
    old_intent: str | None = None
    answer: str
    recommendations: list[RecommendationItem] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)
    react_trace: list[ReactTraceStep] = Field(default_factory=list)


class NewSessionResponse(BaseModel):
    session_id: str
