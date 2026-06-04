from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .tools import enrich_food_items_with_tools


DATASET_MISSING_MESSAGE = (
    "Không tìm thấy file backend/data/foods.json. "
    "Vui lòng đặt dataset JSON thật vào đúng đường dẫn này."
)


class DatasetNotFoundError(FileNotFoundError):
    pass


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _project_dir() -> Path:
    return _backend_dir().parent


def resolve_data_path(raw_path: str | None = None) -> Path:
    load_dotenv()
    configured_path = raw_path or os.getenv("DATA_PATH", "backend/data/foods.json")
    path = Path(configured_path)
    if path.is_absolute():
        return path

    candidates = [
        Path.cwd() / path,
        _project_dir() / path,
        _backend_dir() / path,
    ]

    path_parts = path.parts
    if path_parts and path_parts[0] == "backend":
        stripped = Path(*path_parts[1:])
        candidates.extend(
            [
                _backend_dir() / stripped,
                Path.cwd() / stripped,
            ]
        )

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return candidates[0]


def _extract_list_from_json(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        for key in ("foods", "items", "data", "products"):
            value = payload.get(key)
            if isinstance(value, list):
                return value

    raise ValueError("Dataset JSON phải là list hoặc object có key foods/items/data/products là list.")


def load_foods() -> list[Any]:
    data_path = resolve_data_path()
    if not data_path.exists():
        raise DatasetNotFoundError(DATASET_MISSING_MESSAGE)

    with data_path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    return _extract_list_from_json(payload)


def load_and_enrich_foods() -> list[dict[str, Any]]:
    raw_items = load_foods()
    return enrich_food_items_with_tools(raw_items)

