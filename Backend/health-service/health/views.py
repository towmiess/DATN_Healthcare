from __future__ import annotations

import base64
import hashlib
import json
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

import requests
from django.conf import settings
from django.db import DatabaseError, transaction
from django.db.models import Avg
from django.http import HttpResponse
from rest_framework import permissions, status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    ClinicalBaseline,
    GlucoseMeasurement,
    HealthAssessment,
    HealthProfile,
    ClinicalDocument,
    ClinicalObservation,
    DiagnosisSession,
    LabPanel,
    LabResult,
    PeriodicReport,
    ReportDraft,
    ReportExport,
    RiskPrediction,
    User,
)
from .serializers import (
    ClinicalBaselineExtractSerializer,
    ClinicalBaselineSerializer,
    DiagnosisPredictSerializer,
    GoogleVisionOcrSerializer,
    ReportDraftSerializer,
    ReportExportSerializer,
)
from .clinical_baseline import extract_clinical_baseline
from .report_exporters import build_csv_report, build_pdf_report
from .services import active_baseline_payload, dashboard_payload, decimal_or_none, normalize_features, now, predict, report_period_bounds, risk_band


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
GLUCOSE_CONVERSION_FACTOR = 18.0


def _save_clinical_upload(user_id: int, image_base64: str, mime_type: str) -> tuple[str, str, Path]:
    try:
        content = base64.b64decode(image_base64, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("Dữ liệu ảnh không hợp lệ.") from exc
    if not content or len(content) > 15 * 1024 * 1024:
        raise ValueError("Ảnh hồ sơ phải có dung lượng từ 1 byte đến 15 MB.")

    extensions = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }
    extension = extensions.get(mime_type.lower())
    if extension is None:
        raise ValueError("Hệ thống hiện hỗ trợ ảnh JPEG, PNG hoặc WEBP.")

    relative_path = Path("clinical_uploads") / str(user_id) / f"{uuid4().hex}{extension}"
    absolute_path = settings.MEDIA_ROOT / relative_path
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(content)
    return f"{settings.MEDIA_URL}{relative_path.as_posix()}", hashlib.sha256(content).hexdigest(), absolute_path


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


def _google_vision_status_payload() -> dict[str, object]:
    if settings.GOOGLE_VISION_API_KEY:
        return {
            "configured": True,
            "provider": "api_key",
            "mode": "google-vision",
        }

    try:
        credentials = _google_vision_credentials()
    except Exception as exc:
        return {
            "configured": False,
            "provider": "service_account",
            "mode": "google-vision",
            "message": str(exc),
        }

    if credentials is not None:
        return {
            "configured": True,
            "provider": "service_account",
            "mode": "google-vision",
        }

    return {
        "configured": False,
        "provider": "none",
        "mode": "local-fallback",
        "message": "Google Vision is not configured.",
    }


def _google_vision_error_response(exc: requests.RequestException) -> tuple[str, int]:
    response = getattr(exc, "response", None)
    if response is None:
        return (
            "Google Vision request failed. Check network access from health-service and try again.",
            status.HTTP_502_BAD_GATEWAY,
        )

    provider = _google_vision_status_payload().get("provider")
    error_message = ""
    try:
        error_message = response.json().get("error", {}).get("message", "")
    except ValueError:
        error_message = response.text.strip()

    if response.status_code == 400:
        message = "Google Vision rejected the OCR payload. Check the uploaded image format and request body."
    elif response.status_code == 401:
        message = "Google Vision authentication failed. Recheck the configured API key or service account."
    elif response.status_code == 403 and provider == "api_key":
        message = (
            "Google Vision rejected the API key (403). Check that Cloud Vision API is enabled, billing is active, "
            "and the key is not restricted to HTTP referrers or browser-only use. For backend Docker calls, prefer "
            "an unrestricted key, IP-restricted key, or a service account."
        )
    elif response.status_code == 403:
        message = (
            "Google Vision access was denied (403). Check IAM permissions for the configured service account and "
            "confirm the Vision API is enabled for the project."
        )
    else:
        message = f"Google Vision request failed with status {response.status_code}."

    if error_message and response.status_code not in {403}:
        message = f"{message} Detail: {error_message}"

    return message, status.HTTP_502_BAD_GATEWAY


def _model_api_ocr_text(image_base64: str, mime_type: str) -> str:
    model_url = settings.MODEL_API_URL.strip().rstrip("/")
    if not model_url:
        return ""

    try:
        response = requests.post(
            f"{model_url}/ocr/google-vision",
            json={"image_base64": image_base64, "mime_type": mime_type},
            timeout=8,
        )
        response.raise_for_status()
    except requests.RequestException:
        return ""

    data = response.json()
    text = data.get("text", "")
    return text if isinstance(text, str) else ""


def _perform_google_vision_ocr(
    image_base64: str,
    mime_type: str,
    mode: str,
) -> dict[str, str]:
    feature_type = "DOCUMENT_TEXT_DETECTION" if mode == "document" else "TEXT_DETECTION"
    payload = {
        "requests": [
            {
                "image": {"content": image_base64},
                "features": [{"type": feature_type}],
                "imageContext": {"languageHints": ["vi", "en"]},
            }
        ]
    }

    request_headers = None
    if settings.GOOGLE_VISION_API_KEY:
        endpoint = f"https://vision.googleapis.com/v1/images:annotate?key={settings.GOOGLE_VISION_API_KEY}"
    else:
        request_config = _google_vision_request_config()
        if request_config is None:
            raise ValueError(
                "Google Vision chưa được cấu hình. Hãy thiết lập API key hoặc service account."
            )
        endpoint, request_headers = request_config

    try:
        response = requests.post(endpoint, json=payload, headers=request_headers, timeout=18)
        response.raise_for_status()
    except requests.RequestException:
        model_text = _model_api_ocr_text(image_base64, mime_type)
        if model_text:
            return {"text": model_text, "provider": "model-api-fallback", "mode": mode}
        raise

    data = response.json()
    response_payload = data.get("responses", [{}])[0]
    api_error = response_payload.get("error")
    if api_error:
        raise ValueError(str(api_error.get("message") or "Google Vision không thể đọc ảnh."))
    full_text = response_payload.get("fullTextAnnotation", {}).get("text", "")
    annotations = response_payload.get("textAnnotations", [])
    text = full_text or (annotations[0].get("description", "") if annotations else "")
    model_text = _model_api_ocr_text(image_base64, mime_type)
    if model_text and model_text not in text:
        text = f"{text}\n{model_text}".strip()
    return {
        "text": text,
        "provider": str(_google_vision_status_payload().get("provider") or "google-vision"),
        "mode": mode,
    }


def user_id_from_request(request) -> int:
    user_id = getattr(request.user, "id", None)
    if user_id in (None, "", 0):
        raise NotAuthenticated("Authenticated user context does not include a valid user_id.")

    try:
        return int(user_id)
    except (TypeError, ValueError) as exc:
        raise NotAuthenticated("Authenticated user context contains an invalid user_id.") from exc


def ensure_shadow_user(request) -> User:
    current = now()
    user_id = user_id_from_request(request)
    email = getattr(request.user, "email", "") or f"user-{user_id}@local.health"
    user, _ = User.objects.get_or_create(
        id=user_id,
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
    changed_fields: list[str] = []
    if email and user.email != email:
        user.email = email
        changed_fields.append("email")
    if email and user.full_name != email:
        user.full_name = email
        changed_fields.append("full_name")
    if changed_fields:
        user.updated_at = current
        changed_fields.append("updated_at")
        user.save(update_fields=changed_fields)
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
        "baseline": active_baseline_payload(user_id) or {"has_baseline": False},
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


def _report_highlights(
    input_features: dict,
    features: dict,
    result: dict,
    glucose_values: list[float],
) -> tuple[list[str], list[str]]:
    has_glucose = bool(
        input_features.get("fasting_glucose_mg_dl")
        or input_features.get("fasting_glucose_mmol_l")
        or glucose_values
    )
    glucose = _glucose_value_mg_dl(features) or 0
    has_bmi = bool(input_features.get("weight_kg") and input_features.get("height_cm"))
    bmi = _float_or_none(features.get("bmi")) or 0
    has_blood_pressure = bool(
        input_features.get("systolic_bp_mean") and input_features.get("diastolic_bp_mean")
    )
    systolic = _float_or_none(features.get("systolic_bp_mean")) or 0
    diastolic = _float_or_none(features.get("diastolic_bp_mean")) or 0
    peak_risk = max(float(item.get("positive_probability", 0)) for item in result.values())

    achievements: list[str] = []
    issues: list[str] = []

    if has_glucose and glucose <= 110:
        achievements.append("Đường huyết lúc đói hiện nằm trong vùng kiểm soát chấp nhận được.")
    elif has_glucose:
        issues.append("Đường huyết lúc đói còn cao, nên tiếp tục theo dõi sát hơn.")

    if len(glucose_values) >= 3:
        glucose_spread = max(glucose_values) - min(glucose_values)
        if glucose_spread <= 20:
            achievements.append("Các lần đo đường huyết trong kỳ đang duy trì tương đối ổn định.")
        else:
            issues.append("Đường huyết biến động đáng kể trong kỳ; nên duy trì giờ đo nhất quán.")
        if glucose_values[-1] - glucose_values[-2] >= 10:
            issues.append("Lần đo đường huyết gần nhất tăng rõ so với lần ngay trước đó.")

    if has_bmi and bmi < 25:
        achievements.append("BMI đang ở vùng thuận lợi cho mục tiêu kiểm soát nguy cơ.")
    elif has_bmi:
        issues.append("BMI còn cao, nên duy trì điều chỉnh cân nặng và vận động.")

    if has_blood_pressure and systolic < 130 and diastolic < 85:
        achievements.append("Huyết áp đang trong vùng kiểm soát của báo cáo này.")
    elif has_blood_pressure:
        issues.append("Chỉ số huyết áp cần được theo dõi định kỳ để giảm rủi ro tim mạch.")

    if peak_risk >= 0.5:
        issues.append("Kết quả dự đoán đang ghi nhận ít nhất một nhóm nguy cơ ở mức đáng chú ý.")
    else:
        achievements.append("Mức nguy cơ dự đoán hiện nằm dưới ngưỡng cảnh báo cao.")

    if not input_features.get("hba1c_percent"):
        issues.append("Chưa có HbA1c thực tế; độ tin cậy của đánh giá đường huyết dài hạn bị hạn chế.")

    if not achievements:
        achievements.append("Đã lưu hồ sơ chẩn đoán để tiếp tục theo dõi ở các lần tiếp theo.")
    if not issues:
        issues.append("Nên duy trì lịch đo đều đặn để dashboard phản ánh xu hướng chính xác hơn.")

    return achievements[:3], issues[:3]


def _upsert_periodic_report(
    user_id: int,
    period_type: str,
    profile: HealthProfile,
    input_features: dict,
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
    glucose_values = [float(value) for value in glucose_queryset.order_by("measured_at").values_list("glucose_value", flat=True)]
    achievements, issues = _report_highlights(input_features, features, result, glucose_values)

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
    ).order_by("-generated_at", "-id").first()

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


def _feature_snapshot_metadata(input_features: dict, features: dict) -> dict:
    provided_fields = {
        key
        for key, value in input_features.items()
        if value is not None and value != ""
    }
    derived_fields: set[str] = set()

    if input_features.get("weight_kg") and input_features.get("height_cm"):
        derived_fields.add("bmi")
    if "waist_cm" not in provided_fields and input_features.get("height_cm") and input_features.get("sex"):
        derived_fields.add("waist_cm")
    if "hip_cm" not in provided_fields and features.get("waist_cm") and input_features.get("sex"):
        derived_fields.add("hip_cm")
    unit_pairs = (
        ("fasting_glucose_mg_dl", "fasting_glucose_mmol_l"),
        ("insulin_uU_ml", "insulin_pmol_l"),
        ("total_cholesterol_mg_dl", "total_cholesterol_mmol_l"),
    )
    for primary_key, secondary_key in unit_pairs:
        if primary_key in provided_fields and secondary_key not in provided_fields:
            derived_fields.add(secondary_key)
        elif secondary_key in provided_fields and primary_key not in provided_fields:
            derived_fields.add(primary_key)

    provided_fields -= derived_fields
    defaulted_fields = set(features) - provided_fields - derived_fields
    field_sources = {
        key: (
            "provided"
            if key in provided_fields
            else "derived"
            if key in derived_fields
            else "defaulted"
        )
        for key in features
    }

    return {
        "schema_version": 1,
        "field_sources": field_sources,
        "provided_fields": sorted(provided_fields),
        "derived_fields": sorted(derived_fields),
        "defaulted_fields": sorted(defaulted_fields),
    }


def save_prediction_snapshot(request, input_features: dict, features: dict, result: dict) -> None:
    try:
        with transaction.atomic():
            user = ensure_shadow_user(request)
            current = now()
            active_baseline = ClinicalBaseline.objects.filter(
                user_id=user.id,
                status="ACTIVE",
            ).order_by("-effective_at", "-id").first()
            diagnosis_session = DiagnosisSession.objects.create(
                user_id=user.id,
                session_type="DIAGNOSIS",
                source_type="MANUAL_OR_OCR",
                baseline_id=active_baseline.id if active_baseline else None,
                sample_collected_at=current,
                status="VERIFIED",
                created_at=current,
                updated_at=current,
            )
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
                diagnosis_session_id=diagnosis_session.id,
                assessment_type="DIAGNOSIS",
                risk_level=risk_band(max_probability),
                health_score=decimal_or_none(health_score),
                summary="Diagnosis risk prediction generated by health-service.",
                findings_json={
                    "input_features": input_features,
                    "normalized_features": features,
                    "feature_metadata": _feature_snapshot_metadata(input_features, features),
                    "result": result,
                },
                created_at=current,
            )

            for prediction_type, item in result.items():
                probability = float(item.get("positive_probability", 0))
                RiskPrediction.objects.create(
                    user_id=user.id,
                    assessment_id=assessment.id,
                    diagnosis_session_id=diagnosis_session.id,
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

            _upsert_periodic_report(
                user.id,
                "WEEKLY",
                profile,
                input_features,
                features,
                result,
                current,
                health_score,
            )
            _upsert_periodic_report(
                user.id,
                "MONTHLY",
                profile,
                input_features,
                features,
                result,
                current,
                health_score,
            )
    except DatabaseError:
        # Prediction must stay usable while schema/data is being wired into the full system.
        return


class HealthCheckView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"status": "UP", "service": "health-service"})


class GoogleVisionOcrStatusView(APIView):
    def get(self, request):
        return Response(_google_vision_status_payload())


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
                if report_id:
                    report = PeriodicReport.objects.filter(id=report_id, user_id=user.id).first()
                else:
                    period_type = serializer.validated_data["period_type"]
                    start, end = report_period_bounds(period_type)
                    report = (
                        PeriodicReport.objects.filter(
                            user_id=user.id,
                            period_type=period_type,
                            period_start=start,
                            period_end=end,
                        )
                        .order_by("-generated_at", "-id")
                        .first()
                    )

                if report is None:
                    return Response(
                        {"message": "Chưa có báo cáo thật cho kỳ đã chọn."},
                        status=status.HTTP_404_NOT_FOUND,
                    )

                measurements = list(
                    GlucoseMeasurement.objects.filter(
                        user_id=user.id,
                        measured_at__date__gte=report.period_start,
                        measured_at__date__lte=report.period_end,
                    ).order_by("measured_at")
                )
                assessment = (
                    HealthAssessment.objects.filter(
                        user_id=user.id,
                        assessment_type="DIAGNOSIS",
                        created_at__date__gte=report.period_start,
                        created_at__date__lte=report.period_end,
                    )
                    .order_by("-created_at")
                    .first()
                )

                if export_format == "PDF":
                    file_content = build_pdf_report(report, user, measurements, assessment)
                    content_type = "application/pdf"
                    extension = "pdf"
                elif export_format == "CSV":
                    file_content = build_csv_report(measurements, assessment)
                    content_type = "text/csv; charset=utf-8"
                    extension = "csv"
                else:
                    return Response(
                        {"message": "Định dạng XLSX chưa được hỗ trợ. Hãy dùng PDF hoặc CSV."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                filename = (
                    f"health-report-{report.period_start:%Y%m%d}-{report.period_end:%Y%m%d}.{extension}"
                )
                file_url = f"generated://reports/{report.id}/{filename}"
                export = ReportExport.objects.create(
                    report_id=report.id,
                    user_id=user.id,
                    export_format=export_format,
                    file_url=file_url,
                    exported_at=current,
                )
        except DatabaseError:
            return Response({"message": "Unable to create report export"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        response = HttpResponse(file_content, content_type=content_type, status=status.HTTP_201_CREATED)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["X-Report-Export-Id"] = str(export.id)
        response["Access-Control-Expose-Headers"] = "Content-Disposition, X-Report-Export-Id"
        return response


class ReportDraftView(APIView):
    def get(self, request):
        user_id = user_id_from_request(request)
        drafts = ReportDraft.objects.filter(user_id=user_id).order_by("-updated_at")[:10]
        return Response(
            [
                {
                    "id": draft.id,
                    "period_type": draft.period_type,
                    "period_start": draft.period_start,
                    "period_end": draft.period_end,
                    "status": draft.status,
                    "updated_at": draft.updated_at,
                }
                for draft in drafts
            ]
        )

    def post(self, request):
        serializer = ReportDraftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = ensure_shadow_user(request)
        period_type = serializer.validated_data["period_type"]
        period_start, period_end = report_period_bounds(period_type)
        current = now()
        payload = dashboard_payload(user.id, period_type.lower())
        draft, created = ReportDraft.objects.update_or_create(
            user_id=user.id,
            period_type=period_type,
            period_start=period_start,
            period_end=period_end,
            defaults={
                "payload": payload,
                "status": "DRAFT",
                "updated_at": current,
                "created_at": current,
            },
        )
        return Response(
            {
                "id": draft.id,
                "period_type": draft.period_type,
                "period_start": draft.period_start,
                "period_end": draft.period_end,
                "status": draft.status,
                "updated_at": draft.updated_at,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class ClinicalBaselineListCreateView(APIView):
    def get(self, request):
        user_id = user_id_from_request(request)
        baselines = ClinicalBaseline.objects.filter(user_id=user_id).select_related(
            "diagnosis_session"
        ).order_by("-effective_at")[:20]
        response_data = []
        for baseline in baselines:
            panel = LabPanel.objects.filter(
                user_id=user_id,
                diagnosis_session_id=baseline.diagnosis_session_id,
            ).first()
            results = (
                LabResult.objects.filter(user_id=user_id, lab_panel_id=panel.id).order_by("test_name")
                if panel
                else []
            )
            observations = ClinicalObservation.objects.filter(
                user_id=user_id,
                diagnosis_session_id=baseline.diagnosis_session_id,
            ).order_by("observation_name")
            response_data.append(
                {
                    "id": baseline.id,
                    "label": baseline.label,
                    "provider_name": panel.provider_name if panel else None,
                    "sampled_at": baseline.effective_at,
                    "reported_at": panel.reported_at if panel else None,
                    "status": baseline.status,
                    "results": [
                        {
                            "id": result.id,
                            "test_code": result.test_code,
                            "test_name": result.test_name,
                            "value": float(result.value),
                            "unit": result.unit,
                            "reference_min": (
                                float(result.reference_min) if result.reference_min is not None else None
                            ),
                            "reference_max": (
                                float(result.reference_max) if result.reference_max is not None else None
                            ),
                            "reference_text": result.reference_text,
                            "abnormal_flag": result.abnormal_flag,
                            "source_type": result.source_type,
                            "is_verified": result.is_verified,
                        }
                        for result in results
                    ],
                    "observations": [
                        {
                            "id": observation.id,
                            "observation_code": observation.observation_code,
                            "observation_name": observation.observation_name,
                            "value": float(observation.value),
                            "unit": observation.unit,
                            "reference_min": (
                                float(observation.reference_min)
                                if observation.reference_min is not None
                                else None
                            ),
                            "reference_max": (
                                float(observation.reference_max)
                                if observation.reference_max is not None
                                else None
                            ),
                            "reference_text": observation.reference_text,
                            "abnormal_flag": observation.abnormal_flag,
                            "is_verified": observation.is_verified,
                        }
                        for observation in observations
                    ],
                }
            )
        return Response(response_data)

    def post(self, request):
        serializer = ClinicalBaselineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = ensure_shadow_user(request)
        current = now()
        uploaded_path = None
        file_url = data.get("file_url", "")
        file_sha256 = data.get("file_sha256", "")
        if data.get("image_base64"):
            try:
                file_url, file_sha256, uploaded_path = _save_clinical_upload(
                    user.id,
                    data["image_base64"],
                    data.get("mime_type") or "image/jpeg",
                )
            except ValueError as exc:
                return Response({"message": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                previous = ClinicalBaseline.objects.filter(user_id=user.id, status="ACTIVE").first()
                if previous:
                    previous.status = "ARCHIVED"
                    previous.archived_at = current
                    previous.save(update_fields=["status", "archived_at"])

                session = DiagnosisSession.objects.create(
                    user_id=user.id,
                    session_type="CLINICAL_BASELINE",
                    source_type="HOSPITAL_RECORD",
                    sample_collected_at=data["sampled_at"],
                    status="VERIFIED",
                    created_at=current,
                    updated_at=current,
                )
                document = ClinicalDocument.objects.create(
                    user_id=user.id,
                    diagnosis_session_id=session.id,
                    document_type="LAB_REPORT",
                    original_filename=data.get("original_filename", ""),
                    file_url=file_url,
                    mime_type=data.get("mime_type", ""),
                    provider_name=data["provider_name"],
                    sample_collected_at=data["sampled_at"],
                    ocr_engine=data.get("ocr_engine", ""),
                    raw_ocr_text=data.get("raw_ocr_text", ""),
                    confidence_score=data.get("confidence_score"),
                    verification_status="VERIFIED",
                    file_sha256=file_sha256,
                    created_at=current,
                    verified_at=current,
                )
                panel = None
                if data["results"]:
                    panel = LabPanel.objects.create(
                        user_id=user.id,
                        clinical_document_id=document.id,
                        diagnosis_session_id=session.id,
                        provider_name=data["provider_name"],
                        sampled_at=data["sampled_at"],
                        reported_at=data.get("reported_at"),
                        status="VERIFIED",
                        created_at=current,
                    )
                    LabResult.objects.bulk_create(
                        [
                            LabResult(
                                user_id=user.id,
                                lab_panel_id=panel.id,
                                test_code=item["test_code"].strip().upper(),
                                test_name=item["test_name"],
                                value=item["value"],
                                unit=item["unit"],
                                canonical_value=item.get("canonical_value") or item["value"],
                                canonical_unit=item.get("canonical_unit") or item["unit"],
                                reference_min=item.get("reference_min"),
                                reference_max=item.get("reference_max"),
                                reference_text=item.get("reference_text", ""),
                                abnormal_flag=item.get("abnormal_flag", ""),
                                source_type="HOSPITAL_LAB",
                                confidence_score=item.get("confidence_score"),
                                is_verified=True,
                                observed_at=data["sampled_at"],
                                created_at=current,
                            )
                            for item in data["results"]
                        ]
                    )

                ClinicalObservation.objects.bulk_create(
                    [
                        ClinicalObservation(
                            user_id=user.id,
                            diagnosis_session_id=session.id,
                            clinical_document_id=document.id,
                            observation_code=item["observation_code"].strip().upper(),
                            observation_name=item["observation_name"],
                            value=item["value"],
                            unit=item["unit"],
                            canonical_value=item.get("canonical_value") or item["value"],
                            canonical_unit=item.get("canonical_unit") or item["unit"],
                            reference_min=item.get("reference_min"),
                            reference_max=item.get("reference_max"),
                            reference_text=item.get("reference_text", ""),
                            abnormal_flag=item.get("abnormal_flag", ""),
                            source_type="HOSPITAL_RECORD",
                            confidence_score=item.get("confidence_score"),
                            is_verified=True,
                            observed_at=data["sampled_at"],
                            created_at=current,
                        )
                        for item in data["observations"]
                    ]
                )
                baseline = ClinicalBaseline.objects.create(
                    user_id=user.id,
                    diagnosis_session_id=session.id,
                    label=data.get("label") or f"{data['provider_name']} · {data['sampled_at']:%d/%m/%Y}",
                    effective_at=data["sampled_at"],
                    status="ACTIVE",
                    supersedes_baseline_id=previous.id if previous else None,
                    created_at=current,
                )
        except Exception:
            if uploaded_path and uploaded_path.exists():
                uploaded_path.unlink()
            raise

        return Response(
            {
                "id": baseline.id,
                "diagnosis_session_id": session.id,
                "clinical_document_id": document.id,
                "status": baseline.status,
                "result_count": len(data["results"]),
                "observation_count": len(data["observations"]),
            },
            status=status.HTTP_201_CREATED,
        )


class GoogleVisionOcrView(APIView):
    def post(self, request):
        serializer = GoogleVisionOcrSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = _perform_google_vision_ocr(
                serializer.validated_data["image_base64"],
                serializer.validated_data.get("mime_type") or "image/jpeg",
                serializer.validated_data.get("mode", "document"),
            )
        except requests.RequestException as exc:
            message, response_status = _google_vision_error_response(exc)
            return Response({"message": message}, status=response_status)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return Response({"message": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response(payload)


class ClinicalBaselineExtractView(APIView):
    def post(self, request):
        serializer = ClinicalBaselineExtractSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            ocr_payload = _perform_google_vision_ocr(
                data["image_base64"],
                data.get("mime_type") or "image/jpeg",
                data.get("mode", "document"),
            )
        except requests.RequestException as exc:
            message, response_status = _google_vision_error_response(exc)
            return Response({"message": message}, status=response_status)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            return Response({"message": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        extracted = extract_clinical_baseline(ocr_payload.get("text", ""))
        extracted.update(
            {
                "raw_ocr_text": ocr_payload.get("text", ""),
                "ocr_engine": ocr_payload.get("provider", "google-vision"),
                "original_filename": data.get("original_filename", ""),
                "mime_type": data.get("mime_type") or "image/jpeg",
            }
        )
        return Response(extracted)


class ClinicalBaselineActiveView(APIView):
    def get(self, request):
        payload = active_baseline_payload(user_id_from_request(request))
        return Response(payload or {"has_baseline": False})
