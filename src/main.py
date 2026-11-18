"""CLI Entrypoint cho hệ thống DETOLA AI KOC Discovery."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table

from src.config import SNAPSHOTS_DIR, Settings, ensure_directories
from src.ingestion.kalodata_loader import load_kalodata_candidates
from src.ingestion.seed_fixture import generate_test_fixture
from src.models.schemas import CampaignBrief
from src.pipeline.orchestrator import execute_discovery_pipeline
from src.pipeline.stage3_video import SimulatedCrashError


console = Console()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="detola",
        description="DETOLA — Hệ thống AI KOC Discovery tối ưu token & tự phục hồi (Crash-Resumable)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # Lệnh run: Chạy mới một phiên nghiên cứu & đề xuất KOC
    run_p = sub.add_parser("run", help="Chạy phễu 5 tầng tìm kiếm & đề xuất KOC")
    run_p.add_argument(
        "--input",
        type=str,
        default="",
        help="Đường dẫn file dữ liệu Kalodata (.json, .har, .csv, .xlsx). Nếu để trống sẽ dùng fixture mẫu.",
    )
    run_p.add_argument("--product", type=str, default="Kem chống nắng", help="Tên sản phẩm cần quảng bá")
    run_p.add_argument("--brand-category", type=str, default="Mỹ phẩm Việt Nam", help="Ngành hàng thương hiệu")
    run_p.add_argument("--audience", type=str, default="Nữ, 18–30 tuổi", help="Khách hàng mục tiêu")
    run_p.add_argument("--budget-vnd", type=int, default=30_000_000, help="Tổng ngân sách chiến dịch (VNĐ)")
    run_p.add_argument("--top-k", type=int, default=5, help="Số lượng KOC cần đề xuất")
    run_p.add_argument("--job-id", type=str, default="", help="Đặt tên job_id tùy chọn")
    run_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Chạy mô phỏng offline không gọi Gemini API để kiểm thử luồng & checkpoint miễn phí",
    )
    run_p.add_argument(
        "--simulate-crash-after",
        type=int,
        default=None,
        help="Mô phỏng ngắt đột ngột sau khi phân tích xong N KOC ở Stage 3 để test tính năng resume",
    )

    # Lệnh resume: Khôi phục phiên chạy bị gián đoạn
    res_p = sub.add_parser("resume", help="Tiếp tục một job bị gián đoạn từ checkpoint đã lưu")
    res_p.add_argument("job_id", type=str, help="Mã job_id trong thư mục jobs/ (VD: job_20261118_103000)")
    res_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Ghi đè chế độ dry-run khi khôi phục (mặc định giữ nguyên chế độ lúc khởi tạo job)",
    )

    # Lệnh inspect-input: Kiểm tra nhanh file dữ liệu thu thập từ Kalodata Free Trial
    ins_p = sub.add_parser("inspect-input", help="Kiểm tra & thống kê file dữ liệu KOC từ Kalodata")
    ins_p.add_argument("input_path", type=str, help="Đường dẫn file .json / .har / .csv / .xlsx")

    # Lệnh generate-fixture: Tạo dữ liệu mẫu kiểm thử
    sub.add_parser("generate-fixture", help="Tạo tập fixture 32 KOC mẫu tại data/snapshots/")

    # Lệnh serve: Khởi chạy FastAPI Backend phục vụ giao diện Web chuẩn SEO
    srv_p = sub.add_parser("serve", help="Khởi chạy máy chủ FastAPI cho giao diện Web Console")
    srv_p.add_argument("--host", type=str, default="127.0.0.1", help="Địa chỉ lắng nghe")
    srv_p.add_argument("--port", type=int, default=8000, help="Cổng lắng nghe (mặc định 8000)")

    return parser


def main() -> None:
    """Hàm thực thi chính của CLI."""
    ensure_directories()
    parser = _build_parser()
    args = parser.parse_args()
    settings = Settings()

    if args.command == "generate-fixture":
        path = generate_test_fixture()
        console.print(f"[green]✓ Đã sinh file fixture mẫu tại:[/green] `{path}`")
        return

    if args.command == "serve":
        import uvicorn

        console.print(
            f"[bold cyan]🚀 Đang khởi động DETOLA FastAPI Server tại http://{args.host}:{args.port}[/bold cyan]"
        )
        uvicorn.run("src.api.server:app", host=args.host, port=args.port, reload=False)
        return

    if args.command == "inspect-input":
        target = Path(args.input_path)
        cands = load_kalodata_candidates(target)
        table = Table(title=f"Đã chuẩn hóa {len(cands)} KOC từ {target.name}")
        table.add_column("#", justify="right")
        table.add_column("Handle", style="cyan")
        table.add_column("Followers", justify="right")
        table.add_column("Doanh thu 30d (VNĐ)", justify="right", style="green")
        table.add_column("Video Rev (VNĐ)", justify="right")
        table.add_column("Videos có sẵn", justify="right")
        for i, c in enumerate(cands[:15], start=1):
            table.add_row(
                str(i),
                f"@{c.handle}",
                f"{c.followers:,}",
                f"{c.revenue_30d_vnd:,}",
                f"{c.video_revenue_30d_vnd:,}",
                str(len(c.recent_videos)),
            )
        console.print(table)
        return

    if args.command == "run":
        if args.input:
            input_path = Path(args.input)
        else:
            # Ưu tiên file kalodata_captured.json nếu người dùng đã bỏ vào snapshots, nếu chưa có thì dùng fixture
            real_captured = SNAPSHOTS_DIR / "kalodata_captured.json"
            input_path = real_captured if real_captured.exists() else generate_test_fixture()

        brief = CampaignBrief(
            brand_category=args.brand_category,
            product_name=args.product,
            target_audience=args.audience,
            total_budget_vnd=args.budget_vnd,
            target_koc_count=args.top_k,
        )
        try:
            execute_discovery_pipeline(
                input_file=input_path,
                brief=brief,
                settings=settings,
                job_id=args.job_id or None,
                resume=False,
                dry_run=args.dry_run,
                simulate_crash_after_kocs=args.simulate_crash_after,
            )
        except SimulatedCrashError:
            sys.exit(2)
        return

    if args.command == "resume":
        execute_discovery_pipeline(
            input_file=SNAPSHOTS_DIR / "fixture_sunscreen_pool_32.json",
            brief=CampaignBrief(),
            settings=settings,
            job_id=args.job_id,
            resume=True,
            dry_run=args.dry_run,
            simulate_crash_after_kocs=None,
        )


if __name__ == "__main__":
    main()
