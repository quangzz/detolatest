import { AlertTriangle, CheckCircle2, CircleDot, Loader2, RotateCcw } from 'lucide-react';
import type { JobDetailResponse } from '../../types/discovery';
import { StatusBadge } from '../ui/StatusBadge';

interface FunnelStepperProps {
  jobDetail: JobDetailResponse | null;
  isResuming: boolean;
  onResumeJob: (jobId: string, dryRun: boolean) => void;
}

const STAGES = [
  { key: 'stage0_brief', label: 'Stage 0: Brief Spec', sub: 'Quy đổi ngân sách' },
  { key: 'stage1_hard_filter', label: 'Stage 1: Math Filter', sub: 'Lọc cứng 0-Token' },
  { key: 'stage2_triage', label: 'Stage 2: Batch Triage', sub: 'Flash-Lite 10 KOC/call' },
  { key: 'stage3_video_multimodal', label: 'Stage 3: Video AI', sub: '3x3 Contact Sheet + CC' },
  { key: 'stage4_portfolio', label: 'Stage 4: Portfolio', sub: 'Tối ưu <= Ngân sách' },
];

/** Thanh theo dõi trực quan trạng thái 5 tầng xử lý và nút khôi phục tức thì khi gián đoạn. */
export function FunnelStepper({ jobDetail, isResuming, onResumeJob }: FunnelStepperProps) {
  if (!jobDetail) return null;

  const { status, result } = jobDetail;
  const currentStage = status.current_stage;
  const overallStatus = status.status.toUpperCase();
  const stageIndex =
    overallStatus === 'SUCCESS'
      ? STAGES.length
      : STAGES.findIndex((item) => item.key === currentStage);

  const isInterruptedOrFailed = overallStatus === 'INTERRUPTED' || overallStatus === 'FAILED';
  const inferredDryRun = result ? result.mode === 'dry_run' : true;

  return (
    <section
      aria-labelledby="stepper-heading"
      className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6 shadow-lg"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <h2 id="stepper-heading" className="text-base font-bold text-white">
            2. Trạng Thái Phiên Chạy: <code className="text-emerald-300">{status.job_id}</code>
          </h2>
          <StatusBadge status={overallStatus} />
          {status.resumed_count > 0 && (
            <span className="rounded-full bg-purple-500/15 px-2.5 py-0.5 text-xs font-semibold text-purple-300 border border-purple-500/30">
              Đã Resume {status.resumed_count} lần
            </span>
          )}
        </div>

        {status.progress.stage3_total ? (
          <span className="text-xs font-medium text-slate-400">
            Tiến độ phân tích Video Stage 3: {status.progress.stage3_completed || 0}/{status.progress.stage3_total} Finalists
          </span>
        ) : null}
      </div>

      <ol className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-5">
        {STAGES.map((stage, idx) => {
          const isDone = overallStatus === 'SUCCESS' || (stageIndex > idx && stageIndex !== -1);
          const isCurrent = stageIndex === idx && overallStatus !== 'SUCCESS';

          return (
            <li
              key={stage.key}
              className={`rounded-xl border p-3.5 transition ${
                isDone
                  ? 'border-emerald-500/40 bg-emerald-950/25'
                  : isCurrent
                    ? isInterruptedOrFailed
                      ? 'border-amber-500/60 bg-amber-950/30'
                      : 'border-sky-500/60 bg-sky-950/30'
                    : 'border-slate-800 bg-slate-950/50 opacity-60'
              }`}
            >
              <div className="flex items-center gap-2">
                {isDone ? (
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
                ) : isCurrent && !isInterruptedOrFailed ? (
                  <Loader2 className="h-4 w-4 shrink-0 animate-spin text-sky-400" />
                ) : isCurrent && isInterruptedOrFailed ? (
                  <AlertTriangle className="h-4 w-4 shrink-0 text-amber-400" />
                ) : (
                  <CircleDot className="h-4 w-4 shrink-0 text-slate-500" />
                )}
                <span className="text-xs font-bold text-white">{stage.label}</span>
              </div>
              <p className="mt-1 text-[11px] text-slate-400">{stage.sub}</p>
            </li>
          );
        })}
      </ol>

      {isInterruptedOrFailed && (
        <div
          role="alert"
          className="mt-5 flex flex-wrap items-center justify-between gap-4 rounded-xl border border-amber-500/50 bg-amber-950/30 p-4"
        >
          <div className="max-w-2xl">
            <p className="text-xs font-bold text-amber-300">
              Phiên chạy đang tạm dừng ({overallStatus}) — Tiến độ từng KOC đã được lưu an toàn trong SQLite WAL!
            </p>
            {status.last_error && (
              <p className="mt-1 text-xs text-slate-300">{status.last_error}</p>
            )}
          </div>

          <button
            type="button"
            disabled={isResuming}
            onClick={() => onResumeJob(status.job_id, inferredDryRun)}
            className="inline-flex items-center gap-2 rounded-xl bg-amber-400 px-4 py-2 text-xs font-extrabold text-slate-950 shadow transition hover:bg-amber-300 disabled:opacity-50 focus:ring-2 focus:ring-amber-200 focus:outline-none"
          >
            <RotateCcw className="h-4 w-4" />
            {isResuming ? 'Đang khôi phục...' : 'Resume Tiếp Tục (0 Token Lặp)'}
          </button>
        </div>
      )}
    </section>
  );
}
