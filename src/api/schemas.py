"""Định nghĩa Class DTO độc lập cho REST API (chống Mass Assignment — API3:2023)."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ConfigureApiKeyDto(BaseModel):
    """DTO cập nhật khóa Gemini tạm thời trong bộ nhớ phiên chạy Backend."""

    model_config = ConfigDict(extra="forbid")

    api_key: str = Field(min_length=15, max_length=128, description="Khóa Google AI Studio Gemini API")


class CreateJobDto(BaseModel):
    """DTO khởi tạo phiên chạy nghiên cứu & đề xuất KOC."""

    model_config = ConfigDict(extra="forbid")

    dataset_filename: str = Field(
        default="fixture_sunscreen_pool_32.json",
        min_length=3,
        max_length=120,
    )
    brand_category: str = Field(default="Mỹ phẩm Việt Nam", min_length=2, max_length=120)
    product_name: str = Field(default="Kem chống nắng", min_length=2, max_length=120)
    target_audience: str = Field(default="Nữ, 18–30 tuổi", min_length=2, max_length=120)
    total_budget_vnd: int = Field(default=30_000_000, ge=3_000_000, le=5_000_000_000)
    target_koc_count: int = Field(default=5, ge=1, le=50)
    raw_brief_text: str = Field(default="", max_length=1000)
    dry_run: bool = Field(default=True)
    simulate_crash_after_kocs: Optional[int] = Field(default=None, ge=1, le=20)


class ResumeJobDto(BaseModel):
    """DTO khôi phục phiên chạy bị ngắt giữa chừng."""

    model_config = ConfigDict(extra="forbid")

    dry_run: Optional[bool] = Field(default=None)


class DatasetItemDto(BaseModel):
    """Thông tin tóm tắt 1 tập dữ liệu KOC trong thư mục snapshots."""

    filename: str
    koc_count: int
    is_test: bool
    size_bytes: int
    sample_handles: List[str]
