/** Định nghĩa toàn bộ kiểu dữ liệu TypeScript nghiêm ngặt (không sử dụng any). */

export interface HealthStatus {
  status: string;
  service: string;
  commit: string;
  server_time: string;
  gemini_configured: boolean;
  gemini_key_masked: string;
  models: {
    triage: string;
    multimodal: string;
    portfolio: string;
  };
}

export interface DatasetItem {
  filename: string;
  koc_count: number;
  is_test: boolean;
  size_bytes: number;
  sample_handles: string[];
}

export interface CreateJobPayload {
  dataset_filename: string;
  brand_category: string;
  product_name: string;
  target_audience: string;
  total_budget_vnd: number;
  target_koc_count: number;
  raw_brief_text: string;
  dry_run: boolean;
  simulate_crash_after_kocs: number | null;
}

export interface JobSummaryItem {
  job_id: string;
  status: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'INTERRUPTED' | 'FAILED' | string;
  current_stage: string;
  updated_at: string;
  resumed_count: number;
  product_name: string;
  selected_count: number;
  mode: string;
  total_cost_usd: number;
  llm_calls_count: number;
}

export interface LlmCallRecord {
  timestamp: string;
  mode: string;
  stage: string;
  purpose: string;
  model: string;
  thinking_budget: number;
  images_attached: number;
  prompt_tokens: number;
  cached_tokens: number;
  output_tokens: number;
  thinking_tokens: number;
  cost_usd: number;
  latency_ms: number;
}

export interface StageCostBucket {
  calls: number;
  prompt_tokens: number;
  output_tokens: number;
  thinking_tokens: number;
  cached_tokens: number;
  cost_usd: number;
  latency_ms: number;
}

export interface ScaleProjectionItem {
  target_kocs: number;
  candidate_pool_scanned: number;
  detola_funnel_cost_usd: number;
  detola_funnel_cost_vnd: number;
  naive_baseline_cost_usd: number;
  estimated_wall_time_minutes: number;
}

export interface RecommendedKocCard {
  rank: number;
  koc_id: string;
  handle: string;
  portfolio_role: string;
  allocated_budget_vnd: number;
  final_match_score: number;
  why_selected: string;
  performance_evidence: string[];
  visual_and_video_evidence: string[];
  recommended_content_angle: string;
  risks_or_notes: string;
}

export interface FinalistVideoMeta {
  video_id: string;
  url: string;
  title: string;
  views: number;
  likes: number;
  contact_sheet_url?: string;
}

export interface FinalistDossier {
  candidate: {
    koc_id: string;
    handle: string;
    display_name: string;
    profile_url: string;
    followers: number;
    recent_videos: FinalistVideoMeta[];
  };
}

export interface JobResultPayload {
  job_id: string;
  mode: string;
  elapsed_seconds: number;
  resumed_count: number;
  campaign_brief: {
    brand_category: string;
    product_name: string;
    target_audience: string;
    total_budget_vnd: number;
    target_koc_count: number;
  };
  funnel_stats: {
    raw_candidates: number;
    stage1_qualified: number;
    stage2_finalists: number;
    stage3_video_analyzed: number;
    stage4_selected: number;
  };
  cost_and_tokens: {
    total_calls: number;
    total_prompt_tokens: number;
    total_output_tokens: number;
    total_thinking_tokens: number;
    total_cost_usd: number;
    total_cost_vnd: number;
    by_stage: Record<string, StageCostBucket>;
  };
  scaling_and_savings: {
    naive_baseline_current_pool_usd: number;
    actual_funnel_cost_usd: number;
    token_cost_savings_pct: number;
    scale_projections: Record<string, ScaleProjectionItem>;
  };
  portfolio_recommendation: {
    executive_summary: string;
    total_allocated_budget_vnd: number;
    reserve_seeding_budget_vnd: number;
    portfolio_strategy_rationale: string;
    selected_kocs: RecommendedKocCard[];
  };
  finalist_dossiers: FinalistDossier[];
}

export interface JobDetailResponse {
  status: {
    job_id: string;
    status: string;
    current_stage: string;
    created_at: string;
    updated_at: string;
    resumed_count: number;
    last_error?: string;
    progress: {
      stage3_completed?: number;
      stage3_total?: number;
    };
    metrics_so_far: {
      llm_calls_count: number;
      total_prompt_tokens: number;
      total_output_tokens: number;
      total_thinking_tokens: number;
      total_cost_usd: number;
    };
  };
  llm_calls: LlmCallRecord[];
  recent_logs: string[];
  result: JobResultPayload | null;
}
