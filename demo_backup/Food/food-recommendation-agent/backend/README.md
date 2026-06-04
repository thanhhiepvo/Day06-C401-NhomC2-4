# Backend - AI Food Recommendation Agent

FastAPI backend đọc dataset JSON thật từ `backend/data/foods.json`, enrich dữ liệu bằng tool local, rồi phục vụ API chat/recommendation.

## Chạy local

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Đặt dataset thật:

```bash
mkdir -p data
cp path/to/my_dataset.json data/foods.json
```

Nếu giữ `DATA_PATH=backend/data/foods.json`, backend vẫn tự resolve đúng khi chạy từ thư mục `backend`.

