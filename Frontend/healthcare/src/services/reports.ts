import { apiClient } from "@/api/Fetcher";

export type PeriodType = "weekly" | "monthly";

export type ReportTrendPoint = {
  label: string;
  glucose: number;
};

export type ReportOverview = {
  avg_glucose: number;
  health_score: number;
  bmi: number;
  alerts: number;
};

export type ReportComparisonRow = {
  label: string;
  current: string;
  previous: string;
  delta: string;
  good: boolean;
};

export type ReportHistoryRow = {
  period: string;
  type: string;
  score: number;
  avg: number;
  status: string;
};

export type ReportDashboardData = {
  has_data: boolean;
  period_type: "WEEKLY" | "MONTHLY";
  overview: ReportOverview;
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

export const exportPeriodicReport = async (exportFormat: "PDF" | "CSV" | "XLSX") => {
  const response = await apiClient.post("/reports/export/", {
    export_format: exportFormat,
  });
  return response.data;
};
