import { Database, KeyRound, ShieldCheck, Sparkles } from 'lucide-react';
import type { HealthStatus } from '../../types/discovery';

interface HeaderProps {
  health: HealthStatus | null;
  onOpenApiKeyModal: () => void;
  onOpenKalodataKeyModal: () => void;
}

/** Thanh tiêu đề Semantic <header> & <nav> chuẩn SEO và Accessibility. */
export function Header({ health, onOpenApiKeyModal, onOpenKalodataKeyModal }: HeaderProps) {
  const isLiveReady = Boolean(health?.gemini_configured);
  const isKalodataReady = Boolean(health?.kalodata_configured);

  return (
    <header className="sticky top-0 z-30 border-b border-slate-800/80 bg-slate-950/90 backdrop-blur-md">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-emerald-500 focus:px-4 focus:py-2 focus:text-sm focus:font-bold focus:text-slate-950"
      >
        Bỏ qua điều hướng tới nội dung chính
      </a>

      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-3.5 sm:px-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-400 ring-1 ring-emerald-500/30">
            <Sparkles className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-bold tracking-wider text-emerald-400 uppercase">DETOLA</span>
              <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[11px] text-slate-400">
                commit:{health?.commit || 'local'}
              </span>
            </div>
            <p className="text-sm font-semibold text-slate-200">AI KOC Discovery & Video Evidence Console</p>
          </div>
        </div>

        <nav aria-label="Điều hướng chính" className="flex flex-wrap items-center gap-3">
          <a
            href="#campaign-setup"
            className="rounded-lg px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:bg-slate-800 hover:text-white"
          >
            Thiết lập Chiến dịch
          </a>
          <a
            href="#funnel-telemetry"
            className="rounded-lg px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:bg-slate-800 hover:text-white"
          >
            Phễu & Token Cost
          </a>
          <a
            href="#koc-portfolio"
            className="rounded-lg px-3 py-1.5 text-xs font-medium text-slate-300 transition hover:bg-slate-800 hover:text-white"
          >
            Đề xuất 5 KOC
          </a>

          <span className="inline-flex items-center gap-1.5 rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-1 text-xs font-medium text-sky-300">
            <ShieldCheck className="h-3.5 w-3.5" />
            OWASP Hardened
          </span>

          <button
            type="button"
            onClick={onOpenKalodataKeyModal}
            className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-semibold transition focus:ring-2 focus:ring-sky-400 focus:outline-none ${
              isKalodataReady
                ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25'
                : 'border-sky-500/40 bg-sky-500/15 text-sky-300 hover:bg-sky-500/25'
            }`}
          >
            <Database className="h-3.5 w-3.5" />
            {isKalodataReady ? `Kalodata (${health?.kalodata_key_masked})` : 'Kalodata Open API Key'}
          </button>

          <button
            type="button"
            onClick={onOpenApiKeyModal}
            className={`inline-flex items-center gap-1.5 rounded-xl border px-3.5 py-1.5 text-xs font-semibold transition focus:ring-2 focus:ring-emerald-400 focus:outline-none ${
              isLiveReady
                ? 'border-emerald-500/40 bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25'
                : 'border-amber-500/40 bg-amber-500/15 text-amber-300 hover:bg-amber-500/25'
            }`}
          >
            <KeyRound className="h-3.5 w-3.5" />
            {isLiveReady ? `Gemini Ready (${health?.gemini_key_masked})` : 'Cấu hình Gemini API Key'}
          </button>
        </nav>
      </div>
    </header>
  );
}
