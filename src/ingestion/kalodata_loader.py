"""Bộ đọc và chuẩn hóa dữ liệu KOC từ Kalodata (hỗ trợ JSON capture, HAR, CSV, XLSX)."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from openpyxl import load_workbook

from src.core.security import sanitize_safe_id
from src.models.schemas import KocCandidate, TikTokVideoMeta


# Hệ số nhân cho các hậu tố tiền tệ / số lượng phổ biến trên Kalodata (VN & Quốc tế)
_MULTIPLIERS = {
    "k": 1_000,
    "nghìn": 1_000,
    "ngàn": 1_000,
    "m": 1_000_000,
    "tr": 1_000_000,
    "triệu": 1_000_000,
    "b": 1_000_000_000,
    "tỷ": 1_000_000_000,
    "ty": 1_000_000_000,
}


def parse_human_number(raw: Any, default: float = 0.0) -> float:
    """Chuyển đổi chuỗi số rút gọn (VD: '125.4K', '₫48,5Tr', '1.2 tỷ', '4.6%') về số thực."""
    if raw is None:
        return default
    if isinstance(raw, (int, float)):
        return float(raw)

    text = str(raw).strip().lower()
    if not text or text in {"-", "--", "n/a", "null", "none"}:
        return default

    is_percent = "%" in text
    cleaned = re.sub(r"[₫đ$€£¥,\s]", "", text)

    # Bắt mẫu số + hậu tố (VD: 12.5tr, 85.2k, 1.4b)
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*(tỷ|ty|triệu|tr|nghìn|ngàn|k|m|b)?", cleaned)
    if not match:
        return default

    value = float(match.group(1))
    suffix = (match.group(2) or "").strip()
    if suffix in _MULTIPLIERS:
        value *= _MULTIPLIERS[suffix]

    if is_percent and value > 1.0:
        return round(value / 100.0, 6)
    return value


def _pick_first(record: Dict[str, Any], keys: Iterable[str]) -> Any:
    """Lấy giá trị đầu tiên khác rỗng trong danh sách khóa ứng viên (không phân biệt hoa thường)."""
    lower_map = {str(k).strip().lower(): v for k, v in record.items()}
    for key in keys:
        val = lower_map.get(key.lower())
        if val not in (None, ""):
            return val
    return None


def _normalize_single_record(raw: Dict[str, Any]) -> Optional[KocCandidate]:
    """Chuẩn hóa 1 bản ghi thô từ JSON/CSV/DOM của Kalodata sang KocCandidate."""
    # Nếu bản ghi đã ở dạng chuẩn KocCandidate (từ snapshot của hệ thống)
    if "koc_id" in raw and "handle" in raw and isinstance(raw.get("recent_videos", []), list):
        try:
            return KocCandidate.model_validate(raw)
        except Exception:
            pass

    handle_raw = _pick_first(
        raw,
        [
            "handle",
            "uniqueId",
            "unique_id",
            "tiktok_handle",
            "tiktokHandle",
            "username",
            "creator_handle",
            "tài khoản",
            "id nhà sáng tạo",
            "nhà sáng tạo",
        ],
    )
    if not handle_raw and "raw_row_text" in raw:
        m = re.search(r"@([a-zA-Z0-9._]{3,40})", str(raw["raw_row_text"]))
        if m:
            handle_raw = m.group(1)

    if not handle_raw:
        return None

    raw_clean_handle = re.sub(r"^@+", "", str(handle_raw).strip()).split()[0].lower()
    if not raw_clean_handle or len(raw_clean_handle) < 2:
        return None
    try:
        handle = sanitize_safe_id(raw_clean_handle, fallback="")
    except ValueError:
        return None
    if not handle or len(handle) < 2:
        return None

    display_name = str(
        _pick_first(
            raw,
            ["display_name", "nickname", "nickName", "name", "creator_name", "tên hiển thị"],
        )
        or handle
    ).strip()

    category = str(
        _pick_first(
            raw,
            ["category", "categoryName", "main_category", "ngành hàng", "danh mục"],
        )
        or "Beauty & Personal Care"
    ).strip()

    bio = str(
        _pick_first(raw, ["bio", "signature", "description", "giới thiệu", "tiểu sử"]) or ""
    ).strip()

    followers = int(
        parse_human_number(
            _pick_first(
                raw,
                [
                    "followers",
                    "followerCount",
                    "follower_count",
                    "fans",
                    "người theo dõi",
                    "lượt theo dõi",
                ],
            )
        )
    )

    revenue_30d = int(
        parse_human_number(
            _pick_first(
                raw,
                [
                    "revenue_30d_vnd",
                    "revenue",
                    "gmv",
                    "saleAmount",
                    "total_revenue",
                    "doanh thu",
                    "doanh thu (30 ngày)",
                ],
            )
        )
    )

    video_rev = int(
        parse_human_number(
            _pick_first(
                raw,
                [
                    "video_revenue_30d_vnd",
                    "videoRevenue",
                    "video_gmv",
                    "videoSaleAmount",
                    "doanh thu video",
                ],
            )
        )
    )
    live_rev = int(
        parse_human_number(
            _pick_first(
                raw,
                [
                    "live_revenue_30d_vnd",
                    "liveRevenue",
                    "live_gmv",
                    "liveSaleAmount",
                    "doanh thu live",
                ],
            )
        )
    )
    if revenue_30d > 0 and video_rev == 0 and live_rev == 0:
        # Nếu bảng tóm tắt chỉ có tổng doanh thu, mặc định giả định cân bằng 60% video để chờ làm giàu
        video_rev = int(revenue_30d * 0.6)
        live_rev = revenue_30d - video_rev
    elif revenue_30d == 0 and (video_rev > 0 or live_rev > 0):
        revenue_30d = video_rev + live_rev

    items_sold = int(
        parse_human_number(
            _pick_first(
                raw,
                ["items_sold_30d", "saleCount", "items_sold", "unitsSold", "lượt bán", "số lượng bán"],
            )
        )
    )
    avg_views = int(
        parse_human_number(
            _pick_first(
                raw,
                ["avg_video_views", "avgViews", "avgPlayCount", "lượt xem trung bình", "views trung bình"],
            )
        )
    )
    er = float(
        parse_human_number(
            _pick_first(
                raw,
                ["engagement_rate", "engagementRate", "interactRate", "er", "tỷ lệ tương tác"],
            )
        )
    )
    if er > 1.0:
        er = round(er / 100.0, 5)

    gpm_vnd = int(
        parse_human_number(_pick_first(raw, ["gpm_vnd", "gpm", "videoGpm", "gpm video"]))
    )
    active_videos = int(
        parse_human_number(
            _pick_first(raw, ["active_videos_30d", "videoCount", "videos_30d", "số lượng video"])
        )
    )

    female_ratio_raw = _pick_first(raw, ["female_audience_ratio", "femaleRatio", "tỷ lệ nữ"])
    female_ratio = parse_human_number(female_ratio_raw, -1.0) if female_ratio_raw is not None else None
    if female_ratio is not None and female_ratio < 0:
        female_ratio = None

    age_ratio_raw = _pick_first(raw, ["age_18_30_ratio", "youngAdultRatio", "tỷ lệ 18-30"])
    age_ratio = parse_human_number(age_ratio_raw, -1.0) if age_ratio_raw is not None else None
    if age_ratio is not None and age_ratio < 0:
        age_ratio = None

    est_cost = int(
        parse_human_number(_pick_first(raw, ["estimated_booking_cost_vnd", "booking_fee", "chi phí dự kiến"]))
    )

    kw_raw = _pick_first(raw, ["top_product_keywords", "productKeywords", "topProducts", "sản phẩm nổi bật"])
    if isinstance(kw_raw, list):
        keywords = [str(x).strip() for x in kw_raw if str(x).strip()]
    elif isinstance(kw_raw, str) and kw_raw.strip():
        keywords = [s.strip() for s in re.split(r"[,;|]", kw_raw) if s.strip()]
    else:
        keywords = []

    videos_raw = raw.get("recent_videos") or []
    videos: List[TikTokVideoMeta] = []
    if isinstance(videos_raw, list):
        for v in videos_raw:
            if isinstance(v, dict) and v.get("video_id") and v.get("url"):
                videos.append(TikTokVideoMeta.model_validate(v))

    return KocCandidate(
        koc_id=handle,
        handle=handle,
        display_name=display_name,
        profile_url=f"https://www.tiktok.com/@{handle}",
        category=category,
        bio=bio,
        followers=followers,
        revenue_30d_vnd=revenue_30d,
        video_revenue_30d_vnd=video_rev,
        live_revenue_30d_vnd=live_rev,
        items_sold_30d=items_sold,
        avg_video_views=avg_views,
        engagement_rate=er,
        gpm_vnd=gpm_vnd,
        active_videos_30d=active_videos,
        female_audience_ratio=female_ratio,
        age_18_30_ratio=age_ratio,
        top_product_keywords=keywords,
        estimated_booking_cost_vnd=est_cost,
        recent_videos=videos,
        raw_extra={k: v for k, v in raw.items() if k in {"raw_row_text", "raw_cells", "_source"}},
    )


def load_kalodata_candidates(input_path: Path, max_candidates: int = 1_000) -> List[KocCandidate]:
    """Đọc danh sách ứng viên KOC từ file JSON, HAR, CSV hoặc XLSX có giới hạn trần (API4:2023)."""
    if not input_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file dữ liệu đầu vào: {input_path}")

    suffix = input_path.suffix.lower()
    raw_records: List[Dict[str, Any]] = []

    if suffix in {".json", ".har"}:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            raw_records = [x for x in payload if isinstance(x, dict)]
        elif isinstance(payload, dict):
            if isinstance(payload.get("items"), list):
                raw_records = payload["items"]
            elif isinstance(payload.get("candidates"), list):
                raw_records = payload["candidates"]
            elif isinstance(payload.get("data"), list):
                raw_records = payload["data"]
            elif "log" in payload and isinstance(payload["log"].get("entries"), list):
                # Hỗ trợ đọc trực tiếp file Network .har xuất từ Chrome DevTools
                raw_records = _extract_records_from_har(payload["log"]["entries"])
    elif suffix == ".csv":
        with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            raw_records = [dict(row) for row in reader]
    elif suffix in {".xlsx", ".xlsm"}:
        wb = load_workbook(filename=str(input_path), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if len(rows) >= 2:
            headers = [str(h or f"col_{idx}").strip() for idx, h in enumerate(rows[0])]
            for row in rows[1:]:
                raw_records.append(dict(zip(headers, row)))
        wb.close()
    else:
        raise ValueError(f"Định dạng file chưa được hỗ trợ: {suffix}")

    deduped: Dict[str, KocCandidate] = {}
    for rec in raw_records:
        candidate = _normalize_single_record(rec)
        if candidate is None:
            continue
        existing = deduped.get(candidate.koc_id)
        if existing is None or candidate.revenue_30d_vnd >= existing.revenue_30d_vnd:
            deduped[candidate.koc_id] = candidate

    return list(deduped.values())[:max_candidates]


def _extract_records_from_har(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Đệ quy tìm kiếm danh sách KOC bên trong các gói JSON của file .har."""
    found: List[Dict[str, Any]] = []

    def _walk(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                _walk(item)
        elif isinstance(node, dict):
            if any(k in node for k in ("uniqueId", "unique_id", "handle", "tiktokHandle")) and any(
                k in node for k in ("followerCount", "followers", "revenue", "gmv", "saleAmount")
            ):
                found.append(node)
            for val in node.values():
                if isinstance(val, (dict, list)):
                    _walk(val)

    for entry in entries:
        text = entry.get("response", {}).get("content", {}).get("text")
        if not text or not isinstance(text, str):
            continue
        stripped = text.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                _walk(json.loads(stripped))
            except Exception:
                continue
    return found
