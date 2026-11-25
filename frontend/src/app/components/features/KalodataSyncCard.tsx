import { useState, type FormEvent } from 'react';
import { CloudDownload, KeyRound } from 'lucide-react';
import type { SyncKalodataPayload, SyncKalodataResponse } from '../../types/discovery';

interface KalodataSyncCardProps {
  kalodataConfigured: boolean;
  onOpenKalodataKeyModal: () => void;
  onSyncCreators: (payload: SyncKalodataPayload) => Promise<SyncKalodataResponse>;
  onDatasetSynced: (filename: string) => void;
}

/** Khối đồng bộ trực tiếp danh sách KOC từ Kalodata Open API v1 (/tiktok/creator/rank). */
export function KalodataSyncCard({
  kalodataConfigured,
  onOpenKalodataKeyModal,
  onSyncCreators,
  onDatasetSynced,
}: KalodataSyncCardProps) {
  const [keyword, setKeyword] = useState<string>('kem chống nắng');
  const [followersRange, setFollowersRange] = useState<string>('10000-200000');
  const [creatorType, setCreatorType] = useState<'INDEPENDENT' | 'BELONGED_TO_SELLER' | 'ALL'>('INDEPENDENT');
  const [dateRange, setDateRange] = useState<'lastDay' | 'last7Day' | 'last30Day'>('last30Day');
  const [totalLimit, setTotalLimit] = useState<number>(50);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [syncMessage, setSyncMessage] = useState<string>('');
  const [syncError, setSyncError] = useState<string>('');

  const handleSync = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSyncError('');
    setSyncMessage('');

    if (!kalodataConfigured) {
      onOpenKalodataKeyModal();
      return;
    }

    setIsSyncing(true);
    try {
      const result = await onSyncCreators({
        keyword: keyword.trim(),
        followers_range: followersRange.trim(),
        creator_type: creatorType,
        date_range: dateRange,
        total_limit: totalLimit,
      });
      setSyncMessage(`${result.message} (Tệp: ${result.filename})`);
      onDatasetSynced(result.filename);
    } catch (err) {
      setSyncError(err instanceof Error ? err.message : 'Đồng bộ Kalodata Open API không thành công.');
    } finally {
      setIsSyncing(false);
    }
  };

  return (
    <section
      aria-labelledby="kalodata-openapi-heading"
      className="rounded-2xl border border-sky-800/40 bg-slate-900/85 p-5 shadow-lg"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
        <div>
          <h2 id="kalodata-openapi-heading" className="text-sm font-bold text-white">
            Kết Nối Trực Tiếp Kalodata Open API v1 (<code className="text-sky-300">POST /tiktok/creator/rank</code>)
          </h2>
          <p className="mt-0.5 text-xs text-slate-400">
            Kéo tối đa 100 KOC Việt Nam trong 1 lượt gọi chỉ tốn <strong>0.1 credit</strong> (~$0.01), tự động nạp vào phễu bên dưới.
          </p>
        </div>

        {!kalodataConfigured && (
          <button
            type="button"
            onClick={onOpenKalodataKeyModal}
            className="inline-flex items-center gap-1.5 rounded-lg border border-sky-500/40 bg-sky-500/15 px-3 py-1.5 text-xs font-semibold text-sky-300 hover:bg-sky-500/25"
          >
            <KeyRound className="h-3.5 w-3.5" />
            Nhập secret-key
          </button>
        )}
      </div>

      <form onSubmit={handleSync} className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <div>
          <label htmlFor="kalo-kw" className="block text-[11px] font-semibold text-slate-300">
            Từ khóa ngành/sản phẩm
          </label>
          <input
            id="kalo-kw"
            type="text"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            placeholder="kem chống nắng"
            className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white focus:border-sky-400 focus:outline-none"
          />
        </div>

        <div>
          <label htmlFor="kalo-followers" className="block text-[11px] font-semibold text-slate-300">
            Khoảng Followers
          </label>
          <input
            id="kalo-followers"
            type="text"
            value={followersRange}
            onChange={(e) => setFollowersRange(e.target.value)}
            placeholder="10000-200000"
            className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-1.5 text-xs text-white focus:border-sky-400 focus:outline-none"
          />
        </div>

        <div>
          <label htmlFor="kalo-type" className="block text-[11px] font-semibold text-slate-300">
            Nhóm nhà sáng tạo
          </label>
          <select
            id="kalo-type"
            value={creatorType}
            onChange={(e) => setCreatorType(e.target.value as 'INDEPENDENT' | 'BELONGED_TO_SELLER' | 'ALL')}
            className="mt-1 w-full rounded-xl border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-white focus:border-sky-400 focus:outline-none"
          >
            <option value="INDEPENDENT">KOC Độc lập (INDEPENDENT)</option>
            <option value="BELONGED_TO_SELLER">Thuộc Shop (SELLER)</option>
            <option value="ALL">Tất cả</option>
          </select>
        </div>

        <div>
          <label htmlFor="kalo-limit" className="block text-[11px] font-semibold text-slate-300">
            Số KOC lấy ({dateRange})
          </label>
          <div className="mt-1 flex gap-1.5">
            <input
              id="kalo-limit"
              type="number"
              min={10}
              max={200}
              step={10}
              value={totalLimit}
              onChange={(e) => setTotalLimit(Number(e.target.value))}
              className="w-20 rounded-xl border border-slate-700 bg-slate-950 px-2.5 py-1.5 text-xs text-white focus:border-sky-400 focus:outline-none"
            />
            <select
              aria-label="Khung thời gian dữ liệu"
              value={dateRange}
              onChange={(e) => setDateRange(e.target.value as 'lastDay' | 'last7Day' | 'last30Day')}
              className="w-full rounded-xl border border-slate-700 bg-slate-950 px-2 py-1.5 text-xs text-white focus:border-sky-400 focus:outline-none"
            >
              <option value="last30Day">30 ngày</option>
              <option value="last7Day">7 ngày</option>
              <option value="lastDay">Hôm qua</option>
            </select>
          </div>
        </div>

        <div className="flex items-end">
          <button
            type="submit"
            disabled={isSyncing}
            className="inline-flex w-full items-center justify-center gap-1.5 rounded-xl bg-sky-500 px-4 py-1.5 text-xs font-bold text-slate-950 transition hover:bg-sky-400 disabled:opacity-50"
          >
            <CloudDownload className="h-4 w-4" />
            {isSyncing ? 'Đang kéo...' : 'Kéo KOC từ API'}
          </button>
        </div>
      </form>

      {syncMessage && <p className="mt-3 text-xs font-medium text-emerald-400">{syncMessage}</p>}
      {syncError && (
        <div role="alert" className="mt-3 rounded-xl border border-rose-500/40 bg-rose-950/30 px-3 py-2 text-xs text-rose-200">
          {syncError}
        </div>
      )}
    </section>
  );
}
