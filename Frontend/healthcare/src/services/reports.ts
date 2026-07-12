import { apiClient } from "@/api/Fetcher";
import type { ActiveClinicalBaseline } from "@/services/clinical";

export type PeriodType = "weekly" | "monthly";

export type ReportTrendPoint = {
  label: string;
  timestamp?: string;
  glucose: number;
};

export type ReportOverview = {
  avg_glucose: number;
  health_score: number;
  bmi: number;
  alerts: number;
  score_label: string;
  score_description: string;
};

export type ClinicalMetric = {
  available: boolean;
  primary_value: number | null;
  secondary_value: number | null;
  recorded_at: string | null;
  source: "HOSPITAL_LAB" | "DIAGNOSIS_INPUT" | null;
  provider_name: string | null;
};

export type ReportDataQuality = {
  completed: number;
  total: number;
  coverage_percent: number;
  missing_groups: string[];
  uses_defaults: boolean;
  clinical_metrics: {
    hba1c: ClinicalMetric;
    insulin: ClinicalMetric;
    cholesterol: ClinicalMetric;
  };
};

export type ReportComparisonRow = {
  label: string;
  current: string;
  previous: string;
  delta: string;
  good: boolean;
};

export type ReportHistoryRow = {
  row_key?: string;
  id?: number;
  period: string;
  period_start?: string;
  period_end?: string;
  type: string;
  score: number;
  avg: number;
  status: string;
};

export type BaselineTrackingMetric = {
  key: string;
  label: string;
  unit: string;
  baseline_value: number;
  baseline_at: string;
  current_value: number | null;
  delta: number | null;
  delta_percent: number | null;
  points: Array<{
    timestamp: string;
    label: string;
    value: number;
    source: string;
  }>;
};

export type ReportDashboardData = {
  has_data: boolean;
  period_type: "WEEKLY" | "MONTHLY";
  overview: ReportOverview;
  data_quality: ReportDataQuality;
  baseline: ActiveClinicalBaseline;
  baseline_tracking: BaselineTrackingMetric[];
  trend: ReportTrendPoint[];
  comparison: ReportComparisonRow[];
  achievements: string[];
  issues: string[];
  history: ReportHistoryRow[];
};

export const getReportDashboard = async (
  periodType: PeriodType
): Promise<ReportDashboardData> => {
  const response = await apiClient.get<ReportDashboardData>("/reports/dashboard/", {
    params: { period_type: periodType },
  });
  return response.data;
};

export const exportPeriodicReport = async (
  exportFormat: "PDF" | "CSV",
  periodType: PeriodType
) => {
  const response = await apiClient.post<Blob>(
    "/reports/export/",
    {
      export_format: exportFormat,
      period_type: periodType.toUpperCase(),
    },
    { responseType: "blob" }
  );
  const disposition = String(response.headers["content-disposition"] ?? "");
  const matchedFilename = disposition.match(/filename="?([^";]+)"?/i)?.[1];
  return {
    blob: response.data,
    filename:
      matchedFilename ??
      `health-report-${periodType}.${exportFormat.toLowerCase()}`,
  };
};

export const saveReportDraft = async (periodType: PeriodType) => {
  const response = await apiClient.post("/reports/draft/", {
    period_type: periodType.toUpperCase(),
  });
  return response.data;
};
