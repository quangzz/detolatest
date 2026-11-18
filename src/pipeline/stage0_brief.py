"""Stage 0: Phân tích đề bài chiến dịch và chuyển đổi thành tiêu chí định lượng (SearchSpec)."""

from __future__ import annotations

from src.config import Settings
from src.core.checkpoint import CheckpointStore
from src.core.job_logger import JobLogger
from src.core.llm_gateway import GeminiGateway
from src.models.schemas import CampaignBrief, SearchSpec


STAGE0_SYSTEM_PROMPT = """Bạn là Principal E-commerce & Influencer Strategist tại thị trường TikTok Shop Việt Nam.
Nhiệm vụ: Chuyển đổi đề bài tìm kiếm KOC của nhãn hàng thành bộ tiêu chí lọc định lượng (SearchSpec) sát thực tế thị trường Việt Nam.
Nguyên tắc quan trọng:
1. Tổng ngân sách phải chia cho số lượng KOC mục tiêu và chừa khoảng 5-10% dự phòng seeding/vận chuyển.
2. Với mức 4-7 triệu VNĐ/KOC tại Việt Nam, nhóm phù hợp nhất là Nano/Micro-KOC (khoảng 12,000 - 180,000 followers), tránh Mega KOL quá đắt.
3. Ưu tiên KOC có tỷ trọng doanh thu từ Video tốt (>= 25%) để đảm bảo kỹ năng làm clip review chuyển đổi."""


def run_stage0_brief_parser(
    brief: CampaignBrief,
    settings: Settings,
    gateway: GeminiGateway,
    checkpoint: CheckpointStore,
    job_logger: JobLogger,
) -> SearchSpec:
    """Thực thi Stage 0 hoặc khôi phục từ checkpoint nếu đã chạy trước đó."""
    cached = checkpoint.load("stage0", "search_spec")
    if cached:
        job_logger.info("[STAGE 0] Đã khôi phục SearchSpec từ checkpoint (0 token).")
        return SearchSpec.model_validate(cached)

    avg_budget = max(1_000_000, brief.total_budget_vnd // max(1, brief.target_koc_count))
    user_prompt = (
        f"Ngành hàng: {brief.brand_category}\n"
        f"Sản phẩm: {brief.product_name}\n"
        f"Khách hàng mục tiêu: {brief.target_audience}\n"
        f"Tổng ngân sách: {brief.total_budget_vnd:,} VNĐ cho {brief.target_koc_count} KOC "
        f"(trung bình ~{avg_budget:,} VNĐ/KOC).\n"
        f"Ghi chú thêm: {brief.raw_brief_text or 'Cần bằng chứng hiệu suất, nội dung và phân tích video.'}\n"
        "Hãy sinh SearchSpec chuẩn xác."
    )

    def _mock_spec() -> SearchSpec:
        return SearchSpec(
            campaign_summary=(
                f"Chiến dịch tìm {brief.target_koc_count} Nano/Micro-KOC TikTok quảng bá {brief.product_name} "
                f"tệp {brief.target_audience} trong ngân sách {brief.total_budget_vnd:,} VNĐ."
            ),
            primary_keywords=[
                "kem chống nắng",
                "kcn",
                "spf50",
                "kiềm dầu",
                "nâng tone",
                "skincare",
                "da dầu mụn",
                "chống nắng",
                "lớp finish",
            ],
            negative_keywords=["cờ bạc", "drama", "bán sỉ gia dụng", "nhạc remix"],
            min_followers=10_000,
            max_followers=180_000,
            target_cost_per_koc_min_vnd=int(avg_budget * 0.50),
            target_cost_per_koc_max_vnd=int(avg_budget * 1.30),
            min_video_revenue_share=0.25,
            visual_evaluation_criteria=[
                "Quay cận cảnh làn da thật dưới ánh sáng rõ ràng, không dùng filter làm mờ quá đà",
                "Có thao tác swatch chất kem chống nắng, tán trên da và kiểm tra độ nâng tone/kiềm dầu",
                "Hook 3 giây đầu thu hút tệp nữ 18-30 tuổi (nêu đúng nỗi đau da dầu, vón cục, bí da)",
                "Phong thái chia sẻ tự nhiên, đáng tin cậy, có lời kêu gọi gắn giỏ hàng rõ ràng",
            ],
            portfolio_roles=[
                "Skincare & Ingredient Reviewer (Phân tích màng lọc, thành phần cho da nhạy cảm/dầu mụn)",
                "Daily Finish & Makeup Layering Creator (Test độ nâng tone, tiệp nền cho sinh viên/văn phòng)",
                "Real-Life Endurance Tester (Test kiềm dầu ngoài trời 6-8 tiếng)",
                "High-Conversion Affiliate Reviewer (Săn deal, so sánh giá/dung tích chốt đơn mạnh)",
            ],
        )

    spec = gateway.generate_structured(
        stage="stage0_brief",
        purpose="Chuyển đổi đề bài sang SearchSpec định lượng",
        model_name=settings.multimodal_model,
        system_instruction=STAGE0_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_schema=SearchSpec,
        thinking_budget=0,
        mock_builder=_mock_spec,
    )

    # Đảm bảo khung ngân sách mỗi KOC luôn hợp lý với toán học danh mục
    spec.target_cost_per_koc_min_vnd = max(1_500_000, min(spec.target_cost_per_koc_min_vnd, int(avg_budget * 0.75)))
    spec.target_cost_per_koc_max_vnd = max(int(avg_budget * 1.15), min(spec.target_cost_per_koc_max_vnd, int(avg_budget * 1.45)))

    checkpoint.save("stage0", "search_spec", spec.model_dump())
    job_logger.info(
        f"[STAGE 0] Hoàn tất SearchSpec: follower [{spec.min_followers:,} - {spec.max_followers:,}], "
        f"khung booking [{spec.target_cost_per_koc_min_vnd:,} - {spec.target_cost_per_koc_max_vnd:,} VNĐ]."
    )
    return spec
