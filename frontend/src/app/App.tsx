import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { CampaignForm } from './components/features/CampaignForm';
import { FunnelStepper } from './components/features/FunnelStepper';
import { JobHistorySidebar } from './components/features/JobHistorySidebar';
import { KocPortfolioList } from './components/features/KocPortfolioList';
import { TelemetryPanel } from './components/features/TelemetryPanel';
import { Footer } from './components/layout/Footer';
import { Header } from './components/layout/Header';
import { Modal } from './components/ui/Modal';
import { useDiscoveryApi } from './hooks/useDiscoveryApi';
import { useJobPoller } from './hooks/useJobPoller';
import type { CreateJobPayload, DatasetItem, HealthStatus, JobSummaryItem } from './types/discovery';

/** Container chính kết nối luồng nghiên cứu KOC 5 tầng trên giao diện Web chuẩn SEO. */
export function App() {
  const {
    fetchHealth,
    fetchDatasets,
    uploadDataset,
    updateSessionApiKey,
    fetchJobs,
    fetchJobDetail,
    startJob,
    resumeJob,
  } = useDiscoveryApi();

  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [datasets, setDatasets] = useState<DatasetItem[]>([]);
  const [jobs, setJobs] = useState<JobSummaryItem[]>([]);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [initError, setInitError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [isResuming, setIsResuming] = useState<boolean>(false);

  // Hộp thoại cấu hình khóa Gemini trong RAM phiên Backend (không lưu localStorage)
  const [isKeyModalOpen, setIsKeyModalOpen] = useState<boolean>(false);
  const [apiKeyInput, setApiKeyInput] = useState<string>('');
  const [keyStatusMsg, setKeyStatusMsg] = useState<string>('');

  // Hộp thoại phóng to ảnh Contact Sheet 3x3
  const [zoomImage, setZoomImage] = useState<{ url: string; caption: string } | null>(null);

  const refreshSidebarAndHealth = useCallback(async () => {
    try {
      const [healthData, jobsList] = await Promise.all([fetchHealth(), fetchJobs()]);
      setHealth(healthData);
      setJobs(jobsList);
      setInitError(null);
      setActiveJobId((prev) => prev || jobsList[0]?.job_id || null);
    } catch (err) {
      setInitError(err instanceof Error ? err.message : 'Không thể tải dữ liệu khởi tạo từ Backend.');
    }
  }, [fetchHealth, fetchJobs]);

  useEffect(() => {
    const bootstrap = async () => {
      try {
        const [healthData, dsList, jobsList] = await Promise.all([
          fetchHealth(),
          fetchDatasets(),
          fetchJobs(),
        ]);
        setHealth(healthData);
        setDatasets(dsList);
        setJobs(jobsList);
        if (jobsList.length > 0) {
          setActiveJobId(jobsList[0].job_id);
        }
      } catch (err) {
        setInitError(err instanceof Error ? err.message : 'Không thể kết nối máy chủ FastAPI.');
      }
    };
    void bootstrap();
  }, [fetchDatasets, fetchHealth, fetchJobs]);

  const { jobDetail, pollError } = useJobPoller({
    activeJobId,
    fetchJobDetail,
    onJobSettled: () => {
      void refreshSidebarAndHealth();
    },
  });

  const handleUploadDataset = async (file: File): Promise<DatasetItem> => {
    const item = await uploadDataset(file);
    const updatedList = await fetchDatasets();
    setDatasets(updatedList);
    return item;
  };

  const handleStartJob = async (payload: CreateJobPayload) => {
    setIsSubmitting(true);
    try {
      const created = await startJob(payload);
      setActiveJobId(created.job_id);
      await refreshSidebarAndHealth();
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResumeJob = async (jobId: string, dryRun: boolean) => {
    setIsResuming(true);
    try {
      await resumeJob(jobId, dryRun);
      setActiveJobId(jobId);
      await refreshSidebarAndHealth();
    } finally {
      setIsResuming(false);
    }
  };

  const handleSaveApiKey = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!apiKeyInput.trim()) return;
    try {
      const res = await updateSessionApiKey(apiKeyInput.trim());
      setKeyStatusMsg(res.message);
      setApiKeyInput('');
      await refreshSidebarAndHealth();
      window.setTimeout(() => {
        setIsKeyModalOpen(false);
        setKeyStatusMsg('');
      }, 900);
    } catch (err) {
      setKeyStatusMsg(err instanceof Error ? err.message : 'Không thể cập nhật khóa API.');
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-slate-950 text-slate-100">
      <Header health={health} onOpenApiKeyModal={() => setIsKeyModalOpen(true)} />

      <main id="main-content" className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 sm:px-6">
        <section className="mb-8 rounded-2xl border border-slate-800 bg-gradient-to-r from-slate-900 via-slate-900 to-emerald-950/40 p-6 sm:p-8">
          <span className="inline-block rounded-full bg-emerald-500/15 px-3 py-1 text-xs font-bold text-emerald-300">
            Founding Engineer Prototype • Multi-Stage AI Funnel
          </span>
          <h1 className="mt-3 text-2xl font-extrabold tracking-tight text-white sm:text-3xl">
            Hệ Thống AI KOC Discovery & Phân Tích Video Tối Ưu Chi Phí Token
          </h1>
          <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-300">
            Nghiên cứu từ 50–500 KOC TikTok dựa trên dữ liệu hiệu suất thương mại Kalodata, sàng lọc toán học 0-token,
            nén khung hình video bằng lưới Contact Sheet 3x3 và tự động lưu checkpoint SQLite để khôi phục khi gián đoạn.
          </p>
        </section>

        {(initError || pollError) && (
          <div
            role="alert"
            className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-rose-500/50 bg-rose-950/40 px-4 py-3 text-xs text-rose-200"
          >
            <span>{initError || pollError}</span>
            <button
              type="button"
              onClick={() => void refreshSidebarAndHealth()}
              className="rounded-lg bg-rose-500/20 px-3 py-1 font-bold text-rose-200 hover:bg-rose-500/30"
            >
              Thử kết nối lại
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
          <div className="space-y-6 lg:col-span-8 xl:col-span-9">
            <CampaignForm
              datasets={datasets}
              geminiConfigured={Boolean(health?.gemini_configured)}
              isSubmitting={isSubmitting}
              onUploadDataset={handleUploadDataset}
              onSubmitJob={handleStartJob}
            />

            <FunnelStepper
              jobDetail={jobDetail}
              isResuming={isResuming}
              onResumeJob={handleResumeJob}
            />

            <TelemetryPanel jobDetail={jobDetail} />

            <KocPortfolioList
              result={jobDetail?.result || null}
              onSelectZoomImage={(url, caption) => setZoomImage({ url, caption })}
            />
          </div>

          <div className="lg:col-span-4 xl:col-span-3">
            <JobHistorySidebar
              jobs={jobs}
              activeJobId={activeJobId}
              onSelectJob={(id) => setActiveJobId(id)}
              onQuickResume={(id, mode) => void handleResumeJob(id, mode === 'dry_run')}
            />
          </div>
        </div>
      </main>

      <Footer />

      <Modal
        isOpen={isKeyModalOpen}
        title="Cấu Hình Khóa Gemini API Trong Phiên Backend"
        onClose={() => setIsKeyModalOpen(false)}
        maxWidthClass="max-w-lg"
      >
        <form onSubmit={handleSaveApiKey} className="space-y-4">
          <p className="text-xs leading-relaxed text-slate-300">
            Theo tiêu chuẩn bảo mật OWASP CWE-522, khóa API chỉ được gửi thẳng vào bộ nhớ RAM của máy chủ FastAPI nội bộ
            và <strong>không lưu vào localStorage</strong> trình duyệt.
          </p>
          <div>
            <label htmlFor="gemini-key-input" className="block text-xs font-semibold text-slate-300">
              Google AI Studio API Key (AIza...)
            </label>
            <input
              id="gemini-key-input"
              type="password"
              autoComplete="off"
              placeholder="AIzaSy..."
              value={apiKeyInput}
              onChange={(e) => setApiKeyInput(e.target.value)}
              className="mt-1.5 w-full rounded-xl border border-slate-700 bg-slate-950 px-3.5 py-2 text-sm text-white focus:border-emerald-400 focus:outline-none"
            />
          </div>
          {keyStatusMsg && <p className="text-xs font-medium text-emerald-400">{keyStatusMsg}</p>}
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => setIsKeyModalOpen(false)}
              className="rounded-xl border border-slate-700 px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-800"
            >
              Đóng
            </button>
            <button
              type="submit"
              className="rounded-xl bg-emerald-500 px-4 py-2 text-xs font-bold text-slate-950 hover:bg-emerald-400"
            >
              Lưu vào Backend RAM
            </button>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={Boolean(zoomImage)}
        title={zoomImage?.caption || 'Chi tiết Keyframe Contact Sheet 3x3'}
        onClose={() => setZoomImage(null)}
        maxWidthClass="max-w-4xl"
      >
        {zoomImage && (
          <div className="space-y-3">
            <img
              src={zoomImage.url}
              alt={zoomImage.caption}
              className="max-h-[75vh] w-full rounded-xl border border-slate-700 object-contain"
            />
            <p className="text-center text-xs text-slate-400">
              Nhấn phím <kbd className="rounded bg-slate-800 px-1.5 py-0.5 font-mono">Esc</kbd> hoặc bấm ra ngoài để đóng.
            </p>
          </div>
        )}
      </Modal>
    </div>
  );
}
