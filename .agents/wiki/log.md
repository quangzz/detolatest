# Nhật Ký Kiến Trúc & Quyết Định Kỹ Thuật (Wiki Log)

## [2026-11-18] Khởi tạo Phễu 5 Tầng & Áp dụng Chuẩn URAH Agent Standards
1. **Hybrid Inference Routing:**
   - Tầng lọc cứng định lượng (`Stage 1`) chạy thuần toán học local (`0 token`).
   - Tầng phân loại ngữ nghĩa (`Stage 2`) định tuyến qua model siêu nhẹ `gemini-2.5-flash-lite` (`thinking_budget=0`, gom 10 KOC/call).
   - Tầng phân tích hình ảnh video (`Stage 3`) nén video thành lưới `3x3 Contact Sheet` gửi lên `gemini-2.5-flash` (`thinking_budget=0`).
   - Tầng tối ưu danh mục (`Stage 4`) bật suy luận `thinking_budget=1024` trên `gemini-2.5-flash`.
2. **Áp dụng URAH Engineering & Security Standards (`2026.1`):**
   - Bổ sung `src/core/security.py` chặn SSRF (`API7:2023`), Path Traversal (`CWE-22`), Indirect Prompt Injection (`LLM01:2025`), Denial of Wallet (`LLM04:2025`), Secret Redaction (`API8:2023`), và Reverse Tabnabbing (`CWE-1022`).
   - Triển khai File Bus Pointer Passing trong `orchestrator.py` và bộ kiểm thử `pytest` thực chất tại `tests/`.
