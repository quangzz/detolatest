# Lessons Learned Log — DETOLA Project

Ghi nhận các bài học rút ra và hiệu chỉnh kỹ thuật theo quy chuẩn URAH Network:
- **[2026-11-18] Đồng bộ URAH Agent Standards (`2026.1`):**
  - Luôn kiểm tra `rel="noopener noreferrer"` trên mọi thẻ `<a target="_blank">` trong báo cáo HTML (`CWE-1022`).
  - Không đặt biến toàn cục dạng `window.__...` trong script trình duyệt hoặc trộn dữ liệu test thiếu cờ `is_test` (`agent-working-rules.md` mục 4 & 5).
  - Mọi thao tác đọc URL bên ngoài (`yt-dlp`) và ghép đường dẫn file theo ID người dùng phải đi qua lớp bảo vệ SSRF & Path Traversal (`src/core/security.py`).
