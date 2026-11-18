# SecureVibes Security Assessment Report

> *Compiled from `.securevibes/scan_report.md` via 5 independent source-code verification passes (`src/`, `scripts/`, `jobs/*/report.html` read in full for each cited finding).*

## 📊 1. Executive Summary
- **Target Project:** DETOLA — AI KOC Discovery Pipeline (`E:\detola`)
- **Assessment Date:** 2026-11-18
- **Standards Referenced:** OWASP API Security Top 10 (2023), OWASP LLM Top 10 (2025), OWASP ASVS v4.0.3 Level 2, CWE Top Risks
- **Total Initial Findings Discovered & Remediated:** 5 (100% Remediated & Verified by `pytest`)
- **Residual Open Risk Severity Breakdown:**
  - 🔴 **Critical:** 0
  - 🟠 **High:** 0
  - 🟡 **Medium:** 0
  - 🔵 **Low / Informational:** 0

---

## 🎯 2. Attack Surface & Architecture Overview
- **Backend / Pipeline Architecture:** Python 3.11+ CLI & Orchestrator (`pydantic v2`, `google-genai`, `yt-dlp`, `ffmpeg`, `Pillow`)
- **Frontend / Report Viewer:** Static Self-Contained HTML5 Report (`src/reporting/report_builder.py` -> `jobs/<job_id>/report.html`)
- **Authentication & Secrets:** Server-side `.env` (`GEMINI_API_KEY`), excluded via `.gitignore`, masked in logs via `redact_secrets()`
- **Database & State:** Local SQLite WAL (`jobs/<job_id>/checkpoints.db` & `cache/global_cache.db`) with `contextlib.closing` deterministic handle cleanup

---

## 🔍 3. STRIDE Threat Model & Remediated Findings Log

| STRIDE | Threat Vector in AI KOC Discovery | Mitigating Control Implemented | Verification |
| :--- | :--- | :--- | :--- |
| **S — Spoofing** | Giả mạo URL kênh TikTok trong file JSON đầu vào dẫn hướng tới máy chủ độc hại/nội bộ | Whitelist cứng `ALLOWED_TIKTOK_HOSTS` + giao thức `https://` tại `src/core/security.py` | `test_ssrf_guard_blocks_internal_ips_and_bad_schemes` |
| **T — Tampering** | KOC chèn câu lệnh Prompt Injection vào Bio/Caption/Subtitles nhằm thao túng điểm xếp hạng | `sanitize_untrusted_text()` + đóng khung cách ly `<untrusted_koc_data>` ở Stage 2 & Stage 3 (`LLM01:2025`) | `test_secret_redaction_and_prompt_injection_sanitization` |
| **R — Repudiation** | Thiếu dấu vết kiểm toán chi phí token hoặc trạng thái khi crash giữa chừng | Ghi nguyên tử `status.json`, `llm_calls.json`, `api_calls.json`, `log.txt` trong `jobs/<job_id>/` | `test_crash_recovery_zero_duplicate_calls_and_html_security_headers` |
| **I — Info Disclosure** | Rò rỉ `GEMINI_API_KEY` trong log lỗi hoặc Reverse Tabnabbing trên báo cáo HTML | `redact_secrets()` trong `JobLogger`; `rel="noopener noreferrer"` + CSP meta tag trong `report.html` (`CWE-1022`) | `test_secret_redaction...` & `test_crash_recovery...` |
| **D — Denial of Wallet** | Tập ứng viên quá lớn hoặc vòng lặp LLM gây cạn ngân sách API | Timeout `45,000ms`, trần `max_output_tokens`, giới hạn `1,000` KOC/job và cầu chì `max_job_cost_usd` (`LLM04:2025`) | `test_denial_of_wallet_circuit_breaker` |
| **E — Elevation / Path Escape** | Chèn `../` vào `job_id`, `koc_id` hoặc `video_id` để ghi đè file ngoài thư mục `jobs/` hoặc `data/` | `sanitize_safe_id()` + `ensure_within_directory()` (`Path.is_relative_to`) tại mọi điểm I/O (`CWE-22`) | `test_path_traversal_guard_blocks_dotdot_and_slashes` |

---

## 🛠️ 4. Pre-Flight Security Checklist Verification (URAH Standard)
- [x] **Schema Validation:** 100% đầu vào/đầu ra LLM và dữ liệu KOC kiểm định qua Pydantic v2 (`src/models/schemas.py`).
- [x] **CSPRNG Entropy (`CWE-330`):** Mã phiên động dùng `secrets.token_hex()` trong `generate_secure_job_id()`.
- [x] **File I/O & SSRF Guard (`CWE-22`, `API7:2023`):** Kiểm tra `is_relative_to` và chặn toàn bộ IP RFC1918 / Loopback / `169.254.169.254`.
- [x] **Client Report Security (`CWE-79`, `CWE-1022`):** `html.escape()` toàn bộ biến nội suy, kiểm tra `https://`, gắn `rel="noopener noreferrer"` và thẻ CSP.
- [x] **Clean Source Hygiene (`AGENTS.md` Mục 4 & 5):** Không có biến debug `window.__...`, fixture kiểm thử có cờ `is_test: true`.
- [x] **Dynamic Verification:** `uv run python -m compileall -q src tests` (exit 0) và `uv run pytest -v` (6/6 passed).
