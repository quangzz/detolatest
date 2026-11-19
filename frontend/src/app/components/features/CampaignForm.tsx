import { useEffect, useState, type ChangeEvent, type FormEvent } from 'react';
import { Flame, Play, Upload } from 'lucide-react';
import type { CreateJobPayload, DatasetItem } from '../../types/discovery';

interface CampaignFormProps {
  datasets: DatasetItem[];
  preferredDatasetFilename?: string;
  geminiConfigured: boolean;
  isSubmitting: boolean;
  onUploadDataset: (file: File) => Promise<DatasetItem>;
  onSubmitJob: (payload: CreateJobPayload) => Promise<void>;
}

/** Biểu mẫu thiết lập đề bài chiến dịch, tải dữ liệu Kalodata và bật cờ kiểm thử Crash Recovery. */
export function CampaignForm({
  datasets,
  preferredDatasetFilename,
  geminiConfigured,
  isSubmitting,
  onUploadDataset,
  onSubmitJob,
}: CampaignFormProps) {
  const [selectedDataset, setSelectedDataset] = useState<string>(
    datasets[0]?.filename || 'fixture_sunscreen_pool_32.json'
  );

  useEffect(() => {
    if (preferredDatasetFilename) {
      setSelectedDataset(preferredDatasetFilename);
    }
  }, [preferredDatasetFilename]);
  const [productName, setProductName] = useState<string>('Kem chống nắng');
  const [brandCategory, setBrandCategory] = useState<string>('Mỹ phẩm Việt Nam');
  const [targetAudience, setTargetAudience] = useState<string>('Nữ, 18–30 tuổi');
  const [totalBudgetVnd, setTotalBudgetVnd] = useState<number>(30_000_000);
  const [targetKocCount, setTargetKocCount] = useState<number>(5);
  const [dryRun, setDryRun] = useState<boolean>(true);
  const [enableCrashSim, setEnableCrashSim] = useState<boolean>(false);
  const [crashAfterKocs, setCrashAfterKocs] = useState<number>(2);
  const [uploadStatus, setUploadStatus] = useState<string>('');
  const [formError, setFormError] = useState<string>('');

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setFormError('');
    setUploadStatus('Đang kiểm định và chuẩn hóa tệp Kalodata...');
    try {
      const uploaded = await onUploadDataset(file);
      setSelectedDataset(uploaded.filename);
      setUploadStatus(`Đã nạp ${uploaded.koc_count} KOC từ tệp ${uploaded.filename}`);
    } catch (err) {
      setUploadStatus('');
      setFormError(err instanceof Error ? err.message : 'Tải tệp dữ liệu thất bại.');
    } finally {
      event.target.value = '';
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError('');
    if (!productName.trim() || !targetAudience.trim()) {
      setFormError('Vui lòng nhập đầy đủ tên sản phẩm và khách hàng mục tiêu.');
      return;
    }
    if (totalBudgetVnd < 3_000_000) {
      setFormError('Ngân sách chiến dịch tối thiểu là 3.000.000 VNĐ.');
      return;
    }
    if (!dryRun && !geminiConfigured) {
      setFormError('Bạn đang chọn chế độ Live Gemini API nhưng chưa nhập khóa. Hãy bấm nút Cấu hình Gemini API Key ở góc trên.');
      return;
    }

    try {
      await onSubmitJob({
        dataset_filename: selectedDataset || datasets[0]?.filename || 'fixture_sunscreen_pool_32.json',
        brand_category: brandCategory.trim(),
        product_name: productName.trim(),
        target_audience: targetAudience.trim(),
        total_budget_vnd: totalBudgetVnd,
        target_koc_count: targetKocCount,
        raw_brief_text: '',
        dry_run: dryRun,
        simulate_crash_after_kocs: enableCrashSim ? crashAfterKocs : null,
      });
    } catch (err) {
      setFormError(err instanceof Error ? err.message : 'Không thể khởi chạy phiên nghiên cứu.');
    }
  };

  return (
    <section
      id="campaign-setup"
      aria-labelledby="setup-heading"
      className="rounded-2xl border border-slate-800 bg-slate-900/80 p-6 shadow-lg"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-4">
        <div>
          <h2 id="setup-heading" className="text-lg font-bold text-white">
            1. Thiết Lập Đề Bài Chiến Dịch & Nguồn Dữ Liệu Kalodata
          </h2>
          <p className="mt-0.5 text-xs text-slate-400">
            Tuỳ chỉnh sản phẩm, ngân sách, nạp snapshot Kalodata hoặc bật kiểm thử gián đoạn (Crash-Resume).
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="mt-5 space-y-5">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <div>
            <label htmlFor="product-input" className="block text-xs font-semibold text-slate-300">
              Sản phẩm cần quảng bá
            </label>
            <input
              id="product-input"
              type="text"
              value={productName}
              onChange={(e) => setProductName(e.target.value)}
              className="mt-1.5 w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2 text-sm text-white focus:border-emerald-400 focus:outline-none"
            />
          </div>

          <div>
            <label htmlFor="audience-input" className="block text-xs font-semibold text-slate-300">
              Khách hàng mục tiêu
            </label>
            <input
              id="audience-input"
              type="text"
              value={targetAudience}
              onChange={(e) => setTargetAudience(e.target.value)}
              className="mt-1.5 w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2 text-sm text-white focus:border-emerald-400 focus:outline-none"
            />
          </div>

          <div>
            <label htmlFor="category-input" className="block text-xs font-semibold text-slate-300">
              Ngành hàng thương hiệu
            </label>
            <input
              id="category-input"
              type="text"
              value={brandCategory}
              onChange={(e) => setBrandCategory(e.target.value)}
              className="mt-1.5 w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2 text-sm text-white focus:border-emerald-400 focus:outline-none"
            />
          </div>

          <div>
            <label htmlFor="budget-input" className="block text-xs font-semibold text-slate-300">
              Tổng ngân sách chiến dịch (VNĐ)
            </label>
            <input
              id="budget-input"
              type="number"
              step={1_000_000}
              min={3_000_000}
              value={totalBudgetVnd}
              onChange={(e) => setTotalBudgetVnd(Number(e.target.value))}
              className="mt-1.5 w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2 text-sm text-amber-300 font-semibold focus:border-emerald-400 focus:outline-none"
            />
          </div>

          <div>
            <label htmlFor="topk-input" className="block text-xs font-semibold text-slate-300">
              Số lượng KOC đề xuất (Top-K)
            </label>
            <input
              id="topk-input"
              type="number"
              min={1}
              max={50}
              value={targetKocCount}
              onChange={(e) => setTargetKocCount(Number(e.target.value))}
              className="mt-1.5 w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2 text-sm text-white focus:border-emerald-400 focus:outline-none"
            />
          </div>

          <div>
            <label htmlFor="dataset-select" className="block text-xs font-semibold text-slate-300">
              Tập ứng viên Kalodata đầu vào
            </label>
            <div className="mt-1.5 flex gap-2">
              <select
                id="dataset-select"
                value={selectedDataset}
                onChange={(e) => setSelectedDataset(e.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white focus:border-emerald-400 focus:outline-none"
              >
                {datasets.map((ds) => (
                  <option key={ds.filename} value={ds.filename}>
                    {ds.filename} ({ds.koc_count} KOCs {ds.is_test ? '• Fixture Test' : '• Live Data'})
                  </option>
                ))}
              </select>

              <label
                htmlFor="kalodata-upload"
                title="Tải lên file .json, .csv, .xlsx hoặc .har từ Kalodata"
                className="inline-flex shrink-0 cursor-pointer items-center gap-1 rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:bg-slate-700"
              >
                <Upload className="h-3.5 w-3.5 text-emerald-400" />
                <span>Tải tệp</span>
                <input
                  id="kalodata-upload"
                  type="file"
                  accept=".json,.csv,.xlsx,.har"
                  onChange={handleFileChange}
                  className="sr-only"
                />
              </label>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 rounded-xl border border-slate-800 bg-slate-950/70 p-4 md:grid-cols-2">
          <div className="flex items-start gap-3">
            <input
              id="dryrun-checkbox"
              type="checkbox"
              checked={dryRun}
              onChange={(e) => setDryRun(e.target.checked)}
              className="mt-1 h-4 w-4 rounded border-slate-600 bg-slate-900 text-emerald-500 focus:ring-emerald-400"
            />
            <div>
              <label htmlFor="dryrun-checkbox" className="text-xs font-bold text-slate-200 cursor-pointer">
                Chế độ Dry-Run (Mô phỏng Offline — Không tốn quota Gemini API)
              </label>
              <p className="text-[11px] text-slate-400">
                Bỏ tích ô này khi bạn đã nạp khóa Gemini API để gọi trực tiếp `gemini-2.5-flash-lite` & `gemini-2.5-flash`.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3">
            <input
              id="crashsim-checkbox"
              type="checkbox"
              checked={enableCrashSim}
              onChange={(e) => setEnableCrashSim(e.target.checked)}
              className="mt-1 h-4 w-4 rounded border-slate-600 bg-slate-900 text-amber-500 focus:ring-amber-400"
            />
            <div className="flex-1">
              <label htmlFor="crashsim-checkbox" className="flex items-center gap-1.5 text-xs font-bold text-amber-300 cursor-pointer">
                <Flame className="h-3.5 w-3.5" />
                Kiểm thử Reliability: Giả lập sập giữa chừng ở Stage 3
              </label>
              <div className="mt-1 flex items-center gap-2 text-[11px] text-slate-400">
                <span>Ngắt sau khi xong:</span>
                <input
                  type="number"
                  min={1}
                  max={10}
                  disabled={!enableCrashSim}
                  value={crashAfterKocs}
                  onChange={(e) => setCrashAfterKocs(Number(e.target.value))}
                  aria-label="Số KOC xử lý trước khi giả lập ngắt"
                  className="w-14 rounded border border-slate-700 bg-slate-900 px-2 py-0.5 text-center text-xs text-white disabled:opacity-40"
                />
                <span>KOC (sau đó bấm nút Resume để kiểm chứng 0 token lặp)</span>
              </div>
            </div>
          </div>
        </div>

        {uploadStatus && <p className="text-xs font-medium text-emerald-400">{uploadStatus}</p>}
        {formError && (
          <div role="alert" className="rounded-xl border border-rose-500/50 bg-rose-950/40 px-4 py-2.5 text-xs text-rose-200">
            {formError}
          </div>
        )}

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={isSubmitting}
            className="inline-flex items-center gap-2 rounded-xl bg-emerald-500 px-6 py-2.5 text-sm font-bold text-slate-950 shadow-lg shadow-emerald-500/20 transition hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50 focus:ring-2 focus:ring-emerald-300 focus:outline-none"
          >
            <Play className="h-4 w-4 fill-current" />
            {isSubmitting ? 'Đang khởi chạy...' : 'Chạy Phễu AI KOC Discovery'}
          </button>
        </div>
      </form>
    </section>
  );
}
