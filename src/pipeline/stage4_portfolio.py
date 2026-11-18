"""Stage 4: Tối ưu hóa Danh mục đề xuất KOC (Portfolio Optimization) trong trần ngân sách."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from src.config import Settings
from src.core.checkpoint import CheckpointStore
from src.core.job_logger import JobLogger
from src.core.llm_gateway import GeminiGateway
from src.models.schemas import (
    CampaignBrief,
    KocFinalistDossier,
    PortfolioRecommendation,
    RecommendedKocCard,
    SearchSpec,
)


STAGE4_SYSTEM_PROMPT = """Bạn là Head of Influencer Marketing tại Việt Nam phụ trách tối ưu ngân sách chuyển đổi.
Nhiệm vụ: Từ hồ sơ chi tiết của các ứng viên vòng chung kết (bao gồm chỉ số Kalodata, định giá booking ước tính và bằng chứng phân tích khung hình Video AI [mm:ss]), hãy chọn ra ĐÚNG số lượng KOC mục tiêu tạo thành một DANH MỤC ĐA DẠNG VAI TRÒ và KHÔNG VƯỢT TỔNG NGÂN SÁCH.

Yêu cầu bắt buộc:
1. Tổng `allocated_budget_vnd` của các KOC được chọn CỘNG VỚI `reserve_seeding_budget_vnd` phải <= tổng ngân sách chiến dịch.
2. Mỗi KOC được chọn phải trích dẫn BẰNG CHỨNG CỤ THỂ:
   - `performance_evidence`: dẫn chứng con số thực tế (Followers, Doanh thu 30 ngày, Tỷ trọng doanh thu video, GPM, Views/ER).
   - `visual_and_video_evidence`: dẫn chứng trực tiếp mốc thời gian [mm:ss] từ Contact Sheet và câu nói/nội dung thực tế trong video đã phân tích.
3. Giải thích rõ vì sao KOC đó thuyết phục được tệp khách hàng mục tiêu và gợi ý góc kịch bản quay cụ thể."""


def _dossier_to_prompt_payload(d: KocFinalistDossier) -> Dict[str, Any]:
    """Tạo bản tóm tắt giàu bằng chứng của mỗi finalist để đưa vào Stage 4."""
    c = d.candidate
    return {
        "koc_id": c.koc_id,
        "handle": f"@{c.handle}",
        "display_name": c.display_name,
        "followers": c.followers,
        "revenue_30d_vnd": c.revenue_30d_vnd,
        "video_revenue_30d_vnd": c.video_revenue_30d_vnd,
        "video_revenue_share_pct": round(d.stage1.video_revenue_share * 100, 1),
        "gpm_vnd": c.gpm_vnd,
        "avg_video_views": c.avg_video_views,
        "engagement_rate_pct": round(c.engagement_rate * 100, 2),
        "estimated_booking_vnd": d.stage1.estimated_booking_vnd,
        "composite_score": d.composite_pre_portfolio_score,
        "suggested_role": d.stage2.suggested_role,
        "audience_match_reason": d.stage2.audience_match_reason,
        "video_evidences": [
            {
                "video_id": ev.video_id,
                "video_url": ev.video_url,
                "scores": {
                    "visual": ev.visual_quality_score,
                    "persuasion": ev.content_persuasion_score,
                    "sunscreen_fit": ev.sunscreen_relevance_score,
                },
                "keyframe_observations": ev.keyframe_observations,
                "transcript_quotes": ev.transcript_quotes,
                "authenticity_signals": ev.authenticity_signals,
            }
            for ev in d.video_evidences
        ],
    }


def _select_budget_safe_subset(
    dossiers: List[KocFinalistDossier],
    target_count: int,
    total_budget_vnd: int,
) -> List[KocFinalistDossier]:
    """Chọn tổ hợp KOC điểm cao nhất mà tổng phí ước tính nằm gọn trong ngân sách (fallback & kiểm chứng)."""
    chosen: List[KocFinalistDossier] = []
    running_sum = 0
    # Chừa tối thiểu 5% cho chi phí gửi mẫu sản phẩm (seeding)
    usable_cap = int(total_budget_vnd * 0.95)

    for idx, d in enumerate(dossiers):
        remaining_slots = target_count - len(chosen) - 1
        min_needed_for_rest = remaining_slots * 2_000_000
        fee = d.stage1.estimated_booking_vnd
        if running_sum + fee + min_needed_for_rest <= usable_cap or len(dossiers) - idx <= remaining_slots + 1:
            chosen.append(d)
            running_sum += fee
        if len(chosen) == target_count:
            break

    if len(chosen) < min(target_count, len(dossiers)):
        for d in dossiers:
            if d not in chosen:
                chosen.append(d)
            if len(chosen) == target_count:
                break
    return chosen


def run_stage4_portfolio_synthesis(
    dossiers: List[KocFinalistDossier],
    brief: CampaignBrief,
    spec: SearchSpec,
    settings: Settings,
    gateway: GeminiGateway,
    checkpoint: CheckpointStore,
    job_logger: JobLogger,
) -> PortfolioRecommendation:
    """Tổng hợp và tối ưu hóa danh mục đề xuất cuối cùng (bật suy luận thinking_budget=1024)."""
    cached = checkpoint.load("stage4", "portfolio_recommendation")
    if cached:
        job_logger.info("[STAGE 4] Đã khôi phục PortfolioRecommendation từ checkpoint (0 token).")
        return PortfolioRecommendation.model_validate(cached)

    payloads = [_dossier_to_prompt_payload(d) for d in dossiers]
    user_prompt = (
        f"Đề bài chiến dịch:\n"
        f"- Ngành hàng: {brief.brand_category} | Sản phẩm: {brief.product_name}\n"
        f"- Khách hàng mục tiêu: {brief.target_audience}\n"
        f"- Tổng ngân sách tối đa: {brief.total_budget_vnd:,} VNĐ\n"
        f"- Số lượng KOC cần đề xuất: {brief.target_koc_count}\n"
        f"- Các vai trò danh mục cần phủ: {', '.join(spec.portfolio_roles)}\n\n"
        f"Hồ sơ đầy đủ của {len(payloads)} ứng viên vòng chung kết:\n"
        f"{json.dumps(payloads, ensure_ascii=False, indent=2)}\n\n"
        f"Hãy chọn ra đúng {min(brief.target_koc_count, len(payloads))} KOC tối ưu nhất và xuất PortfolioRecommendation."
    )

    def _mock_portfolio() -> PortfolioRecommendation:
        picked = _select_budget_safe_subset(dossiers, brief.target_koc_count, brief.total_budget_vnd)
        cards: List[RecommendedKocCard] = []
        total_alloc = 0
        for rank, d in enumerate(picked, start=1):
            c = d.candidate
            fee = d.stage1.estimated_booking_vnd
            total_alloc += fee
            vis_ev: List[str] = []
            for ev in d.video_evidences:
                vis_ev.extend(ev.keyframe_observations[:2])
                if ev.transcript_quotes:
                    vis_ev.append(f"Trích thoại ({ev.video_id}): \"{ev.transcript_quotes[0]}\"")
            cards.append(
                RecommendedKocCard(
                    rank=rank,
                    koc_id=c.koc_id,
                    handle=c.handle,
                    portfolio_role=d.stage2.suggested_role,
                    allocated_budget_vnd=fee,
                    final_match_score=d.composite_pre_portfolio_score,
                    why_selected=(
                        f"@{c.handle} sở hữu tệp người xem phù hợp {brief.target_audience}, "
                        f"chi phí booking ước tính {fee:,} VNĐ mang lại hiệu suất chuyển đổi video cao."
                    ),
                    performance_evidence=[
                        f"Followers: {c.followers:,} | Lượt xem TB: {c.avg_video_views:,} views/video (ER: {c.engagement_rate * 100:.2f}%)",
                        f"Doanh thu 30 ngày: {c.revenue_30d_vnd:,} VNĐ (Video chiếm {d.stage1.video_revenue_share * 100:.1f}%, GPM: {c.gpm_vnd:,} VNĐ)",
                    ],
                    visual_and_video_evidence=vis_ev or ["Video quay cận cảnh nền da rõ nét, thuyết trình tự nhiên."],
                    recommended_content_angle=(
                        "Quay video 35-45s: Hook 3s đầu soi da dưới nắng gắt, thoa đủ lượng 2 ngón tay kem chống nắng, "
                        "check lại lớp nền sau 6 tiếng ngoài trời và gắn giỏ hàng deal dùng thử."
                    ),
                    risks_or_notes="Gửi sản phẩm trước 5 ngày để KOC test độ hợp da thực tế trước khi lên kịch bản.",
                )
            )
        if total_alloc > brief.total_budget_vnd and total_alloc > 0:
            scale = (brief.total_budget_vnd * 0.93) / total_alloc
            total_alloc = 0
            for card in cards:
                card.allocated_budget_vnd = int(round((card.allocated_budget_vnd * scale) / 100_000.0) * 100_000)
                total_alloc += card.allocated_budget_vnd

        return PortfolioRecommendation(
            executive_summary=(
                f"Đề xuất danh mục {len(cards)} Micro/Nano-KOC chuyên sâu mảng Skincare & Makeup cho chiến dịch "
                f"{brief.product_name}, tối ưu hóa tổng chi phí booking {total_alloc:,} VNĐ / {brief.total_budget_vnd:,} VNĐ."
            ),
            total_allocated_budget_vnd=total_alloc,
            reserve_seeding_budget_vnd=max(0, brief.total_budget_vnd - total_alloc),
            portfolio_strategy_rationale=(
                "Phân bổ đa dạng vai trò từ phân tích thành phần chuyên sâu, kiểm chứng độ kiềm dầu thực tế đến "
                "lớp finish nâng tone đi học/đi làm nhằm bao phủ trọn hành trình ra quyết định của nữ 18-30 tuổi."
            ),
            selected_kocs=cards,
        )

    portfolio = gateway.generate_structured(
        stage="stage4_portfolio",
        purpose=f"Tổng hợp danh mục {brief.target_koc_count} KOC tối ưu ngân sách {brief.total_budget_vnd:,} VNĐ",
        model_name=settings.portfolio_model,
        system_instruction=STAGE4_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_schema=PortfolioRecommendation,
        thinking_budget=1024,
        max_output_tokens=4096,
        temperature=0.2,
        mock_builder=_mock_portfolio,
    )

    # Kiểm chứng cứng bằng code: Đảm bảo tổng ngân sách phân bổ không bao giờ vượt trần 30 triệu VNĐ
    calc_sum = sum(k.allocated_budget_vnd for k in portfolio.selected_kocs)
    if calc_sum > brief.total_budget_vnd and calc_sum > 0:
        ratio = (brief.total_budget_vnd * 0.94) / calc_sum
        for k in portfolio.selected_kocs:
            k.allocated_budget_vnd = int(round((k.allocated_budget_vnd * ratio) / 100_000.0) * 100_000)
        calc_sum = sum(k.allocated_budget_vnd for k in portfolio.selected_kocs)

    portfolio.total_allocated_budget_vnd = calc_sum
    portfolio.reserve_seeding_budget_vnd = max(0, brief.total_budget_vnd - calc_sum)

    checkpoint.save("stage4", "portfolio_recommendation", portfolio.model_dump())
    job_logger.info(
        f"[STAGE 4] Đã chốt {len(portfolio.selected_kocs)} KOC | Tổng booking: {portfolio.total_allocated_budget_vnd:,} VNĐ "
        f"| Dự phòng seeding: {portfolio.reserve_seeding_budget_vnd:,} VNĐ."
    )
    return portfolio
