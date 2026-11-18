"""Stage 1: Lọc cứng & Chấm điểm hiệu suất định lượng (0 LLM Tokens)."""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

from src.core.checkpoint import CheckpointStore
from src.core.job_logger import JobLogger
from src.models.schemas import KocCandidate, SearchSpec, Stage1Score


# Danh sách từ khóa ngành hàng không phù hợp với mỹ phẩm
_IRRELEVANT_CATEGORIES = {
    "automotive",
    "xe cộ",
    "gaming",
    "điện tử",
    "computer",
    "hardware",
    "thú cưng",
    "pet",
    "xây dựng",
}


def estimate_vietnam_koc_booking_vnd(candidate: KocCandidate) -> int:
    """Ước tính chi phí booking 1 video TikTok tại Việt Nam nếu dữ liệu gốc chưa có báo giá."""
    if candidate.estimated_booking_cost_vnd > 0:
        return candidate.estimated_booking_cost_vnd

    # Công thức nội suy thực tế thị trường Beauty KOC Việt Nam (Nano/Micro -> Macro)
    avg_views = candidate.avg_video_views
    if avg_views <= 0 and candidate.recent_videos:
        avg_views = int(sum(v.views for v in candidate.recent_videos) / len(candidate.recent_videos))
    if avg_views <= 0:
        avg_views = int(candidate.followers * 0.35)

    base_fee = 900_000 + (candidate.followers * 26) + (avg_views * 28)
    gmv_premium = min(2_800_000, int(candidate.video_revenue_30d_vnd * 0.01))
    raw_total = base_fee + gmv_premium
    # Làm tròn đến bậc 100,000 VNĐ
    rounded = int(round(raw_total / 100_000.0) * 100_000)
    return max(1_200_000, rounded)


def score_single_candidate_zero_token(
    candidate: KocCandidate,
    spec: SearchSpec,
) -> Stage1Score:
    """Chấm điểm 1 KOC thuần toán học (0 token) và kiểm tra điều kiện loại sớm."""
    est_cost = estimate_vietnam_koc_booking_vnd(candidate)
    candidate.estimated_booking_cost_vnd = est_cost

    total_rev = max(0, candidate.revenue_30d_vnd)
    video_rev = max(0, candidate.video_revenue_30d_vnd)
    video_share = (video_rev / total_rev) if total_rev > 0 else 0.65

    cat_lower = candidate.category.lower()
    if any(bad in cat_lower for bad in _IRRELEVANT_CATEGORIES):
        return Stage1Score(
            koc_id=candidate.koc_id,
            passed=False,
            reject_reason=f"Ngành hàng lệch tệp ({candidate.category})",
            estimated_booking_vnd=est_cost,
            video_revenue_share=round(video_share, 3),
            quantitative_score=0.0,
        )

    max_allowed_cost = int(spec.target_cost_per_koc_max_vnd * 1.25)
    if est_cost > max_allowed_cost:
        return Stage1Score(
            koc_id=candidate.koc_id,
            passed=False,
            reject_reason=f"Vượt trần ngân sách cho phép ({est_cost:,} VNĐ > {max_allowed_cost:,} VNĐ)",
            estimated_booking_vnd=est_cost,
            video_revenue_share=round(video_share, 3),
            quantitative_score=0.0,
        )

    min_allowed_followers = max(3_000, int(spec.min_followers * 0.5))
    if 0 < candidate.followers < min_allowed_followers:
        return Stage1Score(
            koc_id=candidate.koc_id,
            passed=False,
            reject_reason=f"Lượng người theo dõi quá nhỏ ({candidate.followers:,} < {min_allowed_followers:,})",
            estimated_booking_vnd=est_cost,
            video_revenue_share=round(video_share, 3),
            quantitative_score=0.0,
        )

    if total_rev > 10_000_000 and video_share < spec.min_video_revenue_share:
        return Stage1Score(
            koc_id=candidate.koc_id,
            passed=False,
            reject_reason=(
                f"Kênh thiên lệch Livestream, tỷ trọng doanh thu Video thấp "
                f"({video_share * 100:.1f}% < {spec.min_video_revenue_share * 100:.0f}%)"
            ),
            estimated_booking_vnd=est_cost,
            video_revenue_share=round(video_share, 3),
            quantitative_score=0.0,
        )

    # 1. Điểm sức mạnh chuyển đổi Video (0 - 30): log-scale doanh thu video + GPM
    rev_millions = max(1.0, video_rev / 1_000_000.0)
    rev_points = min(22.0, math.log10(rev_millions + 1.0) * 9.5)
    gpm_points = min(8.0, (candidate.gpm_vnd / 180_000.0) * 8.0) if candidate.gpm_vnd > 0 else 4.0
    conversion_score = rev_points + gpm_points

    # 2. Điểm hiệu quả ROI trên mỗi triệu đồng chi phí booking (0 - 25)
    cost_millions = max(1.0, est_cost / 1_000_000.0)
    views_per_m = (candidate.avg_video_views or int(candidate.followers * 0.35)) / cost_millions
    gmv_per_m = (video_rev / 1_000_000.0) / cost_millions
    roi_score = min(13.0, (views_per_m / 9_000.0) * 13.0) + min(12.0, (gmv_per_m / 25.0) * 12.0)

    # 3. Điểm tương tác & tần suất đăng bài (0 - 20)
    er_pct = (candidate.engagement_rate * 100.0) if candidate.engagement_rate > 0 else 3.5
    er_points = min(13.0, (er_pct / 6.5) * 13.0)
    act_videos = candidate.active_videos_30d or max(3, len(candidate.recent_videos) * 3)
    activity_points = min(7.0, (act_videos / 15.0) * 7.0)
    engagement_score = er_points + activity_points

    # 4. Tín hiệu tệp khán giả Nữ 18-30 & khớp từ khóa sơ bộ (0 - 15)
    female_pts = (candidate.female_audience_ratio * 8.0) if candidate.female_audience_ratio is not None else 5.5
    age_pts = (candidate.age_18_30_ratio * 4.0) if candidate.age_18_30_ratio is not None else 2.8
    blob = " ".join(
        [candidate.bio, candidate.category, " ".join(candidate.top_product_keywords)]
        + [f"{v.title} {v.description}" for v in candidate.recent_videos[:3]]
    ).lower()
    kw_hits = sum(1 for kw in spec.primary_keywords if kw.lower() in blob)
    kw_pts = min(3.0, kw_hits * 1.0)
    audience_score = min(15.0, female_pts + age_pts + kw_pts)

    # 5. Độ khớp vùng ngân sách mục tiêu mỗi KOC (0 - 10)
    if spec.target_cost_per_koc_min_vnd <= est_cost <= spec.target_cost_per_koc_max_vnd:
        budget_fit_score = 10.0
    else:
        budget_fit_score = 6.5

    total_score = round(
        conversion_score + roi_score + engagement_score + audience_score + budget_fit_score,
        2,
    )
    return Stage1Score(
        koc_id=candidate.koc_id,
        passed=True,
        estimated_booking_vnd=est_cost,
        video_revenue_share=round(video_share, 3),
        quantitative_score=min(100.0, total_score),
        score_breakdown={
            "conversion_30": round(conversion_score, 2),
            "roi_efficiency_25": round(roi_score, 2),
            "engagement_activity_20": round(engagement_score, 2),
            "audience_keyword_15": round(audience_score, 2),
            "budget_fit_10": round(budget_fit_score, 2),
        },
    )


def run_stage1_hard_filter(
    candidates: List[KocCandidate],
    spec: SearchSpec,
    max_pass_count: int,
    checkpoint: CheckpointStore,
    job_logger: JobLogger,
) -> Tuple[List[KocCandidate], Dict[str, Stage1Score]]:
    """Chạy lọc cứng 0-token trên toàn bộ tập ứng viên và giữ lại nhóm điểm cao nhất."""
    scores_map: Dict[str, Stage1Score] = {}
    saved_map = checkpoint.load_stage_map("stage1")

    for cand in candidates:
        if cand.koc_id in saved_map:
            score_obj = Stage1Score.model_validate(saved_map[cand.koc_id])
            cand.estimated_booking_cost_vnd = score_obj.estimated_booking_vnd
            scores_map[cand.koc_id] = score_obj
        else:
            score_obj = score_single_candidate_zero_token(cand, spec)
            checkpoint.save("stage1", cand.koc_id, score_obj.model_dump())
            scores_map[cand.koc_id] = score_obj

    passed_candidates = [c for c in candidates if scores_map[c.koc_id].passed]
    passed_candidates.sort(key=lambda c: scores_map[c.koc_id].quantitative_score, reverse=True)
    shortlisted = passed_candidates[:max_pass_count]

    rejected_count = len(candidates) - len(passed_candidates)
    job_logger.info(
        f"[STAGE 1] Lọc 0-token hoàn tất: tổng={len(candidates)}, loại cứng={rejected_count}, "
        f"đạt chuẩn={len(passed_candidates)}, chuyển sang Stage 2={len(shortlisted)}."
    )
    return shortlisted, scores_map
