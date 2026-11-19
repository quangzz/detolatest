"""Bộ kiểm soát an ninh trung tâm tuân thủ OWASP API Top 10 (2023), OWASP LLM (2025) & ASVS L2."""

from __future__ import annotations

import ipaddress
import re
import secrets
import socket
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


# Whitelist tên miền chính thức của TikTok được phép kết nối tải media/metadata
ALLOWED_TIKTOK_HOSTS = frozenset(
    {
        "tiktok.com",
        "www.tiktok.com",
        "m.tiktok.com",
        "vt.tiktok.com",
        "vm.tiktok.com",
    }
)

# Các mẫu khóa bí mật phổ biến cần che tự động trước khi ghi xuống log/artifact
_SECRET_PATTERNS = [
    re.compile(r"AIza[0-9A-Za-z_\-]{30,45}"),
    re.compile(r"sk-[A-Za-z0-9_\-]{20,}"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]{16,}"),
    re.compile(r"(?i)(gemini_api_key\s*=\s*)[^\s\"']+"),
    re.compile(r"(?i)(kalodata_api_key\s*=\s*)[^\s\"']+"),
    re.compile(r"(?i)(secret-key['\"\s:=]+)[A-Za-z0-9._\-]{12,}"),
]

# Các cụm từ tiêm lệnh phổ biến trong bio/caption không tin cậy (LLM01:2025)
_INJECTION_PHRASES = re.compile(
    r"(?i)(ignore\s+(all\s+)?previous\s+instructions|system\s+prompt|you\s+are\s+now\s+|disregard\s+above)"
)


class SecurityViolationError(ValueError):
    """Ngoại lệ phát sinh khi phát hiện đầu vào vi phạm chính sách bảo mật (SSRF, Path Traversal, DoW)."""


def generate_secure_job_id(prefix: str = "job") -> str:
    """Sinh mã phiên làm việc dùng nguồn ngẫu nhiên mật mã CSPRNG (CWE-330 compliant)."""
    clean_prefix = sanitize_safe_id(prefix, fallback="job")[:20]
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    entropy = secrets.token_hex(3)
    return f"{clean_prefix}_{ts}_{entropy}"


def sanitize_safe_id(raw_value: str, fallback: str = "item") -> str:
    """Chuẩn hóa định danh (job_id, koc_id, video_id) chống chèn ký tự nhảy thư mục (CWE-22)."""
    text = str(raw_value or "").strip()
    if ".." in text or "/" in text or "\\" in text or "\x00" in text:
        raise SecurityViolationError(f"Định danh chứa chuỗi điều hướng thư mục không hợp lệ: {raw_value!r}")

    cleaned = re.sub(r"[^a-zA-Z0-9._\-]", "_", text).strip("._-")
    if not cleaned:
        cleaned = fallback
    return cleaned[:64]


def ensure_within_directory(base_dir: Path, candidate_path: Path) -> Path:
    """Kiểm chứng đường dẫn tuyệt đối nằm gọn bên trong thư mục gốc cho phép (CWE-22 Guard)."""
    resolved_base = base_dir.resolve()
    resolved_target = candidate_path.resolve()
    if not resolved_target.is_relative_to(resolved_base):
        raise SecurityViolationError(
            f"Phát hiện truy cập vượt khỏi thư mục cho phép: {resolved_target} (gốc: {resolved_base})"
        )
    return resolved_target


def _assert_public_ip(ip_str: str) -> None:
    """Chặn mọi địa chỉ IP nội bộ RFC1918, Loopback, Link-Local và Cloud Metadata (169.254.169.254)."""
    addr = ipaddress.ip_address(ip_str)
    if (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    ):
        raise SecurityViolationError(f"Chặn địa chỉ IP nội bộ/đặc biệt theo quy tắc chống SSRF: {ip_str}")


def validate_safe_tiktok_url(url: str, resolve_dns: bool = False) -> str:
    """Kiểm định URL trước khi truyền vào yt-dlp hoặc nhúng vào báo cáo HTML (API7:2023 & CWE-79)."""
    raw = str(url or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme.lower() != "https":
        raise SecurityViolationError(f"Chỉ chấp nhận giao thức https:// cho URL bên ngoài: {raw!r}")

    host = (parsed.hostname or "").lower().strip(".")
    if not host:
        raise SecurityViolationError(f"URL thiếu hostname hợp lệ: {raw!r}")

    # Kiểm tra nếu người dùng truyền thẳng địa chỉ IP thay vì tên miền
    try:
        _assert_public_ip(host)
        raise SecurityViolationError(f"Không chấp nhận địa chỉ IP trực tiếp thay cho tên miền TikTok: {host}")
    except ValueError as ip_parse_err:
        if isinstance(ip_parse_err, SecurityViolationError):
            raise

    if host not in ALLOWED_TIKTOK_HOSTS:
        raise SecurityViolationError(f"Tên miền không nằm trong whitelist TikTok an toàn: {host}")

    if resolve_dns:
        try:
            infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
            for info in infos:
                resolved_ip = info[4][0]
                _assert_public_ip(resolved_ip)
        except SecurityViolationError:
            raise
        except OSError:
            # Nếu máy đang offline, cho phép bước kiểm tra tĩnh đi qua để yt-dlp xử lý lỗi kết nối
            pass

    return raw


def sanitize_untrusted_text(raw_text: str, max_length: int = 1500) -> str:
    """Làm sạch dữ liệu văn bản từ KOC bên ngoài chống Indirect Prompt Injection (LLM01:2025)."""
    if not raw_text:
        return ""
    # Loại bỏ ký tự điều khiển ẩn (trừ xuống dòng và tab)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", str(raw_text))
    # Ngăn chặn đóng giả thẻ cách ly XML
    cleaned = cleaned.replace("</untrusted_koc_data>", "[filtered_tag]").replace("<untrusted_koc_data>", "[filtered_tag]")
    cleaned = _INJECTION_PHRASES.sub("[filtered_directive]", cleaned)
    return cleaned.strip()[:max_length]


def wrap_untrusted_xml(content: str) -> str:
    """Đóng khung dữ liệu bên thứ ba trong thẻ cách ly rõ ràng trước khi ghép vào prompt."""
    return f"<untrusted_koc_data>\n{content}\n</untrusted_koc_data>"


def redact_secrets(raw_text: str) -> str:
    """Che toàn bộ API key/token nhạy cảm trước khi lưu vào file log hoặc JSON (API8:2023)."""
    if not raw_text:
        return ""
    masked = str(raw_text)
    masked = _SECRET_PATTERNS[0].sub("AIza[REDACTED_KEY]", masked)
    masked = _SECRET_PATTERNS[1].sub("sk-[REDACTED_KEY]", masked)
    masked = _SECRET_PATTERNS[2].sub(r"\1[REDACTED_TOKEN]", masked)
    masked = _SECRET_PATTERNS[3].sub(r"\1[REDACTED_ENV]", masked)
    masked = _SECRET_PATTERNS[4].sub(r"\1[REDACTED_ENV]", masked)
    masked = _SECRET_PATTERNS[5].sub(r"\1[REDACTED_KALO_KEY]", masked)
    return masked


def validate_safe_signed_cdn_url(url: str, resolve_dns: bool = False) -> str:
    """Kiểm định URL video ký số trả về từ Kalodata /tiktok/video/url (*.cloudfront.net) chống SSRF."""
    raw = str(url or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme.lower() != "https":
        raise SecurityViolationError(f"Signed CDN URL phải dùng giao thức https://: {raw!r}")

    host = (parsed.hostname or "").lower().strip(".")
    if not host or (not host.endswith(".cloudfront.net") and host not in ALLOWED_TIKTOK_HOSTS):
        raise SecurityViolationError(f"Host không thuộc CDN ký số được phép của Kalodata: {host!r}")

    if resolve_dns:
        try:
            infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
            for info in infos:
                _assert_public_ip(info[4][0])
        except SecurityViolationError:
            raise
        except OSError:
            pass
    return raw
