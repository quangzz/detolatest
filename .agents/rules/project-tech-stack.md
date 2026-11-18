# Project Tech Stack & Architecture Rules — DETOLA AI KOC Discovery

## 1. Tech Stack Cụ Thể
- **Language & Runtime:** Python 3.11.9
- **Package & Environment Manager:** `uv` (`pyproject.toml` + `uv.lock`)
- **LLM & Multimodal SDK:** `google-genai` (Google AI Developer API)
  - Stage 0 (Brief Parsing): `gemini-2.5-flash` (`thinking_budget=0`)
  - Stage 2 (Batch Triage): `gemini-2.5-flash-lite` (`thinking_budget=0`)
  - Stage 3 (Video Contact Sheet + Transcript Analysis): `gemini-2.5-flash` (`thinking_budget=0`)
  - Stage 4 (Portfolio Optimization & Evidence Synthesis): `gemini-2.5-flash` (`thinking_budget=1024`)
- **Data Validation & Config:** `pydantic>=2.10`, `pydantic-settings>=2.7`, `python-dotenv`
- **Media & Ingestion:** `yt-dlp` (TikTok public metadata, CC subtitles, low-res MP4 stream), `ffmpeg` 8.1 CLI + `Pillow` (Timestamped 3x3 Keyframe Contact Sheet), `openpyxl` (CSV/XLSX Kalodata fallback)
- **CLI & Resilience:** `rich` (progress & terminal tables), `tenacity` (retry with exponential backoff), `sqlite3` (WAL-mode checkpointing & entity caching)
- **Backend Web API:** `FastAPI` + `Uvicorn` (`src/api/server.py`) với CORS whitelist chặt chẽ, DTO Pydantic validation, phân trang `<= 50` và background job runner.
- **Frontend Web Console (Chuẩn SEO & URAH):** `React 19` + `Vite` + `TypeScript` + `Tailwind CSS v4` + `lucide-react` tại `E:\detola\frontend\`, cấu hình CSS-first trong `src/styles/{fonts.css, theme.css, index.css}` kèm JSON-LD, OpenGraph, `robots.txt`, `sitemap.xml` và Semantic HTML5.
- **Static Report Artifact:** Self-contained HTML5 report (`jobs/<job_id>/report.html`) xuất kèm cho mỗi job.

## 2. Folder Structure Thực Tế
```text
E:\detola\
├── .agents/rules/
│   └── project-tech-stack.md
├── scripts/
│   └── kalodata_console_capture.js   # Script hỗ trợ bắt dữ liệu bảng Kalodata Free Trial không tốn quota
├── src/
│   ├── __init__.py
│   ├── config.py                     # Cấu hình hệ thống, bảng giá Gemini, rate-limit, paths
│   ├── main.py                       # CLI entrypoint (run, resume, import-kalodata, enrich-tiktok)
│   ├── models/
│   │   └── schemas.py                # Pydantic schemas xuyên suốt 5 stages
│   ├── core/
│   │   ├── job_logger.py             # Quản lý jobs/<job_id>/ theo quy tắc Backend Job Logging
│   │   ├── checkpoint.py             # SQLite WAL checkpoint (per-job) & Global KOC/Video cache
│   │   └── llm_gateway.py            # Wrapper google-genai, đếm token/cost chính xác & dry-run
│   ├── ingestion/
│   │   ├── kalodata_loader.py        # Chuẩn hóa dữ liệu Kalodata từ JSON/HAR/CSV/XLSX
│   │   └── tiktok_enricher.py        # yt-dlp lấy danh sách video, phụ đề .vtt 0-token & tải MP4
│   ├── media/
│   │   └── contact_sheet.py          # FFmpeg + Pillow tạo ảnh lưới 3x3 có gắn mốc thời gian [mm:ss]
│   ├── pipeline/
│   │   ├── orchestrator.py           # Điều phối tuần tự 5 tầng, kiểm soát lỗi & phục hồi checkpoint
│   │   ├── stage0_brief.py           # Phân tích brief & quy đổi ngân sách 30M VNĐ
│   │   ├── stage1_hard_filter.py     # Chấm điểm định lượng 0-token
│   │   ├── stage2_triage.py          # Batch LLM lọc ngữ nghĩa & phù hợp tệp Nữ 18-30
│   │   ├── stage3_video.py           # Phân tích đa phương thức Contact Sheet + Transcript
│   │   └── stage4_portfolio.py       # Chọn tổ hợp 5 KOC tối ưu kèm bằng chứng
│   └── reporting/
│       └── report_builder.py         # Xuất BENCHMARK_RESULTS.md và jobs/<job_id>/report.html
├── data/
│   ├── snapshots/                    # Dữ liệu KOC đầu vào đã chuẩn hóa (cho phép chạy lại reproducible)
│   └── media_cache/                  # Cache ảnh Contact Sheet & phụ đề theo video_id
├── cache/                            # SQLite Global Cache tránh phân tích trùng video/KOC giữa các job
├── jobs/                             # Thư mục lưu log từng phiên chạy (status, log, llm_calls, api_calls, result)
├── docs/
│   ├── ARCHITECTURE.md
│   └── BENCHMARK_RESULTS.md
└── README.md
```

## 3. State Management & Persistence Strategy
- **Job-level State (`jobs/<job_id>/`):** Tuân thủ tuyệt đối Backend Job Logging Rule:
  - `status.json`: Cập nhật ngay mỗi khi chuyển stage hoặc xong 1 KOC.
  - `log.txt`: Toàn bộ stdout/debug/error log của phiên.
  - `llm_calls.json`: Ghi append/flush ngay sau mỗi lời gọi Gemini (lưu model, stage, input/output/thinking/cached tokens, cost USD, latency).
  - `api_calls.json`: Ghi mọi lượt gọi `yt-dlp` hoặc đọc nguồn ngoài.
  - `result.json`: Kết quả hoàn chỉnh cuối cùng.
  - `checkpoints.db`: SQLite WAL lưu trạng thái hoàn thành của từng `(stage, item_key)` để chạy tiếp với `--resume <job_id>` khi bị ngắt.
- **Cross-Job Cache (`cache/global_cache.db`):** Cache kết quả phân tích cấp video (`video_id` + `rubric_hash` -> `VideoEvidence`) với TTL 7 ngày để tiết kiệm 100% token khi tái sử dụng KOC giữa nhiều chiến dịch.

## 4. Backend Config (Rate-Limit, Cache, Cost Control)
- **Concurrency:** Giới hạn mặc định `MAX_LLM_CONCURRENCY=4`, `MAX_MEDIA_CONCURRENCY=3` qua `asyncio.Semaphore`.
- **Retry Policy:** Exponential backoff (1s -> 2s -> 4s -> 8s, tối đa 4 lần) cho lỗi mạng và HTTP `429`/`503`.
- **Video Token Budget:** Không upload raw MP4 dài tốn hàng chục nghìn token mặc định; nén thành 1 ảnh JPEG `3x3` (`1080x1080`, quality 82) + phụ đề văn bản (< 1,000 input tokens/video).

## 5. Project-Specific Conventions (Khác biệt hợp lý so với Global Frontend Rules)
- Đây là hệ thống **Backend AI Data Pipeline + CLI + Static Report** bằng Python (không phải multi-page React + Firebase app), nên không sử dụng Firebase mà dùng **Local File + SQLite WAL** theo đúng yêu cầu CLI/Prototype gọn nhẹ trong 3 ngày của đề bài DETOLA.
- Mọi comment trong code viết bằng **tiếng Việt**, tên biến/hàm/class viết bằng **tiếng Anh** chuẩn PEP8 (`snake_case` cho hàm/biến, `PascalCase` cho class).
