from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import requests
from django.conf import settings
from django.db.models import Avg

from .models import GlucoseMeasurement, HealthAssessment, HealthProfile, PeriodicReport


DEFAULT_FEATURES: dict[str, float] = {
    "sex": 2,
    "age_years": 45,
    "race_ethnicity": 3,
    "race_ethnicity_asian": 0,
    "weight_kg": 70,
    "height_cm": 165,
    "bmi": 25.7,
    "waist_cm": 85,
    "hip_cm": 95,
    "hba1c_percent": 5.5,
    "fasting_glucose_mg_dl": 100,
    "fasting_glucose_mmol_l": 5.6,
    "insulin_uU_ml": 9,
    "insulin_pmol_l": 54,
    "fasting_hours": 8,
    "fasting_minutes": 0,
    "total_cholesterol_mg_dl": 190,
    "total_cholesterol_mmol_l": 4.9,
    "high_blood_pressure_history": 0,
    "systolic_bp_mean": 120,
    "diastolic_bp_mean": 80,
    "pulse_mean": 72,
}


def normalize_features(payload: dict[str, Any]) -> dict[str, float]:
    features = DEFAULT_FEATURES.copy()
    for key, value in payload.items():
        if value is None or value == "":
            continue
        try:
            features[key] = float(value)
        except (TypeError, ValueError):
            continue

    weight = features.get("weight_kg")
    height = features.get("height_cm")
    sex = int(features.get("sex", 0) or 0)
    if weight and height:
        features["bmi"] = round(weight / (height / 100) ** 2, 2)

    if height and not payload.get("waist_cm"):
        if sex == 1:
            features["waist_cm"] = round(height * 0.45, 2)
        elif sex == 2:
            features["waist_cm"] = round(height * 0.4, 2)

    waist = features.get("waist_cm")
    if waist and not payload.get("hip_cm"):
        if sex == 1:
            features["hip_cm"] = round(waist / 0.9, 2)
        elif sex == 2:
            features["hip_cm"] = round(waist / 0.7, 2)

    return features


def risk_band(probability: float) -> str:
    if probability >= 0.65:
        return "DANGEROUS"
    if probability >= 0.35:
        return "WARNING"
    return "SAFE"


def _clamp(value: float) -> float:
    return max(0.02, min(0.96, value))


def _target_result(probability: float, positive_label: str, negative_label: str) -> dict[str, Any]:
    probability = _clamp(probability)
    prediction = 1 if probability >= 0.5 else 0
    return {
        "prediction": prediction,
        "label": positive_label if prediction else negative_label,
        "positive_probability": round(probability, 4),
    }


def rule_based_prediction(features: dict[str, float]) -> dict[str, Any]:
    bmi = features["bmi"]
    age = features["age_years"]
    waist = features["waist_cm"]
    hba1c = features["hba1c_percent"]
    glucose = features["fasting_glucose_mg_dl"]
    systolic = features["systolic_bp_mean"]
    diastolic = features["diastolic_bp_mean"]
    cholesterol = features["total_cholesterol_mg_dl"]
    bp_history = features["high_blood_pressure_history"]

    diabetes_score = 0.12
    diabetes_score += max(0, bmi - 24) * 0.025
    diabetes_score += max(0, waist - 85) * 0.008
    diabetes_score += max(0, hba1c - 5.6) * 0.22
    diabetes_score += max(0, glucose - 100) * 0.006
    diabetes_score += max(0, age - 45) * 0.004

    cardio_score = 0.10
    cardio_score += max(0, systolic - 120) * 0.009
    cardio_score += max(0, diastolic - 80) * 0.010
    cardio_score += max(0, cholesterol - 200) * 0.004
    cardio_score += max(0, bmi - 27) * 0.020
    cardio_score += bp_history * 0.18
    cardio_score += max(0, age - 50) * 0.006

    stroke_score = 0.06
    stroke_score += max(0, systolic - 130) * 0.010
    stroke_score += max(0, diastolic - 85) * 0.009
    stroke_score += bp_history * 0.20
    stroke_score += max(0, age - 55) * 0.008
    stroke_score += max(0, glucose - 125) * 0.004

    return {
        "diabetes": _target_result(diabetes_score, "Elevated diabetes risk", "No diabetes risk signal"),
        "cardio": _target_result(cardio_score, "Elevated cardiovascular risk", "No cardiovascular risk signal"),
        "stroke": _target_result(stroke_score, "Elevated stroke risk", "No stroke risk signal"),
    }


def predict(features: dict[str, float]) -> dict[str, Any]:
    model_url = settings.MODEL_API_URL.strip().rstrip("/")
    if model_url:
        try:
            response = requests.post(f"{model_url}/predict/all", json=features, timeout=6)
            response.raise_for_status()
            data = response.json()
            if all(key in data for key in ("diabetes", "cardio", "stroke")):
                return data
        except requests.RequestException:
            pass

    return rule_based_prediction(features)


def report_period_bounds(period_type: str) -> tuple[date, date]:
    today = date.today()
    if period_type.upper() == "MONTHLY":
        start = today.replace(day=1)
        return start, today
    start = today - timedelta(days=today.weekday())
    return start, today


def _float_or_default(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _latest_assessment(user_id: int) -> HealthAssessment | None:
    return (
        HealthAssessment.objects.filter(user_id=user_id, assessment_type="DIAGNOSIS")
        .order_by("-created_at")
        .first()
    )


def _assessment_features(assessment: HealthAssessment | None) -> dict[str, Any]:
    if assessment is None or not isinstance(assessment.findings_json, dict):
        return {}
    normalized = assessment.findings_json.get("normalized_features")
    legacy = assessment.findings_json.get("features")
    if isinstance(normalized, dict):
        return normalized
    if isinstance(legacy, dict):
        return legacy
    return {}


def dashboard_payload(user_id: int, period_type: str) -> dict[str, Any]:
    normalized_type = "MONTHLY" if period_type.lower() == "monthly" else "WEEKLY"
    period_start, period_end = report_period_bounds(normalized_type)

    reports = PeriodicReport.objects.filter(user_id=user_id, period_type=normalized_type).order_by("-period_end")
    current = reports.first()
    previous = reports[1] if reports.count() > 1 else None
    profile = HealthProfile.objects.filter(user_id=user_id).first()
    latest_assessment = _latest_assessment(user_id)
    latest_features = _assessment_features(latest_assessment)

    measurements = GlucoseMeasurement.objects.filter(
        user_id=user_id,
        measured_at__date__gte=period_start,
        measured_at__date__lte=period_end,
    ).order_by("measured_at")
    avg_glucose = measurements.aggregate(value=Avg("glucose_value"))["value"]

    trend = [
        {
            "label": item.measured_at.strftime("%d/%m"),
            "glucose": float(item.glucose_value),
        }
        for item in measurements[:31]
    ]
    if not trend and latest_assessment is not None:
        glucose_value = _float_or_default(latest_features.get("fasting_glucose_mg_dl"))
        if glucose_value:
            trend = [
                {
                    "label": latest_assessment.created_at.strftime("%d/%m"),
                    "glucose": round(glucose_value, 1),
                }
            ]

    score = _float_or_default(
        (current.health_score if current else None)
        or (latest_assessment.health_score if latest_assessment else None)
    )
    bmi = _float_or_default(
        (current.bmi if current else None)
        or (profile.bmi if profile else None)
        or latest_features.get("bmi")
    )
    glucose_value = _float_or_default(
        avg_glucose
        or (current.avg_glucose if current else None)
        or latest_features.get("fasting_glucose_mg_dl")
    )
    previous_glucose = _float_or_default(previous.avg_glucose if previous else None)
    delta = round(((glucose_value - previous_glucose) / previous_glucose) * 100, 1) if previous_glucose else 0
    alerts = 0
    if glucose_value >= 140:
        alerts += 1
    if _float_or_default(latest_features.get("systolic_bp_mean")) >= 130:
        alerts += 1
    if _float_or_default(latest_features.get("diastolic_bp_mean")) >= 85:
        alerts += 1

    achievements = []
    if current and isinstance(current.achievements_json, list):
        achievements = [str(item) for item in current.achievements_json if str(item).strip()]
    elif current and current.achievement_summary:
        achievements = [current.achievement_summary]

    issues = []
    if current and isinstance(current.issues_json, list):
        issues = [str(item) for item in current.issues_json if str(item).strip()]
    elif current and current.issue_summary:
        issues = [current.issue_summary]

    has_data = bool(current or previous or profile or trend or latest_assessment or measurements.exists())

    return {
        "has_data": has_data,
        "period_type": normalized_type,
        "overview": {
            "avg_glucose": round(glucose_value, 1),
            "health_score": round(score, 1),
            "bmi": round(bmi, 1),
            "alerts": alerts,
        },
        "trend": trend,
        "comparison": [
            {
                "label": "Duong huyet trung binh",
                "current": f"{round(glucose_value, 1)} mg/dL",
                "previous": f"{round(previous_glucose, 1)} mg/dL" if previous_glucose else "--",
                "delta": f"{delta:+.1f}%",
                "good": delta <= 0,
            },
            {
                "label": "Health score",
                "current": f"{round(score)}/100",
                "previous": f"{round(_float_or_default(previous.health_score), 1)}/100" if previous else "--",
                "delta": "--" if not previous else f"{score - _float_or_default(previous.health_score):+.1f}",
                "good": True,
            },
            {
                "label": "BMI",
                "current": f"{round(bmi, 1)}",
                "previous": f"{round(_float_or_default(previous.bmi), 1)}" if previous else "--",
                "delta": "--" if not previous else f"{bmi - _float_or_default(previous.bmi):+.1f}",
                "good": True,
            },
            {
                "label": "Canh bao nguy co",
                "current": f"{alerts} lan",
                "previous": f"{1 if previous_glucose >= 140 else 0} lan" if previous_glucose else "--",
                "delta": "--" if not previous_glucose else f"{alerts - (1 if previous_glucose >= 140 else 0):+d}",
                "good": alerts <= (1 if previous_glucose >= 140 else alerts),
            },
        ],
        "achievements": achievements,
        "issues": issues,
        "history": [
            {
                "period": f"{report.period_start:%d/%m} - {report.period_end:%d/%m}",
                "type": "Thang" if report.period_type == "MONTHLY" else "Tuan",
                "score": float(report.health_score or 0),
                "avg": float(report.avg_glucose or 0),
                "status": "Da luu",
            }
            for report in reports[:5]
        ],
    }


def decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(round(float(value), 2)))
    except (TypeError, ValueError):
        return None


def now() -> datetime:
    return datetime.now()
