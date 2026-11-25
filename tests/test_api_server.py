"""Kiểm thử tích hợp cho FastAPI Backend (DTO Validation, Security Headers, Crash-Resume qua REST API)."""

from __future__ import annotations

import shutil
import time

from fastapi.testclient import TestClient

from src.api.server import app
from src.config import JOBS_DIR


client = TestClient(app)


def test_health_and_security_headers() -> None:
    """Kiểm chứng /api/health trả đúng trạng thái, che khóa API và đính kèm OWASP Security Headers."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert resp.headers.get("X-Frame-Options") == "DENY"
    body = resp.json()
    assert body["status"] == "ok"
    assert "gemini_configured" in body


def test_dto_mass_assignment_and_path_traversal_blocked() -> None:
    """Kiểm chứng API3:2023 (chặn trường lạ extra='forbid') và CWE-22 (chặn nhảy thư mục dataset)."""
    bad_mass_assign = client.post(
        "/api/jobs",
        json={
            "product_name": "Kem chống nắng",
            "is_admin": True,
        },
    )
    assert bad_mass_assign.status_code == 422

    bad_traversal = client.post(
        "/api/jobs",
        json={
            "dataset_filename": "../pyproject.toml",
            "dry_run": True,
        },
    )
    assert bad_traversal.status_code == 400


def test_end_to_end_api_crash_and_resume_lifecycle() -> None:
    """Kiểm chứng tạo job qua API -> giả lập ngắt Stage 3 -> gọi API resume -> hoàn tất SUCCESS."""
    created = client.post(
        "/api/jobs",
        json={
            "dataset_filename": "fixture_sunscreen_pool_32.json",
            "product_name": "Kem chống nắng",
            "target_audience": "Nữ, 18–30 tuổi",
            "total_budget_vnd": 30_000_000,
            "target_koc_count": 5,
            "dry_run": True,
            "simulate_crash_after_kocs": 2,
        },
    )
    assert created.status_code == 202
    job_id = created.json()["job_id"]
    job_dir = JOBS_DIR / job_id

    try:
        # Chờ luồng nền dừng tại điểm giả lập sập (INTERRUPTED)
        settled_status = ""
        for _ in range(30):
            detail = client.get(f"/api/jobs/{job_id}").json()
            settled_status = detail["status"]["status"]
            if settled_status in {"INTERRUPTED", "FAILED", "SUCCESS"}:
                break
            time.sleep(0.1)
        assert settled_status == "INTERRUPTED"

        # Gọi endpoint resume để chạy tiếp từ SQLite checkpoint
        resumed = client.post(f"/api/jobs/{job_id}/resume", json={"dry_run": True})
        assert resumed.status_code == 202

        final_detail = {}
        for _ in range(40):
            final_detail = client.get(f"/api/jobs/{job_id}").json()
            if final_detail["status"]["status"] == "SUCCESS":
                break
            time.sleep(0.1)

        assert final_detail["status"]["status"] == "SUCCESS"
        assert final_detail["status"]["resumed_count"] >= 1
        assert len(final_detail["result"]["portfolio_recommendation"]["selected_kocs"]) == 5
    finally:
        time.sleep(0.1)
        if job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)
