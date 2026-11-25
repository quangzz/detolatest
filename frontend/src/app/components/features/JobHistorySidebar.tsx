import { History, RotateCcw } from 'lucide-react';
import type { JobSummaryItem } from '../../types/discovery';
import { StatusBadge } from '../ui/StatusBadge';

interface JobHistorySidebarProps {
  jobs: JobSummaryItem[];
  activeJobId: string | null;
  onSelectJob: (jobId: string) => void;
  onQuickResume: (jobId: string, mode: string) => void;
}

/** Cột bên Semantic <aside> liệt kê lịch sử các phiên làm việc trong thư mục jobs/<job_id>/. */
export function JobHistorySidebar({
  jobs,
  activeJobId,
  onSelectJob,
  onQuickResume,
}: JobHistorySidebarProps) {
  return (
    <aside
      aria-label="Lịch sử phiên chạy"
      className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5 shadow-lg"
    >
      <div className="flex items-center justify-between border-b border-slate-800 pb-3">
        <div className="flex items-center gap-2">
          <History className="h-4 w-4 text-emerald-400" />
          <h2 className="text-sm font-bold text-white">Lịch Sử Jobs ({jobs.length})</h2>
        </div>
      </div>

      {jobs.length === 0 ? (
        <p className="mt-4 text-xs text-slate-400">
          Chưa có phiên chạy nào. Hãy bấm &ldquo;Chạy Phễu AI KOC Discovery&rdquo; để bắt đầu.
        </p>
      ) : (
        <ul className="mt-3 max-h-[540px] space-y-2.5 overflow-y-auto pr-1">
          {jobs.map((job) => {
            const isSelected = job.job_id === activeJobId;
            const canResume = job.status === 'INTERRUPTED' || job.status === 'FAILED';

            return (
              <li key={job.job_id}>
                <div
                  onClick={() => onSelectJob(job.job_id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') onSelectJob(job.job_id);
                  }}
                  className={`cursor-pointer rounded-xl border p-3 transition ${
                    isSelected
                      ? 'border-emerald-500/60 bg-emerald-950/20'
                      : 'border-slate-800 bg-slate-950/60 hover:border-slate-700'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-mono text-xs font-semibold text-slate-200">
                      {job.job_id}
                    </span>
                    <StatusBadge status={job.status} />
                  </div>

                  <div className="mt-2 flex flex-wrap items-center justify-between gap-1 text-[11px] text-slate-400">
                    <span>{job.product_name}</span>
                    <span>${job.total_cost_usd.toFixed(5)} • {job.llm_calls_count} calls</span>
                  </div>

                  {(job.resumed_count > 0 || canResume) && (
                    <div className="mt-2 flex items-center justify-between border-t border-slate-800/80 pt-2">
                      <span className="text-[10px] text-purple-300">
                        {job.resumed_count > 0 ? `Resumed ${job.resumed_count}x` : 'Có checkpoint lưu sẵn'}
                      </span>
                      {canResume && (
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            onQuickResume(job.job_id, job.mode);
                          }}
                          className="inline-flex items-center gap-1 rounded-lg bg-amber-400/20 px-2 py-0.5 text-[11px] font-bold text-amber-300 hover:bg-amber-400/30"
                        >
                          <RotateCcw className="h-3 w-3" />
                          Resume
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </aside>
  );
}
