"""Định nghĩa toàn bộ Pydantic Schemas xuyên suốt 5 tầng xử lý của pipeline."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CampaignBrief(BaseModel):
    """Đầu vào bài toán chiến dịch từ thương hiệu."""

    brand_category: str = Field(default="Mỹ phẩm Việt Nam", description="Ngành hàng thương hiệu")
    product_name: str = Field(default="Kem chống nắng", description="Sản phẩm cần quảng bá")
    target_audience: str = Field(default="Nữ, 18–30 tuổi", description="Chân dung khách hàng mục tiêu")
    total_budget_vnd: int = Field(default=30_000_000, description="Tổng ngân sách chiến dịch (VNĐ)")
    target_koc_count: int = Field(default=5, description="Số lượng KOC cần đề xuất")
    raw_brief_text: str = Field(default="", description="Mô tả bổ sung từ người dùng")


class SearchSpec(BaseModel):
    """Kết quả Stage 0: Chuyển đổi đề bài tự nhiên thành tiêu chí định lượng & rubric chấm điểm."""

    campaign_summary: str
    primary_keywords: List[str] = Field(description="Từ khóa nội dung chính (VD: kem chống nắng, kiềm dầu, nâng tone)")
    negative_keywords: List[str] = Field(description="Từ khóa loại trừ (VD: drama, cờ bạc, bán sỉ gia dụng)")
    min_followers: int = Field(description="Số follower tối thiểu phù hợp ngân sách")
    max_followers: int = Field(description="Số follower tối đa để không vượt ngân sách mỗi KOC")
    target_cost_per_koc_min_vnd: int = Field(description="Giá booking ước tính tối thiểu mỗi KOC (VNĐ)")
    target_cost_per_koc_max_vnd: int = Field(description="Giá booking ước tính tối đa mỗi KOC (VNĐ)")
    min_video_revenue_share: float = Field(
        default=0.25,
        description="Tỷ trọng doanh thu đến từ Video tối thiểu (0.0 - 1.0) để tránh kênh chỉ thuần Livestream",
    )
    visual_evaluation_criteria: List[str] = Field(
        description="Các tiêu chí kiểm tra hình ảnh/video ở Stage 3"
    )
    portfolio_roles: List[str] = Field(
        description="Các vai trò KOC cần phân bổ đa dạng trong danh mục đề xuất"
    )


class TikTokVideoMeta(BaseModel):
    """Thông tin metadata và nội dung trích xuất của 1 video TikTok."""

    video_id: str
    url: str
    title: str = ""
    description: str = ""
    duration_sec: float = 0.0
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    published_at: str = ""
    hashtags: List[str] = Field(default_factory=list)
    transcript_text: str = ""
    transcript_source: str = "none"  # tiktok_cc | caption_fallback | mock
    contact_sheet_path: str = ""


class KocCandidate(BaseModel):
    """Hồ sơ KOC chuẩn hóa từ Kalodata kết hợp làm giàu từ TikTok."""

    koc_id: str = Field(description="Định danh duy nhất (ưu tiên TikTok handle viết thường không @)")
    handle: str = Field(description="TikTok handle không bao gồm ký tự @")
    display_name: str = ""
    profile_url: str = ""
    category: str = "Beauty & Personal Care"
    bio: str = ""
    followers: int = 0
    revenue_30d_vnd: int = 0
    video_revenue_30d_vnd: int = 0
    live_revenue_30d_vnd: int = 0
    items_sold_30d: int = 0
    avg_video_views: int = 0
    engagement_rate: float = 0.0  # Dạng thập phân, ví dụ 0.048 = 4.8%
    gpm_vnd: int = 0  # Gross Merchandise Value per 1,000 views (VNĐ)
    active_videos_30d: int = 0
    female_audience_ratio: Optional[float] = None  # Nếu Kalodata có tỉ lệ khán giả nữ (0.0 - 1.0)
    age_18_30_ratio: Optional[float] = None  # Nếu có tỉ lệ độ tuổi 18-30
    top_product_keywords: List[str] = Field(default_factory=list)
    estimated_booking_cost_vnd: int = 0  # Giá booking 1 video ước tính (nếu chưa có sẽ tự nội suy ở Stage 1)
    recent_videos: List[TikTokVideoMeta] = Field(default_factory=list)
    raw_extra: Dict[str, Any] = Field(default_factory=dict)


class Stage1Score(BaseModel):
    """Kết quả chấm điểm toán học 0-token ở Stage 1."""

    koc_id: str
    passed: bool
    reject_reason: str = ""
    estimated_booking_vnd: int
    video_revenue_share: float
    quantitative_score: float = Field(description="Điểm tổng hợp định lượng thang 0-100")
    score_breakdown: Dict[str, float] = Field(default_factory=dict)


class Stage2ItemScore(BaseModel):
    """Đánh giá ngữ nghĩa của 1 KOC trong batch ở Stage 2."""

    koc_id: str
    semantic_fit_score: float = Field(description="Điểm phù hợp ngách sản phẩm & tệp Nữ 18-30 (0-100)")
    audience_match_reason: str = Field(description="Giải thích ngắn gọn mức độ khớp khách hàng Nữ 18-30")
    suggested_role: str = Field(description="Vai trò gợi ý (VD: Skincare Ingredient Reviewer, Daily Finish Creator...)")
    brand_safety_pass: bool = True
    shortlist_recommended: bool = True


class Stage2BatchResponse(BaseModel):
    """Schema đầu ra có cấu trúc cho 1 lời gọi batch ở Stage 2."""

    evaluations: List[Stage2ItemScore]


class VideoEvidenceItem(BaseModel):
    """Bằng chứng cụ thể trích xuất từ 1 video bằng Multimodal AI ở Stage 3."""

    video_id: str
    video_url: str
    visual_quality_score: float = Field(description="Chất lượng hình ảnh, ánh sáng, cận cảnh làn da (0-100)")
    content_persuasion_score: float = Field(description="Độ thuyết phục của hook, demo chất kem, CTA (0-100)")
    sunscreen_relevance_score: float = Field(description="Mức độ phù hợp để review kem chống nắng (0-100)")
    keyframe_observations: List[str] = Field(
        description="Các quan sát trực quan gắn kèm mốc [mm:ss] nhìn thấy trên Contact Sheet"
    )
    transcript_quotes: List[str] = Field(
        description="Trích dẫn câu nói/hook đắt giá từ phụ đề hoặc caption"
    )
    authenticity_signals: str = Field(description="Nhận xét độ chân thật (da thật, test thật hay quảng cáo công nghiệp)")


class KocFinalistDossier(BaseModel):
    """Hồ sơ tổng hợp đầy đủ của 1 Finalist sau Stage 3 để đưa vào Stage 4."""

    candidate: KocCandidate
    stage1: Stage1Score
    stage2: Stage2ItemScore
    video_evidences: List[VideoEvidenceItem] = Field(default_factory=list)
    composite_pre_portfolio_score: float = 0.0


class RecommendedKocCard(BaseModel):
    """Một KOC nằm trong Top đề xuất cuối cùng kèm lý do và bằng chứng."""

    rank: int
    koc_id: str
    handle: str
    portfolio_role: str
    allocated_budget_vnd: int = Field(description="Ngân sách đề xuất phân bổ cho KOC này (VNĐ)")
    final_match_score: float = Field(description="Điểm phù hợp tổng thể (0-100)")
    why_selected: str = Field(description="Lý do đề xuất gắn với mục tiêu thương hiệu & tệp Nữ 18-30")
    performance_evidence: List[str] = Field(description="Bằng chứng số liệu Kalodata & tương tác TikTok")
    visual_and_video_evidence: List[str] = Field(
        description="Bằng chứng cụ thể từ phân tích hình ảnh Contact Sheet [mm:ss] và lời thoại video"
    )
    recommended_content_angle: str = Field(description="Kịch bản/góc độ nội dung đề xuất khi booking kem chống nắng")
    risks_or_notes: str = Field(description="Lưu ý nhỏ khi hợp tác để tối ưu chuyển đổi")


class PortfolioRecommendation(BaseModel):
    """Kết quả đầu ra của Stage 4: Tổ hợp KOC tối ưu trong ngân sách."""

    executive_summary: str
    total_allocated_budget_vnd: int
    reserve_seeding_budget_vnd: int
    portfolio_strategy_rationale: str
    selected_kocs: List[RecommendedKocCard]
