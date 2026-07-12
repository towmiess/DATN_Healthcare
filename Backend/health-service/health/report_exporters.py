from __future__ import annotations

import csv
import io
from html import escape
from pathlib import Path
from typing import Any, Iterable

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


FIELD_EXPORTS = (
    ("sex", "Giới tính", "mã"),
    ("age_years", "Tuổi", "năm"),
    ("weight_kg", "Cân nặng", "kg"),
    ("height_cm", "Chiều cao", "cm"),
    ("bmi", "BMI", "kg/m2"),
    ("waist_cm", "Vòng eo", "cm"),
    ("hip_cm", "Vòng hông", "cm"),
    ("hba1c_percent", "HbA1c", "%"),
    ("insulin_uU_ml", "Insulin", "uU/mL"),
    ("total_cholesterol_mg_dl", "Cholesterol toàn phần", "mg/dL"),
    ("systolic_bp_mean", "Huyết áp tâm thu", "mmHg"),
    ("diastolic_bp_mean", "Huyết áp tâm trương", "mmHg"),
    ("pulse_mean", "Mạch", "bpm"),
)


def _register_fonts() -> tuple[str, str]:
    regular_candidates = (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    )
    bold_candidates = (
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("C:/Windows/Fonts/arialbd.ttf"),
    )
    regular = next((path for path in regular_candidates if path.exists()), None)
    bold = next((path for path in bold_candidates if path.exists()), None)
    if regular and bold:
        pdfmetrics.registerFont(TTFont("HealthRegular", str(regular)))
        pdfmetrics.registerFont(TTFont("HealthBold", str(bold)))
        return "HealthRegular", "HealthBold"
    return "Helvetica", "Helvetica-Bold"


def _assessment_rows(assessment: Any) -> list[dict[str, Any]]:
    if assessment is None or not isinstance(assessment.findings_json, dict):
        return []
    findings = assessment.findings_json
    normalized = findings.get("normalized_features")
    metadata = findings.get("feature_metadata")
    sources = metadata.get("field_sources") if isinstance(metadata, dict) else {}
    if not isinstance(normalized, dict):
        return []
    if not isinstance(sources, dict):
        sources = {}

    rows = []
    for key, label, unit in FIELD_EXPORTS:
        source = sources.get(key)
        if source not in {"provided", "derived"} or key not in normalized:
            continue
        rows.append(
            {
                "timestamp": assessment.created_at.isoformat(),
                "metric": label,
                "value": normalized[key],
                "unit": unit,
                "source": "NGƯỜI DÙNG/OCR" if source == "provided" else "TỰ ĐỘNG TÍNH",
            }
        )
    return rows


def build_long_rows(measurements: Iterable[Any], assessment: Any) -> list[dict[str, Any]]:
    rows = [
        {
            "timestamp": measurement.measured_at.isoformat(),
            "metric": "Glucose",
            "value": float(measurement.glucose_value),
            "unit": measurement.unit,
            "source": str(measurement.source_type),
        }
        for measurement in measurements
    ]
    rows.extend(_assessment_rows(assessment))
    return sorted(rows, key=lambda row: row["timestamp"])


def build_csv_report(measurements: Iterable[Any], assessment: Any) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=";", lineterminator="\r\n")
    writer.writerow(["timestamp", "chi_so", "gia_tri", "don_vi", "nguon"])
    for row in build_long_rows(measurements, assessment):
        writer.writerow(
            [
                row["timestamp"],
                row["metric"],
                row["value"],
                row["unit"],
                row["source"],
            ]
        )
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


class GlucoseTrendChart(Flowable):
    def __init__(self, points: list[tuple[Any, float]], font_name: str):
        super().__init__()
        self.points = points
        self.font_name = font_name
        self.width = 170 * mm
        self.height = 58 * mm

    def draw(self):
        if not self.points:
            return
        canvas = self.canv
        left = 14 * mm
        right = self.width - 5 * mm
        top = self.height - 7 * mm
        bottom = 12 * mm
        values = [value for _, value in self.points]
        minimum = min(values)
        maximum = max(values)
        padding = max((maximum - minimum) * 0.15, 5)
        minimum -= padding
        maximum += padding
        value_range = max(1, maximum - minimum)

        canvas.setFont(self.font_name, 7)
        canvas.setStrokeColor(colors.HexColor("#dbe4ee"))
        canvas.setFillColor(colors.HexColor("#64748b"))
        for index in range(4):
            ratio = index / 3
            y = bottom + ratio * (top - bottom)
            value = minimum + ratio * value_range
            canvas.line(left, y, right, y)
            canvas.drawRightString(left - 2 * mm, y - 2, f"{value:.1f}")

        coordinates = []
        for index, (timestamp, value) in enumerate(self.points):
            ratio = index / max(1, len(self.points) - 1)
            x = left + ratio * (right - left)
            y = bottom + ((value - minimum) / value_range) * (top - bottom)
            coordinates.append((x, y, timestamp, value))

        canvas.setStrokeColor(colors.HexColor("#2563eb"))
        canvas.setLineWidth(2)
        path = canvas.beginPath()
        for index, (x, y, _, _) in enumerate(coordinates):
            if index == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)
        canvas.drawPath(path)

        label_step = max(1, len(coordinates) // 7)
        for index, (x, y, timestamp, value) in enumerate(coordinates):
            canvas.setFillColor(colors.white)
            canvas.circle(x, y, 2.5, fill=1, stroke=1)
            canvas.setFillColor(colors.HexColor("#334155"))
            canvas.drawCentredString(x, y + 4, f"{value:.1f}")
            if index % label_step == 0 or index == len(coordinates) - 1:
                canvas.setFillColor(colors.HexColor("#64748b"))
                canvas.drawCentredString(x, 4 * mm, timestamp.strftime("%d/%m %H:%M"))


def build_pdf_report(report: Any, user: Any, measurements: list[Any], assessment: Any) -> bytes:
    regular_font, bold_font = _register_fonts()
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title="Báo cáo sức khỏe định kỳ",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "HealthTitle",
        parent=styles["Title"],
        fontName=bold_font,
        fontSize=18,
        leading=23,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#0f172a"),
    )
    heading_style = ParagraphStyle(
        "HealthHeading",
        parent=styles["Heading2"],
        fontName=bold_font,
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#0f766e"),
        spaceBefore=8,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "HealthBody",
        parent=styles["BodyText"],
        fontName=regular_font,
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#334155"),
    )
    small_style = ParagraphStyle(
        "HealthSmall",
        parent=body_style,
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#64748b"),
    )

    story: list[Any] = [
        Paragraph("BÁO CÁO SỨC KHỎE ĐỊNH KỲ", title_style),
        Spacer(1, 5 * mm),
    ]
    summary_data = [
        ["Người dùng", escape(str(user.full_name or user.email))],
        ["Kỳ báo cáo", f"{report.period_start:%d/%m/%Y} - {report.period_end:%d/%m/%Y}"],
        ["Đường huyết trung bình", f"{float(report.avg_glucose or 0):.1f} mg/dL"],
        ["Điểm kiểm soát nguy cơ", f"{float(report.health_score or 0):.1f}/100"],
        ["BMI", f"{float(report.bmi or 0):.1f}"],
    ]
    summary_table = Table(summary_data, colWidths=[52 * mm, 112 * mm])
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), bold_font),
                ("FONTNAME", (1, 0), (1, -1), regular_font),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f1f5f9")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.extend([summary_table, Spacer(1, 5 * mm)])

    if measurements:
        points = [(item.measured_at, float(item.glucose_value)) for item in measurements]
        story.extend(
            [
                Paragraph("Xu hướng đường huyết", heading_style),
                GlucoseTrendChart(points[-31:], regular_font),
                Spacer(1, 4 * mm),
            ]
        )

    story.append(Paragraph("Dữ liệu theo dõi và chẩn đoán", heading_style))
    detail_rows = [["Thời điểm", "Chỉ số", "Giá trị", "Đơn vị", "Nguồn"]]
    for row in build_long_rows(measurements, assessment):
        detail_rows.append(
            [
                row["timestamp"].replace("T", " ")[:16],
                row["metric"],
                str(row["value"]),
                row["unit"],
                row["source"],
            ]
        )
    detail_table = Table(
        detail_rows or [["Chưa có dữ liệu"]],
        repeatRows=1,
        colWidths=[32 * mm, 48 * mm, 22 * mm, 22 * mm, 40 * mm],
    )
    detail_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), bold_font),
                ("FONTNAME", (0, 1), (-1, -1), regular_font),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dbeafe")),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.extend([detail_table, PageBreak()])

    story.append(Paragraph("Thành tựu", heading_style))
    achievements = report.achievements_json if isinstance(report.achievements_json, list) else []
    story.extend(
        Paragraph(f"• {escape(str(item))}", body_style) for item in achievements
    )
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Vấn đề cần cải thiện", heading_style))
    issues = report.issues_json if isinstance(report.issues_json, list) else []
    story.extend(Paragraph(f"• {escape(str(item))}", body_style) for item in issues)
    story.extend(
        [
            Spacer(1, 12 * mm),
            Paragraph(
                "Báo cáo mang tính tham khảo và hỗ trợ theo dõi, không thay thế chẩn đoán hoặc chỉ định của nhân viên y tế.",
                small_style,
            ),
        ]
    )

    document.build(story)
    return output.getvalue()
