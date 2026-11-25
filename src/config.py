"""Cấu hình trung tâm cho hệ thống DETOLA AI KOC Discovery."""

from __future__ import annotations

from pathlib import Path
from typing import Dict
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
MEDIA_CACHE_DIR = DATA_DIR / "media_cache"
VIDEOS_CACHE_DIR = MEDIA_CACHE_DIR / "videos"
SHEETS_CACHE_DIR = MEDIA_CACHE_DIR / "contact_sheets"
SUBS_CACHE_DIR = MEDIA_CACHE_DIR / "subtitles"
JOBS_DIR = ROOT_DIR / "jobs"
GLOBAL_CACHE_DIR = ROOT_DIR / "cache"


class ModelPrice(BaseModel):
    """Đơn giá USD cho mỗi 1 triệu token trên Google AI Developer API."""

    input_per_1m: float
    cached_input_per_1m: float
    output_per_1m: float  # Bao gồm cả output tokens và thinking tokens


# Bảng giá tham chiếu chính thức của Gemini API (USD / 1M tokens)
GEMINI_PRICING_USD_PER_1M: Dict[str, ModelPrice] = {
    "gemini-3.5-flash-lite": ModelPrice(
        input_per_1m=0.30,
        cached_input_per_1m=0.03,
        output_per_1m=2.50,
    ),
    "gemini-3.8-flash": ModelPrice(
        input_per_1m=0.75,
        cached_input_per_1m=0.075,
        output_per_1m=3.75,
    ),
    "gemini-2.5-flash-lite": ModelPrice(
        input_per_1m=0.10,
        cached_input_per_1m=0.01,
        output_per_1m=0.40,
    ),
    "gemini-2.5-flash": ModelPrice(
        input_per_1m=0.30,
        cached_input_per_1m=0.03,
        output_per_1m=2.50,
    ),
    "gemini-2.5-pro": ModelPrice(
        input_per_1m=1.25,
        cached_input_per_1m=0.125,
        output_per_1m=10.00,
    ),
}


class Settings(BaseSettings):
    """Cấu hình đọc từ biến môi trường hoặc file .env."""

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_use_vertexai: bool = Field(default=False, alias="GEMINI_USE_VERTEXAI")
    kalodata_api_key: str = Field(default="", alias="KALODATA_API_KEY")
    kalodata_base_url: str = Field(
        default="https://www.kalodata.com/openapi/v1",
        alias="KALODATA_BASE_URL",
    )
    kalodata_region: str = Field(default="VN", alias="KALODATA_REGION")
    kalodata_language: str = Field(default="vi-VN", alias="KALODATA_LANGUAGE")
    kalodata_currency: str = Field(default="VND", alias="KALODATA_CURRENCY")
    kalodata_use_video_url_fallback: bool = Field(
        default=False,
        alias="KALODATA_USE_VIDEO_URL_FALLBACK",
    )

    triage_model: str = Field(default="gemini-3.5-flash-lite", alias="GEMINI_TRIAGE_MODEL")
    multimodal_model: str = Field(default="gemini-3.5-flash-lite", alias="GEMINI_MULTIMODAL_MODEL")
    portfolio_model: str = Field(default="gemini-3.5-flash-lite", alias="GEMINI_PORTFOLIO_MODEL")

    usd_to_vnd_rate: float = Field(default=25500.0, alias="USD_TO_VND_RATE")
    max_llm_concurrency: int = Field(default=4, alias="MAX_LLM_CONCURRENCY")
    max_media_concurrency: int = Field(default=2, alias="MAX_MEDIA_CONCURRENCY")

    # Ràng buộc bảo vệ tài nguyên theo chuẩn OWASP API4:2023 & LLM04:2025 (Denial of Wallet)
    llm_timeout_ms: int = Field(default=45_000, alias="LLM_TIMEOUT_MS")
    max_job_cost_usd: float = Field(default=0.50, alias="MAX_JOB_COST_USD")
    max_candidates_per_job: int = Field(default=1_000, alias="MAX_CANDIDATES_PER_JOB")

    # Cấu hình phễu mặc định (tỉ lệ thu hẹp ở từng tầng)
    stage1_pass_multiplier: int = 8  # Lấy gấp 8 lần target_koc_count sau lọc cứng 0-token
    stage2_batch_size: int = 10  # Gom 10 KOC trong 1 lần gọi Gemini Flash-Lite
    stage2_pass_multiplier: float = 2.4  # Giữ gấp ~2.4 lần target_koc_count vào vòng phân tích Video AI
    videos_per_finalist: int = 2  # Phân tích tối đa 2 video tiêu biểu cho mỗi finalist


def ensure_directories() -> None:
    """Đảm bảo toàn bộ thư mục dữ liệu, cache và jobs tồn tại."""
    for directory in (
        SNAPSHOTS_DIR,
        VIDEOS_CACHE_DIR,
        SHEETS_CACHE_DIR,
        SUBS_CACHE_DIR,
        JOBS_DIR,
        GLOBAL_CACHE_DIR,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def calculate_call_cost_usd(
    model_name: str,
    prompt_tokens: int,
    cached_tokens: int,
    output_tokens: int,
    thinking_tokens: int = 0,
) -> float:
    """Tính chi phí USD chính xác của 1 lời gọi Gemini dựa trên usage metadata."""
    price = GEMINI_PRICING_USD_PER_1M.get(
        model_name,
        GEMINI_PRICING_USD_PER_1M["gemini-2.5-flash"],
    )
    non_cached_input = max(0, prompt_tokens - cached_tokens)
    billable_output = max(0, output_tokens) + max(0, thinking_tokens)
    cost = (
        (non_cached_input / 1_000_000.0) * price.input_per_1m
        + (max(0, cached_tokens) / 1_000_000.0) * price.cached_input_per_1m
        + (billable_output / 1_000_000.0) * price.output_per_1m
    )
    return round(cost, 8)
