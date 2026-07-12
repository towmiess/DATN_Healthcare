from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import requests
from django.conf import settings
from django.db.models import Avg

from .models import (
    ClinicalBaseline,
    ClinicalDocument,
    ClinicalObservation,
    GlucoseMeasurement,
    HealthAssessment,
    HealthProfile,
    LabResult,
    PeriodicReport,
    ReportDraft,
    ReportExport,
)


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

GLUCOSE_CONVERSION_FACTOR = 18.0
INSULIN_PMOL_PER_UU = 6.0
CHOLESTEROL_MG_DL_PER_MMOL_L = 38.67
MALE_WAIST_HEIGHT_RATIO = 0.45
FEMALE_WAIST_HEIGHT_RATIO = 0.4
MALE_HIP_WAIST_DIVISOR = 0.9
FEMALE_HIP_WAIST_DIVISOR = 0.7

BASELINE_FIELD_SPECS = {
    "HEIGHT_CM": ("height_cm", "Chiều cao", "cm"),
    "WEIGHT_KG": ("weight_kg", "Cân nặng", "kg"),
    "BMI": ("bmi", "BMI", "kg/m2"),
    "WAIST_CM": ("waist_cm", "Vòng eo", "cm"),
    "SYSTOLIC_BP": ("systolic_bp_mean", "Huyết áp tâm thu", "mmHg"),
    "DIASTOLIC_BP": ("diastolic_bp_mean", "Huyết áp tâm trương", "mmHg"),
    "PULSE": ("pulse_mean", "Mạch", "bpm"),
    "FASTING_GLUCOSE": ("fasting_glucose_mg_dl", "Glucose đói", "mg/dL"),
    "HBA1C": ("hba1c_percent", "HbA1c", "%"),
    "TOTAL_CHOLESTEROL": (
        "total_cholesterol_mg_dl",
        "Cholesterol toàn phần",
        "mg/dL",
    ),
    "FASTING_INSULIN": ("insulin_uU_ml", "Insulin đói", "uU/mL"),
}


def _expected_waist_cm(sex: int, height: float | None) -> float | None:
    if not height:
        return None
    if sex == 1:
        return round(height * MALE_WAIST_HEIGHT_RATIO, 2)
    if sex == 2:
        return round(height * FEMALE_WAIST_HEIGHT_RATIO, 2)
    return None


def _expected_hip_cm(sex: int, waist: float | None) -> float | None:
    if not waist:
        return None
    if sex == 1:
        return round(waist / MALE_HIP_WAIST_DIVISOR, 2)
    if sex == 2:
        return round(waist / FEMALE_HIP_WAIST_DIVISOR, 2)
    return None


def _sync_unit_pair(
    features: dict[str, float],
    payload: dict[str, Any],
    primary_key: str,
    secondary_key: str,
    secondary_per_primary: float,
) -> None:
    has_primary = payload.get(primary_key) not in (None, "")
    has_secondary = payload.get(secondary_key) not in (None, "")
    if has_primary and not has_secondary:
        features[secondary_key] = round(features[primary_key] * secondary_per_primary, 2)
    elif has_secondary and not has_primary:
        features[primary_key] = round(features[secondary_key] / secondary_per_primary, 2)


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

    _sync_unit_pair(
        features,
        payload,
        "fasting_glucose_mg_dl",
        "fasting_glucose_mmol_l",
        1 / GLUCOSE_CONVERSION_FACTOR,
    )
    _sync_unit_pair(
        features,
        payload,
        "insulin_uU_ml",
        "insulin_pmol_l",
        INSULIN_PMOL_PER_UU,
    )
    _sync_unit_pair(
        features,
        payload,
        "total_cholesterol_mg_dl",
        "total_cholesterol_mmol_l",
        1 / CHOLESTEROL_MG_DL_PER_MMOL_L,
    )

    if height and not payload.get("waist_cm"):
        expected_waist = _expected_waist_cm(sex, height)
        if expected_waist is not None:
            features["waist_cm"] = expected_waist

    waist = features.get("waist_cm")
    if waist and not payload.get("hip_cm"):
        expected_hip = _expected_hip_cm(sex, waist)
        if expected_hip is not None:
            features["hip_cm"] = expected_hip

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


def _latest_assessment(
    user_id: int,
    period_start: date | None = None,
    period_end: date | None = None,
) -> HealthAssessment | None:
    assessments = HealthAssessment.objects.filter(user_id=user_id, assessment_type="DIAGNOSIS")
    if period_start is not None:
        assessments = assessments.filter(created_at__date__gte=period_start)
    if period_end is not None:
        assessments = assessments.filter(created_at__date__lte=period_end)
    return assessments.order_by("-created_at").first()


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


def _assessment_input_features(assessment: HealthAssessment | None) -> dict[str, Any]:
    if assessment is None or not isinstance(assessment.findings_json, dict):
        return {}
    raw_features = assessment.findings_json.get("input_features")
    return raw_features if isinstance(raw_features, dict) else {}


def _assessment_feature_sources(assessment: HealthAssessment | None) -> dict[str, str]:
    if assessment is None or not isinstance(assessment.findings_json, dict):
        return {}
    metadata = assessment.findings_json.get("feature_metadata")
    if not isinstance(metadata, dict):
        return {}
    sources = metadata.get("field_sources")
    return sources if isinstance(sources, dict) else {}


def active_baseline_payload(user_id: int) -> dict[str, Any] | None:
    baseline = (
        ClinicalBaseline.objects.filter(user_id=user_id, status="ACTIVE")
        .select_related("diagnosis_session")
        .order_by("-effective_at", "-id")
        .first()
    )
    if baseline is None:
        return None

    document = (
        ClinicalDocument.objects.filter(
            user_id=user_id,
            diagnosis_session_id=baseline.diagnosis_session_id,
        )
        .order_by("-created_at")
        .first()
    )
    values: dict[str, dict[str, Any]] = {}

    for observation in ClinicalObservation.objects.filter(
        user_id=user_id,
        diagnosis_session_id=baseline.diagnosis_session_id,
        is_verified=True,
    ):
        spec = BASELINE_FIELD_SPECS.get(observation.observation_code.upper())
        if spec is None:
            continue
        feature_key, label, default_unit = spec
        values[feature_key] = {
            "feature_key": feature_key,
            "code": observation.observation_code,
            "label": label,
            "value": float(observation.canonical_value or observation.value),
            "unit": observation.canonical_unit or observation.unit or default_unit,
            "original_value": float(observation.value),
            "original_unit": observation.unit,
            "reference_text": observation.reference_text or "",
            "abnormal_flag": observation.abnormal_flag or "",
            "source": observation.source_type,
        }

    lab_results = LabResult.objects.filter(
        user_id=user_id,
        lab_panel__diagnosis_session_id=baseline.diagnosis_session_id,
        is_verified=True,
    ).select_related("lab_panel")
    for result in lab_results:
        spec = BASELINE_FIELD_SPECS.get(result.test_code.upper())
        if spec is None:
            continue
        feature_key, label, default_unit = spec
        value = float(result.canonical_value or result.value)
        unit = result.canonical_unit or result.unit or default_unit
        values[feature_key] = {
            "feature_key": feature_key,
            "code": result.test_code,
            "label": label,
            "value": value,
            "unit": unit,
            "original_value": float(result.value),
            "original_unit": result.unit,
            "reference_text": result.reference_text or "",
            "abnormal_flag": result.abnormal_flag or "",
            "source": result.source_type,
        }

        if feature_key == "fasting_glucose_mg_dl":
            values["fasting_glucose_mmol_l"] = {
                **values[feature_key],
                "feature_key": "fasting_glucose_mmol_l",
                "value": round(value / GLUCOSE_CONVERSION_FACTOR, 2),
                "unit": "mmol/L",
            }
        elif feature_key == "total_cholesterol_mg_dl":
            values["total_cholesterol_mmol_l"] = {
                **values[feature_key],
                "feature_key": "total_cholesterol_mmol_l",
                "value": round(value / CHOLESTEROL_MG_DL_PER_MMOL_L, 2),
                "unit": "mmol/L",
            }
        elif feature_key == "insulin_uU_ml":
            values["insulin_pmol_l"] = {
                **values[feature_key],
                "feature_key": "insulin_pmol_l",
                "value": round(value * INSULIN_PMOL_PER_UU, 2),
                "unit": "pmol/L",
            }

    return {
        "has_baseline": True,
        "id": baseline.id,
        "label": baseline.label,
        "effective_at": baseline.effective_at.isoformat(),
        "status": baseline.status,
        "provider_name": document.provider_name if document else None,
        "document": (
            {
                "id": document.id,
                "original_filename": document.original_filename,
                "file_url": document.file_url,
                "verification_status": document.verification_status,
            }
            if document
            else None
        ),
        "values": values,
    }


def _baseline_tracking_payload(user_id: int, baseline_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not baseline_payload:
        return []
    baseline_values = baseline_payload.get("values", {})
    assessments = list(
        HealthAssessment.objects.filter(
            user_id=user_id,
            assessment_type="DIAGNOSIS",
            created_at__gte=baseline_payload["effective_at"],
        ).order_by("created_at")
    )
    metrics = []
    primary_keys = (
        "fasting_glucose_mg_dl",
        "weight_kg",
        "bmi",
        "waist_cm",
        "systolic_bp_mean",
        "diastolic_bp_mean",
        "pulse_mean",
        "hba1c_percent",
        "total_cholesterol_mg_dl",
        "insulin_uU_ml",
    )
    for feature_key in primary_keys:
        baseline_value = baseline_values.get(feature_key)
        if not baseline_value:
            continue
        points = []
        for assessment in assessments:
            sources = _assessment_feature_sources(assessment)
            if sources.get(feature_key) not in {"provided", "derived"}:
                continue
            value = _assessment_features(assessment).get(feature_key)
            if value in (None, ""):
                continue
            points.append(
                {
                    "timestamp": assessment.created_at.isoformat(),
                    "label": assessment.created_at.strftime("%d/%m %H:%M"),
                    "value": round(float(value), 2),
                    "source": "DIAGNOSIS_INPUT",
                }
            )
        current_value = points[-1]["value"] if points else None
        delta = round(current_value - baseline_value["value"], 2) if current_value is not None else None
        delta_percent = (
            round(delta / baseline_value["value"] * 100, 1)
            if delta is not None and baseline_value["value"]
            else None
        )
        metrics.append(
            {
                "key": feature_key,
                "label": baseline_value["label"],
                "unit": baseline_value["unit"],
                "baseline_value": baseline_value["value"],
                "baseline_at": baseline_payload["effective_at"],
                "current_value": current_value,
                "delta": delta,
                "delta_percent": delta_percent,
                "points": points,
            }
        )
    return metrics


def _dashboard_data_quality(
    user_id: int,
    assessment: HealthAssessment | None,
    normalized_features: dict[str, Any],
) -> dict[str, Any]:
    raw_features = _assessment_input_features(assessment)
    field_sources = _assessment_feature_sources(assessment)
    latest_lab_results: dict[str, LabResult] = {}
    lab_code_map = {
        "HBA1C": "hba1c",
        "HB_A1C": "hba1c",
        "INSULIN": "insulin",
        "FASTING_INSULIN": "insulin",
        "TOTAL_CHOLESTEROL": "cholesterol",
        "CHOLESTEROL_TOTAL": "cholesterol",
    }
    for result in (
        LabResult.objects.filter(
            user_id=user_id,
            is_verified=True,
            test_code__in=tuple(lab_code_map),
        )
        .select_related("lab_panel")
        .order_by("-observed_at", "-id")
    ):
        metric_key = lab_code_map.get(result.test_code.upper())
        if metric_key and metric_key not in latest_lab_results:
            latest_lab_results[metric_key] = result

    groups = (
        ("Giới tính", ("sex",), None),
        ("Tuổi", ("age_years",), None),
        ("Cân nặng", ("weight_kg",), None),
        ("Chiều cao", ("height_cm",), None),
        ("BMI", ("bmi",), None),
        ("Vòng eo", ("waist_cm",), None),
        ("HbA1c", ("hba1c_percent",), "hba1c"),
        ("Glucose đói", ("fasting_glucose_mg_dl", "fasting_glucose_mmol_l"), None),
        ("Insulin", ("insulin_uU_ml", "insulin_pmol_l"), "insulin"),
        ("Cholesterol", ("total_cholesterol_mg_dl", "total_cholesterol_mmol_l"), "cholesterol"),
        ("Huyết áp", ("systolic_bp_mean", "diastolic_bp_mean"), None),
    )

    def has_real_value(keys: tuple[str, ...], lab_metric: str | None) -> bool:
        if lab_metric and lab_metric in latest_lab_results:
            return True
        return any(
            field_sources.get(key) in {"provided", "derived"}
            or (key in raw_features and raw_features.get(key) not in (None, ""))
            for key in keys
        )

    missing_groups = [
        label for label, keys, lab_metric in groups if not has_real_value(keys, lab_metric)
    ]
    completed_groups = len(groups) - len(missing_groups)

    def metric_payload(
        metric_key: str,
        primary_key: str,
        secondary_key: str | None = None,
    ) -> dict[str, Any]:
        lab_result = latest_lab_results.get(metric_key)
        if lab_result is not None:
            value = float(lab_result.value)
            normalized_unit = lab_result.unit.lower().replace("µ", "u").replace("μ", "u")
            primary_value = value
            secondary_value = None
            if metric_key == "insulin":
                if "pmol" in normalized_unit:
                    primary_value = value / INSULIN_PMOL_PER_UU
                    secondary_value = value
                else:
                    secondary_value = value * INSULIN_PMOL_PER_UU
            elif metric_key == "cholesterol":
                if "mmol" in normalized_unit:
                    primary_value = value * CHOLESTEROL_MG_DL_PER_MMOL_L
                    secondary_value = value
                else:
                    secondary_value = value / CHOLESTEROL_MG_DL_PER_MMOL_L
            return {
                "available": True,
                "primary_value": round(primary_value, 2),
                "secondary_value": (
                    round(secondary_value, 2) if secondary_value is not None else None
                ),
                "recorded_at": lab_result.observed_at.isoformat(),
                "source": "HOSPITAL_LAB",
                "provider_name": lab_result.lab_panel.provider_name,
            }

        keys = (primary_key,) if secondary_key is None else (primary_key, secondary_key)
        available = any(field_sources.get(key) == "provided" for key in keys) or any(
            key in raw_features and raw_features.get(key) not in (None, "") for key in keys
        )
        return {
            "available": available,
            "primary_value": (
                _float_or_default(normalized_features.get(primary_key)) if available else None
            ),
            "secondary_value": (
                _float_or_default(normalized_features.get(secondary_key))
                if available and secondary_key
                else None
            ),
            "recorded_at": assessment.created_at.isoformat() if available and assessment else None,
            "source": "DIAGNOSIS_INPUT" if available else None,
            "provider_name": None,
        }

    return {
        "completed": completed_groups,
        "total": len(groups),
        "coverage_percent": round(completed_groups / len(groups) * 100),
        "missing_groups": missing_groups,
        "uses_defaults": bool(missing_groups),
        "clinical_metrics": {
            "hba1c": metric_payload("hba1c", "hba1c_percent"),
            "insulin": metric_payload("insulin", "insulin_uU_ml", "insulin_pmol_l"),
            "cholesterol": metric_payload(
                "cholesterol",
                "total_cholesterol_mg_dl",
                "total_cholesterol_mmol_l",
            ),
        },
    }


def _distinct_periodic_reports(user_id: int, period_type: str) -> list[PeriodicReport]:
    reports = PeriodicReport.objects.filter(user_id=user_id, period_type=period_type).order_by(
        "-period_end",
        "-generated_at",
        "-id",
    )
    distinct_reports: list[PeriodicReport] = []
    seen_periods: set[tuple[str, date, date]] = set()
    for report in reports:
        period_key = (report.period_type, report.period_start, report.period_end)
        if period_key in seen_periods:
            continue
        seen_periods.add(period_key)
        distinct_reports.append(report)
    return distinct_reports


def _weekly_glucose_trend(measurements) -> list[dict[str, Any]]:
    points = list(measurements.order_by("-measured_at")[:31])
    points.reverse()
    dates = [item.measured_at.date() for item in points]
    duplicate_dates = {measurement_date for measurement_date in dates if dates.count(measurement_date) > 1}

    return [
        {
            "label": item.measured_at.strftime(
                "%d/%m %H:%M" if item.measured_at.date() in duplicate_dates else "%d/%m"
            ),
            "timestamp": item.measured_at.isoformat(),
            "glucose": round(float(item.glucose_value), 1),
        }
        for item in points
    ]


def _monthly_glucose_trend(measurements) -> list[dict[str, Any]]:
    daily_measurements = (
        measurements.values("measured_at__date")
        .annotate(glucose=Avg("glucose_value"))
        .order_by("measured_at__date")
    )
    return [
        {
            "label": item["measured_at__date"].strftime("%d/%m"),
            "timestamp": item["measured_at__date"].isoformat(),
            "glucose": round(float(item["glucose"]), 1),
        }
        for item in daily_measurements
    ]


def dashboard_payload(user_id: int, period_type: str) -> dict[str, Any]:
    normalized_type = "MONTHLY" if period_type.lower() == "monthly" else "WEEKLY"
    period_start, period_end = report_period_bounds(normalized_type)

    reports = _distinct_periodic_reports(user_id, normalized_type)
    current = next(
        (
            report
            for report in reports
            if report.period_start == period_start and report.period_end == period_end
        ),
        None,
    )
    previous = next((report for report in reports if report.period_end < period_start), None)
    profile = HealthProfile.objects.filter(user_id=user_id).first()
    latest_assessment = _latest_assessment(user_id, period_start, period_end)
    latest_known_assessment = _latest_assessment(user_id)
    latest_features = _assessment_features(latest_assessment)
    data_quality = _dashboard_data_quality(
        user_id,
        latest_known_assessment,
        _assessment_features(latest_known_assessment),
    )
    baseline = active_baseline_payload(user_id)
    baseline_tracking = _baseline_tracking_payload(user_id, baseline)

    measurements = GlucoseMeasurement.objects.filter(
        user_id=user_id,
        measured_at__date__gte=period_start,
        measured_at__date__lte=period_end,
    ).order_by("measured_at")
    avg_glucose = measurements.aggregate(value=Avg("glucose_value"))["value"]

    trend = (
        _monthly_glucose_trend(measurements)
        if normalized_type == "MONTHLY"
        else _weekly_glucose_trend(measurements)
    )
    if not trend and latest_assessment is not None:
        glucose_value = _float_or_default(latest_features.get("fasting_glucose_mg_dl"))
        if glucose_value:
            trend = [
                {
                    "label": latest_assessment.created_at.strftime("%d/%m"),
                    "timestamp": latest_assessment.created_at.isoformat(),
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

    history_rows = []
    for report in reports[:5]:
        latest_export = ReportExport.objects.filter(report_id=report.id, user_id=user_id).order_by(
            "-exported_at",
            "-id",
        ).first()
        history_rows.append(
            {
                "row_key": f"report-{report.id}",
                "id": report.id,
                "period": f"{report.period_start:%d/%m} - {report.period_end:%d/%m}",
                "period_start": report.period_start.isoformat(),
                "period_end": report.period_end.isoformat(),
                "type": "Tháng" if report.period_type == "MONTHLY" else "Tuần",
                "score": float(report.health_score or 0),
                "avg": float(report.avg_glucose or 0),
                "status": f"Đã xuất {latest_export.export_format}" if latest_export else "Đã lưu",
            }
        )

    drafts = ReportDraft.objects.filter(user_id=user_id, period_type=normalized_type).order_by(
        "-updated_at"
    )[:5]
    for draft in drafts:
        draft_overview = draft.payload.get("overview", {}) if isinstance(draft.payload, dict) else {}
        history_rows.append(
            {
                "row_key": f"draft-{draft.id}",
                "id": draft.id,
                "period": f"{draft.period_start:%d/%m} - {draft.period_end:%d/%m}",
                "period_start": draft.period_start.isoformat(),
                "period_end": draft.period_end.isoformat(),
                "type": "Tháng" if draft.period_type == "MONTHLY" else "Tuần",
                "score": _float_or_default(draft_overview.get("health_score")),
                "avg": _float_or_default(draft_overview.get("avg_glucose")),
                "status": "Bản nháp",
            }
        )
    history_rows.sort(key=lambda item: (item["period_end"], item["row_key"]), reverse=True)

    return {
        "has_data": has_data,
        "period_type": normalized_type,
        "overview": {
            "avg_glucose": round(glucose_value, 1),
            "health_score": round(score, 1),
            "bmi": round(bmi, 1),
            "alerts": alerts,
            "score_label": (
                "Kiểm soát tốt" if score >= 75 else "Cần chú ý" if score >= 50 else "Nguy cơ cao"
            ),
            "score_description": "Tính từ nhóm nguy cơ cao nhất của lần dự đoán gần nhất.",
        },
        "data_quality": data_quality,
        "baseline": baseline or {"has_baseline": False},
        "baseline_tracking": baseline_tracking,
        "trend": trend,
        "comparison": [
            {
                "label": "Đường huyết trung bình",
                "current": f"{round(glucose_value, 1)} mg/dL",
                "previous": f"{round(previous_glucose, 1)} mg/dL" if previous_glucose else "--",
                "delta": f"{delta:+.1f}%",
                "good": delta <= 0,
            },
            {
                "label": "Điểm kiểm soát nguy cơ",
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
                "label": "Cảnh báo nguy cơ",
                "current": f"{alerts} lần",
                "previous": f"{1 if previous_glucose >= 140 else 0} lần" if previous_glucose else "--",
                "delta": "--" if not previous_glucose else f"{alerts - (1 if previous_glucose >= 140 else 0):+d}",
                "good": alerts <= (1 if previous_glucose >= 140 else alerts),
            },
        ],
        "achievements": achievements,
        "issues": issues,
        "history": history_rows[:8],
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
