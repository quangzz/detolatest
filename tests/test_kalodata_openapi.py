"""Kiểm thử toàn diện tích hợp Kalodata Open API v1 (Auth, Credit Metering, Error 1053/1054 & SSRF)."""

from __future__ import annotations

import json
from typing import Any, Dict

import httpx
import pytest

from src.config import Settings
from src.core.checkpoint import GlobalEntityCache
from src.core.security import SecurityViolationError, redact_secrets
from src.ingestion.kalodata_openapi_client import KalodataOpenApiClient


def test_kalodata_openapi_rank_detail_videos_and_credit_metering(tmp_path) -> None:
    """Kiểm chứng header secret-key, ánh xạ schema /creator/rank, /creator/detail, /video/rank và tính credit."""
    call_counter: Dict[str, int] = {}

    def _mock_handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("secret-key") == "kalo_live_secret_123456"
        path = request.url.path
        call_counter[path] = call_counter.get(path, 0) + 1

        if path.endswith("/credit/balance"):
            return httpx.Response(
                200,
                json={"success": True, "code": "0", "data": {"remaining_credits": 98.5}},
            )

        body: Dict[str, Any] = json.loads(request.content.decode("utf-8"))
        assert body["region"] == "VN"
        assert body["language"] == "vi-VN"
        assert body["currency"] == "VND"

        if path.endswith("/tiktok/creator/rank"):
            assert body["sort_field"] == {"field": "video_revenue", "type": "DESC"}
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "code": "0",
                    "data": [
                        {
                            "creator_id": "7100998877",
                            "creator_nickname": "Linh Skincare Official",
                            "creator_handle": "@linh.skincare.vn",
                            "revenue": 195_000_000,
                            "video_revenue": 160_000_000,
                            "live_revenue": 35_000_000,
                            "sales_volumn": 890,
                            "creator_followers": "72.4K",
                            "content_views": "480K",
                            "category_list": ["Beauty & Personal Care", "Skincare"],
                            "ter_category_list": ["Kem chống nắng"],
                        }
                    ],
                },
            )

        if path.endswith("/tiktok/creator/detail"):
            assert body["creator_id"] == "7100998877"
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "code": "0",
                    "data": {
                        "creator_id": "7100998877",
                        "creator_status": "INDEPENDENT",
                        "creator_bio": "Review kem chống nắng da dầu mụn",
                        "video_gpm": 172_000,
                        "video_number": 16,
                        "video_views": 640_000,
                    },
                },
            )

        if path.endswith("/tiktok/video/rank"):
            assert body["creator_id"] == "7100998877"
            assert body["is_ai_video"] == 0
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "code": "0",
                    "data": [
                        {
                            "video_id": "7499001122",
                            "video_title": "Test kem chống nắng kiềm dầu 8 tiếng #kemchongnang #skincare",
                            "belonged_creator_id": "7100998877",
                            "belonged_creator_handle": "linh.skincare.vn",
                            "revenue": 54_000_000,
                            "views": 68_000,
                            "ads_roas": 3.4,
                            "digg_count": 4_200,
                            "comment_count": 310,
                            "share_count": 195,
                            "ad": 1,
                            "ai_video": 0,
                            "publish_date": "2026/11/10 19:30:00",
                        }
                    ],
                },
            )

        return httpx.Response(404, json={"success": False, "message": "Not found"})

    cache = GlobalEntityCache()
    cache.db_path = tmp_path / "isolated_cache.db"
    cache._init_db()

    settings = Settings(KALODATA_API_KEY="kalo_live_secret_123456")
    client = KalodataOpenApiClient(
        settings=settings,
        global_cache=cache,
        http_transport=httpx.MockTransport(_mock_handler),
    )

    balance = client.get_credit_balance()
    assert balance["remaining_credits"] == 98.5
    assert client.total_credits_estimated == 0.0  # /credit/balance miễn phí 0 credit

    ranked = client.rank_creators(keyword="kem chống nắng", page_size=20)
    assert len(ranked) == 1
    cand = ranked[0]
    assert cand.handle == "linh.skincare.vn"
    assert cand.kalodata_creator_id == "7100998877"
    assert cand.followers == 72_400
    assert cand.items_sold_30d == 890
    assert client.total_credits_estimated == 0.1

    enriched = client.enrich_finalist_from_openapi(cand)
    assert enriched.bio == "Review kem chống nắng da dầu mụn"
    assert enriched.gpm_vnd == 172_000
    assert enriched.avg_video_views == 40_000
    assert len(enriched.recent_videos) == 1
    assert enriched.recent_videos[0].revenue_vnd == 54_000_000
    assert round(client.total_credits_estimated, 2) == 0.3  # 0.1 rank + 0.1 detail + 0.1 video/rank


def test_kalodata_video_url_codes_1054_1053_and_ssrf(tmp_path) -> None:
    """Kiểm chứng xử lý mã đặc thù 1054 (queued), 1053 (missing cache chống gọi lặp) và chặn SSRF CDN."""
    attempts = {"1053_calls": 0}

    def _video_url_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        vid = body["video_id"]
        if vid == "vid_ok":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "code": "0",
                    "data": {
                        "video_id": "vid_ok",
                        "video_url": "https://d4ewq8axz3ayo.cloudfront.net/videos/vid_ok.mp4",
                        "expires_at": "2026-11-19T10:00:00Z",
                    },
                },
            )
        if vid == "vid_1054":
            return httpx.Response(
                200,
                json={"success": False, "code": "1054", "message": "Video fetch queued"},
            )
        if vid == "vid_1053":
            attempts["1053_calls"] += 1
            return httpx.Response(
                200,
                json={"success": False, "code": "1053", "message": "Video does not exist"},
            )
        if vid == "vid_ssrf":
            return httpx.Response(
                200,
                json={
                    "success": True,
                    "code": "0",
                    "data": {
                        "video_id": "vid_ssrf",
                        "video_url": "https://127.0.0.1/internal_secret.mp4",
                    },
                },
            )
        return httpx.Response(400, json={"success": False})

    cache = GlobalEntityCache()
    cache.db_path = tmp_path / "video_url_cache.db"
    cache._init_db()

    client = KalodataOpenApiClient(
        settings=Settings(KALODATA_API_KEY="kalo_live_secret_123456"),
        global_cache=cache,
        http_transport=httpx.MockTransport(_video_url_handler),
    )

    # 1. Signed CloudFront hợp lệ
    ok_url = client.get_video_signed_url("vid_ok")
    assert ok_url == "https://d4ewq8axz3ayo.cloudfront.net/videos/vid_ok.mp4"
    assert client.total_credits_estimated == 0.5

    # 2. Mã 1054 trả None êm ái, không cộng credit
    assert client.get_video_signed_url("vid_1054") is None
    assert client.total_credits_estimated == 0.5

    # 3. Mã 1053 lưu cờ âm để lần gọi thứ 2 không bắn request lên Kalodata trong cửa sổ khóa 60s
    assert client.get_video_signed_url("vid_1053") is None
    assert client.get_video_signed_url("vid_1053") is None
    assert attempts["1053_calls"] == 1

    # 4. Chặn SSRF nếu CDN trả về host lạ / IP nội bộ
    with pytest.raises(SecurityViolationError):
        client.get_video_signed_url("vid_ssrf")


def test_kalodata_base_url_ssrf_and_secret_redaction() -> None:
    """Kiểm chứng chặn Base URL giả mạo và che secret-key trong log."""
    with pytest.raises(SecurityViolationError):
        KalodataOpenApiClient(
            settings=Settings(
                KALODATA_API_KEY="kalo_live_secret_123456",
                KALODATA_BASE_URL="https://evil-proxy.example.com/openapi/v1",
            )
        )

    masked = redact_secrets("Header lỗi: secret-key: kalo_live_secret_999888777666")
    assert "kalo_live_secret_999888777666" not in masked
    assert "[REDACTED_KALO_KEY]" in masked
