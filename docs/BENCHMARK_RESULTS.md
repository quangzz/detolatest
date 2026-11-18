# DETOLA — Benchmark Results & KOC Recommendations

- **Job ID:** `pytest_crash_resume_suite` (`DRY_RUN`)
- **Bài toán:** Tìm **5 KOC TikTok** quảng bá **Kem chống nắng** (Mỹ phẩm Việt Nam)
- **Khách hàng mục tiêu:** Nữ, 18–30 tuổi | **Ngân sách tối đa:** 30,000,000 VNĐ
- **Tổng thời gian xử lý:** `0.33 giây` | **Số lần Resume phục hồi:** `1`

---

## 1. Thống Kê Phễu Lọc & Hiệu Quả Chi Phí AI (Token Efficiency)

| Tầng xử lý (Stage) | Đầu vào -> Đầu ra | Lượt gọi LLM | Input Tokens | Output + Thinking Tokens | Chi phí (USD) |
| :--- | :--- | ---: | ---: | ---: | ---: |
| **Stage 0: Brief Parser** | 1 brief -> SearchSpec | 1 | 214 | 302 | `$0.000819` |
| **Stage 1: Quantitative Filter (0-Token)** | 32 -> 18 KOCs | 0 | 0 | 0 | `$0.000000` |
| **Stage 2: Batch Triage (Flash-Lite)** | 18 -> 12 Finalists | 0 | 0 | 0 | `$0.000000` |
| **Stage 3: 3x3 Contact Sheet Vision** | 12 Finalists Video AI | 13 | 12,677 | 2,666 | `$0.010468` |
| **Stage 4: Portfolio Synthesis** | 12 -> Top 5 KOCs | 1 | 5,601 | 2,103 | `$0.006938` |
| **TỔNG CỘNG** | **32 -> 5 KOCs** | **15** | **18,492** | **5,071** | **`$0.018225` (~465 VNĐ)** |

> **So sánh với Kiến trúc Naive (gửi trực tiếp raw video toàn tập 32 KOC):** Tốn khoảng **`$0.3370`** -> Phễu DETOLA tiết kiệm **`94.59%` chi phí AI**.

### Dự phóng Mở rộng Quy mô (50 – 500 KOC)

| Quy mô mục tiêu | Tổng Pool KOC quét | Chi phí Kiến trúc Naive | Chi phí Phễu DETOLA | Quy đổi VNĐ | Thời gian dự kiến (8 luồng song song) |
| :--- | ---: | ---: | ---: | ---: | ---: |
| **Tìm 5 KOC** | 50 KOCs | `$0.53` | **`$0.0182`** | ~464 VNĐ | ~0.12 phút |
| **Tìm 50 KOC** | 500 KOCs | `$5.26` | **`$0.1823`** | ~4,649 VNĐ | ~0.45 phút |
| **Tìm 500 KOC** | 5,000 KOCs | `$52.65` | **`$1.8225`** | ~46,474 VNĐ | ~4.46 phút |

---

## 2. Danh Mục 5 KOC Đề Xuất & Bằng Chứng Cụ Thể

- **Chiến lược phân bổ:** Phân bổ đa dạng vai trò từ phân tích thành phần chuyên sâu, kiểm chứng độ kiềm dầu thực tế đến lớp finish nâng tone đi học/đi làm nhằm bao phủ trọn hành trình ra quyết định của nữ 18-30 tuổi.
- **Tổng ngân sách booking phân bổ:** **22,700,000 VNĐ** / 30,000,000 VNĐ *(Dự phòng seeding/vận chuyển: 7,300,000 VNĐ)*

### #1. @linhskincare.lab — *Daily Finish & Makeup Layering Creator (Test độ nâng tone, tiệp nền cho sinh viên/văn phòng)*
- **TikTok Profile:** https://www.tiktok.com/@linhskincare.lab
- **Điểm phù hợp tổng hợp:** `90.46/100` | **Ngân sách đề xuất:** **5,400,000 VNĐ**
- **Lý do lựa chọn:** @linhskincare.lab sở hữu tệp người xem phù hợp Nữ, 18–30 tuổi, chi phí booking ước tính 5,400,000 VNĐ mang lại hiệu suất chuyển đổi video cao.
- **Bằng chứng dữ liệu hiệu suất (Kalodata & TikTok):**
  - Followers: 68,500 | Lượt xem TB: 42,000 views/video (ER: 5.80%)
  - Doanh thu 30 ngày: 185,000,000 VNĐ (Video chiếm 82.2%, GPM: 168,000 VNĐ)
- **Bằng chứng phân tích hình ảnh & nội dung Video AI (Contact Sheet 3x3 & Phụ đề):**
  - [00:01] Ô #1 HOOK OPEN: Mở đầu cận mặt dưới ánh sáng tự nhiên rõ nét, nêu thẳng vấn đề da dầu dễ bết rít.
  - [00:12] Ô #4-#5 TEXTURE SWATCH & SKIN APPLY: Thoa trực tiếp lượng kem chuẩn 2 ngón tay lên má, thấy rõ kết cấu thấm nhanh không vón.
  - Trích thoại (74100101): "[00:01] Mấy bà da dầu mụn hay bị vón cục kem chống nắng thì nhìn kỹ nền da cam thường của tui nha | [00:12] Th"
  - [00:01] Ô #1 HOOK OPEN: Mở đầu cận mặt dưới ánh sáng tự nhiên rõ nét, nêu thẳng vấn đề da dầu dễ bết rít.
  - [00:12] Ô #4-#5 TEXTURE SWATCH & SKIN APPLY: Thoa trực tiếp lượng kem chuẩn 2 ngón tay lên má, thấy rõ kết cấu thấm nhanh không vón.
  - Trích thoại (74100102): "Mẹo reapply KCN cho dân văn phòng cực nhanh #kcn #skincareroutine"
- **Góc kịch bản đề xuất:** Quay video 35-45s: Hook 3s đầu soi da dưới nắng gắt, thoa đủ lượng 2 ngón tay kem chống nắng, check lại lớp nền sau 6 tiếng ngoài trời và gắn giỏ hàng deal dùng thử.
- **Lưu ý hợp tác:** Gửi sản phẩm trước 5 ngày để KOC test độ hợp da thực tế trước khi lên kịch bản.

### #2. @myanh.glowup — *Skincare & Ingredient Reviewer (Phân tích màng lọc, thành phần cho da nhạy cảm/dầu mụn)*
- **TikTok Profile:** https://www.tiktok.com/@myanh.glowup
- **Điểm phù hợp tổng hợp:** `87.87/100` | **Ngân sách đề xuất:** **4,600,000 VNĐ**
- **Lý do lựa chọn:** @myanh.glowup sở hữu tệp người xem phù hợp Nữ, 18–30 tuổi, chi phí booking ước tính 4,600,000 VNĐ mang lại hiệu suất chuyển đổi video cao.
- **Bằng chứng dữ liệu hiệu suất (Kalodata & TikTok):**
  - Followers: 52,000 | Lượt xem TB: 38,000 views/video (ER: 6.20%)
  - Doanh thu 30 ngày: 148,000,000 VNĐ (Video chiếm 85.1%, GPM: 154,000 VNĐ)
- **Bằng chứng phân tích hình ảnh & nội dung Video AI (Contact Sheet 3x3 & Phụ đề):**
  - [00:01] Ô #1 HOOK OPEN: Mở đầu cận mặt dưới ánh sáng tự nhiên rõ nét, nêu thẳng vấn đề da dầu dễ bết rít.
  - [00:12] Ô #4-#5 TEXTURE SWATCH & SKIN APPLY: Thoa trực tiếp lượng kem chuẩn 2 ngón tay lên má, thấy rõ kết cấu thấm nhanh không vón.
  - Trích thoại (74100201): "[00:01] Sáng dậy trễ 10 phút thì chỉ cần đúng em kem chống nắng nâng tone này là tự tin tới giảng đường | [00:"
- **Góc kịch bản đề xuất:** Quay video 35-45s: Hook 3s đầu soi da dưới nắng gắt, thoa đủ lượng 2 ngón tay kem chống nắng, check lại lớp nền sau 6 tiếng ngoài trời và gắn giỏ hàng deal dùng thử.
- **Lưu ý hợp tác:** Gửi sản phẩm trước 5 ngày để KOC test độ hợp da thực tế trước khi lên kịch bản.

### #3. @han.sensitive.skin — *High-Conversion Affiliate Reviewer (Săn deal, so sánh giá/dung tích chốt đơn mạnh)*
- **TikTok Profile:** https://www.tiktok.com/@han.sensitive.skin
- **Điểm phù hợp tổng hợp:** `85.98/100` | **Ngân sách đề xuất:** **3,600,000 VNĐ**
- **Lý do lựa chọn:** @han.sensitive.skin sở hữu tệp người xem phù hợp Nữ, 18–30 tuổi, chi phí booking ước tính 3,600,000 VNĐ mang lại hiệu suất chuyển đổi video cao.
- **Bằng chứng dữ liệu hiệu suất (Kalodata & TikTok):**
  - Followers: 36,500 | Lượt xem TB: 29,000 views/video (ER: 6.40%)
  - Doanh thu 30 ngày: 112,000,000 VNĐ (Video chiếm 85.7%, GPM: 149,000 VNĐ)
- **Bằng chứng phân tích hình ảnh & nội dung Video AI (Contact Sheet 3x3 & Phụ đề):**
  - [00:01] Ô #1 HOOK OPEN: Mở đầu cận mặt dưới ánh sáng tự nhiên rõ nét, nêu thẳng vấn đề da dầu dễ bết rít.
  - [00:12] Ô #4-#5 TEXTURE SWATCH & SKIN APPLY: Thoa trực tiếp lượng kem chuẩn 2 ngón tay lên má, thấy rõ kết cấu thấm nhanh không vón.
  - Trích thoại (74100501): "[00:01] Da đang bong tróc vì Retinol mà bôi sai kem chống nắng là xót chảy nước mắt liền | [00:13] Em này chứa"
- **Góc kịch bản đề xuất:** Quay video 35-45s: Hook 3s đầu soi da dưới nắng gắt, thoa đủ lượng 2 ngón tay kem chống nắng, check lại lớp nền sau 6 tiếng ngoài trời và gắn giỏ hàng deal dùng thử.
- **Lưu ý hợp tác:** Gửi sản phẩm trước 5 ngày để KOC test độ hợp da thực tế trước khi lên kịch bản.

### #4. @ngocdeal.beauty — *Skincare & Ingredient Reviewer (Phân tích màng lọc, thành phần cho da nhạy cảm/dầu mụn)*
- **TikTok Profile:** https://www.tiktok.com/@ngocdeal.beauty
- **Điểm phù hợp tổng hợp:** `85.89/100` | **Ngân sách đề xuất:** **4,700,000 VNĐ**
- **Lý do lựa chọn:** @ngocdeal.beauty sở hữu tệp người xem phù hợp Nữ, 18–30 tuổi, chi phí booking ước tính 4,700,000 VNĐ mang lại hiệu suất chuyển đổi video cao.
- **Bằng chứng dữ liệu hiệu suất (Kalodata & TikTok):**
  - Followers: 44,000 | Lượt xem TB: 34,000 views/video (ER: 4.90%)
  - Doanh thu 30 ngày: 230,000,000 VNĐ (Video chiếm 76.1%, GPM: 198,000 VNĐ)
- **Bằng chứng phân tích hình ảnh & nội dung Video AI (Contact Sheet 3x3 & Phụ đề):**
  - [00:01] Ô #1 HOOK OPEN: Mở đầu cận mặt dưới ánh sáng tự nhiên rõ nét, nêu thẳng vấn đề da dầu dễ bết rít.
  - [00:12] Ô #4-#5 TEXTURE SWATCH & SKIN APPLY: Thoa trực tiếp lượng kem chuẩn 2 ngón tay lên má, thấy rõ kết cấu thấm nhanh không vón.
  - Trích thoại (74100401): "[00:01] Đừng tiếc tiền mua kem chống nắng vì tiền trị nám đắt gấp 20 lần | [00:11] Tuýp 50ml chất gel mỏng nhẹ"
- **Góc kịch bản đề xuất:** Quay video 35-45s: Hook 3s đầu soi da dưới nắng gắt, thoa đủ lượng 2 ngón tay kem chống nắng, check lại lớp nền sau 6 tiếng ngoài trời và gắn giỏ hàng deal dùng thử.
- **Lưu ý hợp tác:** Gửi sản phẩm trước 5 ngày để KOC test độ hợp da thực tế trước khi lên kịch bản.

### #5. @vy.officebeauty — *Daily Finish & Makeup Layering Creator (Test độ nâng tone, tiệp nền cho sinh viên/văn phòng)*
- **TikTok Profile:** https://www.tiktok.com/@vy.officebeauty
- **Điểm phù hợp tổng hợp:** `84.22/100` | **Ngân sách đề xuất:** **4,400,000 VNĐ**
- **Lý do lựa chọn:** @vy.officebeauty sở hữu tệp người xem phù hợp Nữ, 18–30 tuổi, chi phí booking ước tính 4,400,000 VNĐ mang lại hiệu suất chuyển đổi video cao.
- **Bằng chứng dữ liệu hiệu suất (Kalodata & TikTok):**
  - Followers: 61,000 | Lượt xem TB: 31,000 views/video (ER: 4.70%)
  - Doanh thu 30 ngày: 134,000,000 VNĐ (Video chiếm 76.1%, GPM: 142,000 VNĐ)
- **Bằng chứng phân tích hình ảnh & nội dung Video AI (Contact Sheet 3x3 & Phụ đề):**
  - [00:01] Ô #1 HOOK OPEN: Mở đầu cận mặt dưới ánh sáng tự nhiên rõ nét, nêu thẳng vấn đề da dầu dễ bết rít.
  - [00:12] Ô #4-#5 TEXTURE SWATCH & SKIN APPLY: Thoa trực tiếp lượng kem chuẩn 2 ngón tay lên má, thấy rõ kết cấu thấm nhanh không vón.
  - Trích thoại (74100601): "Routine buổi sáng gọn nhẹ cho chị em công sở #skincarevanphong #kemchongnang"
- **Góc kịch bản đề xuất:** Quay video 35-45s: Hook 3s đầu soi da dưới nắng gắt, thoa đủ lượng 2 ngón tay kem chống nắng, check lại lớp nền sau 6 tiếng ngoài trời và gắn giỏ hàng deal dùng thử.
- **Lưu ý hợp tác:** Gửi sản phẩm trước 5 ngày để KOC test độ hợp da thực tế trước khi lên kịch bản.
