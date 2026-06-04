# Demo script — Quick Meal Picker (~5 phút)

## Phân vai gợi ý

| Phút | Người | Nội dung |
|------|--------|----------|
| 0:00–0:45 | Đoàn Minh Quang | Product Canvas: pain (choice overload), user, build slice |
| 0:45–1:00 | Trường Thành Thảo | 1 bằng chứng (self-use + 1 paper) |
| 1:00–3:30 | Nguyễn Công Thành + Võ Thanh Hiệp | **Live demo** (bên dưới) |
| 3:30–4:00 | Nguyễn Công Tuấn Anh | Augment vs automate; AI decision |
| 4:00–4:30 | Nguyễn Tuấn Minh | Failure mode + mitigation |
| 4:30–5:00 | Q&A — mỗi người trả lời phần mình |

## Live demo (thứ tự bấm)

### 1. Happy path (~60s)

1. Mở `http://localhost:3000`
2. Chọn **Trưa**, budget **50000**
3. Chips: **Ăn no**, **Không cay**, **Giao < 25 phút**
4. Prompt: `Trưa nay 50k, ăn no, không cay`
5. Bấm **Gợi ý 3 món** → show 3 cards + lý do + confidence
6. Chọn 1 món → **Checkout mock** (nhắc: user vẫn quyết định trên app thật)

### 2. Low-confidence (~45s)

1. **Làm mới** session
2. Chỉ nhập prompt: `Ăn gì cũng được` (để trống budget)
3. Bấm gợi ý → AI hỏi 1 câu → chọn **Ăn no** → nhận shortlist

### 3. Failure + correction (~60s)

1. Happy path lại
2. Nếu có món cay / đắt → bấm **Không cay** hoặc **Rẻ hơn**
3. Chỉ ra dòng **“Đã cập nhật tiêu chí”** và shortlist mới

## Câu Q&A chuẩn bị

- **Augment hay automate?** Augment — AI shortlist, human chọn & checkout.
- **Failure mode chính?** Gợi ý sai khẩu vị/ngân sách → chips + refine.
- **Phần bạn làm?** (mỗi người theo bảng phân công trong `spec/spec.md`)

## Backup

- Quay video màn hình nếu mạng/API lỗi
- Screenshot trong `codebase/docs/screenshots/` (tự thêm sau dry-run)
