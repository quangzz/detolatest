"""FastAPI Backend Gateway kết nối Phễu 5 tầng DETOLA với giao diện Web chuẩn SEO."""

from __future__ import annotations

import json
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from src.api.schemas import (
    ConfigureApiKeyDto,
    ConfigureKalodataKeyDto,
    CreateJobDto,
    DatasetItemDto,
    ResumeJobDto,
    SyncKalodataDto,
)
from src.config import JOBS_DIR, ROOT_DIR, SNAPSHOTS_DIR, Settings, ensure_directories
from src.core.job_logger import JobLogger
from src.core.security import (
    SecurityViolationError,
    ensure_within_directory,
    generate_secure_job_id,
    sanitize_safe_id,
)
from src.ingestion.kalodata_loader import load_kalodata_candidates
from src.ingestion.kalodata_openapi_client import KalodataApiError, KalodataOpenApiClient
from src.ingestion.seed_fixture import generate_test_fixture
from src.models.schemas import CampaignBrief
from src.pipeline.orchestrator import execute_discovery_pipeline


# Whitelist tên miền Frontend được phép gọi API (cấm dùng '*' theo chuẩn API7:2023)
ALLOWED_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # Trần 10MB chống cạn kiệt tài nguyên (API4:2023)
ALLOWED_UPLOAD_SUFFIXES = {".json", ".csv", ".xlsx", ".har"}

# Lưu khóa API tạm thời trong RAM của tiến trình Backend (không đụng file .env, không lộ xuống Client)
_RUNTIME_STATE: Dict[str, str] = {
    "api_key_override": "",
    "kalodata_key_override": "",
}
_ACTIVE_JOBS_LOCK = threading.Lock()
_ACTIVE_JOBS: set[str] = set()

app = FastAPI(
    title="DETOLA AI KOC Discovery API",
    version="0.2.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def attach_security_headers(request: Request, call_next: Any) -> Response:
    """Đính kèm HTTP Security Headers theo chuẩn OWASP WSTG-CONF & ASVS V14."""
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


def _build_effective_settings() -> Settings:
    """Lấy cấu hình hiện hành có ưu tiên khóa API nạp qua RAM trong phiên."""
    settings = Settings()
    override = _RUNTIME_STATE.get("api_key_override", "").strip()
    if override:
        settings.gemini_api_key = override
    kalo_override = _RUNTIME_STATE.get("kalodata_key_override", "").strip()
    if kalo_override:
        settings.kalodata_api_key = kalo_override
    return settings


def _mask_key_status(key: str, placeholder: str = "your_gemini_api_key_here") -> tuple[bool, str]:
    """Kiểm tra trạng thái khóa API và chỉ trả về chuỗi che an toàn."""
    clean = (key or "").strip()
    if not clean or clean == placeholder or len(clean) < 10:
        return False, "Chưa cấu hình"
    return True, f"{clean[:4]}••••••••{clean[-3:]}"


def _get_git_commit_short() -> str:
    """Lấy mã commit hiện tại phục vụ endpoint /api/health (AGENTS.md Mục 0)."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT_DIR),
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        return (proc.stdout or "local").strip() or "local"
    except Exception:
        return "local"


@app.get("/api/health")
def get_health() -> Dict[str, Any]:
    """Kiểm tra sức khỏe hệ thống, phiên bản commit và trạng thái sẵn sàng của Gemini + Kalodata Open API."""
    ensure_directories()
    settings = _build_effective_settings()
    configured, masked = _mask_key_status(settings.gemini_api_key, "your_gemini_api_key_here")
    kalo_configured, kalo_masked = _mask_key_status(
        settings.kalodata_api_key,
        "your_kalodata_secret_key_here",
    )
    return {
        "status": "ok",
        "service": "detola-koc-discovery",
        "commit": _get_git_commit_short(),
        "server_time": datetime.now(timezone.utc).isoformat(),
        "gemini_configured": configured,
        "gemini_key_masked": masked,
        "kalodata_configured": kalo_configured,
        "kalodata_key_masked": kalo_masked,
        "kalodata_region": settings.kalodata_region,
        "models": {
            "triage": settings.triage_model,
            "multimodal": settings.multimodal_model,
            "portfolio": settings.portfolio_model,
        },
    }


@app.post("/api/settings/api-key")
def set_runtime_api_key(dto: ConfigureApiKeyDto) -> Dict[str, Any]:
    """Cập nhật khóa Gemini trong bộ nhớ phiên chạy Backend (không lưu localStorage phía Client)."""
    clean_key = dto.api_key.strip()
    _RUNTIME_STATE["api_key_override"] = clean_key
    configured, masked = _mask_key_status(clean_key, "your_gemini_api_key_here")
    return {
        "configured": configured,
        "gemini_key_masked": masked,
        "message": "Đã nạp khóa Gemini API vào phiên chạy Backend thành công.",
    }


@app.post("/api/settings/kalodata-key")
def set_runtime_kalodata_key(dto: ConfigureKalodataKeyDto) -> Dict[str, Any]:
    """Cập nhật khóa secret-key của Kalodata Open API trong RAM Backend và kiểm tra số dư (0 credit)."""
    clean_key = dto.secret_key.strip()
    _RUNTIME_STATE["kalodata_key_override"] = clean_key
    settings = _build_effective_settings()
    configured, masked = _mask_key_status(clean_key, "your_kalodata_secret_key_here")

    balance_info: Optional[Dict[str, Any]] = None
    verify_note = "Đã lưu khóa secret-key vào RAM Backend."
    try:
        client = KalodataOpenApiClient(settings=settings)
        balance_info = client.get_credit_balance()
        verify_note = "Đã xác thực thành công với Kalodata Open API (/credit/balance — 0 credit)!"
    except Exception as exc:
        verify_note = f"Đã lưu khóa vào RAM (lưu ý khi kiểm tra /credit/balance: {exc})"

    return {
        "configured": configured,
        "kalodata_key_masked": masked,
        "balance": balance_info,
        "message": verify_note,
    }


@app.get("/api/kalodata/balance")
def check_kalodata_balance() -> Dict[str, Any]:
    """Kiểm tra số dư credit Kalodata Open API (miễn phí 0 credit)."""
    settings = _build_effective_settings()
    client = KalodataOpenApiClient(settings=settings)
    if not client.is_configured():
        raise HTTPException(status_code=400, detail="Chưa cấu hình khóa secret-key của Kalodata Open API.")
    try:
        data = client.get_credit_balance()
        return {"status": "ok", "balance": data}
    except KalodataApiError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/kalodata/sync")
def sync_kalodata_creators(dto: SyncKalodataDto) -> Dict[str, Any]:
    """Gọi trực tiếp POST /tiktok/creator/rank từ Kalodata Open API v1 và lưu thành dataset mới."""
    settings = _build_effective_settings()
    client = KalodataOpenApiClient(settings=settings)
    if not client.is_configured():
        raise HTTPException(
            status_code=400,
            detail="Vui lòng bấm nút Cấu hình Kalodata Key để nhập secret-key trước khi đồng bộ trực tiếp.",
        )

    ctype = "" if dto.creator_type == "ALL" else dto.creator_type
    try:
        out_path, candidates = client.sync_creators_to_snapshot(
            keyword=dto.keyword,
            followers_range=dto.followers_range,
            creator_type=ctype,
            date_range=dto.date_range,
            total_limit=dto.total_limit,
        )
    except KalodataApiError as exc:
        raise HTTPException(status_code=400, detail=f"Kalodata Open API báo lỗi: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Không thể kết nối Kalodata Open API: {exc}") from exc

    return {
        "filename": out_path.name,
        "koc_count": len(candidates),
        "estimated_credits_used": client.total_credits_estimated,
        "sample_handles": [f"@{c.handle}" for c in candidates[:5]],
        "message": (
            f"Đã kéo thành công {len(candidates)} KOC từ Kalodata Open API v1 "
            f"(ước tính chỉ tốn {client.total_credits_estimated} credit)!"
        ),
    }


@app.get("/api/datasets", response_model=List[DatasetItemDto])
def list_datasets() -> List[DatasetItemDto]:
    """Liệt kê các tập dữ liệu KOC khả dụng trong data/snapshots/ (tự khởi tạo fixture nếu trống)."""
    ensure_directories()
    fixture_file = SNAPSHOTS_DIR / "fixture_sunscreen_pool_32.json"
    if not fixture_file.exists():
        generate_test_fixture(fixture_file)

    items: List[DatasetItemDto] = []
    for path in sorted(SNAPSHOTS_DIR.iterdir()):
        if not path.is_file() or path.suffix.lower() not in ALLOWED_UPLOAD_SUFFIXES:
            continue
        try:
            cands = load_kalodata_candidates(path, max_candidates=1_000)
            is_test = path.name.startswith("fixture_")
            if path.suffix.lower() == ".json":
                raw_obj = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw_obj, dict) and "is_test" in raw_obj:
                    is_test = bool(raw_obj["is_test"])
            items.append(
                DatasetItemDto(
                    filename=path.name,
                    koc_count=len(cands),
                    is_test=is_test,
                    size_bytes=path.stat().st_size,
                    sample_handles=[f"@{c.handle}" for c in cands[:5]],
                )
            )
        except Exception:
            continue
    return items


@app.post("/api/datasets/upload", response_model=DatasetItemDto)
async def upload_dataset(file: UploadFile = File(...)) -> DatasetItemDto:
    """Tải lên file dữ liệu Kalodata (.json, .csv, .xlsx, .har) kèm kiểm tra kích thước & đường dẫn."""
    ensure_directories()
    orig_name = Path(file.filename or "kalodata_upload.json").name
    suffix = Path(orig_name).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        raise HTTPException(
            status_code=400,
            detail="Định dạng file không hợp lệ. Chỉ chấp nhận .json, .csv, .xlsx hoặc .har.",
        )

    stem_safe = sanitize_safe_id(Path(orig_name).stem, fallback="kalodata_upload")
    dest_path = ensure_within_directory(SNAPSHOTS_DIR, SNAPSHOTS_DIR / f"{stem_safe}{suffix}")

    raw_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Kích thước file vượt quá giới hạn 10MB.")

    dest_path.write_bytes(raw_bytes)
    try:
        cands = load_kalodata_candidates(dest_path, max_candidates=1_000)
    except Exception as exc:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Không thể đọc dữ liệu KOC từ file: {exc}") from exc

    if not cands:
        dest_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=400,
            detail="Không tìm thấy bản ghi KOC hợp lệ nào trong file vừa tải lên.",
        )

    return DatasetItemDto(
        filename=dest_path.name,
        koc_count=len(cands),
        is_test=False,
        size_bytes=len(raw_bytes),
        sample_handles=[f"@{c.handle}" for c in cands[:5]],
    )


def _run_pipeline_worker(
    *,
    job_id: str,
    input_file: Path,
    brief: CampaignBrief,
    settings: Settings,
    resume: bool,
    dry_run: bool,
    simulate_crash_after_kocs: Optional[int],
) -> None:
    """Luồng nền thực thi pipeline và giải phóng khóa job khi hoàn tất hoặc dừng."""
    try:
        execute_discovery_pipeline(
            input_file=input_file,
            brief=brief,
            settings=settings,
            job_id=job_id,
            resume=resume,
            dry_run=dry_run,
            simulate_crash_after_kocs=simulate_crash_after_kocs,
        )
    except Exception:
        # Trạng thái INTERRUPTED / FAILED đã được JobLogger ghi đầy đủ vào status.json & log.txt
        pass
    finally:
        with _ACTIVE_JOBS_LOCK:
            _ACTIVE_JOBS.discard(job_id)


@app.post("/api/jobs", status_code=202)
def create_discovery_job(dto: CreateJobDto) -> Dict[str, Any]:
    """Khởi chạy một phiên nghiên cứu KOC mới trên luồng nền và trả về mã job_id ngay lập tức."""
    ensure_directories()
    settings = _build_effective_settings()
    configured, _ = _mask_key_status(settings.gemini_api_key)
    if not dto.dry_run and not configured:
        raise HTTPException(
            status_code=400,
            detail="Chưa cấu hình GEMINI_API_KEY để chạy chế độ Live. Vui lòng nhập khóa Gemini hoặc bật chế độ Dry-Run.",
        )

    try:
        safe_ds_name = Path(dto.dataset_filename).name
        if ".." in dto.dataset_filename or "/" in dto.dataset_filename or "\\" in dto.dataset_filename:
            raise SecurityViolationError("Tên file dataset không hợp lệ.")
        input_path = ensure_within_directory(SNAPSHOTS_DIR, SNAPSHOTS_DIR / safe_ds_name)
    except SecurityViolationError as sec_err:
        raise HTTPException(status_code=400, detail=str(sec_err)) from sec_err

    if not input_path.exists():
        if safe_ds_name == "fixture_sunscreen_pool_32.json":
            generate_test_fixture(input_path)
        else:
            raise HTTPException(status_code=404, detail=f"Không tìm thấy tập dữ liệu: {safe_ds_name}")

    job_id = generate_secure_job_id("webjob")
    # Khởi tạo status.json đồng bộ trước khi trả HTTP 202 để Client poll tức thì không bị 404
    JobLogger(job_id=job_id, resume=False)

    brief = CampaignBrief(
        brand_category=dto.brand_category,
        product_name=dto.product_name,
        target_audience=dto.target_audience,
        total_budget_vnd=dto.total_budget_vnd,
        target_koc_count=dto.target_koc_count,
        raw_brief_text=dto.raw_brief_text,
    )

    with _ACTIVE_JOBS_LOCK:
        _ACTIVE_JOBS.add(job_id)

    worker = threading.Thread(
        target=_run_pipeline_worker,
        kwargs={
            "job_id": job_id,
            "input_file": input_path,
            "brief": brief,
            "settings": settings,
            "resume": False,
            "dry_run": dto.dry_run,
            "simulate_crash_after_kocs": dto.simulate_crash_after_kocs,
        },
        daemon=True,
    )
    worker.start()

    return {
        "job_id": job_id,
        "status": "RUNNING",
        "message": "Đã khởi chạy tiến trình nghiên cứu KOC.",
    }


@app.post("/api/jobs/{job_id}/resume", status_code=202)
def resume_discovery_job(job_id: str, dto: ResumeJobDto) -> Dict[str, Any]:
    """Khôi phục phiên chạy bị ngắt (INTERRUPTED / FAILED) tiếp tục từ SQLite checkpoint."""
    try:
        safe_id = sanitize_safe_id(job_id)
        job_dir = ensure_within_directory(JOBS_DIR, JOBS_DIR / safe_id)
    except SecurityViolationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not job_dir.exists() or not (job_dir / "status.json").exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên làm việc cần khôi phục.")

    with _ACTIVE_JOBS_LOCK:
        if safe_id in _ACTIVE_JOBS:
            raise HTTPException(status_code=409, detail="Phiên làm việc này đang chạy.")
        _ACTIVE_JOBS.add(safe_id)

    settings = _build_effective_settings()
    default_fixture = SNAPSHOTS_DIR / "fixture_sunscreen_pool_32.json"
    if not default_fixture.exists():
        generate_test_fixture(default_fixture)

    worker = threading.Thread(
        target=_run_pipeline_worker,
        kwargs={
            "job_id": safe_id,
            "input_file": default_fixture,
            "brief": CampaignBrief(),
            "settings": settings,
            "resume": True,
            "dry_run": bool(dto.dry_run) if dto.dry_run is not None else True,
            "simulate_crash_after_kocs": None,
        },
        daemon=True,
    )
    worker.start()
    return {
        "job_id": safe_id,
        "status": "RUNNING",
        "message": f"Đang khôi phục phiên {safe_id} từ checkpoint đã lưu.",
    }


@app.get("/api/jobs")
def list_jobs(limit: int = Query(default=20, ge=1, le=50)) -> List[Dict[str, Any]]:
    """Lấy danh sách lịch sử các phiên chạy gần nhất (giới hạn phân trang <= 50 theo API4:2023)."""
    ensure_directories()
    summaries: List[Dict[str, Any]] = []
    job_dirs = [p for p in JOBS_DIR.iterdir() if p.is_dir() and (p / "status.json").exists()]
    job_dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    for jdir in job_dirs[:limit]:
        try:
            st = json.loads((jdir / "status.json").read_text(encoding="utf-8"))
            product_name = ""
            selected_count = 0
            mode = "dry_run"
            res_path = jdir / "result.json"
            if res_path.exists():
                res = json.loads(res_path.read_text(encoding="utf-8"))
                product_name = res.get("campaign_brief", {}).get("product_name", "")
                selected_count = len(res.get("portfolio_recommendation", {}).get("selected_kocs", []))
                mode = res.get("mode", mode)
            summaries.append(
                {
                    "job_id": st.get("job_id", jdir.name),
                    "status": st.get("status", "UNKNOWN"),
                    "current_stage": st.get("current_stage", ""),
                    "updated_at": st.get("updated_at", ""),
                    "resumed_count": st.get("resumed_count", 0),
                    "product_name": product_name or "Kem chống nắng",
                    "selected_count": selected_count,
                    "mode": mode,
                    "total_cost_usd": st.get("metrics_so_far", {}).get("total_cost_usd", 0.0),
                    "llm_calls_count": st.get("metrics_so_far", {}).get("llm_calls_count", 0),
                }
            )
        except Exception:
            continue
    return summaries


@app.get("/api/jobs/{job_id}")
def get_job_detail(job_id: str) -> Dict[str, Any]:
    """Lấy chi tiết tiến độ realtime, log gần nhất, danh sách LLM calls và kết quả đề xuất KOC."""
    try:
        safe_id = sanitize_safe_id(job_id)
        job_dir = ensure_within_directory(JOBS_DIR, JOBS_DIR / safe_id)
    except SecurityViolationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    status_file = job_dir / "status.json"
    if not status_file.exists():
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên làm việc.")

    status_data = json.loads(status_file.read_text(encoding="utf-8"))

    llm_calls: List[Dict[str, Any]] = []
    llm_file = job_dir / "llm_calls.json"
    if llm_file.exists():
        try:
            raw_calls = json.loads(llm_file.read_text(encoding="utf-8"))
            if isinstance(raw_calls, list):
                llm_calls = raw_calls[-100:]
        except Exception:
            llm_calls = []

    log_lines: List[str] = []
    log_file = job_dir / "log.txt"
    if log_file.exists():
        try:
            log_lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()[-80:]
        except Exception:
            log_lines = []

    result_data: Optional[Dict[str, Any]] = None
    result_file = job_dir / "result.json"
    if result_file.exists():
        try:
            result_data = json.loads(result_file.read_text(encoding="utf-8"))
            # Ánh xạ đường dẫn ảnh Contact Sheet sang URL tĩnh an toàn của API
            for dossier in result_data.get("finalist_dossiers", []):
                for vid in dossier.get("candidate", {}).get("recent_videos", []):
                    sheet_p = vid.get("contact_sheet_path", "")
                    if sheet_p:
                        img_name = Path(sheet_p).name
                        if (job_dir / "assets" / img_name).exists():
                            vid["contact_sheet_url"] = f"/api/jobs/{safe_id}/assets/{img_name}"
        except Exception:
            result_data = None

    return {
        "status": status_data,
        "llm_calls": llm_calls,
        "recent_logs": log_lines,
        "result": result_data,
    }


@app.get("/api/jobs/{job_id}/assets/{asset_name}")
def get_job_asset(job_id: str, asset_name: str) -> FileResponse:
    """Phục vụ ảnh JPEG Contact Sheet 3x3 của job sau khi kiểm định chống Path Traversal."""
    try:
        safe_id = sanitize_safe_id(job_id)
        safe_asset = sanitize_safe_id(asset_name)
        assets_dir = ensure_within_directory(JOBS_DIR, JOBS_DIR / safe_id / "assets")
        asset_path = ensure_within_directory(assets_dir, assets_dir / safe_asset)
    except SecurityViolationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not asset_path.exists() or asset_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh minh chứng.")

    return FileResponse(str(asset_path), media_type="image/jpeg")
