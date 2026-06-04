# Quick Meal Picker — Prototype Day 06

**Track:** Food & Local Delivery · **App tham chiếu:** ShopeeFood / GrabFood  
AI gợi ý **3 món** (augment) — user vẫn quyết định và đặt trên app thật.

> Toàn bộ source prototype nằm trong thư mục `codebase/` này. SPEC: [`../spec/spec.md`](../spec/spec.md) · Demo script: [`../spec/demo-script.md`](../spec/demo-script.md)

---

## Thành viên nhóm

- Đoàn Minh Quang — MHV: 2A202600757
- Trường Thành Thảo — MHV: 2A202600735
- Nguyễn Công Tuấn Anh — MHV: 2A202600977
- Nguyễn Công Thành — MHV: 2A202600696
- Nguyễn Tuấn Minh — MHV: 2A202600692
- Võ Thanh Hiệp — MHV: 2A202600836

---

## Cài đặt & chạy

```bash
cd codebase

python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Sửa .env: OPENAI_API_KEY=...

python app.py
```

Mở **http://localhost:3000**

## Biến môi trường (`.env`)

| Biến | Mô tả |
|------|--------|
| `OPENAI_API_KEY` | Bắt buộc cho **AI thật** (checkpoint 13:00) |
| `OPENAI_BASE_URL` | Mặc định `https://api.openai.com/v1` |
| `OPENAI_MODEL` | Mặc định `gpt-4o-mini` |
| `PORT` | Mặc định `3000` |
| `FLASK_DEBUG` | `1` để debug Flask |

Không có key → **rule fallback** (có nhãn trên UI).

## Công nghệ

| Thành phần | File / công cụ |
|------------|----------------|
| Backend | `app.py` (Flask) |
| Frontend | `public/` |
| AI | OpenAI SDK, JSON mode |
| Dữ liệu | `data/meals.json` |
| Dependencies | `requirements.txt` |

Tùy chọn: `server.js` + `npm start` (Node, cùng API).

## Demo 4 paths

1. **Happy:** Trưa, 50k, Ăn no + Không cay → 3 cards → Chọn món  
2. **Low-confidence:** “Ăn gì cũng được”, budget trống → 1 câu hỏi  
3. **Failure / Correction:** Chips “Không cay”, “Rẻ hơn” → refine  

Chi tiết: [`../spec/demo-script.md`](../spec/demo-script.md)

## Phân công

| Thành viên | Phần |
|------------|------|
| Nguyễn Công Tuấn Anh | Mock data, prompt (`app.py`, `meals.json`) |
| Nguyễn Công Thành | UI (`public/`) |
| Nguyễn Tuấn Minh | Test 4 paths |
| Võ Thanh Hiệp | README, demo script, repo |
| Đoàn Minh Quang | SPEC |
| Trường Thành Thảo | Evidence |

## Cấu trúc

```
codebase/
├── app.py
├── requirements.txt
├── .gitignore
├── .env.example
├── data/meals.json
├── public/
│   ├── index.html
│   ├── styles.css
│   └── app.js
├── server.js          # optional Node backend
└── package.json
```

**Lưu ý:** Không commit `.env` hoặc API key.
