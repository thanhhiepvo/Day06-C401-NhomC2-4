from __future__ import annotations

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .agent import run_react_agent
from .data_loader import DATASET_MISSING_MESSAGE, DatasetNotFoundError, load_and_enrich_foods
from .schemas import ChatRequest, ChatResponse, NewSessionResponse, SessionData
from .storage import (
    create_session,
    ensure_session,
    get_session,
    load_store,
    save_message,
    set_last_filters,
    set_last_recommendations,
    set_old_intent,
)


load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_store()
    try:
        app.state.food_items = load_and_enrich_foods()
        app.state.data_loaded = True
        app.state.load_message = None
    except DatasetNotFoundError:
        app.state.food_items = []
        app.state.data_loaded = False
        app.state.load_message = DATASET_MISSING_MESSAGE
    except Exception as exc:
        app.state.food_items = []
        app.state.data_loaded = False
        app.state.load_message = f"Không thể load dataset: {exc}"

    yield


app = FastAPI(
    title="AI Food Recommendation Agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    food_items = getattr(app.state, "food_items", [])
    data_loaded = getattr(app.state, "data_loaded", False)
    if data_loaded:
        return {
            "status": "ok",
            "foods_loaded": len(food_items),
            "data_loaded": True,
        }

    return {
        "status": "warning",
        "foods_loaded": 0,
        "data_loaded": False,
        "message": getattr(app.state, "load_message", DATASET_MISSING_MESSAGE),
    }


@app.get("/foods")
def get_foods() -> list[dict]:
    return getattr(app.state, "food_items", [])


@app.get("/foods/enrich-status")
def enrich_status() -> dict:
    food_items = getattr(app.state, "food_items", [])
    data_loaded = getattr(app.state, "data_loaded", False)
    if not data_loaded:
        return {
            "loaded": False,
            "total_items": 0,
            "has_new_price": False,
            "has_estimated_time_minutes": False,
            "message": getattr(app.state, "load_message", DATASET_MISSING_MESSAGE),
        }

    return {
        "loaded": True,
        "total_items": len(food_items),
        "has_new_price": all("new_price" in item for item in food_items),
        "has_estimated_time_minutes": all("estimated_time_minutes" in item for item in food_items),
        "message": (
            "Dataset thật đã được load và enrich bằng calculate_new_price và "
            "calculate_estimated_time khi backend khởi động."
        ),
    }


@app.post("/sessions/new", response_model=NewSessionResponse)
def new_session() -> dict:
    session = create_session()
    return {"session_id": session["session_id"]}


@app.get("/sessions/{session_id}", response_model=SessionData)
def read_session(session_id: str) -> dict:
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy session.")
    return session


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> dict:
    session = ensure_session(request.session_id)
    save_message(session["session_id"], "user", request.message)

    result = run_react_agent(
        message=request.message,
        session=session,
        food_items=getattr(app.state, "food_items", []),
        data_loaded=getattr(app.state, "data_loaded", False),
    )

    if result["intent"] == "new_chat":
        session = create_session()
        result["session_id"] = session["session_id"]
    else:
        result["session_id"] = session["session_id"]
        if result["intent"] in ("recommend_food", "filter_food") and result["recommendations"]:
            set_last_recommendations(session["session_id"], result["recommendations"])
        if result["intent"] in ("recommend_food", "filter_food"):
            set_last_filters(session["session_id"], result.get("active_filters", {}))
        if result["intent"] not in ("unknown", "small_talk"):
            set_old_intent(session["session_id"], result["intent"])

    save_message(result["session_id"], "assistant", result["answer"])
    return result
