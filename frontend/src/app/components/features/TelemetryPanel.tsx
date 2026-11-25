import { useState } from 'react';
import { BarChart3, Cpu, FileTerminal } from 'lucide-react';
import type { JobDetailResponse } from '../../types/discovery';

interface TelemetryPanelProps {
  jobDetail: JobDetailResponse | null;
}

/** Bảng đo lường Token/Chi phí AI, bảng dự phóng 50–500 KOC và trình xem llm_calls.json + log.txt. */
export function TelemetryPanel({ jobDetail }: TelemetryPanelProps) {
  const [activeTab, setActiveTab] = useState<'scaling' | 'llm_calls' | 'logs'>('scaling');

  if (!jobDetail) return null;

  const { status, llm_calls: llmCalls, recent_logs: recentLogs, result } = jobDetail;
  const totalCostUsd = result ? result.cost_and_tokens.total_cost_usd : status.metrics_so_far.total_cost_usd;
  const totalCostVnd = result ? result.cost_and_tokens.total_cost_vnd : Math.round(totalCostUsd * 25_500);
  const totalCalls = result ? result.cost_and_tokens.total_calls : status.metrics_so_far.llm_calls_count;
  const savingsPct = result ? result.scaling_and_savings.token_cost_savings_pct : 94.5;
  const allocatedVnd = result ? result.portfolio_recommendation.total_allocated_budget_vnd : 0;
  const reserveVnd = result ? result.portfolio_recommendation.reserve_seeding_budget_vnd : 0;

  return (
    <section
      id="funnel-telemetry"
      aria-labelledby="telemetry-heading"
      className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6 shadow-lg"
    >
      <h2 id="telemetry-heading" className="text-base font-bold text-white">
        3. Đo Lường Hiệu Quả Chi Phí Token (Token Efficiency) & Nhật Ký Thực Thi
      </h2>

      <div className="mt-4 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
          <div className="text-[11px] font-semibold text-slate-400 uppercase">Tổng Chi Phí AI</div>
          <div className="mt-1 text-2xl font-extrabold text-emerald-400">${totalCostUsd.toFixed(5)}</div>
          <div className="mt-0.5 text-xs text-slate-400">~{totalCostVnd.toLocaleString('vi-VN')} đ ({totalCalls} calls)</div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
          <div className="text-[11px] font-semibold text-slate-400 uppercase">Tiết Kiệm So Với Raw Video</div>
          <div className="mt-1 text-2xl font-extrabold text-sky-400">{savingsPct}%</div>
          <div className="mt-0.5 text-xs text-slate-400">Nhờ phễu 0-token + lưới 3x3</div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
          <div className="text-[11px] font-semibold text-slate-400 uppercase">Ngân Sách Booking Chốt</div>
          <div className="mt-1 text-2xl font-extrabold text-amber-400">
            {allocatedVnd > 0 ? `${(allocatedVnd / 1_000_000).toFixed(1)}Tr` : 'Đang tính...'}
          </div>
          <div className="mt-0.5 text-xs text-slate-400">
            Dự phòng seeding: {reserveVnd.toLocaleString('vi-VN')} đ
          </div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-950/70 p-4">
          <div className="text-[11px] font-semibold text-slate-400 uppercase">Phễu Lọc & Thời Gian</div>
          <div className="mt-1 text-2xl font-extrabold text-purple-400">
            {result ? `${result.funnel_stats.raw_candidates} → ${result.funnel_stats.stage4_selected}` : 'Đang quét'}
          </div>
          <div className="mt-0.5 text-xs text-slate-400">
            {result ? `Hoàn tất trong ${result.elapsed_seconds}s` : `Stage: ${status.current_stage}`}
          </div>
        </div>
      </div>

      <div className="mt-6 flex flex-wrap gap-2 border-b border-slate-800 pb-3">
        <button
          type="button"
          onClick={() => setActiveTab('scaling')}
          className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
            activeTab === 'scaling' ? 'bg-emerald-500 text-slate-950' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
          }`}
        >
          <BarChart3 className="h-3.5 w-3.5" />
          Dự phóng Mở rộng (5 – 500 KOC)
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('llm_calls')}
          className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
            activeTab === 'llm_calls' ? 'bg-emerald-500 text-slate-950' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
          }`}
        >
          <Cpu className="h-3.5 w-3.5" />
          LLM Calls Ledger ({llmCalls.length})
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('logs')}
          className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-1.5 text-xs font-semibold transition ${
            activeTab === 'logs' ? 'bg-emerald-500 text-slate-950' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
          }`}
        >
          <FileTerminal className="h-3.5 w-3.5" />
          Nhật ký Phiên (log.txt)
        </button>
      </div>

      <div className="mt-4">
        {activeTab === 'scaling' && result && (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="border-b border-slate-800 text-[11px] text-slate-400 uppercase">
                <tr>
                  <th className="py-2.5 pr-4">Quy mô mục tiêu</th>
                  <th className="py-2.5 pr-4 text-right">Pool KOC quét</th>
                  <th className="py-2.5 pr-4 text-right">Chi phí Naive (Raw Video)</th>
                  <th className="py-2.5 pr-4 text-right">Chi phí Phễu DETOLA</th>
                  <th className="py-2.5 pr-4 text-right">Quy đổi VNĐ</th>
                  <th className="py-2.5 text-right">Thời gian dự kiến</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {Object.values(result.scaling_and_savings.scale_projections).map((row) => (
                  <tr key={row.target_kocs}>
                    <td className="py-2.5 pr-4 font-bold text-white">Tìm {row.target_kocs} KOC</td>
                    <td className="py-2.5 pr-4 text-right">{row.candidate_pool_scanned.toLocaleString('vi-VN')}</td>
                    <td className="py-2.5 pr-4 text-right text-slate-400 line-through">
                      ${row.naive_baseline_cost_usd.toFixed(2)}
                    </td>
                    <td className="py-2.5 pr-4 text-right font-bold text-emerald-400">
                      ${row.detola_funnel_cost_usd.toFixed(4)}
                    </td>
                    <td className="py-2.5 pr-4 text-right">~{row.detola_funnel_cost_vnd.toLocaleString('vi-VN')} đ</td>
                    <td className="py-2.5 text-right">~{row.estimated_wall_time_minutes} phút</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'scaling' && !result && (
          <p className="text-xs text-slate-400">
            Bảng dự phóng quy mô 50–500 KOC sẽ hiển thị ngay khi phiên chạy tổng hợp xong Stage 4 (hoặc bấm xem tab Nhật ký Phiên để kiểm tra tiến độ).
          </p>
        )}

        {activeTab === 'llm_calls' && (
          <div className="max-h-72 overflow-y-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="sticky top-0 bg-slate-900 text-[11px] text-slate-400 uppercase">
                <tr>
                  <th className="py-2 pr-3">Stage</th>
                  <th className="py-2 pr-3">Mục đích</th>
                  <th className="py-2 pr-3">Model</th>
                  <th className="py-2 pr-3 text-right">In / Out+Think</th>
                  <th className="py-2 text-right">Chi phí ($)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {llmCalls.map((call, idx) => (
                  <tr key={`${call.timestamp}-${idx}`}>
                    <td className="py-2 pr-3 font-mono text-[11px] text-sky-300">{call.stage}</td>
                    <td className="py-2 pr-3">{call.purpose}</td>
                    <td className="py-2 pr-3 font-mono text-[11px] text-slate-400">{call.model}</td>
                    <td className="py-2 pr-3 text-right font-mono">
                      {call.prompt_tokens} / {call.output_tokens + call.thinking_tokens}
                    </td>
                    <td className="py-2 text-right font-mono text-emerald-400">${call.cost_usd.toFixed(6)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {activeTab === 'logs' && (
          <pre className="max-h-72 overflow-y-auto rounded-xl border border-slate-800 bg-slate-950 p-4 font-mono text-[11px] leading-relaxed text-slate-300">
            {recentLogs.length > 0 ? recentLogs.join('\n') : 'Chưa có dòng log nào.'}
          </pre>
        )}
      </div>
    </section>
  );
}
