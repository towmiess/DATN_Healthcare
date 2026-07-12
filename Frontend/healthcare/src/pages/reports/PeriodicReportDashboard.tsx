import React, { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  CalendarDays,
  CheckCircle2,
  FilePlus2,
  FileSpreadsheet,
  FileText,
  HeartPulse,
  Info,
  LineChart,
  Loader2,
  Save,
  Target,
  Upload,
  X,
} from "lucide-react";
import {
  exportPeriodicReport,
  getReportDashboard,
  ReportDashboardData,
  saveReportDraft,
} from "@/services/reports";
import {
  createClinicalBaseline,
  ClinicalBaselineExtraction,
  extractClinicalBaseline,
} from "@/services/clinical";
import "./PeriodicReportDashboard.scss";

type PeriodType = "weekly" | "monthly";
type GlucoseUnit = "mg_dl" | "mmol_l";

type TrendPoint = {
  label: string;
  timestamp?: string;
  glucose: number;
};

type Metric = {
  label: string;
  value: string;
  delta: string;
  tone: "good" | "warning" | "danger" | "neutral";
  icon: React.ReactNode;
  detail?: string;
  progress?: number;
};

const glucoseConversionFactor = 18;
const glucoseUnitLabels: Record<GlucoseUnit, string> = {
  mg_dl: "mg/dL",
  mmol_l: "mmol/L",
};

const localizeTextMap: Record<string, string> = {
  "canh bao nguy co": "Cảnh báo nguy cơ",
  "da luu": "Đã lưu",
  "duong huyet trung binh": "Đường huyết trung bình",
  "thang": "Tháng",
  "tuan": "Tuần",
};

const normalizeTextKey = (value: string) =>
  value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .trim()
    .toLowerCase();

const localizeReportText = (value: string) => {
  if (!value || value === "--") return value;

  const localized = localizeTextMap[normalizeTextKey(value)];
  if (localized) return localized;

  return value.replace(/\blan\b/gi, "lần");
};

const formatNumber = (value: number, fractionDigits = 1) => {
  const rounded = Number(value.toFixed(fractionDigits));
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(fractionDigits);
};

const glucoseMgDlToDisplayValue = (value: number, unit: GlucoseUnit) =>
  unit === "mg_dl" ? value : value / glucoseConversionFactor;

const formatGlucoseValue = (value: number, unit: GlucoseUnit) =>
  `${formatNumber(glucoseMgDlToDisplayValue(value, unit), 1)} ${glucoseUnitLabels[unit]}`;

const parseGlucoseMgDl = (value: string) => {
  const match = value.match(/-?\d+(?:[.,]\d+)?/);
  if (!match) return null;

  const numericValue = Number(match[0].replace(",", "."));
  if (!Number.isFinite(numericValue)) return null;

  return /mmol\s*\/?\s*l/i.test(value) ? numericValue * glucoseConversionFactor : numericValue;
};

const isGlucoseLabel = (label: string) => {
  const normalized = normalizeTextKey(label);
  return normalized.includes("duong huyet") || normalized.includes("glucose");
};

const getMetrics = (periodType: PeriodType): Metric[] => [
  {
    label: periodType === "weekly" ? "Đường huyết tuần" : "Đường huyết tháng",
    value: "--",
    delta: "--",
    tone: "neutral",
    icon: <Activity size={18} />,
  },
  {
    label: "Điểm kiểm soát nguy cơ",
    value: "--",
    delta: "--",
    tone: "neutral",
    icon: <HeartPulse size={18} />,
  },
  {
    label: "BMI",
    value: "--",
    delta: "--",
    tone: "neutral",
    icon: <Target size={18} />,
  },
  {
    label: "Cảnh báo",
    value: "--",
    delta: "--",
    tone: "neutral",
    icon: <AlertTriangle size={18} />,
  },
];

const buildChartPath = (points: TrendPoint[], referenceValues: number[] = []) => {
  const leftPadding = 48;
  const rightPadding = 24;
  const height = 190;
  const pointSpacing = 76;
  const width = Math.max(640, leftPadding + rightPadding + (points.length - 1) * pointSpacing);
  const values = [...points.map((point) => point.glucose), ...referenceValues];
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const spread = maxValue - minValue;
  const padding = Math.max(spread * 0.18, maxValue < 40 ? 0.5 : 10);
  const min = minValue - padding;
  const max = maxValue + padding;
  const plotWidth = width - leftPadding - rightPadding;
  const stepX = points.length > 1 ? plotWidth / (points.length - 1) : 0;
  const range = Math.max(1, max - min);

  const coords = points.map((point, index) => {
    const x = points.length === 1 ? width / 2 : leftPadding + index * stepX;
    const y = height - ((point.glucose - min) / range) * height;
    return { x, y, ...point };
  });

  const line = coords
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(" ");

  const area = `${line} L ${width - rightPadding} ${height} L ${leftPadding} ${height} Z`;

  const gridLines = [0, 1, 2, 3].map((index) => {
    const ratio = index / 3;
    return {
      y: height - ratio * height,
      value: min + ratio * range,
    };
  });

  return { coords, gridLines, leftPadding, line, area, width, height, rightPadding, min, range };
};

const splitTrendLabel = (label: string) => {
  const [dateLabel, timeLabel] = label.split(/\s+/, 2);
  return { dateLabel, timeLabel };
};

const formatRecordedDate = (value: string | null) => {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString("vi-VN");
};

const PeriodicReportDashboard: React.FC = () => {
  const [periodType, setPeriodType] = useState<PeriodType>("weekly");
  const [glucoseUnit, setGlucoseUnit] = useState<GlucoseUnit>("mg_dl");
  const [dashboardData, setDashboardData] = useState<ReportDashboardData | null>(null);
  const [isDashboardLoading, setIsDashboardLoading] = useState(true);
  const [dashboardLoadError, setDashboardLoadError] = useState(false);
  const [exportingFormat, setExportingFormat] = useState<"PDF" | "CSV" | null>(null);
  const [exportMessage, setExportMessage] = useState("");
  const [isSavingDraft, setIsSavingDraft] = useState(false);
  const [draftMessage, setDraftMessage] = useState("");
  const [showBaselineDialog, setShowBaselineDialog] = useState(false);
  const [baselineFile, setBaselineFile] = useState<File | null>(null);
  const [baselineExtraction, setBaselineExtraction] = useState<ClinicalBaselineExtraction | null>(null);
  const [isExtractingBaseline, setIsExtractingBaseline] = useState(false);
  const [isSavingBaseline, setIsSavingBaseline] = useState(false);
  const [baselineMessage, setBaselineMessage] = useState("");
  const [selectedTrackingKey, setSelectedTrackingKey] = useState("fasting_glucose_mg_dl");
  const trend = useMemo(() => dashboardData?.trend ?? [], [dashboardData]);
  const displayTrend = useMemo(
    () =>
      trend.map((point) => ({
        ...point,
        glucose: glucoseMgDlToDisplayValue(point.glucose, glucoseUnit),
      })),
    [glucoseUnit, trend]
  );
  const baselineGlucoseMgDl = dashboardData?.baseline.values?.fasting_glucose_mg_dl?.value;
  const displayBaselineGlucose =
    baselineGlucoseMgDl === undefined
      ? undefined
      : glucoseMgDlToDisplayValue(baselineGlucoseMgDl, glucoseUnit);
  const chart = useMemo(
    () =>
      displayTrend.length
        ? buildChartPath(
            displayTrend,
            displayBaselineGlucose === undefined ? [] : [displayBaselineGlucose]
          )
        : null,
    [displayBaselineGlucose, displayTrend]
  );
  const metrics = getMetrics(periodType);
  const activeComparisonRows = useMemo(
    () => dashboardData?.comparison ?? [],
    [dashboardData]
  );
  const displayComparisonRows = useMemo(
    () =>
      activeComparisonRows.map((row) => {
        const label = localizeReportText(row.label);
        const shouldConvertGlucose = isGlucoseLabel(row.label);
        const currentGlucose = shouldConvertGlucose ? parseGlucoseMgDl(row.current) : null;
        const previousGlucose = shouldConvertGlucose ? parseGlucoseMgDl(row.previous) : null;

        return {
          ...row,
          label,
          current:
            shouldConvertGlucose && currentGlucose !== null
              ? formatGlucoseValue(currentGlucose, glucoseUnit)
              : localizeReportText(row.current),
          previous:
            shouldConvertGlucose && previousGlucose !== null
              ? formatGlucoseValue(previousGlucose, glucoseUnit)
              : localizeReportText(row.previous),
        };
      }),
    [activeComparisonRows, glucoseUnit]
  );
  const activeAchievements = dashboardData?.achievements ?? [];
  const activeIssues = dashboardData?.issues ?? [];
  const activeReportHistory = dashboardData?.history ?? [];
  const dataQuality = dashboardData?.data_quality;
  const activeBaseline = dashboardData?.baseline;
  const trackingMetrics = dashboardData?.baseline_tracking ?? [];
  const selectedTrackingMetric =
    trackingMetrics.find((metric) => metric.key === selectedTrackingKey) ?? trackingMetrics[0];
  const trackingPoints = useMemo(
    () =>
      (selectedTrackingMetric?.points ?? []).map((point) => ({
        label: point.label,
        timestamp: point.timestamp,
        glucose: point.value,
      })),
    [selectedTrackingMetric]
  );
  const trackingChart = useMemo(
    () =>
      trackingPoints.length && selectedTrackingMetric
        ? buildChartPath(trackingPoints, [selectedTrackingMetric.baseline_value])
        : null,
    [selectedTrackingMetric, trackingPoints]
  );
  const clinicalMetrics = dataQuality
    ? [
        {
          key: "hba1c",
          label: "HbA1c",
          value: dataQuality.clinical_metrics.hba1c.available
            ? `${formatNumber(dataQuality.clinical_metrics.hba1c.primary_value ?? 0, 2)}%`
            : "Chưa có",
          detail: dataQuality.clinical_metrics.hba1c.available
            ? `${
                dataQuality.clinical_metrics.hba1c.source === "HOSPITAL_LAB"
                  ? dataQuality.clinical_metrics.hba1c.provider_name ?? "Xét nghiệm bệnh viện"
                  : "Dữ liệu chẩn đoán"
              } · ${formatRecordedDate(dataQuality.clinical_metrics.hba1c.recorded_at)}`
            : "Cần kết quả xét nghiệm thực tế",
          available: dataQuality.clinical_metrics.hba1c.available,
        },
        {
          key: "insulin",
          label: "Insulin",
          value: dataQuality.clinical_metrics.insulin.available
            ? `${formatNumber(dataQuality.clinical_metrics.insulin.primary_value ?? 0, 2)} uU/mL`
            : "Chưa có",
          detail: dataQuality.clinical_metrics.insulin.available
            ? `${formatNumber(dataQuality.clinical_metrics.insulin.secondary_value ?? 0, 2)} pmol/L`
            : "Không hiển thị giá trị mặc định",
          available: dataQuality.clinical_metrics.insulin.available,
        },
        {
          key: "cholesterol",
          label: "Cholesterol",
          value: dataQuality.clinical_metrics.cholesterol.available
            ? `${formatNumber(dataQuality.clinical_metrics.cholesterol.primary_value ?? 0, 2)} mg/dL`
            : "Chưa có",
          detail: dataQuality.clinical_metrics.cholesterol.available
            ? `${formatNumber(dataQuality.clinical_metrics.cholesterol.secondary_value ?? 0, 2)} mmol/L`
            : "Không hiển thị giá trị mặc định",
          available: dataQuality.clinical_metrics.cholesterol.available,
        },
      ]
    : [];

  if (dashboardData?.has_data && dashboardData.overview) {
    metrics[0].value = formatGlucoseValue(dashboardData.overview.avg_glucose, glucoseUnit);
    metrics[1].value = `${dashboardData.overview.health_score}/100`;
    metrics[1].detail = dashboardData.overview.score_label;
    metrics[1].progress = dashboardData.overview.health_score;
    metrics[2].value = `${dashboardData.overview.bmi}`;
    metrics[3].value = `${dashboardData.overview.alerts} lần`;
    metrics.forEach((metric, index) => {
      const comparison = activeComparisonRows[index];
      if (!comparison || comparison.delta === "--") {
        metric.delta = "--";
        metric.tone = "neutral";
        return;
      }
      metric.delta = comparison.delta;
      metric.tone = comparison.good ? "good" : "warning";
    });
  }

  useEffect(() => {
    let isMounted = true;
    setIsDashboardLoading(true);
    setDashboardLoadError(false);

    getReportDashboard(periodType)
      .then((data) => {
        if (isMounted) setDashboardData(data);
      })
      .catch(() => {
        if (isMounted) {
          setDashboardData(null);
          setDashboardLoadError(true);
        }
      })
      .finally(() => {
        if (isMounted) setIsDashboardLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [periodType]);

  const handleExport = async (format: "PDF" | "CSV") => {
    setExportingFormat(format);
    setExportMessage("");
    try {
      const { blob, filename } = await exportPeriodicReport(format, periodType);
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = objectUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);
      setExportMessage(`Đã tạo báo cáo ${format} từ dữ liệu của kỳ đang chọn.`);
    } catch {
      setExportMessage("Không thể xuất báo cáo. Hãy đảm bảo kỳ đang chọn đã có dữ liệu.");
    } finally {
      setExportingFormat(null);
    }
  };

  const handleSaveDraft = async () => {
    setIsSavingDraft(true);
    setDraftMessage("");
    try {
      await saveReportDraft(periodType);
      setDraftMessage("Đã lưu bản nháp có cấu trúc cho kỳ đang chọn.");
    } catch {
      setDraftMessage("Không thể lưu bản nháp. Vui lòng thử lại.");
    } finally {
      setIsSavingDraft(false);
    }
  };

  const handleBaselineFile = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    event.target.value = "";
    if (!file) return;

    setBaselineFile(file);
    setBaselineExtraction(null);
    setIsExtractingBaseline(true);
    setBaselineMessage("Đang đọc hồ sơ bằng Google Vision...");
    try {
      const extraction = await extractClinicalBaseline(file);
      const fallbackDate = new Date().toISOString();
      setBaselineExtraction({
        ...extraction,
        metadata: {
          ...extraction.metadata,
          provider_name: extraction.metadata.provider_name || "Cơ sở xét nghiệm",
          sampled_at: extraction.metadata.sampled_at || fallbackDate,
        },
      });
      setBaselineMessage(
        `Đã nhận diện ${extraction.observations.length + extraction.results.length} chỉ số. Hãy kiểm tra trước khi xác nhận.`
      );
    } catch (error) {
      setBaselineMessage(
        error instanceof Error ? error.message : "Không thể đọc hồ sơ xét nghiệm."
      );
    } finally {
      setIsExtractingBaseline(false);
    }
  };

  const updateBaselineMetadata = (
    key: "provider_name" | "sampled_at" | "reported_at",
    value: string
  ) => {
    setBaselineExtraction((current) =>
      current
        ? {
            ...current,
            metadata: { ...current.metadata, [key]: value || null },
          }
        : current
    );
  };

  const updateBaselineCandidateValue = (
    group: "observations" | "results",
    index: number,
    value: string
  ) => {
    const numericValue = Number(value);
    setBaselineExtraction((current) => {
      if (!current) return current;
      const candidates = current[group].map((candidate, candidateIndex) =>
        candidateIndex === index
          ? {
              ...candidate,
              value: Number.isFinite(numericValue) ? numericValue : 0,
              canonical_value: Number.isFinite(numericValue) ? numericValue : 0,
            }
          : candidate
      );
      return { ...current, [group]: candidates };
    });
  };

  const closeBaselineDialog = () => {
    setShowBaselineDialog(false);
    setBaselineFile(null);
    setBaselineExtraction(null);
    setBaselineMessage("");
  };

  const handleConfirmBaseline = async () => {
    if (!baselineExtraction?.metadata.sampled_at) {
      setBaselineMessage("Vui lòng xác nhận ngày lấy mẫu.");
      return;
    }
    setIsSavingBaseline(true);
    setBaselineMessage("Đang lưu mốc xét nghiệm...");
    try {
      await createClinicalBaseline(baselineFile, baselineExtraction);
      const refreshed = await getReportDashboard(periodType);
      setDashboardData(refreshed);
      closeBaselineDialog();
    } catch (error) {
      setBaselineMessage(
        error instanceof Error ? error.message : "Không thể lưu mốc xét nghiệm."
      );
    } finally {
      setIsSavingBaseline(false);
    }
  };

  return (
    <section className="report-page" aria-labelledby="report-title">
      <div className="report-page__header">
        <div>
          <p className="report-page__eyebrow">Periodic Report</p>
          <h1 id="report-title">Báo cáo sức khỏe định kỳ</h1>
        </div>

        <div className="report-page__toolbar">
          <button
            type="button"
            className="report-page__add-baseline"
            onClick={() => setShowBaselineDialog(true)}
          >
            <FilePlus2 size={16} />
            <span>Thêm hồ sơ</span>
          </button>
          <div className="report-page__actions" role="tablist" aria-label="Kỳ báo cáo">
            <button
              type="button"
              className={`report-page__tab${periodType === "weekly" ? " report-page__tab--active" : ""}`}
              onClick={() => setPeriodType("weekly")}
            >
              <CalendarDays size={16} />
              <span>Tuần</span>
            </button>
            <button
              type="button"
              className={`report-page__tab${periodType === "monthly" ? " report-page__tab--active" : ""}`}
              onClick={() => setPeriodType("monthly")}
            >
              <LineChart size={16} />
              <span>Tháng</span>
            </button>
          </div>
        </div>
      </div>

      <section className="report-baseline-summary" aria-labelledby="baseline-summary-title">
        <div>
          <p className="report-page__eyebrow">Clinical Baseline</p>
          <h2 id="baseline-summary-title">Mốc xét nghiệm đang sử dụng</h2>
          <span>
            {activeBaseline?.has_baseline
              ? `${activeBaseline.provider_name || activeBaseline.label} · ${formatRecordedDate(activeBaseline.effective_at ?? null)}`
              : "Chưa có hồ sơ bệnh viện được xác nhận làm mốc."}
          </span>
        </div>
        {activeBaseline?.has_baseline ? (
          <div className="report-baseline-summary__values">
            {Object.values(activeBaseline.values ?? {})
              .filter(
                (value, index, values) =>
                  values.findIndex((item) => item.code === value.code) === index
              )
              .slice(0, 6)
              .map((value) => (
                <span key={value.code}>
                  {value.label} <strong>{formatNumber(value.value, 2)} {value.unit}</strong>
                </span>
              ))}
          </div>
        ) : (
          <button type="button" onClick={() => setShowBaselineDialog(true)}>
            <Upload size={16} />
            <span>Tải hồ sơ đầu tiên</span>
          </button>
        )}
      </section>

      <div className="report-metrics">
        {metrics.map((metric) => (
          <article className={`report-metric report-metric--${metric.tone}`} key={metric.label}>
            <div className="report-metric__icon">{metric.icon}</div>
            <div>
              <p>{metric.label}</p>
              <strong>{metric.value}</strong>
              {metric.progress !== undefined && (
                <div
                  className="report-metric__progress"
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={metric.progress}
                >
                  <i style={{ width: `${Math.max(0, Math.min(100, metric.progress))}%` }} />
                </div>
              )}
              {metric.detail && <small className="report-metric__detail">{metric.detail}</small>}
              <span>
                {metric.delta === "--" ? (
                  "Chưa có dữ liệu kỳ trước"
                ) : (
                  <>
                    {metric.delta.startsWith("-") ? <ArrowDownRight size={14} /> : <ArrowUpRight size={14} />}
                    {metric.delta} so với kỳ trước
                  </>
                )}
              </span>
            </div>
          </article>
        ))}
      </div>

      {dataQuality && dashboardData?.has_data && (
        <section className="report-data-quality" aria-labelledby="data-quality-title">
          <div className="report-data-quality__summary">
            <div>
              <p className="report-page__eyebrow">Data quality</p>
              <h2 id="data-quality-title">Độ đầy đủ dữ liệu</h2>
            </div>
            <strong>{dataQuality.coverage_percent}%</strong>
            <div className="report-data-quality__bar" aria-hidden="true">
              <i style={{ width: `${dataQuality.coverage_percent}%` }} />
            </div>
            <span>
              {dataQuality.completed}/{dataQuality.total} nhóm chỉ số có dữ liệu thật hoặc được tính từ dữ liệu thật
            </span>
          </div>

          <div className="report-data-quality__metrics">
            {clinicalMetrics.map((metric) => (
              <div
                className={`report-data-quality__metric${
                  metric.available ? " is-available" : ""
                }`}
                key={metric.key}
              >
                <span>{metric.label}</span>
                <strong>{metric.value}</strong>
                <small>{metric.detail}</small>
              </div>
            ))}
          </div>

          {dataQuality.missing_groups.length > 0 && (
            <p className="report-data-quality__notice">
              <Info size={16} />
              <span>Đang thiếu: {dataQuality.missing_groups.join(", ")}.</span>
            </p>
          )}
        </section>
      )}

      {activeBaseline?.has_baseline && (
        <section className="report-baseline-tracking" aria-labelledby="baseline-tracking-title">
          <div className="report-baseline-tracking__header">
            <div>
              <p className="report-page__eyebrow">Baseline Tracking</p>
              <h2 id="baseline-tracking-title">Biến thiên so với chỉ số gốc</h2>
            </div>
            {trackingMetrics.length > 0 && (
              <select
                value={selectedTrackingMetric?.key ?? ""}
                onChange={(event) => setSelectedTrackingKey(event.target.value)}
                aria-label="Chỉ số cần theo dõi"
              >
                {trackingMetrics.map((metric) => (
                  <option key={metric.key} value={metric.key}>{metric.label}</option>
                ))}
              </select>
            )}
          </div>

          {selectedTrackingMetric ? (
            <>
              <div className="report-baseline-tracking__summary">
                <span>Chỉ số gốc <strong>{formatNumber(selectedTrackingMetric.baseline_value, 2)} {selectedTrackingMetric.unit}</strong></span>
                <span>Gần nhất <strong>{selectedTrackingMetric.current_value === null ? "Chưa có" : `${formatNumber(selectedTrackingMetric.current_value, 2)} ${selectedTrackingMetric.unit}`}</strong></span>
                <span>Chênh lệch <strong>{selectedTrackingMetric.delta === null ? "--" : `${selectedTrackingMetric.delta > 0 ? "+" : ""}${formatNumber(selectedTrackingMetric.delta, 2)} ${selectedTrackingMetric.unit}`}</strong></span>
              </div>
              <div className="report-baseline-tracking__chart">
                {trackingChart ? (
                  <svg viewBox={`0 0 ${trackingChart.width} ${trackingChart.height + 48}`} style={{ minWidth: `${trackingChart.width}px` }}>
                    {trackingChart.gridLines.map((gridLine) => (
                      <g key={gridLine.y} className="report-chart__grid">
                        <line x1={trackingChart.leftPadding} x2={trackingChart.width - trackingChart.rightPadding} y1={gridLine.y} y2={gridLine.y} />
                        <text x={trackingChart.leftPadding - 10} y={gridLine.y + 4} textAnchor="end">{formatNumber(gridLine.value, 1)}</text>
                      </g>
                    ))}
                    <line
                      className="report-chart__baseline"
                      x1={trackingChart.leftPadding}
                      x2={trackingChart.width - trackingChart.rightPadding}
                      y1={trackingChart.height - ((selectedTrackingMetric.baseline_value - trackingChart.min) / trackingChart.range) * trackingChart.height}
                      y2={trackingChart.height - ((selectedTrackingMetric.baseline_value - trackingChart.min) / trackingChart.range) * trackingChart.height}
                    />
                    <path className="report-chart__line" d={trackingChart.line} />
                    {trackingChart.coords.map((point, index) => (
                      <g key={point.timestamp ?? index}>
                        <circle className="report-chart__dot" cx={point.x} cy={point.y} r="5" />
                        <text x={point.x} y={Math.max(14, point.y - 12)} textAnchor="middle" className="report-chart__value">{formatNumber(point.glucose, 2)}</text>
                        <text x={point.x} y={trackingChart.height + 22} textAnchor="middle" className="report-chart__axis-label">{splitTrendLabel(point.label).dateLabel}</text>
                      </g>
                    ))}
                  </svg>
                ) : (
                  <div className="report-chart__empty">Chưa có lần đo mới sau mốc xét nghiệm này.</div>
                )}
              </div>
            </>
          ) : (
            <div className="report-chart__empty">Hồ sơ chưa có chỉ số phù hợp để theo dõi.</div>
          )}

          <div className="report-baseline-tracking__table">
            {trackingMetrics.map((metric) => (
              <button type="button" key={metric.key} onClick={() => setSelectedTrackingKey(metric.key)}>
                <span>{metric.label}</span>
                <small>{formatNumber(metric.baseline_value, 2)} {metric.unit}</small>
                <strong>{metric.current_value === null ? "Chưa có lần đo" : `${formatNumber(metric.current_value, 2)} ${metric.unit}`}</strong>
                <em>{metric.delta_percent === null ? "--" : `${metric.delta_percent > 0 ? "+" : ""}${formatNumber(metric.delta_percent, 1)}%`}</em>
              </button>
            ))}
          </div>
        </section>
      )}

      <div className="report-grid">
        <section className="report-panel report-panel--trend">
          <div className="report-panel__header">
            <div>
              <p className="report-page__eyebrow">Glucose Trend</p>
              <h2>Xu hướng đường huyết</h2>
            </div>
            <div className="report-unit-toggle" role="group" aria-label="Đơn vị đường huyết">
              {(["mg_dl", "mmol_l"] as const).map((unit) => (
                <button
                  type="button"
                  key={unit}
                  className={`report-unit-toggle__button${
                    glucoseUnit === unit ? " report-unit-toggle__button--active" : ""
                  }`}
                  aria-pressed={glucoseUnit === unit}
                  onClick={() => setGlucoseUnit(unit)}
                >
                  {glucoseUnitLabels[unit]}
                </button>
              ))}
            </div>
          </div>

          <div className="report-chart" aria-label="Biểu đồ xu hướng đường huyết">
            {chart ? (
              <svg
                viewBox={`0 0 ${chart.width} ${chart.height + 52}`}
                role="img"
                style={{ minWidth: `${chart.width}px` }}
              >
                {chart.gridLines.map((gridLine) => (
                  <g key={gridLine.y} className="report-chart__grid">
                    <line
                      x1={chart.leftPadding}
                      x2={chart.width - chart.rightPadding}
                      y1={gridLine.y}
                      y2={gridLine.y}
                    />
                    <text x={chart.leftPadding - 10} y={gridLine.y + 4} textAnchor="end">
                      {formatNumber(gridLine.value, 1)}
                    </text>
                  </g>
                ))}
                {displayBaselineGlucose !== undefined && (
                  <g>
                    <line
                      className="report-chart__baseline"
                      x1={chart.leftPadding}
                      x2={chart.width - chart.rightPadding}
                      y1={chart.height - ((displayBaselineGlucose - chart.min) / chart.range) * chart.height}
                      y2={chart.height - ((displayBaselineGlucose - chart.min) / chart.range) * chart.height}
                    />
                    <text
                      className="report-chart__baseline-label"
                      x={chart.width - chart.rightPadding}
                      y={chart.height - ((displayBaselineGlucose - chart.min) / chart.range) * chart.height - 6}
                      textAnchor="end"
                    >
                      Mốc {formatNumber(displayBaselineGlucose, 1)} {glucoseUnitLabels[glucoseUnit]}
                    </text>
                  </g>
                )}
                <path className="report-chart__area" d={chart.area} />
                <path className="report-chart__line" d={chart.line} />
                {chart.coords.map((point, index) => {
                  const { dateLabel, timeLabel } = splitTrendLabel(point.label);
                  return (
                    <g key={point.timestamp ?? `${point.label}-${index}`}>
                      <circle className="report-chart__dot" cx={point.x} cy={point.y} r="5" />
                      <text
                        x={point.x}
                        y={chart.height + 22}
                        textAnchor="middle"
                        className="report-chart__axis-label"
                      >
                        <tspan x={point.x}>{dateLabel}</tspan>
                        {timeLabel && <tspan x={point.x} dy="14">{timeLabel}</tspan>}
                      </text>
                      <text
                        x={point.x}
                        y={Math.max(14, point.y - 12)}
                        textAnchor="middle"
                        className="report-chart__value"
                      >
                        {formatNumber(point.glucose, 1)}
                      </text>
                    </g>
                  );
                })}
              </svg>
            ) : (
              <div className="report-chart__empty">
                {isDashboardLoading
                  ? "Đang tải dữ liệu báo cáo..."
                  : dashboardLoadError
                    ? "Không thể tải dữ liệu báo cáo. Vui lòng thử lại."
                    : "Chưa có dữ liệu đường huyết cho kỳ này."}
              </div>
            )}
          </div>
        </section>

        <section className="report-panel">
          <div className="report-panel__header">
            <div>
              <p className="report-page__eyebrow">Period Comparison</p>
              <h2>So sánh kỳ trước</h2>
            </div>
            <button type="button" className="report-panel__ghost">
              <ArrowDownRight size={15} />
              <span>Delta %</span>
            </button>
          </div>

          <div className="report-comparison">
            {displayComparisonRows.length ? (
              displayComparisonRows.map((row) => (
                <div className="report-comparison__row" key={row.label}>
                  <span>{row.label}</span>
                  <strong>{row.current}</strong>
                  <small>{row.previous}</small>
                  <em className={row.good ? "is-good" : "is-warning"}>{row.delta}</em>
                </div>
              ))
            ) : (
              <div className="report-chart__empty">Chưa có dữ liệu để so sánh kỳ trước.</div>
            )}
          </div>
        </section>

        <section className="report-panel">
          <div className="report-panel__header">
            <div>
              <p className="report-page__eyebrow">Achievements</p>
              <h2>Thành tựu</h2>
            </div>
            <CheckCircle2 size={21} className="report-panel__header-icon report-panel__header-icon--good" />
          </div>

          <div className="report-list">
            {activeAchievements.length ? (
              activeAchievements.map((item) => (
                <div className="report-list__item" key={item}>
                  <CheckCircle2 size={17} />
                  <span>{item}</span>
                </div>
              ))
            ) : (
              <div className="report-chart__empty">Chưa có thành tựu được ghi nhận.</div>
            )}
          </div>
        </section>

        <section className="report-panel">
          <div className="report-panel__header">
            <div>
              <p className="report-page__eyebrow">Issues</p>
              <h2>Vấn đề cần cải thiện</h2>
            </div>
            <AlertTriangle size={21} className="report-panel__header-icon report-panel__header-icon--warning" />
          </div>

          <div className="report-list report-list--issues">
            {activeIssues.length ? (
              activeIssues.map((item) => (
                <div className="report-list__item" key={item}>
                  <AlertTriangle size={17} />
                  <span>{item}</span>
                </div>
              ))
            ) : (
              <div className="report-chart__empty">Chưa có vấn đề nổi bật cho kỳ này.</div>
            )}
          </div>
        </section>
      </div>

      <section className="report-export">
        <div>
          <p className="report-page__eyebrow">Report Export</p>
          <h2>Xuất báo cáo</h2>
        </div>

        <div className="report-export__actions">
          <button
            type="button"
            onClick={() => void handleExport("PDF")}
            disabled={exportingFormat !== null}
          >
            <FileText size={17} />
            <span>{exportingFormat === "PDF" ? "Đang tạo PDF" : "PDF"}</span>
          </button>
          <button
            type="button"
            onClick={() => void handleExport("CSV")}
            disabled={exportingFormat !== null}
          >
            <FileSpreadsheet size={17} />
            <span>{exportingFormat === "CSV" ? "Đang tạo CSV" : "CSV"}</span>
          </button>
        </div>
        {exportMessage && <p className="report-export__message">{exportMessage}</p>}
      </section>

      <section className="report-draft" aria-labelledby="report-draft-title">
        <div>
          <p className="report-page__eyebrow">Draft</p>
          <h2 id="report-draft-title">Lưu tiến trình báo cáo</h2>
          <span>Bản nháp được lưu trong hệ thống và có thể cập nhật lại, không tạo file tải xuống.</span>
        </div>
        <button type="button" onClick={() => void handleSaveDraft()} disabled={isSavingDraft}>
          <Save size={17} />
          <span>{isSavingDraft ? "Đang lưu" : "Lưu bản nháp"}</span>
        </button>
        {draftMessage && <p>{draftMessage}</p>}
      </section>

      <section className="report-history">
        <div className="report-history__header">
          <h2>Lịch sử báo cáo</h2>
          <span>{activeReportHistory.length} bản ghi</span>
        </div>

        <div className="report-history__table">
          {activeReportHistory.length ? (
            activeReportHistory.map((report, index) => (
              <div
                className="report-history__row"
                key={report.row_key ?? report.id ?? `${report.type}-${report.period}-${index}`}
              >
                <span>{report.period}</span>
                <strong>{localizeReportText(report.type)}</strong>
                <small>{report.score}/100</small>
                <small>{formatGlucoseValue(report.avg, glucoseUnit)}</small>
                <em>{localizeReportText(report.status)}</em>
              </div>
            ))
          ) : (
            <div className="report-chart__empty">Chưa có lịch sử báo cáo cho tài khoản này.</div>
          )}
        </div>
      </section>

      {showBaselineDialog && (
        <div className="report-baseline-dialog" role="presentation" onMouseDown={closeBaselineDialog}>
          <div
            className="report-baseline-dialog__content"
            role="dialog"
            aria-modal="true"
            aria-labelledby="baseline-dialog-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="report-baseline-dialog__header">
              <div>
                <p className="report-page__eyebrow">Clinical Record</p>
                <h2 id="baseline-dialog-title">Thêm hồ sơ xét nghiệm làm mốc</h2>
              </div>
              <button type="button" onClick={closeBaselineDialog} aria-label="Đóng">
                <X size={19} />
              </button>
            </div>

            <label className="report-baseline-dialog__upload">
              <input type="file" accept="image/jpeg,image/png,image/webp" onChange={handleBaselineFile} />
              {isExtractingBaseline ? <Loader2 size={22} className="report-spin" /> : <Upload size={22} />}
              <span>{baselineFile ? baselineFile.name : "Chọn ảnh phiếu xét nghiệm"}</span>
              <small>OCR chỉ tạo dữ liệu nháp. Chỉ số chỉ được lưu sau khi bạn xác nhận.</small>
            </label>

            {baselineMessage && <p className="report-baseline-dialog__message">{baselineMessage}</p>}

            {baselineExtraction && (
              <>
                <div className="report-baseline-dialog__metadata">
                  <label>
                    <span>Cơ sở xét nghiệm</span>
                    <input
                      value={baselineExtraction.metadata.provider_name ?? ""}
                      onChange={(event) => updateBaselineMetadata("provider_name", event.target.value)}
                    />
                  </label>
                  <label>
                    <span>Ngày lấy mẫu</span>
                    <input
                      type="date"
                      value={String(baselineExtraction.metadata.sampled_at ?? "").slice(0, 10)}
                      onChange={(event) => updateBaselineMetadata("sampled_at", `${event.target.value}T00:00:00+07:00`)}
                    />
                  </label>
                  <label>
                    <span>Ngày trả kết quả</span>
                    <input
                      type="date"
                      value={String(baselineExtraction.metadata.reported_at ?? "").slice(0, 10)}
                      onChange={(event) => updateBaselineMetadata("reported_at", event.target.value ? `${event.target.value}T00:00:00+07:00` : "")}
                    />
                  </label>
                </div>

                {(["observations", "results"] as const).map((group) => (
                  <div className="report-baseline-dialog__group" key={group}>
                    <h3>{group === "observations" ? "Nhân trắc và dấu hiệu sinh tồn" : "Kết quả xét nghiệm"}</h3>
                    <div className="report-baseline-dialog__table">
                      {baselineExtraction[group].map((candidate, index) => (
                        <label key={candidate.observation_code ?? candidate.test_code ?? index}>
                          <span>{candidate.observation_name ?? candidate.test_name}</span>
                          <input
                            type="number"
                            step="any"
                            value={candidate.value}
                            onChange={(event) => updateBaselineCandidateValue(group, index, event.target.value)}
                          />
                          <small>{candidate.unit}</small>
                          <em>{candidate.reference_text || "Không có khoảng tham chiếu"}</em>
                        </label>
                      ))}
                    </div>
                  </div>
                ))}

                <div className="report-baseline-dialog__actions">
                  <button type="button" onClick={closeBaselineDialog}>Hủy</button>
                  <button
                    type="button"
                    className="is-primary"
                    onClick={() => void handleConfirmBaseline()}
                    disabled={isSavingBaseline}
                  >
                    {isSavingBaseline ? <Loader2 size={17} className="report-spin" /> : <CheckCircle2 size={17} />}
                    <span>{isSavingBaseline ? "Đang lưu" : "Xác nhận và đặt làm mốc"}</span>
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </section>
  );
};

export default PeriodicReportDashboard;

