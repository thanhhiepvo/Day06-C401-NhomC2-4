# SPEC sản phẩm

Ở Day 5, mỗi nhóm đã viết một bản SPEC nhẹ. Đến Day 6, nhóm hoàn thiện bản này cho đủ để bắt tay vào build và mang đi demo — vẫn ngắn gọn, nhưng đủ để bảo vệ được những quyết định sản phẩm của mình.

Hãy hình dung SPEC như một lập luận, chứ không phải một danh sách tính năng. Nó cần trả lời rõ bốn câu hỏi: sản phẩm giải vấn đề gì và cho ai, AI tham gia quyết định điều gì, chuyện gì xảy ra khi AI trả lời sai, và những nhận định của nhóm dựa trên bằng chứng nào.

Viết SPEC vào `spec/spec.md`, có thể kèm slide demo (`spec/demo-slides.pdf`).

---

## 1. Bằng chứng

Trước hết, nỗi đau mà nhóm muốn giải đến từ đâu? Phần này cần dựa trên quan sát thật chứ không phải phỏng đoán. Nhóm nên có:

- **Trải nghiệm trực tiếp** — chính nhóm dùng thử app hoặc quy trình đó và ghi lại những chỗ thấy vướng.
- **Ít nhất một nguồn từ bên ngoài nhóm** — đánh giá công khai trên App Store hoặc Google Play, một buổi phỏng vấn ngắn với người dùng thật, bình luận trên diễn đàn hay mạng xã hội, hoặc cách những sản phẩm khác đang xử lý cùng vấn đề.

Mỗi nhận định nên đi kèm trích dẫn, ảnh chụp màn hình hoặc một quan sát cụ thể. Nếu có ý nào nhóm chưa tìm được nguồn từ bên ngoài, hãy ghi rõ đó là giả định thay vì trình bày như một sự thật.

## 2. Lát cắt để build

Thay vì cố làm cả sản phẩm, nhóm chọn ra lát cắt nhỏ nhất đủ để chứng minh ý tưởng. Lát cắt này gói gọn trong một câu: một người dùng, một công việc, một quyết định mà AI đưa ra, và một kết quả trả về. Đây mới là phần nhóm thật sự dựng nên và mang đi demo.

## 3. AI Product Canvas

Canvas là một trang giúp sản phẩm không trôi ngược về "một demo cho vui". Nhóm trả lời lần lượt bốn ô:

| Ô | Câu hỏi cần trả lời |
|---|---------------------|
| **Value** — Giá trị | Sản phẩm dành cho ai, họ đau ở đâu, và AI giải được điều gì mà cách làm hiện tại chưa giải tốt? |
| **Trust** — Niềm tin | Khi AI trả lời sai, người dùng nhận ra bằng cách nào, và họ sửa lại, hoàn tác hay chuyển sang người thật ra sao? |
| **Feasibility** — Tính khả thi | Có đáng để build không? Hãy cân nhắc chi phí mỗi lượt gọi, độ trễ, dữ liệu cần có, rủi ro lớn nhất, và ngưỡng mà nhóm sẵn sàng dừng lại. |
| **Tín hiệu học** | Khi người dùng chỉnh sửa kết quả, dữ liệu đó đi về đâu và giúp sản phẩm khá lên nhờ tín hiệu nào? |

## 4. Tăng năng lực hay tự động hóa

Đây là một quyết định sản phẩm, không phải lựa chọn mặc định. Nhóm cần nói rõ: AI chỉ gợi ý và chuẩn bị cho con người (tăng năng lực — augment), hay AI tự hành động trong phạm vi đã định (tự động hóa — automate)? Con người giữ quyền quyết định ở bước nào? Và vì sao nhóm chọn mức đó cho lát cắt này — thường thì câu trả lời nằm ở chỗ sai thì hậu quả nặng đến đâu và có dễ hoàn tác hay không.

## 5. Bốn đường đi của trải nghiệm

Một tính năng AI không chỉ có đường thuận. Nhóm cần thiết kế cho cả bốn tình huống mà người dùng có thể gặp:

| Đường đi | Câu hỏi | Ví dụ cách xử lý |
|----------|---------|------------------|
| **Đường thuận** | AI đúng và tự tin — người dùng thấy gì? | Gợi ý hiện rõ, chấp nhận chỉ bằng một thao tác |
| **Khi AI không chắc** | AI lưỡng lự — có hỏi lại không? | Đưa ra vài lựa chọn hoặc xin thêm thông tin |
| **Khi AI sai** | Kết quả sai — người dùng gỡ ra thế nào? | Cho hoàn tác, sửa trực tiếp, hoặc chuyển sang người thật |
| **Khi người dùng sửa** | Người dùng chỉnh lại — dữ liệu đi về đâu? | Lưu lại để cập nhật quy tắc hoặc tập kiểm thử |

## 6. Những kiểu lỗi đáng lo nhất

Liệt kê một đến ba kiểu lỗi nguy hiểm nhất của sản phẩm. Với mỗi kiểu, nói rõ ba điều: lỗi thường xuất hiện khi nào (chẳng hạn đầu vào mơ hồ, câu hỏi ngoài phạm vi, dữ liệu thiếu, hay người dùng cố tình đánh lừa), nếu xảy ra thì ai chịu thiệt và nặng đến đâu, và prototype sẽ xử lý bằng cách nào — hỏi lại, hiện nguồn, để con người duyệt, cho hoàn tác, hay có sẵn phương án dự phòng.

## 7. Kế hoạch kiểm thử và bằng chứng demo

Để chứng minh được khi đứng demo, nhóm chuẩn bị sẵn hai đầu vào để thử: một đầu vào bình thường cho đường thuận, và một đầu vào khó hoặc gây nhiễu để cho thấy sản phẩm phục hồi ra sao khi AI không chắc. Bên cạnh đó, giữ lại các bằng chứng trong quá trình làm: ảnh chụp màn hình, nhật ký prompt, các trường hợp đã test, và những đánh đổi mà nhóm đã cân nhắc khi quyết định.

## 8. Phân công

Cuối cùng, ghi rõ ai phụ trách phần nào — người viết và kiểm thử prompt, người dựng giao diện, người giữ repo, người viết kịch bản demo, và người lo phần bằng chứng. Mỗi thành viên cần có một phần đủ rõ để tự mình giải thích được khi demo.
