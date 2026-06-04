# Quick Meal Picker — SPEC Day 06

**Track:** Food & Local Delivery (Zone 3) — decision support khi đặt đồ ăn  
**App thật tham chiếu:** ShopeeFood / GrabFood workflow  
**Cập nhật:** 04/06/2026

## Thành viên nhóm

- Đoàn Minh Quang — MHV: 2A202600757
- Trường Thành Thảo — MHV: 2A202600735
- Nguyễn Công Tuấn Anh — MHV: 2A202600977
- Nguyễn Công Thành — MHV: 2A202600696
- Nguyễn Tuấn Minh — MHV: 2A202600692
- Võ Thanh Hiệp — MHV: 2A202600836

| Mã HV | Họ và tên |
|-------|-----------|
| 2A202600757 | Đoàn Minh Quang |
| 2A202600735 | Trường Thành Thảo |
| 2A202600977 | Nguyễn Công Tuấn Anh |
| 2A202600696 | Nguyễn Công Thành |
| 2A202600692 | Nguyễn Tuấn Minh |
| 2A202600836 | Võ Thanh Hiệp |

---

## 1. Bằng chứng

### Self-use

- Mở ShopeeFood / GrabFood giờ trưa: user lướt qua nhiều quán, món, banner, voucher, rating trước khi chọn.
- Thường mất **5–10 phút** khi chưa có món trong đầu; cuối cùng hay quay về món quen (cơm tấm, bún bò).
- Gợi ý sai khẩu vị / ngân sách → mất niềm tin, quay lại tự lướt.

### Nguồn ngoài nhóm

| Bằng chứng | Nguồn |
|-----------|--------|
| Choice overload → decision paralysis trong online food ordering | [Kumala & Maizi, 2025](https://journal.stmiki.ac.id/index.php/jmt/article/view/1560) |
| Sinh viên: information overload, cognitive strain trên food delivery apps | [Arohi & Dayal, 2024](https://9vom.in/journals/index.php/vips/article/view/323) |
| Choice overload mạnh khi task khó, preference không rõ | [Chernev et al., 2015](https://www.kellogg.northwestern.edu/academics-research/research/detail/2015/when-product-assortment-leads-to-choice-overload-a-conceptual/?p=1) |
| GrabFood nhấn mạnh đa dạng lựa chọn | [grab.com/vn/food](https://www.grab.com/vn/food/) |

**Giả định (cần kiểm thêm):** Tỷ lệ chính xác “mất >5 phút chọn món” trong lớp — kế hoạch survey 5 người trước demo.

### Insight → Opportunity

- **Insight:** User không cần thêm món để xem; cần **giảm tải quyết định** theo giờ ăn, ngân sách, ETA, lịch sử, khẩu vị.
- **Opportunity:** AI **augment** bước chọn → shortlist **3 món** có lý do, cho phép refine ngay khi sai.

---

## 2. Lát cắt build (build slice)

> Cho sinh viên hoặc dân văn phòng đang mở app giao đồ ăn nhưng **chưa biết ăn gì**, prototype dùng AI để **augment** việc chọn món — xếp hạng và gợi ý **3 món** theo giờ ăn, ngân sách, lịch sử mock, ETA — tạo **3 thẻ** (giá, ETA, lý do, confidence, CTA) — xử lý failure “gợi ý sai khẩu vị/ngân sách” bằng **feedback chip** refine trong một lượt.

**Out of scope Day 06:** API ShopeeFood/GrabFood thật; tự đặt đơn/thanh toán; tài khoản thật; tư vấn y tế/dị ứng phức tạp.

---

## 3. AI Product Canvas

| Ô | Nội dung |
|---|----------|
| **Value** | Sinh viên / NV văn phòng, ngân sách ~40–70k, giờ trưa/tối. Pain: quá nhiều tín hiệu, không biết ăn gì. AI rút còn 3 lựa chọn có lý do — nhanh hơn lướt danh sách dài. |
| **Trust** | Hiển thị tiêu chí đang dùng + confidence. Sai → chip “Không cay”, “Rẻ hơn”, … + refine ngay. Không copy “đã đặt món”. User là người quyết định cuối. |
| **Feasibility** | Mock catalog ~15 món; 1 LLM call/lượt gợi ý (~vài cent). Latency chấp nhận demo. Dừng nếu chi phí/API không ổn → rule fallback có nhãn rõ. |
| **Tín hiệu học** | Correction trong session cập nhật constraints hiện tại (không lưu dài hạn prototype). Backlog: log chip + choice để tune ranking. |

---

## 4. Augment vs Automate

| | Quyết định |
|---|------------|
| **Chọn** | **Augment** — AI gợi ý + giải thích; user chọn món và checkout (mock). |
| **Vì sao** | Chọn món = khẩu vị + ngân sách + cảm giác lúc đó; tự đặt sai → mất kiểm soát, khó hoàn tác. |
| **Human** | Decider: chọn món, sửa tiêu chí, bỏ gợi ý. |
| **AI không làm** | Tự checkout, thanh toán, lưu preference nhạy cảm không đồng ý. |

---

## 5. Bốn đường đi

| Path | Trigger | Hành vi prototype |
|------|---------|-------------------|
| **Happy** | Đủ: giờ + budget + 1–2 preference | 3 cards + lý do + chọn món → checkout mock |
| **Low-confidence** | “Ăn gì cũng được”, thiếu budget | Hỏi **1 câu**: “Ăn no, nhẹ hay tiết kiệm?” |
| **Failure** | Gợi ý cay / vượt budget / ETA dài | Chips + giải thích sẽ loại bỏ gì |
| **Correction** | Bấm chip hoặc text ngắn | Refine shortlist + dòng “Đã cập nhật: …” |

---

## 6. Failure modes

| Lỗi | Khi nào | Hậu quả | Mitigation prototype |
|-----|---------|---------|------------------------|
| **Sai khẩu vị / ngân sách** | Input mơ hồ, mock data thiếu tag | Mất niềm tin, bỏ app | Chips, hiển thị criteria, refine LLM |
| **Hallucination món** | Model bịa món ngoài catalog | Demo sai dữ liệu | Chỉ chọn từ `meals.json`; server validate ID |
| **Low-confidence bỏ qua** | User vội, input cực ngắn | Gợi ý ngẫu nhiên | Rule + model trả `mode: clarify` |

---

## 7. Kế hoạch demo & kiểm thử

### Input demo (script 5 phút)

| Case | Input |
|------|--------|
| **Happy** | Trưa 12:10, 50k, ăn no, không cay, history: cơm tấm, bún bò |
| **Low-confidence** | “Ăn gì cũng được” (không budget) |
| **Failure → Correction** | Happy path → thấy món cay → “Không cay” / “Rẻ hơn” |

### Acceptance

- [ ] End-to-end trong 3–5 phút
- [ ] ≥1 path mỗi loại (happy, low-conf, failure, correction)
- [ ] Mỗi món: reason, price, ETA, confidence
- [ ] **Gọi LLM thật** (OpenAI-compatible API)
- [ ] Không gây hiểu nhầm đã đặt món

### Phân công

| Thành viên | Phần |
|------------|------|
| Trường Thành Thảo | Evidence / research |
| Đoàn Minh Quang | SPEC |
| Nguyễn Công Tuấn Anh | Mock data, prompt, guardrails |
| Nguyễn Công Thành | UI prototype |
| Nguyễn Tuấn Minh | Test 4 paths, failure |
| Võ Thanh Hiệp | Demo script, README, repo |

---

## 8. Liên kết artifact

- Thin SPEC Day 05: `VinUni_Lab5_AI_Product/02-group-spec/spec-final.html`
- Prototype: `codebase/`
- Demo script: `spec/demo-script.md`
