import { useCallback } from 'react';
import type {
  CreateJobPayload,
  DatasetItem,
  HealthStatus,
  JobDetailResponse,
  JobSummaryItem,
} from '../types/discovery';

/** Chuyển đổi lỗi HTTP/mạng sang thông báo tiếng Việt thân thiện với người dùng. */
async function parseApiResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let serverDetail = '';
    try {
      const errBody = (await response.json()) as { detail?: string };
      if (typeof errBody.detail === 'string') {
        serverDetail = errBody.detail;
      }
    } catch {
      serverDetail = '';
    }
    if (response.status === 413) {
      throw new Error('Tệp tải lên vượt quá dung lượng tối đa 10MB.');
    }
    if (serverDetail) {
      throw new Error(serverDetail);
    }
    throw new Error('Không thể kết nối máy chủ xử lý. Vui lòng kiểm tra Backend FastAPI và thử lại.');
  }
  return (await response.json()) as T;
}

/** Custom hook tập trung các lời gọi REST API tới Backend DETOLA. */
export function useDiscoveryApi() {
  const fetchHealth = useCallback(async (): Promise<HealthStatus> => {
    const resp = await fetch('/api/health');
    return parseApiResponse<HealthStatus>(resp);
  }, []);

  const fetchDatasets = useCallback(async (): Promise<DatasetItem[]> => {
    const resp = await fetch('/api/datasets');
    return parseApiResponse<DatasetItem[]>(resp);
  }, []);

  const uploadDataset = useCallback(async (file: File): Promise<DatasetItem> => {
    const formData = new FormData();
    formData.append('file', file);
    const resp = await fetch('/api/datasets/upload', {
      method: 'POST',
      body: formData,
    });
    return parseApiResponse<DatasetItem>(resp);
  }, []);

  const updateSessionApiKey = useCallback(
    async (apiKey: string): Promise<{ configured: boolean; gemini_key_masked: string; message: string }> => {
      const resp = await fetch('/api/settings/api-key', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey }),
      });
      return parseApiResponse<{ configured: boolean; gemini_key_masked: string; message: string }>(resp);
    },
    []
  );

  const fetchJobs = useCallback(async (): Promise<JobSummaryItem[]> => {
    const resp = await fetch('/api/jobs?limit=25');
    return parseApiResponse<JobSummaryItem[]>(resp);
  }, []);

  const fetchJobDetail = useCallback(async (jobId: string): Promise<JobDetailResponse> => {
    const resp = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`);
    return parseApiResponse<JobDetailResponse>(resp);
  }, []);

  const startJob = useCallback(async (payload: CreateJobPayload): Promise<{ job_id: string }> => {
    const resp = await fetch('/api/jobs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    return parseApiResponse<{ job_id: string }>(resp);
  }, []);

  const resumeJob = useCallback(async (jobId: string, dryRun: boolean): Promise<{ job_id: string }> => {
    const resp = await fetch(`/api/jobs/${encodeURIComponent(jobId)}/resume`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dry_run: dryRun }),
    });
    return parseApiResponse<{ job_id: string }>(resp);
  }, []);

  return {
    fetchHealth,
    fetchDatasets,
    uploadDataset,
    updateSessionApiKey,
    fetchJobs,
    fetchJobDetail,
    startJob,
    resumeJob,
  };
}
