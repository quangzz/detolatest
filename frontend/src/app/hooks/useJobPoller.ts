import { useEffect, useState } from 'react';
import type { JobDetailResponse } from '../types/discovery';

interface UseJobPollerParams {
  activeJobId: string | null;
  fetchJobDetail: (jobId: string) => Promise<JobDetailResponse>;
  onJobSettled: () => void;
}

/** Custom hook tự động cập nhật tiến độ realtime khi Job đang RUNNING và tự dọn dẹp bộ đếm khi hoàn tất. */
export function useJobPoller({ activeJobId, fetchJobDetail, onJobSettled }: UseJobPollerParams) {
  const [jobDetail, setJobDetail] = useState<JobDetailResponse | null>(null);
  const [isLoadingDetail, setIsLoadingDetail] = useState<boolean>(false);
  const [pollError, setPollError] = useState<string | null>(null);

  useEffect(() => {
    if (!activeJobId) {
      setJobDetail(null);
      return;
    }

    let isCancelled = false;
    let timerId: number | undefined;

    const loadOnce = async (isInitial: boolean) => {
      if (isInitial) {
        setIsLoadingDetail(true);
      }
      try {
        const detail = await fetchJobDetail(activeJobId);
        if (isCancelled) return;
        setJobDetail(detail);
        setPollError(null);

        const currentStatus = detail.status.status;
        if (currentStatus === 'RUNNING' || currentStatus === 'PENDING') {
          timerId = window.setTimeout(() => {
            void loadOnce(false);
          }, 900);
        } else {
          onJobSettled();
        }
      } catch (err) {
        if (!isCancelled) {
          setPollError(err instanceof Error ? err.message : 'Không thể tải trạng thái phiên chạy.');
        }
      } finally {
        if (!isCancelled && isInitial) {
          setIsLoadingDetail(false);
        }
      }
    };

    void loadOnce(true);

    return () => {
      isCancelled = true;
      if (timerId !== undefined) {
        window.clearTimeout(timerId);
      }
    };
  }, [activeJobId, fetchJobDetail, onJobSettled]);

  return { jobDetail, isLoadingDetail, pollError };
}
