import { ExternalLink, ZoomIn } from 'lucide-react';
import type { FinalistDossier, JobResultPayload } from '../../types/discovery';

interface KocPortfolioListProps {
  result: JobResultPayload | null;
  onSelectZoomImage: (url: string, caption: string) => void;
}

/** Danh sách thẻ Semantic <article> trình bày 5 KOC đề xuất kèm bằng chứng Kalodata & lưới 3x3 Contact Sheet. */
export function KocPortfolioList({ result, onSelectZoomImage }: KocPortfolioListProps) {
  if (!result) return null;

  const { portfolio_recommendation: portfolio, finalist_dossiers: dossiers, campaign_brief: brief } = result;
  const dossierMap = new Map<string, FinalistDossier>();
  dossiers.forEach((d) => dossierMap.set(d.candidate.koc_id, d));

  return (
    <section id="koc-portfolio" aria-labelledby="portfolio-heading" className="space-y-5">
      <div className="rounded-2xl border border-emerald-800/40 bg-emerald-950/20 p-5">
        <h2 id="portfolio-heading" className="text-lg font-bold text-white">
          4. Danh Mục {portfolio.selected_kocs.length} KOC Đề Xuất Tối Ưu Trong Ngân Sách{' '}
          {brief.total_budget_vnd.toLocaleString('vi-VN')} VNĐ
        </h2>
        <p className="mt-1.5 text-xs leading-relaxed text-slate-300">{portfolio.portfolio_strategy_rationale}</p>
      </div>

      {portfolio.selected_kocs.map((card) => {
        const dossier = dossierMap.get(card.koc_id);
        const candidate = dossier?.candidate;
        const safeProfileUrl =
          candidate?.profile_url && candidate.profile_url.startsWith('https://')
            ? candidate.profile_url
            : `https://www.tiktok.com/@${card.handle}`;

        const contactSheets =
          candidate?.recent_videos.filter((vid) => Boolean(vid.contact_sheet_url)) || [];

        return (
          <article
            key={card.koc_id}
            className="rounded-2xl border border-slate-800 bg-slate-900/90 p-6 shadow-lg transition hover:border-slate-700"
          >
            <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-800 pb-4">
              <div>
                <span className="inline-block rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-bold text-emerald-300 border border-emerald-500/30">
                  TOP #{card.rank} • {card.portfolio_role}
                </span>
                <h3 className="mt-2 flex items-center gap-2 text-xl font-extrabold text-white">
                  <a
                    href={safeProfileUrl}
                    target="_blank" rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 hover:text-emerald-400 underline"
                  >
                    @{card.handle}
                    <ExternalLink className="h-4 w-4 text-slate-400" />
                  </a>
                  {candidate?.display_name && (
                    <span className="text-sm font-normal text-slate-400">({candidate.display_name})</span>
                  )}
                </h3>
              </div>

              <div className="text-right">
                <div className="text-[11px] font-semibold text-slate-400 uppercase">Ngân sách đề xuất</div>
                <div className="text-lg font-extrabold text-amber-400">
                  {card.allocated_budget_vnd.toLocaleString('vi-VN')} VNĐ
                </div>
                <div className="text-xs font-semibold text-emerald-400">Match Score: {card.final_match_score}/100</div>
              </div>
            </div>

            <p className="mt-4 text-sm leading-relaxed text-slate-300">{card.why_selected}</p>

            <div className="mt-5 grid grid-cols-1 gap-6 lg:grid-cols-3">
              <div className="space-y-4 lg:col-span-2">
                <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4">
                  <div className="text-xs font-bold tracking-wider text-sky-400 uppercase">
                    Bằng chứng Hiệu suất Thương mại (Kalodata & TikTok)
                  </div>
                  <ul className="mt-2 list-inside list-disc space-y-1 text-xs leading-relaxed text-slate-300">
                    {card.performance_evidence.map((ev, i) => (
                      <li key={i}>{ev}</li>
                    ))}
                  </ul>
                </div>

                <div className="rounded-xl border border-slate-800/80 bg-slate-950/70 p-4">
                  <div className="text-xs font-bold tracking-wider text-purple-400 uppercase">
                    Bằng chứng Phân tích Video AI (Contact Sheet [mm:ss] & Phụ đề)
                  </div>
                  <ul className="mt-2 list-inside list-disc space-y-1.5 text-xs leading-relaxed text-slate-300">
                    {card.visual_and_video_evidence.map((ev, i) => (
                      <li key={i}>{ev}</li>
                    ))}
                  </ul>
                </div>

                <div className="rounded-xl border border-emerald-800/40 bg-emerald-950/30 p-4 text-xs leading-relaxed text-emerald-100">
                  <strong className="text-emerald-300">Góc kịch bản đề xuất:</strong> {card.recommended_content_angle}
                </div>
              </div>

              <div className="space-y-3">
                <div className="text-xs font-bold tracking-wider text-amber-300 uppercase">
                  Keyframe Contact Sheet (3x3)
                </div>

                {contactSheets.length === 0 ? (
                  <p className="text-xs italic text-slate-500">Chưa có ảnh khung hình đính kèm.</p>
                ) : (
                  contactSheets.map((vid) => (
                    <button
                      key={vid.video_id}
                      type="button"
                      onClick={() =>
                        onSelectZoomImage(
                          vid.contact_sheet_url || '',
                          `Contact Sheet 3x3 của @${card.handle} — Video ${vid.video_id}`
                        )
                      }
                      className="group block w-full text-left focus:ring-2 focus:ring-emerald-400 focus:outline-none rounded-xl"
                    >
                      <img
                        src={vid.contact_sheet_url}
                        alt={`Lưới 9 khung hình video TikTok ${vid.video_id} của KOC @${card.handle} phân tích chất lượng review kem chống nắng`}
                        loading="lazy"
                        className="w-full rounded-xl border border-slate-700 object-cover transition group-hover:border-emerald-400"
                      />
                      <span className="mt-1.5 inline-flex items-center gap-1 text-[11px] text-slate-400 group-hover:text-emerald-300">
                        <ZoomIn className="h-3.5 w-3.5" />
                        Phóng to lưới 9 khung hình [mm:ss] ({vid.views.toLocaleString('vi-VN')} views)
                      </span>
                    </button>
                  ))
                )}
              </div>
            </div>
          </article>
        );
      })}
    </section>
  );
}
