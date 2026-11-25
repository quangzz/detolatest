"""Bộ điều phối trung tâm (Orchestrator) quản lý luồng 5 tầng, đo thời gian, phục hồi lỗi và tính toán mở rộng."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Optional

from rich.console import Console

from src.config import Settings
from src.core.checkpoint import CheckpointStore, GlobalEntityCache
from src.core.job_logger import JobLogger
from src.core.llm_gateway import GeminiGateway
from src.ingestion.kalodata_loader import load_kalodata_candidates
from src.ingestion.kalodata_openapi_client import KalodataOpenApiClient
from src.ingestion.tiktok_enricher import TikTokEnricher
from src.models.schemas import CampaignBrief
from src.pipeline.stage0_brief import run_stage0_brief_parser
from src.pipeline.stage1_hard_filter import run_stage1_hard_filter
from src.pipeline.stage2_triage import run_stage2_batch_triage
from src.pipeline.stage3_video import SimulatedCrashError, run_stage3_video_analysis
from src.pipeline.stage4_portfolio import run_stage4_portfolio_synthesis
from src.reporting.report_builder import generate_all_reports


console = Console()


def compute_scaling_and_savings_projection(
    raw_pool_size: int,
    target_koc_count: int,
    actual_cost_usd: float,
    actual_elapsed_sec: float,
    usd_to_vnd_rate: float,
) -> Dict[str, Any]:
    """Tính toán mức tiết kiệm so với kiến trúc Naive (đẩy thẳng raw video cho mọi ứng viên) và ngoại suy 50-500 KOC."""
    # Kiến trúc Naive: Phân tích trực tiếp 2 video MP4 45 giây (~13,500 video tokens/video) cho toàn bộ ứng viên trong pool
    # với Gemini 2.5 Flash ($0.30/1M in, $2.50/1M out + ~800 output/thinking tokens mỗi KOC)
    naive_input_tokens_per_koc = 2 * 13_500 + 600
    naive_output_tokens_per_koc = 900
    naive_cost_per_koc_usd = (naive_input_tokens_per_koc / 1_000_000.0) * 0.30 + (
        naive_output_tokens_per_koc / 1_000_000.0
    ) * 2.50
    naive_total_for_current_pool_usd = round(raw_pool_size * naive_cost_per_koc_usd, 6)

    effective_actual = max(actual_cost_usd, 0.0001)
    cost_reduction_pct = (
        round((1.0 - (effective_actual / naive_total_for_current_pool_usd)) * 100.0, 2)
        if naive_total_for_current_pool_usd > effective_actual
        else 0.0
    )

    # Ngoại suy tuyến tính theo tỷ lệ phễu cho bài toán cần tìm 50 KOC (pool ~500) và 500 KOC (pool ~5,000)
    unit_cost_per_selected_koc = effective_actual / max(1, target_koc_count)
    # Với concurrency = 4 ở tầng LLM/Media, thời gian tăng dưới tuyến tính so với chạy tuần tự
    unit_time_sec_per_selected_koc = max(1.5, actual_elapsed_sec / max(1, target_koc_count))

    projections = {}
    for scale_target in (5, 50, 500):
        est_pool = scale_target * max(10, raw_pool_size // max(1, target_koc_count))
        est_funnel_usd = round(unit_cost_per_selected_koc * scale_target, 4)
        est_naive_usd = round(est_pool * naive_cost_per_koc_usd, 2)
        # Khi chạy song song 8 worker ở quy mô lớn, tốc độ trung bình nhanh hơn ~2.8x so với tuần tự
        parallel_speedup = 1.0 if scale_target == 5 else 2.8
        est_minutes = round((unit_time_sec_per_selected_koc * scale_target) / parallel_speedup / 60.0, 2)
        projections[f"find_{scale_target}_kocs"] = {
            "target_kocs": scale_target,
            "candidate_pool_scanned": est_pool,
            "detola_funnel_cost_usd": est_funnel_usd,
            "detola_funnel_cost_vnd": int(round(est_funnel_usd * usd_to_vnd_rate)),
            "naive_baseline_cost_usd": est_naive_usd,
            "estimated_wall_time_minutes": est_minutes,
        }

    return {
        "naive_baseline_current_pool_usd": naive_total_for_current_pool_usd,
        "actual_funnel_cost_usd": round(actual_cost_usd, 6),
        "token_cost_savings_pct": cost_reduction_pct,
        "scale_projections": projections,
    }


def execute_discovery_pipeline(
    *,
    input_file: Path,
    brief: CampaignBrief,
    settings: Settings,
    job_id: Optional[str] = None,
    resume: bool = False,
    dry_run: bool = False,
    simulate_crash_after_kocs: Optional[int] = None,
) -> Dict[str, Any]:
    """Chạy toàn trình hệ thống AI KOC Discovery từ dữ liệu đầu vào đến xuất báo cáo."""
    job_logger = JobLogger(job_id=job_id, resume=resume)
    checkpoint = CheckpointStore(job_logger.checkpoint_db_path)
    global_cache = GlobalEntityCache()

    # Lưu/khôi phục cấu hình phiên chạy để lệnh --resume không cần nhập lại tham số
    if resume:
        saved_meta = checkpoint.load("meta", "run_config")
        if saved_meta:
            input_file = Path(saved_meta["input_file"])
            brief = CampaignBrief.model_validate(saved_meta["brief"])
            dry_run = bool(saved_meta.get("dry_run", dry_run))
    else:
        checkpoint.save(
            "meta",
            "run_config",
            {
                "input_file": str(input_file.resolve()),
                "brief": brief.model_dump(),
                "dry_run": dry_run,
            },
        )

    prior_elapsed = float(checkpoint.load("meta", "accumulated_sec") or 0.0)
    run_start_ts = time.perf_counter()

    gateway = GeminiGateway(settings=settings, job_logger=job_logger, dry_run=dry_run)
    kalodata_client = KalodataOpenApiClient(
        settings=settings,
        job_logger=job_logger,
        global_cache=global_cache,
    )
    enricher = TikTokEnricher(
        job_logger=job_logger,
        global_cache=global_cache,
        dry_run=dry_run,
        kalodata_client=kalodata_client,
        use_kalodata_video_url_fallback=settings.kalodata_use_video_url_fallback,
    )

    try:
        job_logger.update_status(status="RUNNING", current_stage="ingestion")
        candidates = load_kalodata_candidates(
            input_file,
            max_candidates=settings.max_candidates_per_job,
        )
        if not candidates:
            raise ValueError(f"Không tìm thấy ứng viên KOC hợp lệ nào trong {input_file}")
        console.print(
            f"[bold cyan]▶ Job `{job_logger.job_id}`[/bold cyan] | Đã nạp [bold]{len(candidates)}[/bold] ứng viên KOC từ `{input_file.name}` "
            f"| Chế độ: [bold yellow]{'DRY-RUN' if dry_run else 'LIVE GEMINI API'}[/bold yellow]"
        )

        # Stage 0: Brief -> SearchSpec
        job_logger.update_status(status="RUNNING", current_stage="stage0_brief")
        spec = run_stage0_brief_parser(brief, settings, gateway, checkpoint, job_logger)
        console.print(
            f"  [green]✓ Stage 0[/green]: Quy đổi ngân sách -> Khung booking "
            f"[bold]{spec.target_cost_per_koc_min_vnd:,} – {spec.target_cost_per_koc_max_vnd:,} VNĐ/KOC[/bold]"
        )

        # Stage 1: Hard Filter & Math Scoring (0 Tokens)
        job_logger.update_status(status="RUNNING", current_stage="stage1_hard_filter")
        max_stage1_pass = max(brief.target_koc_count * settings.stage1_pass_multiplier, 15)
        stage1_passed, stage1_scores = run_stage1_hard_filter(
            candidates=candidates,
            spec=spec,
            max_pass_count=max_stage1_pass,
            checkpoint=checkpoint,
            job_logger=job_logger,
        )
        console.print(
            f"  [green]✓ Stage 1 (0 Token)[/green]: Quét {len(candidates)} KOC -> Giữ lại [bold]{len(stage1_passed)}[/bold] KOC đạt chuẩn định lượng & ngân sách"
        )

        # Stage 2: Batch Triage (gemini-2.5-flash-lite)
        job_logger.update_status(status="RUNNING", current_stage="stage2_triage")
        max_finalists = max(brief.target_koc_count + 2, int(round(brief.target_koc_count * settings.stage2_pass_multiplier)))
        finalists, stage2_scores = run_stage2_batch_triage(
            candidates=stage1_passed,
            stage1_scores=stage1_scores,
            brief=brief,
            spec=spec,
            max_finalists=max_finalists,
            settings=settings,
            gateway=gateway,
            checkpoint=checkpoint,
            global_cache=global_cache,
            job_logger=job_logger,
        )
        console.print(
            f"  [green]✓ Stage 2 (Batch Flash-Lite)[/green]: Đánh giá ngữ nghĩa -> Chọn [bold]{len(finalists)}[/bold] Finalists vào vòng Video AI"
        )

        # Stage 3: Multimodal Contact Sheet Video Analysis (gemini-2.5-flash)
        job_logger.update_status(status="RUNNING", current_stage="stage3_video_multimodal")
        dossiers = run_stage3_video_analysis(
            finalists=finalists,
            stage1_scores=stage1_scores,
            stage2_scores=stage2_scores,
            brief=brief,
            spec=spec,
            settings=settings,
            gateway=gateway,
            enricher=enricher,
            checkpoint=checkpoint,
            global_cache=global_cache,
            job_logger=job_logger,
            simulate_crash_after_kocs=simulate_crash_after_kocs,
            kalodata_client=kalodata_client,
        )
        console.print(
            f"  [green]✓ Stage 3 (Multimodal Contact Sheet 3x3)[/green]: Hoàn tất phân tích hình ảnh & phụ đề cho [bold]{len(dossiers)}[/bold] Finalists"
        )

        # Stage 4: Portfolio Synthesis (gemini-2.5-flash, thinking_budget=1024)
        job_logger.update_status(status="RUNNING", current_stage="stage4_portfolio")
        portfolio = run_stage4_portfolio_synthesis(
            dossiers=dossiers,
            brief=brief,
            spec=spec,
            settings=settings,
            gateway=gateway,
            checkpoint=checkpoint,
            job_logger=job_logger,
        )

        total_elapsed_sec = round(prior_elapsed + (time.perf_counter() - run_start_ts), 2)
        checkpoint.save("meta", "accumulated_sec", total_elapsed_sec)

        cost_summary = job_logger.get_cost_summary()
        total_cost_vnd = int(round(cost_summary["total_cost_usd"] * settings.usd_to_vnd_rate))
        scaling_projection = compute_scaling_and_savings_projection(
            raw_pool_size=len(candidates),
            target_koc_count=brief.target_koc_count,
            actual_cost_usd=cost_summary["total_cost_usd"],
            actual_elapsed_sec=total_elapsed_sec,
            usd_to_vnd_rate=settings.usd_to_vnd_rate,
        )

        funnel_stats = {
            "raw_candidates": len(candidates),
            "stage1_qualified": len(stage1_passed),
            "stage2_finalists": len(finalists),
            "stage3_video_analyzed": len(dossiers),
            "stage4_selected": len(portfolio.selected_kocs),
        }

        result_payload: Dict[str, Any] = {
            "job_id": job_logger.job_id,
            "mode": "dry_run" if dry_run else "live",
            "elapsed_seconds": total_elapsed_sec,
            "resumed_count": job_logger._status_data.get("resumed_count", 0),
            "campaign_brief": brief.model_dump(),
            "search_spec": spec.model_dump(),
            "funnel_stats": funnel_stats,
            "cost_and_tokens": {
                **cost_summary,
                "total_cost_vnd": total_cost_vnd,
            },
            "scaling_and_savings": scaling_projection,
            "portfolio_recommendation": portfolio.model_dump(),
            "finalist_dossiers": [d.model_dump() for d in dossiers],
        }

        job_logger.write_result(result_payload)
        report_paths = generate_all_reports(result_payload=result_payload, job_dir=job_logger.job_dir)

        console.print(
            f"  [green]✓ Stage 4 (Portfolio Optimizer)[/green]: Chốt [bold]{len(portfolio.selected_kocs)} KOC[/bold] "
            f"(Tổng phí: [bold]{portfolio.total_allocated_budget_vnd:,} VNĐ[/bold] <= {brief.total_budget_vnd:,} VNĐ)"
        )
        console.print(
            f"[bold green]★ HOÀN TẤT![/bold green] Chi phí AI: [bold]${cost_summary['total_cost_usd']:.5f} (~{total_cost_vnd:,} VNĐ)[/bold] "
            f"| Tiết kiệm: [bold]{scaling_projection['token_cost_savings_pct']}%[/bold] | Thời gian: [bold]{total_elapsed_sec}s[/bold]"
        )
        console.print(f"  📄 Báo cáo HTML: `{report_paths['html_report']}`")
        console.print(f"  📊 Benchmark MD: `{report_paths['benchmark_md']}`")

        # Tuân thủ quy chuẩn File Bus & Pointer Passing (agentic-engineering-discipline.md Mục 2):
        # Trả về con trỏ đường dẫn file thay vì truyền cục dữ liệu lớn qua bộ nhớ ngữ cảnh
        return {
            "job_id": job_logger.job_id,
            "status": "SUCCESS",
            "status_url": str(job_logger.status_path),
            "log_url": str(job_logger.log_path),
            "result_url": str(job_logger.result_path),
            "report_html_url": str(report_paths["html_report"]),
            "benchmark_md_url": str(report_paths["benchmark_md"]),
            "funnel_stats": funnel_stats,
            "total_cost_usd": cost_summary["total_cost_usd"],
            "total_allocated_budget_vnd": portfolio.total_allocated_budget_vnd,
        }

    except SimulatedCrashError as sim_err:
        elapsed_so_far = round(prior_elapsed + (time.perf_counter() - run_start_ts), 2)
        checkpoint.save("meta", "accumulated_sec", elapsed_so_far)
        job_logger.update_status(
            status="INTERRUPTED",
            error_message=str(sim_err),
        )
        console.print(f"[bold yellow]⚡ ĐÃ MÔ PHỎNG NGẮT GIỮA CHỪNG:[/bold yellow] {sim_err}")
        raise
    except KeyboardInterrupt:
        elapsed_so_far = round(prior_elapsed + (time.perf_counter() - run_start_ts), 2)
        checkpoint.save("meta", "accumulated_sec", elapsed_so_far)
        job_logger.update_status(
            status="INTERRUPTED",
            error_message="Người dùng nhấn Ctrl+C ngắt tiến trình.",
        )
        job_logger.error("Tiến trình bị ngắt bởi người dùng (KeyboardInterrupt). Tiến độ đã được lưu.")
        raise
    except Exception as exc:
        elapsed_so_far = round(prior_elapsed + (time.perf_counter() - run_start_ts), 2)
        checkpoint.save("meta", "accumulated_sec", elapsed_so_far)
        job_logger.update_status(status="FAILED", error_message=str(exc))
        job_logger.error(f"Pipeline gặp lỗi: {exc}")
        raise
