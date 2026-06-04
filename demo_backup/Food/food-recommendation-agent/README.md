# AI Food Recommendation Agent

Project demo hackathon dùng FastAPI + Next.js + OpenAI API + dataset JSON local để gợi ý món ăn bằng một ReAct flow đơn giản. Backend chỉ đọc dữ liệu từ dataset thật, enrich trong memory bằng tool local, lọc/rank top 3 món và lưu session chat bằng JSON file.

## Phiên bản đang dùng

Project đã được pin theo version hiện tại trên máy:

```txt
Python 3.13.5
Node.js 22.21.1
npm 10.9.4
FastAPI 0.115.0
uvicorn 0.32.0
OpenAI Python SDK 2.31.0
python-dotenv 1.1.0
Pydantic 2.9.2
Next.js 16.2.7
React 19.2.7
React DOM 19.2.7
TypeScript 6.0.3
```

Dockerfile cũng dùng các runtime tương ứng và frontend dùng `npm ci` để bám `package-lock.json`.

## Chuẩn bị dataset

Không có dataset mẫu trong repo này. Hãy copy dataset thật của bạn vào đúng vị trí:

```bash
mkdir -p backend/data
cp path/to/my_dataset.json backend/data/foods.json
```

Dataset cần là JSON list hoặc object có key `foods`, `items`, `data` hoặc `products` là list. Mỗi item có thể thiếu field; backend sẽ tự dùng default an toàn và không ghi đè file dataset gốc.

## Tạo file môi trường

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

## Điền API key

Mở `backend/.env` và điền:

```env
OPENAI_API_KEY=your_key_here
```

Model mặc định là:

```env
OPENAI_MODEL=gpt-4o-mini
```

Nếu lỡ nhập `gpt-4-o-mini`, backend sẽ tự map về model id chuẩn `gpt-4o-mini`.

Không commit hoặc chia sẻ file `.env` vì có thể chứa API key thật.

Nếu OpenAI API lỗi hoặc chưa có key, backend tự fallback sang parser rule-based để vẫn demo được.

## Chạy bằng Docker

```bash
docker compose up --build
```

Docker mount dataset từ `./backend/data` vào `/app/data`. File `.env.example` đang để `DATA_PATH=backend/data/foods.json`, backend có logic resolve path để vẫn đọc đúng `/app/data/foods.json` trong container.

## Mở web

```txt
http://localhost:3000
```

## Test backend

```txt
http://localhost:8000/health
http://localhost:8000/foods
http://localhost:8000/foods/enrich-status
```

Khi dataset chưa có, `/health` và `/foods/enrich-status` sẽ trả:

```txt
Không tìm thấy file backend/data/foods.json. Vui lòng đặt dataset JSON thật vào đúng đường dẫn này.
```

Khi dataset đã load và enrich thành công, `/foods/enrich-status` sẽ có:

```json
{
  "loaded": true,
  "has_new_price": true,
  "has_estimated_time_minutes": true
}
```

## Chạy backend riêng

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Nếu chạy từ thư mục `backend`, bạn có thể đặt dataset tại:

```bash
mkdir -p data
cp path/to/my_dataset.json data/foods.json
```

Backend vẫn hỗ trợ `DATA_PATH=backend/data/foods.json` khi chạy từ project root hoặc từ Docker.

## Chạy frontend riêng

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

Frontend mặc định gọi backend tại:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## API chính

`GET /health`: kiểm tra backend và trạng thái dataset.

`GET /foods`: xem danh sách món đã enrich, gồm `parsed_price`, `new_price`, `estimated_time_minutes`.

`GET /foods/enrich-status`: kiểm tra dataset đã được enrich bằng `calculate_new_price` và `calculate_estimated_time` chưa.

`POST /chat`: gửi tin nhắn chatbot.

```json
{
  "session_id": "optional-session-id",
  "message": "Tôi muốn món chiên xào dưới 60k và giao dưới 25 phút"
}
```

`POST /sessions/new`: tạo chat mới.

`GET /sessions/{session_id}`: xem lịch sử chat, intent cũ và `last_recommendations`.

## Logic agent

Backend xử lý theo các bước ngắn:

1. Load dataset thật từ `backend/data/foods.json`.
2. Normalize field thiếu bằng default an toàn.
3. Parse `price` thành `parsed_price`.
4. Tính `new_price` bằng `calculate_new_price`.
5. Tính `estimated_time_minutes` bằng `calculate_estimated_time`.
6. Dùng OpenAI để extract filter; nếu lỗi thì fallback rule-based.
7. Lọc món theo rating, ngân sách, category, keyword và thời gian chờ.
8. Khi có yêu cầu giao nhanh/chờ ít, filter bắt buộc dùng `check_wait_time_match`.
9. Rank món bằng rating, sold count, voucher, thời gian, giá, url/image và trạng thái lỗi crawl.
10. Lưu `last_recommendations` theo session để trả lời câu hỏi tiếp như `cho tôi link món số 2`.
11. Với câu ngoài phạm vi như `bạn là ai`, `tao là gì của mày`, `tôi muốn ăn bạn`, backend phân loại `small_talk`, gọi GPT mini để trả lời dí dỏm và kéo người dùng về câu hỏi đặt món.

Project không tự bịa món ăn, nguyên liệu, mô tả, url, rating, không đặt món và không gọi API giao đồ ăn thật.
