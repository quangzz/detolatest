# Hybrid Inference Routing & OWASP LLM/API Security Design

## 1. Hybrid Inference (Định tuyến mô hình thông minh)
Áp dụng đúng quy chuẩn mục 3 của `agentic-engineering-discipline.md`:
- **Local Deterministic Router (`Stage 1`):** 0ms latency API, `0 token` — loại bỏ tức thì các hồ sơ vi phạm ngân sách cứng, thuần Livestream, hoặc sai ngành.
- **Lightweight Cloud Router (`Stage 2` — `gemini-2.5-flash-lite`):** Gom lô 10 KOC/call với `thinking_budget=0` để sàng lọc ngữ nghĩa nhanh với chi phí \$0.10/1M input tokens.
- **Targeted Multimodal & Portfolio Reasoning (`Stage 3 & 4` — `gemini-2.5-flash`):** Chỉ kích hoạt cho nhóm Finalists đã qua 2 vòng lọc, dùng Contact Sheet nén khung hình và kiểm soát trần `thinking_budget`.

## 2. Phòng vệ Bảo mật Đa lớp (OWASP API 2023 & OWASP LLM 2025)
- **`LLM01:2025` (Indirect Prompt Injection):** Dữ liệu bio/caption/transcript từ KOC bên ngoài được lọc ký tự điều khiển, loại bỏ thẻ đóng mở giả mạo và đóng khung trong `<untrusted_koc_data>` kèm chỉ thị cách ly ở `system_instruction`.
- **`LLM04:2025` & `API4:2023` (Denial of Wallet & Timeout):** Mọi lời gọi Gemini bắt buộc có `timeout=45000ms`, giới hạn `max_output_tokens`, và cầu chì ngân sách `MAX_JOB_COST_USD` (mặc định \$0.50/job).
- **`API7:2023` (SSRF Prevention):** Chỉ cho phép tải media từ whitelist tên miền chính thức của TikTok qua `https://`, chặn toàn bộ dải IP nội bộ RFC1918/Loopback/Cloud Metadata.
- **`CWE-22` (Path Traversal):** Mọi ID (`job_id`, `koc_id`, `video_id`) đều được chuẩn hóa an toàn và kiểm tra `Path.resolve().is_relative_to(base_dir)`.
- **`CWE-1022` & `CWE-79` (Client Report Hardening):** Báo cáo `report.html` escape toàn bộ chuỗi động, kiểm tra giao thức URL `https://`, gắn `rel="noopener noreferrer"` trên mọi thẻ `target="_blank"` và áp dụng CSP meta header.
