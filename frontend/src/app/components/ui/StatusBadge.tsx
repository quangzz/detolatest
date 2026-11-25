interface StatusBadgeProps {
  status: string;
}

/** Nhãn hiển thị màu sắc ngữ nghĩa theo trạng thái phiên chạy. */
export function StatusBadge({ status }: StatusBadgeProps) {
  const normalized = status.toUpperCase();
  let colorClass = 'bg-slate-800 text-slate-300 border-slate-700';

  if (normalized === 'SUCCESS') {
    colorClass = 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40';
  } else if (normalized === 'RUNNING' || normalized === 'PENDING') {
    colorClass = 'bg-sky-500/15 text-sky-300 border-sky-500/40 animate-pulse';
  } else if (normalized === 'INTERRUPTED') {
    colorClass = 'bg-amber-500/15 text-amber-300 border-amber-500/40';
  } else if (normalized === 'FAILED') {
    colorClass = 'bg-rose-500/15 text-rose-300 border-rose-500/40';
  }

  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold ${colorClass}`}>
      {normalized}
    </span>
  );
}
