# Technical Design Specification — DETOLA AI KOC Discovery (Source of Truth)

> Tài liệu đặc tả kỹ thuật chuẩn theo kỷ luật **Spec-Driven Development** (`rules/agentic-engineering-discipline.md`). Mọi thay đổi về schema, luồng xử lý và giới hạn an ninh phải được cập nhật tại đây và kiểm chứng qua `pytest`.

## 1. Bất Biến Nghiệp Vụ & Ngân Sách (Business Invariants)
1. **Budget Cap Invariant:** Tổng `allocated_budget_vnd` của toàn bộ KOC được chọn cộng với `reserve_seeding_budget_vnd` luôn phải `<= total_budget_vnd` (mặc định `30,000,000 VNĐ`).
2. **Evidence-Backed Invariant:** Mỗi KOC trong danh sách đề xuất cuối cùng bắt buộc phải có:
   - Ít nhất 1 dẫn chứng số liệu định lượng (`performance_evidence`).
   - Ít nhất 1 dẫn chứng hình ảnh/lời thoại từ phân tích video (`visual_and_video_evidence`).
3. **Test Namespace Separation (`agent-working-rules.md` Mục 4 & 5):** Dữ liệu giả lập kiểm thử phải gắn cờ `is_test: true` rõ ràng, tách biệt hoàn toàn với snapshot dữ liệu thực thu thập từ Kalodata.

## 2. Giao Thức File Bus & Pointer Passing
Để chống tràn Context Window và tuân thủ `backend-job-logging.md`:
- Mọi phiên chạy ghi trực tiếp vào `jobs/<job_id>/{status.json, log.txt, llm_calls.json, api_calls.json, result.json, checkpoints.db}`.
- Kết quả điều phối trả về cấu trúc con trỏ nhẹ (`JobExecutionPointers`):
  ```json
  {
    "job_id": "job_...",
    "status": "SUCCESS",
    "status_url": "jobs/<job_id>/status.json",
    "log_url": "jobs/<job_id>/log.txt",
    "result_url": "jobs/<job_id>/result.json",
    "report_html_url": "jobs/<job_id>/report.html",
    "benchmark_md_url": "docs/BENCHMARK_RESULTS.md"
  }
  ```

## 3. Ràng Buộc An Ninh & Kiểm Soát Chi Phí (Security & Cost Guardrails)
| Hạng mục | Tiêu chuẩn tham chiếu | Ràng buộc kỹ thuật bắt buộc |
| :--- | :--- | :--- |
| **Path Safety** | `CWE-22`, `ASVS V12` | Mọi `job_id`, `koc_id`, `video_id` đi qua `sanitize_safe_id` và `ensure_within_directory`. |
| **SSRF Defense** | `API7:2023`, `WSTG-INPV-11` | Chỉ cho phép tải media từ `https://*.tiktok.com`, chặn IP nội bộ/loopback/link-local. |
| **Prompt Isolation** | `LLM01:2025` | Bọc dữ liệu mô tả KOC/video trong thẻ `<untrusted_koc_data>`, khử ký tự điều khiển và thẻ giả mạo. |
| **Denial of Wallet** | `LLM04:2025`, `API4:2023` | Timeout cứng `45,000ms` mỗi lần gọi LLM, giới hạn `max_output_tokens`, cầu chì `max_job_cost_usd` (\$0.50), giới hạn tối đa `1,000` ứng viên/lần nạp. |
| **Secret Redaction** | `API8:2023`, `WSTG-ERRH` | Tự động che khóa `AIza...`, `Bearer ...`, `sk-...` trước khi ghi xuống đĩa. |
| **HTML Report** | `CWE-79`, `CWE-1022` | Escape toàn bộ dữ liệu động, kiểm tra `https://` cho link ngoài, bắt buộc `rel="noopener noreferrer"` và thẻ meta CSP. |
