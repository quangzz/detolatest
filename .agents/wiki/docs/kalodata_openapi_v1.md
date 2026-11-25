# Đặc Tả Tích Hợp Chính Thức: Kalodata Open API v1 (`https://www.kalodata.com/openapi/v1`)

Tài liệu tham chiếu trích xuất trực tiếp từ `https://www.kalodata.com/open-center/docs` & `/open-center/pricing`.

## 1. Xác Thực & Tham Số Chung
- **Base URL:** `https://www.kalodata.com/openapi/v1`
- **Headers bắt buộc:**
  - `secret-key: <KALODATA_API_KEY>`
  - `Content-Type: application/json;charset=UTF-8`
- **Tham số chung cho thị trường Việt Nam:**
  - `region`: `"VN"`
  - `language`: `"vi-VN"`
  - `currency`: `"VND"`
  - `date_range`: `"last30Day"` (hoặc `"last7Day"`, `"yyyy-MM-dd~yyyy-MM-dd"` tối đa 30 ngày cho `/rank`)

## 2. Các Endpoint Tích Hợp & Định Mức Credit (`1 credit ≈ $0.10 USD`)
| Endpoint | Method | Rate Limit | Chi phí Credit | Vai trò trong Phễu DETOLA |
| :--- | :---: | :---: | :---: | :--- |
| `/credit/balance` | `GET` | — | **0 credit** | Kiểm tra kết nối khóa `secret-key` và số dư credit hiện tại |
| `/tiktok/category/rank` | `POST` | 10 req/10s | `0.1 × ceil(N/100)` | Tra cứu mã ngành hàng (`category_id`) tại thị trường VN |
| `/tiktok/creator/rank` | `POST` | 10 req/10s | `0.1 × ceil(N/100)` | Thu thập tới 100 KOC phù hợp khung follower & từ khóa chỉ với **0.1 credit** |
| `/tiktok/creator/detail` | `POST` | 500 req/10s | `0.1 credit` | Chỉ gọi cho nhóm **Finalists (Stage 3)** để lấy `creator_bio`, `video_gpm`, liên hệ |
| `/tiktok/video/rank` | `POST` | 10 req/10s | `0.1 × ceil(N/100)` | Lấy danh sách video bán hàng doanh thu cao nhất của từng Finalist (`creator_id`) |
| `/tiktok/video/detail` | `POST` | 100 req/10s | `0.1 credit` | Lấy chi tiết `duration`, `video_gpm`, `ads_roas`, `ai_video` khi cần |
| `/tiktok/video/url` | `POST` | 10 req/10s | `0.5 credit` | Fallback tải MP4 CloudFront (xử lý mã `1054` đang xếp hàng tải và `1053` không tồn tại) |

## 3. Chiến Lược Tối Ưu Hóa Credit Kalodata (Credit Efficiency)
Thay vì gọi `/tiktok/creator/detail` và `/tiktok/video/url` cho toàn bộ 100 ứng viên (tốn `>60 credits` ~ `\$6.00`), DETOLA:
1. Gọi 1 lần `/tiktok/creator/rank` (`page_size=100`, tốn **0.1 credit** ~ `\$0.01`) để nạp pool đầu vào.
2. Chạy Stage 1 (`0 token`) + Stage 2 (`gemini-2.5-flash-lite`) lọc còn 12 Finalists.
3. Chỉ gọi `/tiktok/creator/detail` + `/tiktok/video/rank` cho 12 Finalists (tốn `2.4 credits`), ưu tiên tải video qua `yt-dlp` (`0 credit`) và chỉ gọi `/tiktok/video/url` làm phao cứu sinh khi cần.
