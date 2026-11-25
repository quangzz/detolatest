"""Xuất báo cáo Benchmark Markdown và Dashboard HTML trực quan đính kèm ảnh Contact Sheet 3x3."""

from __future__ import annotations

import html
import shutil
from pathlib import Path
from typing import Any, Dict, List

from src.config import ROOT_DIR
from src.core.security import validate_safe_tiktok_url


def generate_all_reports(result_payload: Dict[str, Any], job_dir: Path) -> Dict[str, Path]:
    """Sinh đồng thời report.html trong thư mục job và cập nhật docs/BENCHMARK_RESULTS.md."""
    docs_dir = ROOT_DIR / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    assets_dir = job_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    # Sao chép các ảnh Contact Sheet của 5 KOC được chọn vào thư mục job/assets để HTML xem độc lập
    dossier_map: Dict[str, Dict[str, Any]] = {
        d["candidate"]["koc_id"]: d for d in result_payload.get("finalist_dossiers", [])
    }
    sheet_rel_by_koc: Dict[str, List[str]] = {}
    for card in result_payload["portfolio_recommendation"]["selected_kocs"]:
        kid = card["koc_id"]
        dossier = dossier_map.get(kid, {})
        rels: List[str] = []
        for v in dossier.get("candidate", {}).get("recent_videos", []):
            src_sheet = v.get("contact_sheet_path")
            if src_sheet and Path(src_sheet).exists():
                dst = assets_dir / Path(src_sheet).name
                if src_sheet != str(dst):
                    shutil.copy2(src_sheet, dst)
                rels.append(f"assets/{dst.name}")
        sheet_rel_by_koc[kid] = rels

    md_content = _render_benchmark_markdown(result_payload, dossier_map)
    job_md_path = job_dir / "BENCHMARK_RESULTS.md"
    docs_md_path = docs_dir / "BENCHMARK_RESULTS.md"
    job_md_path.write_text(md_content, encoding="utf-8")
    docs_md_path.write_text(md_content, encoding="utf-8")

    html_content = _render_interactive_html(result_payload, dossier_map, sheet_rel_by_koc)
    html_path = job_dir / "report.html"
    html_path.write_text(html_content, encoding="utf-8")

    return {
        "html_report": html_path,
        "benchmark_md": docs_md_path,
        "job_benchmark_md": job_md_path,
    }


def _render_benchmark_markdown(
    data: Dict[str, Any],
    dossier_map: Dict[str, Dict[str, Any]],
) -> str:
    """Tạo nội dung Markdown chuẩn chỉnh cho yêu cầu bàn giao #4 (Benchmark Results)."""
    brief = data["campaign_brief"]
    funnel = data["funnel_stats"]
    cost = data["cost_and_tokens"]
    scale = data["scaling_and_savings"]
    portfolio = data["portfolio_recommendation"]

    lines: List[str] = [
        "# DETOLA — Benchmark Results & KOC Recommendations",
        "",
        f"- **Job ID:** `{data['job_id']}` (`{data['mode'].upper()}`)",
        f"- **Bài toán:** Tìm **{brief['target_koc_count']} KOC TikTok** quảng bá **{brief['product_name']}** ({brief['brand_category']})",
        f"- **Khách hàng mục tiêu:** {brief['target_audience']} | **Ngân sách tối đa:** {brief['total_budget_vnd']:,} VNĐ",
        f"- **Tổng thời gian xử lý:** `{data['elapsed_seconds']} giây` | **Số lần Resume phục hồi:** `{data.get('resumed_count', 0)}`",
        "",
        "---",
        "",
        "## 1. Thống Kê Phễu Lọc & Hiệu Quả Chi Phí AI (Token Efficiency)",
        "",
        "| Tầng xử lý (Stage) | Đầu vào -> Đầu ra | Lượt gọi LLM | Input Tokens | Output + Thinking Tokens | Chi phí (USD) |",
        "| :--- | :--- | ---: | ---: | ---: | ---: |",
    ]

    stage_labels = [
        ("stage0_brief", "Stage 0: Brief Parser", f"1 brief -> SearchSpec"),
        ("stage1_hard_filter", "Stage 1: Quantitative Filter (0-Token)", f"{funnel['raw_candidates']} -> {funnel['stage1_qualified']} KOCs"),
        ("stage2_triage", "Stage 2: Batch Triage (Flash-Lite)", f"{funnel['stage1_qualified']} -> {funnel['stage2_finalists']} Finalists"),
        ("stage3_video_multimodal", "Stage 3: 3x3 Contact Sheet Vision", f"{funnel['stage2_finalists']} Finalists Video AI"),
        ("stage4_portfolio", "Stage 4: Portfolio Synthesis", f"{funnel['stage3_video_analyzed']} -> Top {funnel['stage4_selected']} KOCs"),
    ]
    by_stage = cost.get("by_stage", {})
    for key, title, flow_desc in stage_labels:
        st = by_stage.get(key, {"calls": 0, "prompt_tokens": 0, "output_tokens": 0, "thinking_tokens": 0, "cost_usd": 0.0})
        out_plus_think = st["output_tokens"] + st["thinking_tokens"]
        lines.append(
            f"| **{title}** | {flow_desc} | {st['calls']} | {st['prompt_tokens']:,} | {out_plus_think:,} | `${st['cost_usd']:.6f}` |"
        )

    lines.extend(
        [
            f"| **TỔNG CỘNG** | **{funnel['raw_candidates']} -> {funnel['stage4_selected']} KOCs** | **{cost['total_calls']}** | **{cost['total_prompt_tokens']:,}** | **{cost['total_output_tokens'] + cost['total_thinking_tokens']:,}** | **`${cost['total_cost_usd']:.6f}` (~{cost['total_cost_vnd']:,} VNĐ)** |",
            "",
            f"> **So sánh với Kiến trúc Naive (gửi trực tiếp raw video toàn tập {funnel['raw_candidates']} KOC):** Tốn khoảng **`${scale['naive_baseline_current_pool_usd']:.4f}`** -> Phễu DETOLA tiết kiệm **`{scale['token_cost_savings_pct']}%` chi phí AI**.",
            "",
            "### Dự phóng Mở rộng Quy mô (50 – 500 KOC)",
            "",
            "| Quy mô mục tiêu | Tổng Pool KOC quét | Chi phí Kiến trúc Naive | Chi phí Phễu DETOLA | Quy đổi VNĐ | Thời gian dự kiến (8 luồng song song) |",
            "| :--- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )

    for p_key in ("find_5_kocs", "find_50_kocs", "find_500_kocs"):
        p = scale["scale_projections"][p_key]
        lines.append(
            f"| **Tìm {p['target_kocs']} KOC** | {p['candidate_pool_scanned']:,} KOCs | `${p['naive_baseline_cost_usd']:.2f}` | **`${p['detola_funnel_cost_usd']:.4f}`** | ~{p['detola_funnel_cost_vnd']:,} VNĐ | ~{p['estimated_wall_time_minutes']} phút |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 2. Danh Mục 5 KOC Đề Xuất & Bằng Chứng Cụ Thể",
            "",
            f"- **Chiến lược phân bổ:** {portfolio['portfolio_strategy_rationale']}",
            f"- **Tổng ngân sách booking phân bổ:** **{portfolio['total_allocated_budget_vnd']:,} VNĐ** / {brief['total_budget_vnd']:,} VNĐ *(Dự phòng seeding/vận chuyển: {portfolio['reserve_seeding_budget_vnd']:,} VNĐ)*",
            "",
        ]
    )

    for card in portfolio["selected_kocs"]:
        dossier = dossier_map.get(card["koc_id"], {})
        cand = dossier.get("candidate", {})
        profile_url = cand.get("profile_url") or f"https://www.tiktok.com/@{card['handle']}"
        lines.extend(
            [
                f"### #{card['rank']}. @{card['handle']} — *{card['portfolio_role']}*",
                f"- **TikTok Profile:** {profile_url}",
                f"- **Điểm phù hợp tổng hợp:** `{card['final_match_score']}/100` | **Ngân sách đề xuất:** **{card['allocated_budget_vnd']:,} VNĐ**",
                f"- **Lý do lựa chọn:** {card['why_selected']}",
                "- **Bằng chứng dữ liệu hiệu suất (Kalodata & TikTok):**",
            ]
        )
        for pe in card["performance_evidence"]:
            lines.append(f"  - {pe}")
        lines.append("- **Bằng chứng phân tích hình ảnh & nội dung Video AI (Contact Sheet 3x3 & Phụ đề):**")
        for ve in card["visual_and_video_evidence"]:
            lines.append(f"  - {ve}")
        lines.extend(
            [
                f"- **Góc kịch bản đề xuất:** {card['recommended_content_angle']}",
                f"- **Lưu ý hợp tác:** {card['risks_or_notes']}",
                "",
            ]
        )

    return "\n".join(lines)


def _render_interactive_html(
    data: Dict[str, Any],
    dossier_map: Dict[str, Dict[str, Any]],
    sheet_rel_by_koc: Dict[str, List[str]],
) -> str:
    """Sinh file HTML5 độc lập hiển thị trực quan phễu chi phí, 5 KOC và ảnh Contact Sheet."""
    brief = data["campaign_brief"]
    funnel = data["funnel_stats"]
    cost = data["cost_and_tokens"]
    scale = data["scaling_and_savings"]
    portfolio = data["portfolio_recommendation"]

    cards_html: List[str] = []
    for card in portfolio["selected_kocs"]:
        kid = card["koc_id"]
        dossier = dossier_map.get(kid, {})
        cand = dossier.get("candidate", {})
        raw_profile_url = cand.get("profile_url") or f"https://www.tiktok.com/@{card['handle']}"
        try:
            verified_url = validate_safe_tiktok_url(raw_profile_url, resolve_dns=False)
        except ValueError:
            verified_url = "#"
        profile_url = html.escape(verified_url)

        perf_li = "".join(f"<li>{html.escape(x)}</li>" for x in card["performance_evidence"])
        vis_li = "".join(f"<li>{html.escape(x)}</li>" for x in card["visual_and_video_evidence"])

        imgs_html = ""
        for rel_img in sheet_rel_by_koc.get(kid, []):
            imgs_html += (
                f'<a href="{html.escape(rel_img)}" target="_blank" rel="noopener noreferrer" class="block group">'
                f'<img src="{html.escape(rel_img)}" alt="Contact sheet" loading="lazy" '
                f'class="rounded-lg border border-slate-700 group-hover:border-emerald-400 transition w-full object-cover" />'
                f'<span class="text-xs text-slate-400 mt-1 block">🔍 Bấm để phóng to lưới 9 khung hình [mm:ss]</span></a>'
            )

        cards_html.append(
            f"""
            <div class="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-lg">
              <div class="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
                <div>
                  <span class="inline-block px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-300 mr-2">
                    TOP #{card['rank']} • {html.escape(card['portfolio_role'])}
                  </span>
                  <h3 class="text-xl font-bold text-white mt-2">
                    <a href="{profile_url}" target="_blank" rel="noopener noreferrer" class="hover:text-emerald-400 underline">@{html.escape(card['handle'])}</a>
                    <span class="text-sm font-normal text-slate-400 ml-2">({html.escape(cand.get('display_name', ''))})</span>
                  </h3>
                </div>
                <div class="text-right">
                  <div class="text-xs uppercase text-slate-400">Ngân sách phân bổ</div>
                  <div class="text-lg font-bold text-amber-400">{card['allocated_budget_vnd']:,} VNĐ</div>
                  <div class="text-xs text-emerald-400 font-semibold">Match Score: {card['final_match_score']}/100</div>
                </div>
              </div>

              <p class="text-slate-300 mt-4 text-sm leading-relaxed">{html.escape(card['why_selected'])}</p>

              <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 mt-5">
                <div class="lg:col-span-2 space-y-4">
                  <div class="bg-slate-950/70 rounded-xl p-4 border border-slate-800/80">
                    <h4 class="text-xs font-bold uppercase tracking-wider text-sky-400 mb-2">📊 Bằng chứng Hiệu suất (Kalodata & TikTok)</h4>
                    <ul class="list-disc list-inside text-sm text-slate-300 space-y-1">{perf_li}</ul>
                  </div>
                  <div class="bg-slate-950/70 rounded-xl p-4 border border-slate-800/80">
                    <h4 class="text-xs font-bold uppercase tracking-wider text-purple-400 mb-2">🎬 Bằng chứng Phân tích Video AI (Contact Sheet [mm:ss] & Phụ đề)</h4>
                    <ul class="list-disc list-inside text-sm text-slate-300 space-y-1.5">{vis_li}</ul>
                  </div>
                  <div class="bg-emerald-950/30 rounded-xl p-4 border border-emerald-800/40 text-sm text-emerald-100">
                    <strong>💡 Góc kịch bản đề xuất:</strong> {html.escape(card['recommended_content_angle'])}
                  </div>
                </div>
                <div class="space-y-3">
                  <h4 class="text-xs font-bold uppercase tracking-wider text-amber-300">🖼️ Keyframe Contact Sheet (3x3)</h4>
                  {imgs_html or '<div class="text-xs text-slate-500 italic">Không có ảnh đính kèm</div>'}
                </div>
              </div>
            </div>
            """
        )

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src https://cdn.tailwindcss.com; style-src 'unsafe-inline'; img-src 'self' data:; object-src 'none'; base-uri 'self';" />
  <title>DETOLA AI KOC Discovery — {html.escape(data['job_id'])}</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen font-sans">
  <div class="max-w-6xl mx-auto px-4 py-10 space-y-8">
    <header class="border-b border-slate-800 pb-6 flex flex-wrap justify-between items-end gap-4">
      <div>
        <div class="text-xs font-bold uppercase tracking-widest text-emerald-400">DETOLA — Founding Engineer Prototype</div>
        <h1 class="text-3xl font-extrabold text-white mt-1">AI KOC Discovery & Video Evidence Report</h1>
        <p class="text-slate-400 text-sm mt-1">
          Sản phẩm: <strong>{html.escape(brief['product_name'])}</strong> • Mục tiêu: <strong>{html.escape(brief['target_audience'])}</strong> • Ngân sách trần: <strong>{brief['total_budget_vnd']:,} VNĐ</strong>
        </p>
      </div>
      <div class="text-xs text-slate-400 bg-slate-900 px-4 py-2.5 rounded-xl border border-slate-800">
        Job: <code class="text-emerald-300">{html.escape(data['job_id'])}</code> • Mode: <strong>{html.escape(data['mode'].upper())}</strong> • Resumed: <strong>{data.get('resumed_count', 0)}x</strong>
      </div>
    </header>

    <section class="grid grid-cols-2 md:grid-cols-4 gap-4">
      <div class="bg-slate-900 p-5 rounded-2xl border border-slate-800">
        <div class="text-xs text-slate-400 uppercase">Tổng Chi Phí AI</div>
        <div class="text-2xl font-extrabold text-emerald-400 mt-1">${cost['total_cost_usd']:.5f}</div>
        <div class="text-xs text-slate-400 mt-1">~{cost['total_cost_vnd']:,} VNĐ ({cost['total_calls']} calls)</div>
      </div>
      <div class="bg-slate-900 p-5 rounded-2xl border border-slate-800">
        <div class="text-xs text-slate-400 uppercase">Tiết Kiệm So Với Naive</div>
        <div class="text-2xl font-extrabold text-sky-400 mt-1">{scale['token_cost_savings_pct']}%</div>
        <div class="text-xs text-slate-400 mt-1">Naive raw video: ${scale['naive_baseline_current_pool_usd']:.4f}</div>
      </div>
      <div class="bg-slate-900 p-5 rounded-2xl border border-slate-800">
        <div class="text-xs text-slate-400 uppercase">Ngân Sách Phân Bổ</div>
        <div class="text-2xl font-extrabold text-amber-400 mt-1">{portfolio['total_allocated_budget_vnd']:,} đ</div>
        <div class="text-xs text-slate-400 mt-1">Dự phòng seeding: {portfolio['reserve_seeding_budget_vnd']:,} đ</div>
      </div>
      <div class="bg-slate-900 p-5 rounded-2xl border border-slate-800">
        <div class="text-xs text-slate-400 uppercase">Phễu Thu Hẹp & Thời Gian</div>
        <div class="text-2xl font-extrabold text-purple-400 mt-1">{funnel['raw_candidates']} → {funnel['stage4_selected']}</div>
        <div class="text-xs text-slate-400 mt-1">Xử lý hoàn tất trong {data['elapsed_seconds']}s</div>
      </div>
    </section>

    <section class="bg-slate-900/70 border border-slate-800 rounded-2xl p-6">
      <h2 class="text-lg font-bold text-white mb-2">Chiến lược Danh mục (Portfolio Rationale)</h2>
      <p class="text-sm text-slate-300 leading-relaxed">{html.escape(portfolio['portfolio_strategy_rationale'])}</p>
    </section>

    <section class="space-y-6">
      <h2 class="text-xl font-bold text-white">Top {len(portfolio['selected_kocs'])} KOC Đề Xuất & Bằng Chứng Cụ Thể</h2>
      {''.join(cards_html)}
    </section>
  </div>
</body>
</html>
"""
