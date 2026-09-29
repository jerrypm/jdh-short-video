import { request } from "./api";

export const metricLabels = {
  engaged_views: "Engaged views",
  average_view_duration_seconds: "Durasi tonton rata-rata (dtk)",
  average_view_percentage: "Rata-rata ditonton (%)",
  likes: "Likes",
  comments: "Komentar",
  shares: "Dibagikan",
};
export type Metric = keyof typeof metricLabels;
export const metrics = Object.keys(metricLabels) as Metric[];
export type Measurement = Record<Metric, number | null> & {
  project_id: string;
  video_id: string;
  published_on: string;
  period_start: string;
  period_end: string;
  report_timezone: string;
  captured_at: string;
  definition: "youtube_engaged_views_v1" | "custom";
  definition_note: string;
  source: string;
};
export type PerformanceRecord = Measurement & {
  id: string;
  origin: "csv" | "manual";
  imported_at: string;
  included: boolean;
  exclusion_reason: string;
};
export type PerformanceEvidence = Pick<
  PerformanceRecord,
  | "id"
  | "project_id"
  | "source"
  | "period_start"
  | "period_end"
  | "captured_at"
  | "report_timezone"
  | "definition"
  | "definition_note"
  | Metric
> & {
  start_age_days: number;
  period_days: number;
};
export type PerformanceView = {
  revision: number;
  records: PerformanceRecord[];
  projects: { id: string; name: string }[];
  ai_project_ids: string[];
  latest_ids: string[];
  notice: string;
  cohorts: {
    definition: string;
    definition_note: string;
    report_timezone: string;
    start_age_days: number;
    period_days: number;
    video_count: number;
    metric_counts: Record<Metric, number>;
    medians: Record<Metric, number | null>;
  }[];
};
export type ImportReview = {
  review_id: string;
  can_apply: boolean;
  actions: {
    id: string;
    action: "add" | "duplicate" | "conflict" | "replace";
    row: Measurement;
    previous: PerformanceRecord | null;
  }[];
};
export const performanceRequest = <T>(
  path = "",
  method = "GET",
  body?: unknown,
) =>
  request<T>("/performance" + path, method, body, AbortSignal.timeout(10000));

export const metricText = (value: number | null | undefined) =>
  value == null
    ? "—"
    : value.toLocaleString("id-ID", { maximumFractionDigits: 2 });

export function emptyMeasurement(): Measurement {
  return {
    project_id: "",
    video_id: "",
    published_on: "",
    period_start: "",
    period_end: "",
    report_timezone: "America/Los_Angeles",
    captured_at: new Date().toISOString(),
    definition: "youtube_engaged_views_v1",
    definition_note: "",
    source: "",
    engaged_views: null,
    average_view_duration_seconds: null,
    average_view_percentage: null,
    likes: null,
    comments: null,
    shares: null,
  };
}

export function measurementOnly(row: PerformanceRecord): Measurement {
  const fields = Object.keys(emptyMeasurement()) as (keyof Measurement)[];
  return Object.fromEntries(
    fields.map((key) => [key, row[key]]),
  ) as Measurement;
}

export function numericMetric(value: string): number | null {
  if (!value.trim()) return null;
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed < 0)
    throw new Error("Metrik harus angka positif atau nol.");
  return parsed;
}
