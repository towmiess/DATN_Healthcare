import React, { useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  CalendarDays,
  CheckCircle2,
  Download,
  FileSpreadsheet,
  FileText,
  HeartPulse,
  LineChart,
  Target,
} from "lucide-react";
import "./PeriodicReportDashboard.scss";

type PeriodType = "weekly" | "monthly";

type TrendPoint = {
  label: string;
  glucose: number;
};

type Metric = {
  label: string;
  value: string;
  delta: string;
  tone: "good" | "warning" | "danger" | "neutral";
  icon: React.ReactNode;
};

const weeklyTrend: TrendPoint[] = [
  { label: "T2", glucose: 142 },
  { label: "T3", glucose: 136 },
  { label: "T4", glucose: 128 },
  { label: "T5", glucose: 132 },
  { label: "T6", glucose: 124 },
  { label: "T7", glucose: 118 },
  { label: "CN", glucose: 121 },
];

const monthlyTrend: TrendPoint[] = [
  { label: "W1", glucose: 148 },
  { label: "W2", glucose: 139 },
  { label: "W3", glucose: 131 },
  { label: "W4", glucose: 124 },
];

const comparisonRows = [
  { label: "Đường huyết trung bình", current: "124 mg/dL", previous: "139 mg/dL", delta: "-10.8%", good: true },
  { label: "Health score", current: "82/100", previous: "76/100", delta: "+7.9%", good: true },
  { label: "BMI", current: "26.2", previous: "26.8", delta: "-2.2%", good: true },
  { label: "Cảnh báo nguy cơ", current: "2 lần", previous: "5 lần", delta: "-60%", good: true },
];

const achievements = [
  "Đường huyết lúc đói ổn định hơn trong 5/7 ngày gần nhất.",
  "Tần suất ghi nhận chỉ số đạt 92%, cao hơn kỳ trước.",
  "BMI và cân nặng giảm nhẹ theo đúng mục tiêu hiện tại.",
];

const issues = [
  "Có 2 lần đường huyết sau ăn vượt ngưỡng cảnh báo.",
  "Bữa tối vẫn là khoảng thời gian có biến động glucose cao nhất.",
  "Cần duy trì đo vào khung giờ cố định để báo cáo chính xác hơn.",
];

const reportHistory = [
  { period: "08/06 - 14/06", type: "Tuần", score: 82, avg: 124, status: "Sẵn sàng" },
  { period: "01/06 - 07/06", type: "Tuần", score: 76, avg: 139, status: "Đã xuất PDF" },
  { period: "Tháng 05/2026", type: "Tháng", score: 74, avg: 145, status: "Đã xuất CSV" },
];

const getMetrics = (periodType: PeriodType): Metric[] => [
  {
    label: periodType === "weekly" ? "Đường huyết tuần" : "Đường huyết tháng",
    value: periodType === "weekly" ? "124 mg/dL" : "131 mg/dL",
    delta: periodType === "weekly" ? "-10.8%" : "-6.4%",
    tone: "good",
    icon: <Activity size={18} />,
  },
  {
    label: "Health score",
    value: periodType === "weekly" ? "82/100" : "79/100",
    delta: periodType === "weekly" ? "+7.9%" : "+4.1%",
    tone: "good",
    icon: <HeartPulse size={18} />,
  },
  {
    label: "BMI",
    value: periodType === "weekly" ? "26.2" : "26.5",
    delta: periodType === "weekly" ? "-0.6" : "-0.3",
    tone: "neutral",
    icon: <Target size={18} />,
  },
  {
    label: "Cảnh báo",
    value: periodType === "weekly" ? "2 lần" : "8 lần",
    delta: periodType === "weekly" ? "-3" : "-5",
    tone: "warning",
    icon: <AlertTriangle size={18} />,
  },
];

const buildChartPath = (points: TrendPoint[]) => {
  const width = 560;
  const height = 190;
  const min = Math.min(...points.map((point) => point.glucose)) - 10;
  const max = Math.max(...points.map((point) => point.glucose)) + 10;
  const stepX = width / (points.length - 1);

  const coords = points.map((point, index) => {
    const x = index * stepX;
    const y = height - ((point.glucose - min) / (max - min)) * height;
    return { x, y, ...point };
  });

  const line = coords
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(" ");

  const area = `${line} L ${width} ${height} L 0 ${height} Z`;

  return { coords, line, area, width, height };
};

const PeriodicReportDashboard: React.FC = () => {
  const [periodType, setPeriodType] = useState<PeriodType>("weekly");
  const trend = periodType === "weekly" ? weeklyTrend : monthlyTrend;
  const chart = useMemo(() => buildChartPath(trend), [trend]);
  const metrics = getMetrics(periodType);

  return (
    <section className="report-page" aria-labelledby="report-title">
      <div className="report-page__header">
        <div>
          <p className="report-page__eyebrow">Periodic Report</p>
          <h1 id="report-title">Báo cáo sức khỏe định kỳ</h1>
        </div>

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

      <div className="report-metrics">
        {metrics.map((metric) => (
          <article className={`report-metric report-metric--${metric.tone}`} key={metric.label}>
            <div className="report-metric__icon">{metric.icon}</div>
            <div>
              <p>{metric.label}</p>
              <strong>{metric.value}</strong>
              <span>
                {metric.delta.startsWith("-") ? <ArrowDownRight size={14} /> : <ArrowUpRight size={14} />}
                {metric.delta} so với kỳ trước
              </span>
            </div>
          </article>
        ))}
      </div>

      <div className="report-grid">
        <section className="report-panel report-panel--trend">
          <div className="report-panel__header">
            <div>
              <p className="report-page__eyebrow">Glucose Trend</p>
              <h2>Xu hướng đường huyết</h2>
            </div>
            <span className="report-panel__badge">mg/dL</span>
          </div>

          <div className="report-chart" aria-label="Biểu đồ xu hướng đường huyết">
            <svg viewBox={`0 0 ${chart.width} ${chart.height + 34}`} role="img">
              <path className="report-chart__area" d={chart.area} />
              <path className="report-chart__line" d={chart.line} />
              {chart.coords.map((point) => (
                <g key={point.label}>
                  <circle className="report-chart__dot" cx={point.x} cy={point.y} r="5" />
                  <text x={point.x} y={chart.height + 26} textAnchor="middle">
                    {point.label}
                  </text>
                  <text x={point.x} y={Math.max(14, point.y - 12)} textAnchor="middle" className="report-chart__value">
                    {point.glucose}
                  </text>
                </g>
              ))}
            </svg>
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
            {comparisonRows.map((row) => (
              <div className="report-comparison__row" key={row.label}>
                <span>{row.label}</span>
                <strong>{row.current}</strong>
                <small>{row.previous}</small>
                <em className={row.good ? "is-good" : "is-warning"}>{row.delta}</em>
              </div>
            ))}
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
            {achievements.map((item) => (
              <div className="report-list__item" key={item}>
                <CheckCircle2 size={17} />
                <span>{item}</span>
              </div>
            ))}
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
            {issues.map((item) => (
              <div className="report-list__item" key={item}>
                <AlertTriangle size={17} />
                <span>{item}</span>
              </div>
            ))}
          </div>
        </section>
      </div>

      <section className="report-export">
        <div>
          <p className="report-page__eyebrow">Report Export</p>
          <h2>Xuất báo cáo</h2>
        </div>

        <div className="report-export__actions">
          <button type="button">
            <FileText size={17} />
            <span>PDF</span>
          </button>
          <button type="button">
            <FileSpreadsheet size={17} />
            <span>CSV</span>
          </button>
          <button type="button">
            <Download size={17} />
            <span>Lưu bản nháp</span>
          </button>
        </div>
      </section>

      <section className="report-history">
        <div className="report-history__header">
          <h2>Lịch sử báo cáo</h2>
          <span>{reportHistory.length} bản ghi</span>
        </div>

        <div className="report-history__table">
          {reportHistory.map((report) => (
            <div className="report-history__row" key={report.period}>
              <span>{report.period}</span>
              <strong>{report.type}</strong>
              <small>{report.score}/100</small>
              <small>{report.avg} mg/dL</small>
              <em>{report.status}</em>
            </div>
          ))}
        </div>
      </section>
    </section>
  );
};

export default PeriodicReportDashboard;
