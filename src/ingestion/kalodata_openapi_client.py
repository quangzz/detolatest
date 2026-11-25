"""Client chính thức tích hợp Kalodata Open API v1 (https://www.kalodata.com/openapi/v1)."""

from __future__ import annotations

import json
import math
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from src.config import SNAPSHOTS_DIR, Settings, ensure_directories
from src.core.checkpoint import GlobalEntityCache
from src.core.job_logger import JobLogger
from src.core.security import (
    SecurityViolationError,
    ensure_within_directory,
    redact_secrets,
    sanitize_safe_id,
    validate_safe_signed_cdn_url,
)
from src.ingestion.kalodata_loader import parse_human_number
from src.models.schemas import KocCandidate, TikTokVideoMeta


ALLOWED_KALODATA_API_HOSTS = frozenset({"www.kalodata.com", "kalodata.com"})


class KalodataApiError(RuntimeError):
    """Ngoại lệ nghiệp vụ trả về từ Kalodata Open API v1."""

    def __init__(self, message: str, code: str = "", status_code: int = 0) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class KalodataTransientNetworkError(RuntimeError):
    """Lỗi mạng hoặc HTTP 429/5xx tạm thời cho phép tự động thử lại."""


class KalodataOpenApiClient:
    """Client giao tiếp chuẩn với Kalodata Open API v1 kèm kiểm soát Rate Limit (10 req/10s) & đo Credit."""

    def __init__(
        self,
        settings: Settings,
        job_logger: Optional[JobLogger] = None,
        global_cache: Optional[GlobalEntityCache] = None,
        http_transport: Optional[httpx.BaseTransport] = None,
    ) -> None:
        self.settings = settings
        self.job_logger = job_logger
        self.global_cache = global_cache or GlobalEntityCache()
        self._transport = http_transport

        self.base_url = self._validate_base_url(settings.kalodata_base_url)
        self.api_key = (settings.kalodata_api_key or "").strip()
        self._rate_lock = threading.Lock()
        self._last_request_ts = 0.0
        self.total_credits_estimated = 0.0

    @staticmethod
    def _validate_base_url(raw_url: str) -> str:
        """Đảm bảo Base URL chỉ trỏ tới máy chủ HTTPS chính thức của Kalodata (chống SSRF)."""
        cleaned = (raw_url or "https://www.kalodata.com/openapi/v1").strip().rstrip("/")
        parsed = urlparse(cleaned)
        if parsed.scheme.lower() != "https" or (parsed.hostname or "").lower() not in ALLOWED_KALODATA_API_HOSTS:
            raise SecurityViolationError(f"Base URL Kalodata không hợp lệ: {raw_url!r}")
        return cleaned

    def is_configured(self) -> bool:
        """Kiểm tra khóa secret-key của Kalodata đã được cung cấp hợp lệ hay chưa."""
        return bool(
            self.api_key
            and self.api_key != "your_kalodata_secret_key_here"
            and len(self.api_key) >= 10
        )

    def _throttle_rate_limit(self, min_interval_sec: float = 0.25) -> None:
        """Giữ nhịp gọi an toàn dưới ngưỡng 10 req / 10s của các endpoint /rank."""
        with self._rate_lock:
            elapsed = time.perf_counter() - self._last_request_ts
            if elapsed < min_interval_sec:
                time.sleep(min_interval_sec - elapsed)
            self._last_request_ts = time.perf_counter()

    @retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1.0, min=1.0, max=8.0),
        retry=retry_if_exception_type(KalodataTransientNetworkError),
    )
    def _request(
        self,
        method: str,
        endpoint_path: str,
        json_body: Optional[Dict[str, Any]] = None,
        min_interval_sec: float = 0.25,
    ) -> Dict[str, Any]:
        """Thực thi HTTP request kèm header `secret-key` chuẩn của Kalodata Open Center."""
        if not self.is_configured():
            raise KalodataApiError("Chưa cấu hình KALODATA_API_KEY (secret-key).")

        self._throttle_rate_limit(min_interval_sec=min_interval_sec)
        url = f"{self.base_url}/{endpoint_path.lstrip('/')}"
        headers = {
            "secret-key": self.api_key,
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "application/json",
        }

        start_ts = time.perf_counter()
        try:
            with httpx.Client(timeout=30.0, transport=self._transport) as client:
                if method.upper() == "GET":
                    resp = client.get(url, headers=headers)
                else:
                    resp = client.post(url, headers=headers, json=json_body or {})
        except httpx.RequestError as exc:
            raise KalodataTransientNetworkError(f"Lỗi kết nối mạng tới Kalodata: {redact_secrets(str(exc))}") from exc

        latency_ms = round((time.perf_counter() - start_ts) * 1000.0, 2)

        if resp.status_code in {429, 502, 503, 504}:
            raise KalodataTransientNetworkError(f"Kalodata trả mã tạm thời HTTP {resp.status_code}")

        try:
            envelope = resp.json()
        except Exception as exc:
            raise KalodataApiError(
                f"Phản hồi từ Kalodata không phải JSON hợp lệ (HTTP {resp.status_code})",
                status_code=resp.status_code,
            ) from exc

        if not isinstance(envelope, dict):
            raise KalodataApiError("Cấu trúc phản hồi Kalodata không hợp lệ.", status_code=resp.status_code)

        success = bool(envelope.get("success", resp.status_code == 200))
        code = str(envelope.get("code") or "")
        message = str(envelope.get("message") or "")

        est_credits = self._estimate_credits(endpoint_path, envelope, success=success)
        self.total_credits_estimated = round(self.total_credits_estimated + est_credits, 4)

        if self.job_logger is not None:
            self.job_logger.log_api_call(
                {
                    "provider": "kalodata_openapi_v1",
                    "endpoint": endpoint_path,
                    "http_status": resp.status_code,
                    "success": success,
                    "code": code,
                    "cached": bool(envelope.get("cached", False)),
                    "estimated_credits": est_credits,
                    "latency_ms": latency_ms,
                }
            )

        if not success or resp.status_code >= 400:
            raise KalodataApiError(
                message=message or f"Kalodata từ chối yêu cầu (code={code}, HTTP={resp.status_code})",
                code=code,
                status_code=resp.status_code,
            )

        return envelope

    @staticmethod
    def _estimate_credits(endpoint_path: str, envelope: Dict[str, Any], success: bool) -> float:
        """Tính số credit tiêu thụ theo bảng giá chính thức tại /open-center/pricing."""
        if not success:
            return 0.0
        clean_ep = endpoint_path.strip("/").lower()
        if clean_ep.startswith("credit/"):
            return 0.0
        if clean_ep.endswith("/rank"):
            data = envelope.get("data")
            rows = len(data) if isinstance(data, list) else 1
            if rows == 0:
                return 0.0
            return round(0.1 * math.ceil(rows / 100.0), 4)
        if clean_ep == "tiktok/video/url":
            return 0.5
        if clean_ep in {"tiktok/product/images", "tiktok/product/comments"}:
            return 0.01
        if clean_ep == "tiktok/product/comment/insight":
            return 0.0 if envelope.get("cached") else 1.0
        return 0.1

    def _public_params(self, date_range: str = "last30Day") -> Dict[str, str]:
        """Sinh bộ 4 tham số toàn cục bắt buộc cho mọi endpoint dữ liệu của Kalodata."""
        return {
            "region": self.settings.kalodata_region,
            "language": self.settings.kalodata_language,
            "currency": self.settings.kalodata_currency,
            "date_range": date_range,
        }

    def get_credit_balance(self) -> Dict[str, Any]:
        """Truy vấn số dư credit hiện tại của tài khoản (GET /credit/balance — miễn phí 0 credit)."""
        envelope = self._request("GET", "/credit/balance", min_interval_sec=0.05)
        data = envelope.get("data")
        return data if isinstance(data, dict) else {"raw": data}

    def rank_categories(
        self,
        date_range: str = "last30Day",
        page_size: int = 50,
        category_level: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Lấy bảng xếp hạng ngành hàng TikTok Shop (POST /tiktok/category/rank)."""
        body: Dict[str, Any] = {
            **self._public_params(date_range=date_range),
            "sort_field": {"field": "revenue", "type": "DESC"},
            "page_size": max(1, min(100, page_size)),
            "page_number": 1,
        }
        if category_level in {1, 2, 3}:
            body["category_level"] = category_level
        env = self._request("POST", "/tiktok/category/rank", json_body=body, min_interval_sec=1.0)
        data = env.get("data")
        return data if isinstance(data, list) else []

    def rank_creators(
        self,
        *,
        keyword: str = "",
        followers_range: str = "10000-200000",
        creator_type: str = "INDEPENDENT",
        category_id_list: str = "",
        date_range: str = "last30Day",
        sort_by: str = "video_revenue",
        page_size: int = 50,
        page_number: int = 1,
    ) -> List[KocCandidate]:
        """Tìm kiếm và xếp hạng KOC (POST /tiktok/creator/rank — tối đa 100 KOC chỉ tốn 0.1 credit)."""
        body: Dict[str, Any] = {
            **self._public_params(date_range=date_range),
            "sort_field": {"field": sort_by, "type": "DESC"},
            "page_size": max(1, min(100, page_size)),
            "page_number": max(1, page_number),
            "need_category": 1,
            "need_ter_category": 1,
        }
        if keyword.strip():
            body["keyword"] = keyword.strip()
        if followers_range.strip():
            body["followers_range"] = followers_range.strip()
        if creator_type in {"INDEPENDENT", "BELONGED_TO_SELLER"}:
            body["creator_type"] = creator_type
        if category_id_list.strip():
            body["category_id_list"] = category_id_list.strip()

        env = self._request("POST", "/tiktok/creator/rank", json_body=body, min_interval_sec=1.0)
        rows = env.get("data")
        if not isinstance(rows, list):
            return []

        candidates: List[KocCandidate] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            cand = self._map_creator_rank_row(row)
            if cand is not None:
                candidates.append(cand)
        return candidates

    def get_creator_detail(self, creator_id: str, date_range: str = "last30Day") -> Optional[Dict[str, Any]]:
        """Lấy hồ sơ chi tiết KOC (POST /tiktok/creator/detail — 0.1 credit, có cache 7 ngày)."""
        if not creator_id:
            return None
        cache_key = f"{self.settings.kalodata_region}:{date_range}:{creator_id}"
        cached = self.global_cache.get("kalodata_creator_detail", cache_key)
        if cached and isinstance(cached, dict):
            return cached

        body = {
            **self._public_params(date_range=date_range),
            "creator_id": str(creator_id),
            "need_extra": True,
        }
        env = self._request("POST", "/tiktok/creator/detail", json_body=body, min_interval_sec=0.1)
        data = env.get("data")
        if isinstance(data, dict):
            self.global_cache.set("kalodata_creator_detail", cache_key, data)
            return data
        return None

    def rank_creator_videos(
        self,
        creator_id: str,
        keyword: str = "",
        date_range: str = "last30Day",
        page_size: int = 5,
    ) -> List[TikTokVideoMeta]:
        """Lấy danh sách video bán hàng tốt nhất của 1 KOC (POST /tiktok/video/rank — 0.1 credit)."""
        if not creator_id:
            return []
        cache_key = f"{self.settings.kalodata_region}:{date_range}:{creator_id}:{keyword}:{page_size}"
        cached = self.global_cache.get("kalodata_creator_videos", cache_key)
        if cached and isinstance(cached, list):
            return [TikTokVideoMeta.model_validate(v) for v in cached]

        body: Dict[str, Any] = {
            **self._public_params(date_range=date_range),
            "creator_id": str(creator_id),
            "sort_field": {"field": "revenue", "type": "DESC"},
            "page_size": max(1, min(50, page_size)),
            "page_number": 1,
            "is_ai_video": 0,  # Ưu tiên video người thật review thay vì video AI công nghiệp
        }
        if keyword.strip():
            body["keyword"] = keyword.strip()

        env = self._request("POST", "/tiktok/video/rank", json_body=body, min_interval_sec=1.0)
        rows = env.get("data")
        if not isinstance(rows, list):
            return []

        videos: List[TikTokVideoMeta] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            vid = str(row.get("video_id") or "").strip()
            handle = re.sub(r"^@+", "", str(row.get("belonged_creator_handle") or "creator")).strip().lower()
            if not vid:
                continue
            title = str(row.get("video_title") or "").strip()
            hashtags = re.findall(r"#([\wÀ-ỹ]+)", title)
            videos.append(
                TikTokVideoMeta(
                    video_id=vid,
                    url=f"https://www.tiktok.com/@{handle}/video/{vid}",
                    title=title[:140],
                    description=title,
                    views=int(parse_human_number(row.get("views"))),
                    likes=int(parse_human_number(row.get("digg_count"))),
                    comments=int(parse_human_number(row.get("comment_count"))),
                    shares=int(parse_human_number(row.get("share_count"))),
                    published_at=str(row.get("publish_date") or ""),
                    hashtags=hashtags[:10],
                    revenue_vnd=int(parse_human_number(row.get("revenue"))),
                    ads_roas=float(parse_human_number(row.get("ads_roas"))),
                    is_ad=bool(int(row.get("ad") or 0) == 1),
                    is_ai_video=bool(int(row.get("ai_video") or 0) == 1),
                )
            )

        if videos:
            self.global_cache.set(
                "kalodata_creator_videos",
                cache_key,
                [v.model_dump() for v in videos],
            )
        return videos

    def get_video_signed_url(self, video_id: str) -> Optional[str]:
        """Lấy URL video MP4 ký số từ CloudFront của Kalodata (POST /tiktok/video/url — 0.5 credit).

        Xử lý đặc thù theo tài liệu:
        - Mã `1054`: Video chưa lưu sẵn, Kalodata đang xếp hàng tải bất đồng bộ -> trả None an toàn.
        - Mã `1053`: Video không tồn tại (bị khóa 60s nếu gọi lại) -> ghi nhớ âm 120s để không gọi lặp!
        """
        if not video_id:
            return None
        neg_flag = self.global_cache.get("kalodata_video_missing_1053", video_id)
        if neg_flag:
            return None

        try:
            env = self._request(
                "POST",
                "/tiktok/video/url",
                json_body={"video_id": str(video_id)},
                min_interval_sec=1.0,
            )
        except KalodataApiError as api_err:
            if api_err.code == "1053":
                self.global_cache.set("kalodata_video_missing_1053", video_id, {"missing": True})
            if api_err.code in {"1053", "1054"}:
                if self.job_logger:
                    self.job_logger.info(
                        f"[KALODATA] /tiktok/video/url trả mã {api_err.code} cho video {video_id}: {api_err}"
                    )
                return None
            raise

        data = env.get("data")
        if not isinstance(data, dict):
            return None
        signed_url = str(data.get("video_url") or "").strip()
        if not signed_url:
            return None
        return validate_safe_signed_cdn_url(signed_url, resolve_dns=True)

    def enrich_finalist_from_openapi(self, candidate: KocCandidate, date_range: str = "last30Day") -> KocCandidate:
        """Làm giàu sâu chỉ dành riêng cho ứng viên vòng Finalist (Stage 3) để tối ưu hóa credit."""
        if not self.is_configured() or not candidate.kalodata_creator_id:
            return candidate

        try:
            detail = self.get_creator_detail(candidate.kalodata_creator_id, date_range=date_range)
            if detail:
                if detail.get("creator_bio"):
                    candidate.bio = str(detail["creator_bio"]).strip()
                if detail.get("creator_status"):
                    candidate.creator_status = str(detail["creator_status"]).strip()
                video_gpm = int(parse_human_number(detail.get("video_gpm")))
                if video_gpm > 0:
                    candidate.gpm_vnd = video_gpm
                video_num = int(parse_human_number(detail.get("video_number")))
                if video_num > 0:
                    candidate.active_videos_30d = video_num
                video_views_total = int(parse_human_number(detail.get("video_views")))
                if video_views_total > 0 and video_num > 0:
                    candidate.avg_video_views = video_views_total // video_num
        except Exception as exc:
            if self.job_logger:
                self.job_logger.info(
                    f"[WARN] Bỏ qua làm giàu creator/detail cho @{candidate.handle}: {redact_secrets(str(exc))}"
                )

        if not candidate.recent_videos:
            try:
                vids = self.rank_creator_videos(
                    creator_id=candidate.kalodata_creator_id,
                    date_range=date_range,
                    page_size=4,
                )
                if vids:
                    candidate.recent_videos = vids
            except Exception as exc:
                if self.job_logger:
                    self.job_logger.info(
                        f"[WARN] Bỏ qua làm giàu video/rank cho @{candidate.handle}: {redact_secrets(str(exc))}"
                    )

        return candidate

    def sync_creators_to_snapshot(
        self,
        *,
        keyword: str = "kem chống nắng",
        followers_range: str = "10000-200000",
        creator_type: str = "INDEPENDENT",
        category_id_list: str = "",
        date_range: str = "last30Day",
        total_limit: int = 50,
    ) -> tuple[Path, List[KocCandidate]]:
        """Kéo danh sách KOC từ /tiktok/creator/rank theo phân trang và lưu thành file snapshot chuẩn hóa."""
        ensure_directories()
        target_total = max(1, min(500, total_limit))
        collected: Dict[str, KocCandidate] = {}
        pages_needed = math.ceil(target_total / 100.0)

        for page_num in range(1, pages_needed + 1):
            remaining = target_total - len(collected)
            if remaining <= 0:
                break
            batch = self.rank_creators(
                keyword=keyword,
                followers_range=followers_range,
                creator_type=creator_type,
                category_id_list=category_id_list,
                date_range=date_range,
                page_size=min(100, remaining),
                page_number=page_num,
            )
            if not batch:
                break
            for item in batch:
                collected[item.koc_id] = item
            if len(batch) < min(100, remaining):
                break

        candidates = list(collected.values())
        slug_kw = sanitize_safe_id(keyword or "all", fallback="creators")[:24]
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"kalodata_openapi_{slug_kw}_{ts}.json"
        out_path = ensure_within_directory(SNAPSHOTS_DIR, SNAPSHOTS_DIR / filename)

        payload = {
            "is_test": False,
            "source": "kalodata_openapi_v1",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "query": {
                "region": self.settings.kalodata_region,
                "keyword": keyword,
                "followers_range": followers_range,
                "creator_type": creator_type,
                "date_range": date_range,
            },
            "estimated_credits_used": self.total_credits_estimated,
            "koc_count": len(candidates),
            "items": [c.model_dump() for c in candidates],
        }
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return out_path, candidates

    @staticmethod
    def _map_creator_rank_row(row: Dict[str, Any]) -> Optional[KocCandidate]:
        """Ánh xạ bản ghi trả về từ POST /tiktok/creator/rank sang KocCandidate."""
        raw_handle = str(row.get("creator_handle") or row.get("creator_id") or "").strip()
        clean_handle = re.sub(r"^@+", "", raw_handle).split()[0].lower()
        if not clean_handle:
            return None
        try:
            safe_handle = sanitize_safe_id(clean_handle, fallback="")
        except ValueError:
            return None
        if len(safe_handle) < 2:
            return None

        cat_list = row.get("category_list") if isinstance(row.get("category_list"), list) else []
        ter_list = row.get("ter_category_list") if isinstance(row.get("ter_category_list"), list) else []
        main_cat = str(cat_list[0]).strip() if cat_list else "Beauty & Personal Care"
        sub_cats = [str(x).strip() for x in (cat_list[1:] + ter_list) if str(x).strip()]

        followers = int(parse_human_number(row.get("creator_followers")))
        content_views = int(parse_human_number(row.get("content_views")))
        revenue = int(parse_human_number(row.get("revenue")))
        video_rev = int(parse_human_number(row.get("video_revenue")))
        live_rev = int(parse_human_number(row.get("live_revenue")))
        sales_vol = int(parse_human_number(row.get("sales_volumn")))

        return KocCandidate(
            koc_id=safe_handle,
            kalodata_creator_id=str(row.get("creator_id") or "").strip(),
            handle=safe_handle,
            display_name=str(row.get("creator_nickname") or safe_handle).strip(),
            profile_url=f"https://www.tiktok.com/@{safe_handle}",
            category=main_cat,
            sub_categories=sub_cats,
            followers=followers,
            revenue_30d_vnd=revenue,
            video_revenue_30d_vnd=video_rev,
            live_revenue_30d_vnd=live_rev,
            items_sold_30d=sales_vol,
            avg_video_views=max(0, content_views // 12) if content_views > 0 else 0,
            top_product_keywords=sub_cats[:6],
        )
