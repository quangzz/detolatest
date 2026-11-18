# DETOLA — AI KOC Discovery System

Hệ thống nghiên cứu, chấm điểm đa phương thức (Video AI) và đề xuất danh mục KOC TikTok với **chi phí token tối ưu (>94% tiết kiệm so với phân tích raw video)** và **khả năng tự phục hồi tiến độ (Crash-Resumable)**, xây dựng cho bài kiểm tra **DETOLA — Founding Engineer**.

---

## 1. Điểm Nổi Bật Của Giải Pháp

- **Phễu lọc 5 tầng tối ưu chi phí (Multi-Stage Funnel):**
  - **Stage 0 (`gemini-2.5-flash`, `thinking=0`):** Chuyển đổi đề bài tự nhiên & ngân sách 30 triệu VNĐ sang khung giá booking hợp lý (Nano/Micro-KOC) và bộ tiêu chí chấm điểm.
  - **Stage 1 (`0 Token` Math Filter):** Loại tức thì Mega KOL vượt ngân sách, kênh chỉ thuần Livestream bán sỉ hoặc lệch ngành hàng; tính điểm ROI/triệu đồng chi phí.
  - **Stage 2 (`gemini-2.5-flash-lite`, gom 10 KOC/call, `thinking=0`):** Đánh giá độ khớp tệp **Nữ 18–30 tuổi** và phân vai trò chiến dịch.
  - **Stage 3 (`gemini-2.5-flash` Vision + `yt-dlp` + `ffmpeg`):** Trích xuất phụ đề TikTok có sẵn (`0 token` STT) và ghép 9 khung hình quan trọng thành **1 tấm ảnh lưới Contact Sheet 3x3 có gắn mốc `[mm:ss]`** (~520 image tokens thay vì ~13,500 raw video tokens).
  - **Stage 4 (`gemini-2.5-flash`, `thinking=1024`):** Tối ưu hóa danh mục 5 KOC đa dạng vai trò, đảm bảo tổng ngân sách `<= 30.000.000 VNĐ` kèm trích dẫn bằng chứng số liệu & mốc giây video cụ thể.
- **Tự động lưu tiến độ & Phục hồi khi ngắt giữa chừng (`SQLite WAL` + `jobs/<job_id>/`):** Hỗ trợ ngắt đột ngột ở bất kỳ bước nào và chạy tiếp bằng `detola resume <job_id>` không tốn lại 1 token nào cho các KOC đã xử lý.
- **Báo cáo Trực quan & Đo lường Minh bạch:** Mỗi phiên chạy tự động xuất `jobs/<job_id>/report.html` (kèm ảnh Contact Sheet 3x3), `llm_calls.json`, `status.json` và cập nhật `docs/BENCHMARK_RESULTS.md`.

---

## 2. Yêu Cầu Hệ Thống & Cài Đặt Nhanh

### Yêu cầu
- **Python 3.11+** và trình quản lý gói **`uv`** (hoặc `pip`)
- **`ffmpeg`** đã có trong `PATH` hệ thống (dùng để cắt khung hình video ở Stage 3)
- Khóa **`GEMINI_API_KEY`** từ Google AI Studio (chỉ cần khi chạy chế độ Live; chế độ `--dry-run` không cần khóa API)

### Cài đặt (trong 10 giây)
```powershell
cd E:\detola
uv sync
Copy-Item .env.example .env
# Mở file .env và điền GEMINI_API_KEY=AIza... của bạn
```

---

## 3. Hướng Dẫn Chạy Demo & Kiểm Thử

### Cách 1: Chạy kiểm thử toàn trình Offline (Không tốn tiền API)
```powershell
uv run detola run --dry-run --job-id demo_dryrun
```
Mở file `E:\detola\jobs\demo_dryrun\report.html` trên trình duyệt để xem bảng điều khiển trực quan.

### Cách 2: Kiểm thử Khả năng Phục hồi khi Bị Gián đoạn (Reliability / Crash Recovery)
```powershell
# Bước 1: Cố tình làm sập tiến trình sau khi phân tích xong 2 KOC ở Stage 3
uv run detola run --dry-run --job-id crash_demo --simulate-crash-after 2

# Bước 2: Khôi phục tiến trình — hệ thống tự động đọc SQLite checkpoint, bỏ qua 2 KOC đầu với 0 token và chạy tiếp!
uv run detola resume crash_demo --dry-run
```

### Cách 3: Thu thập Dữ liệu Thực từ Kalodata (7-Day Free Trial) & Chạy Live với Gemini API

Vì tài khoản **Kalodata Free Trial 7 ngày** khóa nút xuất Excel và giới hạn số lượt bấm vào trang chi tiết KOC mỗi ngày, dự án cung cấp sẵn công cụ thu thập thụ động không tốn quota:

1. Đăng nhập `https://www.kalodata.com` (chọn thị trường **Việt Nam**).
2. Vào mục **Creator (Nhà sáng tạo)** -> Lọc ngành **Beauty & Personal Care / Chăm sóc da** (hoặc tìm *"kem chống nắng"*), lọc Follower khoảng **10K – 200K**.
3. Nhấn `F12` mở tab **Console**, copy toàn bộ nội dung file `scripts/kalodata_console_capture.js` dán vào Console và nhấn `Enter`.
4. Bấm chuyển qua vài trang danh sách KOC để gom đủ 30–60 ứng viên, sau đó bấm nút màu xanh **`📥 Tải JSON KOC`** ở góc phải dưới màn hình để tải file `kalodata_captured.json`.
5. Chép `kalodata_captured.json` vào `E:\detola\data\snapshots\kalodata_captured.json` và kiểm tra dữ liệu:
   ```powershell
   uv run detola inspect-input data/snapshots/kalodata_captured.json
   ```
6. Chạy Live với Gemini API (tự động kéo video + phụ đề TikTok + tạo Contact Sheet 3x3 + phân tích AI):
   ```powershell
   uv run detola run --input data/snapshots/kalodata_captured.json --job-id live_sunscreen_benchmark
   ```
*(Ngoài ra, `--input` cũng đọc trực tiếp được file `.csv`, `.xlsx` từ Kalodata bản trả phí hoặc file Network `.har`).*

---

## 4. Cấu Trúc Tài Liệu Bàn Giao

- **Kiến trúc & Quyết định Thiết kế:** Xem chi tiết tại [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- **Kết quả Đề xuất 5 KOC & Benchmark Chi phí/Thời gian:** Xem tại [`docs/BENCHMARK_RESULTS.md`](docs/BENCHMARK_RESULTS.md)
- **Nhật ký Chi tiết Phiên chạy (`jobs/<job_id>/`):**
  - `status.json`: Tiến độ và tổng hợp token realtime
  - `llm_calls.json`: Chi tiết từng lời gọi Gemini (prompt/output/thinking tokens, latency, USD cost)
  - `api_calls.json`: Lịch sử gọi `yt-dlp` thu thập video & phụ đề
  - `result.json` & `report.html`: Hồ sơ kết quả đầy đủ và giao diện báo cáo trực quan

---

## 5. Giới Hạn Hiện Tại & Hướng Mở Rộng Lên Production

### Giới hạn hiện tại của bản Prototype
1. **Ước tính giá Booking KOC:** Kalodata không công khai bảng giá booking riêng tư của từng KOC, nên Stage 1 sử dụng mô hình hồi quy thực nghiệm dựa trên `followers`, `avg_video_views` và `video_revenue_30d`. Trong thực tế cần kết nối thêm CRM báo giá lịch sử của Agency.
2. **Phụ thuộc chống bot của TikTok khi tải số lượng lớn:** Ở quy mô 5–20 KOC demo, `yt-dlp` hoạt động trực tiếp ổn định; tuy nhiên nếu tải đồng thời hàng nghìn video không qua proxy dân cư (residential proxy), TikTok có thể trả về mã chặn tạm thời.
3. **Phân tích âm thanh khi video không có phụ đề CC:** Hiện tại nếu video không bật phụ đề tự động của TikTok, hệ thống fallback sang mô tả/hashtag kết hợp Contact Sheet hình ảnh thay vì chạy Whisper STT nhằm giữ tốc độ và chi phí tối thiểu.

### Hướng mở rộng (500 – 10.000+ KOC)
1. **Tầng Hàng đợi Phân tán (Celery / Temporal + Redis):** Tách riêng cụm Media Worker (`yt-dlp` + `ffmpeg` gắn proxy pool) và cụm LLM Evaluator để đạt thông lượng ~100 KOC/phút.
2. **Gemini Batch API (Giảm thêm 50% đơn giá token):** Với các chiến dịch nghiên cứu không đòi hỏi phản hồi tức thì dưới 1 phút, chuyển Stage 2 và Stage 3 sang Gemini Batch Mode giúp giảm một nửa chi phí trên mỗi triệu token.
3. **Vector & Multimodal Feature Store (pgvector):** Lưu vector biểu diễn phong cách hình ảnh và tệp khán giả của từng KOC đã từng quét tại Việt Nam; các chiến dịch mỹ phẩm tiếp theo có thể truy xuất gần như tức thời từ kho tri thức nội bộ.
