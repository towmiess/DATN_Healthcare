from __future__ import annotations

import base64
import json
from datetime import timedelta
from functools import lru_cache

import requests
from django.conf import settings
from django.db import DatabaseError, transaction
from django.db.models import Avg
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    GlucoseMeasurement,
    HealthAssessment,
    HealthProfile,
    PeriodicReport,
    ReportExport,
    RiskPrediction,
    User,
)
from .serializers import DiagnosisPredictSerializer, GoogleVisionOcrSerializer, ReportExportSerializer
from .services import dashboard_payload, decimal_or_none, normalize_features, now, predict, report_period_bounds, risk_band


FORM_VALUE_KEYS = (
    "sex",
    "age_years",
    "weight_kg",
    "height_cm",
    "bmi",
    "waist_cm",
    "hip_cm",
    "hba1c_percent",
    "fasting_glucose_mg_dl",
    "fasting_glucose_mmol_l",
    "insulin_uU_ml",
    "insulin_pmol_l",
    "fasting_hours",
    "fasting_minutes",
    "total_cholesterol_mg_dl",
    "total_cholesterol_mmol_l",
    "high_blood_pressure_history",
    "systolic_bp_mean",
    "diastolic_bp_mean",
    "pulse_mean",
)
INTEGER_VALUE_KEYS = {"sex", "high_blood_pressure_history"}
DERIVED_VALUE_KEYS = {"bmi", "waist_cm", "hip_cm"}
GLUCOSE_CONVERSION_FACTOR = 18.0182


def _load_google_vision_service_account_info() -> dict | None:
    raw_json = settings.GOOGLE_APPLICATION_CREDENTIALS_JSON.strip()
    if raw_json:
        return json.loads(raw_json)

    raw_b64 = settings.GOOGLE_APPLICATION_CREDENTIALS_B64.strip()
    if raw_b64:
        return json.loads(base64.b64decode(raw_b64).decode("utf-8"))

    credentials_path = settings.GOOGLE_APPLICATION_CREDENTIALS.strip()
    if credentials_path:
        with open(credentials_path, encoding="utf-8") as credential_file:
            return json.load(credential_file)

    return None


@lru_cache(maxsize=1)
def _google_vision_credentials():
    service_account_info = _load_google_vision_service_account_info()
    if not service_account_info:
        return None

    try:
        from google.oauth2 import service_account
    except ImportError as exc:
        raise RuntimeError("google-auth is not installed in health-service.") from exc

    return service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )


def _google_vision_request_config() -> tuple[str, dict[str, str]] | None:
    credentials = _google_vision_credentials()
    if credentials is None:
        return None

    try:
        from google.auth.transport.requests import Request
    except ImportError as exc:
        raise RuntimeError("google-auth transport layer is unavailable.") from exc

    if not credentials.valid or credentials.expired or not credentials.token:
        credentials.refresh(Request())

    return (
        "https://vision.googleapis.com/v1/images:annotate",
        {
            "Authorization": f"Bearer {credentials.token}",
            "Content-Type": "application/json",
        },
    )


def user_id_from_request(request) -> int:
    return int(getattr(request.user, "id", None) or 1)


def ensure_shadow_user(request) -> User:
    current = now()
    email = getattr(request.user, "email", "") or f"user-{user_id_from_request(request)}@local.health"
    user, _ = User.objects.get_or_create(
        id=user_id_from_request(request),
        defaults={
            "full_name": email,
            "email": email,
            "phone_number": None,
            "password": "",
            "avatar": None,
            "status": True,
            "created_at": current,
            "updated_at": current,
        },
    )
    return user


def _float_or_none(value) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _frontend_number(value, key: str):
    number = _float_or_none(value)
    if number is None:
        return None
    if key in INTEGER_VALUE_KEYS:
        return int(round(number))
    rounded = round(number, 2)
    return int(rounded) if float(rounded).is_integer() else rounded


def _profile_snapshot_value(profile: HealthProfile | None, key: str):
    if profile is None:
        return None

    if key == "sex":
        if profile.gender == "MALE":
            return 1
        if profile.gender == "FEMALE":
            return 2
        return None

    field_map = {
        "height_cm": profile.height_cm,
        "weight_kg": profile.weight_kg,
        "waist_cm": profile.waist_cm,
        "bmi": profile.bmi,
    }
    return field_map.get(key)


def _assessment_feature_bundle(assessment: HealthAssessment | None) -> tuple[dict, dict]:
    findings = assessment.findings_json if assessment and isinstance(assessment.findings_json, dict) else {}
    raw_features = findings.get("input_features")
    normalized_features = findings.get("normalized_features") or findings.get("features")
    return (
        raw_features if isinstance(raw_features, dict) else {},
        normalized_features if isinstance(normalized_features, dict) else {},
    )


def _prediction_result_from_assessment(assessment: HealthAssessment | None) -> dict | None:
    if assessment is None:
        return None

    findings = assessment.findings_json if isinstance(assessment.findings_json, dict) else {}
    result = findings.get("result")
    if isinstance(result, dict) and all(key in result for key in ("diabetes", "cardio", "stroke")):
        return result

    predictions = RiskPrediction.objects.filter(assessment_id=assessment.id)
    if not predictions.exists():
        return None

    payload = {}
    label_map = {
        "DIABETES": ("Elevated diabetes risk", "No diabetes risk signal"),
        "CARDIO": ("Elevated cardiovascular risk", "No cardiovascular risk signal"),
        "STROKE": ("Elevated stroke risk", "No stroke risk signal"),
    }
    for prediction in predictions:
        key = prediction.prediction_type.lower()
        positive_label, negative_label = label_map.get(
            prediction.prediction_type.upper(),
            ("Elevated risk", "No risk signal"),
        )
        probability = float(prediction.risk_percent or 0) / 100
        payload[key] = {
            "prediction": 1 if prediction.high_risk_flag else 0,
            "label": positive_label if prediction.high_risk_flag else negative_label,
            "positive_probability": round(probability, 4),
        }

    return payload if all(key in payload for key in ("diabetes", "cardio", "stroke")) else None


def _diagnosis_snapshot_payload(user_id: int) -> dict:
    profile = HealthProfile.objects.filter(user_id=user_id).first()
    assessment = (
        HealthAssessment.objects.filter(user_id=user_id, assessment_type="DIAGNOSIS")
        .order_by("-created_at")
        .first()
    )
    raw_features, normalized_features = _assessment_feature_bundle(assessment)

    values = {}
    for key in FORM_VALUE_KEYS:
        value = raw_features.get(key)
        if value in (None, "") and key in DERIVED_VALUE_KEYS:
            value = normalized_features.get(key)
        if value in (None, ""):
            value = _profile_snapshot_value(profile, key)

        normalized_value = _frontend_number(value, key)
        if normalized_value is not None:
            values[key] = normalized_value

    result = _prediction_result_from_assessment(assessment)

    return {
        "has_data": bool(values or result),
        "values": values,
        "latest_result": result,
        "latest_assessment": (
            {
                "id": assessment.id,
                "created_at": assessment.created_at.isoformat(),
                "risk_level": assessment.risk_level,
                "health_score": float(assessment.health_score) if assessment.health_score is not None else None,
            }
            if assessment
            else None
        ),
    }


def _glucose_value_mg_dl(features: dict) -> float | None:
    glucose_mg_dl = _float_or_none(features.get("fasting_glucose_mg_dl"))
    if glucose_mg_dl and glucose_mg_dl > 0:
        return glucose_mg_dl

    glucose_mmol_l = _float_or_none(features.get("fasting_glucose_mmol_l"))
    if glucose_mmol_l and glucose_mmol_l > 0:
        return glucose_mmol_l * GLUCOSE_CONVERSION_FACTOR

    return None


def _report_highlights(features: dict, result: dict) -> tuple[list[str], list[str]]:
    glucose = _glucose_value_mg_dl(features) or 0
    bmi = _float_or_none(features.get("bmi")) or 0
    systolic = _float_or_none(features.get("systolic_bp_mean")) or 0
    diastolic = _float_or_none(features.get("diastolic_bp_mean")) or 0
    peak_risk = max(float(item.get("positive_probability", 0)) for item in result.values())

    achievements: list[str] = []
    issues: list[str] = []

    if glucose and glucose <= 110:
        achievements.append("Đường huyết lúc đói hiện nằm trong vùng kiểm soát chấp nhận được.")
    else:
        issues.append("Đường huyết lúc đói còn cao, nên tiếp tục theo dõi sát hơn.")

    if bmi and bmi < 25:
        achievements.append("BMI đang ở vùng thuận lợi cho mục tiêu kiểm soát nguy cơ.")
    elif bmi:
        issues.append("BMI còn cao, nên duy trì điều chỉnh cân nặng và vận động.")

    if systolic and diastolic and systolic < 130 and diastolic < 85:
        achievements.append("Huyết áp hiện chưa ghi nhận vượt ngưỡng cảnh báo chính.")
    elif systolic or diastolic:
        issues.append("Chỉ số huyết áp cần được theo dõi định kỳ để giảm rủi ro tim mạch.")

    if peak_risk >= 0.5:
        issues.append("Kết quả dự đoán đang ghi nhận ít nhất một nhóm nguy cơ ở mức đáng chú ý.")
    else:
        achievements.append("Các mô hình dự đoán hiện chưa ghi nhận nhóm nguy cơ vượt ngưỡng cao.")

    if not achievements:
        achievements.append("Đã lưu hồ sơ chẩn đoán để tiếp tục theo dõi ở các lần tiếp theo.")
    if not issues:
        issues.append("Nên duy trì lịch đo đều đặn để dashboard phản ánh xu hướng chính xác hơn.")

    return achievements[:3], issues[:3]


def _upsert_periodic_report(
    user_id: int,
    period_type: str,
    profile: HealthProfile,
    features: dict,
    result: dict,
    current_time,
    health_score: float | None,
) -> None:
    period_start, period_end = report_period_bounds(period_type)
    glucose_queryset = GlucoseMeasurement.objects.filter(
        user_id=user_id,
        measured_at__date__gte=period_start,
        measured_at__date__lte=period_end,
    )
    avg_glucose = glucose_queryset.aggregate(value=Avg("glucose_value"))["value"]
    achievements, issues = _report_highlights(features, result)

    report_defaults = {
        "avg_glucose": decimal_or_none(avg_glucose),
        "health_score": decimal_or_none(health_score),
        "bmi": profile.bmi,
        "weight_change": None,
        "achievement_summary": " ".join(achievements),
        "issue_summary": " ".join(issues),
        "achievements_json": achievements,
        "issues_json": issues,
        "file_url": "",
        "generated_by": "health-service",
        "generated_at": current_time,
    }
    report = PeriodicReport.objects.filter(
        user_id=user_id,
        period_type=period_type,
        period_start=period_start,
        period_end=period_end,
    ).first()

    if report is None:
        PeriodicReport.objects.create(
            user_id=user_id,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            **report_defaults,
        )
        return

    for key, value in report_defaults.items():
        setattr(report, key, value)
    report.save()


def save_prediction_snapshot(request, input_features: dict, features: dict, result: dict) -> None:
    try:
        with transaction.atomic():
            user = ensure_shadow_user(request)
            current = now()
            profile = HealthProfile.objects.filter(user_id=user.id).first()
            if profile is None:
                profile = HealthProfile.objects.create(
                    user_id=user.id,
                    gender="MALE" if int(features.get("sex", 2)) == 1 else "FEMALE",
                    height_cm=decimal_or_none(features.get("height_cm")),
                    weight_kg=decimal_or_none(features.get("weight_kg")),
                    waist_cm=decimal_or_none(features.get("waist_cm")),
                    bmi=decimal_or_none(features.get("bmi")),
                    created_at=current,
                    updated_at=current,
                )
            else:
                profile.gender = "MALE" if int(features.get("sex", 2)) == 1 else "FEMALE"
                profile.height_cm = decimal_or_none(features.get("height_cm"))
                profile.weight_kg = decimal_or_none(features.get("weight_kg"))
                profile.waist_cm = decimal_or_none(features.get("waist_cm"))
                profile.bmi = decimal_or_none(features.get("bmi"))
                profile.updated_at = current
                profile.save()

            max_probability = max(float(item.get("positive_probability", 0)) for item in result.values())
            health_score = 100 - max_probability * 100
            assessment = HealthAssessment.objects.create(
                user_id=user.id,
                health_profile_id=profile.id,
                assessment_type="DIAGNOSIS",
                risk_level=risk_band(max_probability),
                health_score=decimal_or_none(health_score),
                summary="Diagnosis risk prediction generated by health-service.",
                findings_json={
                    "input_features": input_features,
                    "normalized_features": features,
                    "result": result,
                },
                created_at=current,
            )

            for prediction_type, item in result.items():
                probability = float(item.get("positive_probability", 0))
                RiskPrediction.objects.create(
                    user_id=user.id,
                    assessment_id=assessment.id,
                    model_name="django-health-service",
                    prediction_type=prediction_type.upper(),
                    risk_percent=decimal_or_none(probability * 100) or 0,
                    risk_band=risk_band(probability),
                    high_risk_flag=probability >= 0.5,
                    feature_snapshot=features,
                    created_at=current,
                )

            glucose_value = _glucose_value_mg_dl(features)
            if glucose_value is not None:
                GlucoseMeasurement.objects.create(
                    user_id=user.id,
                    glucose_value=decimal_or_none(glucose_value) or 0,
                    unit="mg/dL",
                    measurement_context="FASTING",
                    measured_at=current,
                    source_type="MANUAL",
                    note="Captured from diagnosis submission.",
                    created_at=current,
                )

            _upsert_periodic_report(user.id, "WEEKLY", profile, features, result, current, health_score)
            _upsert_periodic_report(user.id, "MONTHLY", profile, features, result, current, health_score)
    except DatabaseError:
        # Prediction must stay usable while schema/data is being wired into the full system.
        return


class HealthCheckView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"status": "UP", "service": "health-service"})


class DiagnosisPredictView(APIView):
    def post(self, request):
        serializer = DiagnosisPredictSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        input_features = dict(serializer.validated_data)
        features = normalize_features(input_features)
        result = predict(features)
        save_prediction_snapshot(request, input_features, features, result)

        return Response(result)


class DiagnosisSnapshotView(APIView):
    def get(self, request):
        try:
            return Response(_diagnosis_snapshot_payload(user_id_from_request(request)))
        except DatabaseError:
            return Response(
                {
                    "has_data": False,
                    "values": {},
                    "latest_result": None,
                    "latest_assessment": None,
                }
            )


class ReportDashboardView(APIView):
    def get(self, request):
        period_type = request.query_params.get("period_type", "weekly")
        return Response(dashboard_payload(user_id_from_request(request), period_type))


class ReportExportView(APIView):
    def post(self, request):
        serializer = ReportExportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        export_format = serializer.validated_data["export_format"]
        current = now()

        try:
            with transaction.atomic():
                user = ensure_shadow_user(request)
                report_id = serializer.validated_data.get("report_id")
                report = PeriodicReport.objects.filter(id=report_id, user_id=user.id).first() if report_id else None
                if report is None:
                    start, end = report_period_bounds("WEEKLY")
                    report = PeriodicReport.objects.create(
                        user_id=user.id,
                        period_type="WEEKLY",
                        period_start=start,
                        period_end=end,
                        avg_glucose=124,
                        health_score=82,
                        bmi=26.2,
                        weight_change=0,
                        achievement_summary="Auto-generated report draft.",
                        issue_summary="No critical issue recorded.",
                        achievements_json=[],
                        issues_json=[],
                        file_url="",
                        generated_by="health-service",
                        generated_at=current,
                    )

                file_url = f"/reports/{report.id}/exports/report-{report.id}.{export_format.lower()}"
                export = ReportExport.objects.create(
                    report_id=report.id,
                    user_id=user.id,
                    export_format=export_format,
                    file_url=file_url,
                    exported_at=current,
                )
        except DatabaseError:
            return Response({"message": "Unable to create report export"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(
            {
                "id": export.id,
                "report_id": report.id,
                "export_format": export.export_format,
                "file_url": export.file_url,
                "exported_at": export.exported_at,
            },
            status=status.HTTP_201_CREATED,
        )


class GoogleVisionOcrView(APIView):
    def post(self, request):
        serializer = GoogleVisionOcrSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payload = {
            "requests": [
                {
                    "image": {"content": serializer.validated_data["image_base64"]},
                    "features": [{"type": "TEXT_DETECTION"}],
                    "imageContext": {"languageHints": ["vi", "en"]},
                }
            ]
        }

        request_headers = None
        if settings.GOOGLE_VISION_API_KEY:
            endpoint = f"https://vision.googleapis.com/v1/images:annotate?key={settings.GOOGLE_VISION_API_KEY}"
        else:
            try:
                request_config = _google_vision_request_config()
            except Exception as exc:
                return Response({"message": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

            if request_config is None:
                return Response(
                    {
                        "message": (
                            "Google Vision is not configured. Set GOOGLE_VISION_API_KEY "
                            "or GOOGLE_APPLICATION_CREDENTIALS(_JSON/_B64)."
                        )
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

            endpoint, request_headers = request_config

        try:
            response = requests.post(endpoint, json=payload, headers=request_headers, timeout=12)
            response.raise_for_status()
        except requests.RequestException as exc:
            return Response({"message": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        data = response.json()
        annotations = data.get("responses", [{}])[0].get("textAnnotations", [])
        text = annotations[0].get("description", "") if annotations else ""
        return Response({"text": text})
