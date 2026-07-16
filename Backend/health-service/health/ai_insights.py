from __future__ import annotations

import base64
import hmac
import json
import os
import re
from hashlib import sha256
from typing import Any
from uuid import uuid4

import requests
from django.conf import settings
from django.db import DatabaseError

from .models import AiInsight, HealthAssessment, RiskPrediction, User
from .services import dashboard_payload, now


LOWER_IS_BETTER = {
    "fasting_glucose_mg_dl",
    "fasting_glucose_mmol_l",
    "hba1c_percent",
    "weight_kg",
    "bmi",
    "waist_cm",
    "hip_cm",
    "systolic_bp_mean",
    "diastolic_bp_mean",
    "total_cholesterol_mg_dl",
    "total_cholesterol_mmol_l",
    "insulin_uU_ml",
    "insulin_pmol_l",
}

METRIC_LABELS = {
    "fasting_glucose_mg_dl": "Glucose đói",
    "fasting_glucose_mmol_l": "Glucose đói",
    "hba1c_percent": "HbA1c",
    "weight_kg": "Cân nặng",
    "bmi": "BMI",
    "waist_cm": "Vòng eo",
    "hip_cm": "Vòng hông",
    "systolic_bp_mean": "Huyết áp tâm thu",
    "diastolic_bp_mean": "Huyết áp tâm trương",
    "total_cholesterol_mg_dl": "Cholesterol toàn phần",
    "total_cholesterol_mmol_l": "Cholesterol toàn phần",
    "insulin_uU_ml": "Insulin",
    "insulin_pmol_l": "Insulin",
    "pulse_mean": "Mạch đập",
}

TERM_EXPLANATIONS = {
    "fasting_glucose_mg_dl": "Glucose đói là lượng đường trong máu sau khi nhịn ăn; chỉ số cao cho thấy đường huyết đang khó kiểm soát.",
    "fasting_glucose_mmol_l": "Glucose đói là lượng đường trong máu sau khi nhịn ăn; chỉ số cao cho thấy đường huyết đang khó kiểm soát.",
    "hba1c_percent": "HbA1c phản ánh mức đường huyết trung bình trong khoảng 2-3 tháng gần đây.",
    "bmi": "BMI là chỉ số khối cơ thể, giúp ước tính tình trạng cân nặng so với chiều cao.",
    "systolic_bp_mean": "Huyết áp tâm thu là áp lực máu khi tim co bóp; nếu cao kéo dài có thể làm tăng nguy cơ tim mạch.",
    "diastolic_bp_mean": "Huyết áp tâm trương là áp lực máu khi tim nghỉ giữa hai nhịp; nếu cao kéo dài cần theo dõi thêm.",
    "total_cholesterol_mg_dl": "Cholesterol toàn phần là lượng mỡ máu tổng quát; chỉ số cao có thể làm tăng nguy cơ tim mạch.",
    "total_cholesterol_mmol_l": "Cholesterol toàn phần là lượng mỡ máu tổng quát; chỉ số cao có thể làm tăng nguy cơ tim mạch.",
    "insulin_uU_ml": "Insulin là hormone giúp đưa glucose từ máu vào tế bào; bất thường có thể liên quan đến đề kháng insulin.",
    "insulin_pmol_l": "Insulin là hormone giúp đưa glucose từ máu vào tế bào; bất thường có thể liên quan đến đề kháng insulin.",
    "pulse_mean": "Mạch đập là số lần tim đập mỗi phút; thay đổi lớn nên được theo dõi cùng triệu chứng đi kèm.",
}

PREDICTION_LABELS = {
    "DIABETES": "Nguy cơ tiểu đường",
    "PREDIABETES": "Nguy cơ tiền tiểu đường",
    "GESTATIONAL_DIABETES": "Nguy cơ tiểu đường thai kỳ",
}

PREDICTION_EXPLANATIONS = {
    "DIABETES": "Nguy cơ tiểu đường là xác suất mô hình dự đoán bạn có dấu hiệu liên quan đến bệnh tiểu đường dựa trên dữ liệu hiện có.",
    "PREDIABETES": "Tiền tiểu đường là giai đoạn đường huyết cao hơn bình thường nhưng chưa chắc đã là tiểu đường.",
    "GESTATIONAL_DIABETES": "Tiểu đường thai kỳ là rối loạn đường huyết xuất hiện hoặc được phát hiện trong thời gian mang thai.",
}


def _format_value(value: float | None, unit: str) -> str:
    if value is None:
        return "chưa có dữ liệu"
    rounded = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{rounded} {unit}".strip()


def _metric_level(key: str, current: float, delta_percent: float | None) -> tuple[str, bool]:
    """Return UI severity from common clinical reference ranges.

    These ranges are intentionally broad and only drive colors/explanations in the report UI.
    They are not used as a medical diagnosis.
    """
    if key == "fasting_glucose_mg_dl":
        if current < 70 or current >= 126:
            return "high", True
        if current >= 100:
            return "medium", True
        return "low", False
    if key == "fasting_glucose_mmol_l":
        if current < 3.9 or current >= 7.0:
            return "high", True
        if current >= 5.6:
            return "medium", True
        return "low", False
    if key == "hba1c_percent":
        if current >= 6.5:
            return "high", True
        if current >= 5.7:
            return "medium", True
        return "low", False
    if key == "bmi":
        if current >= 30 or current < 18.5:
            return "high", True
        if current >= 25:
            return "medium", True
        return "low", False
    if key == "systolic_bp_mean":
        if current >= 140 or current < 90:
            return "high", True
        if current >= 130:
            return "medium", True
        return "low", False
    if key == "diastolic_bp_mean":
        if current >= 90 or current < 60:
            return "high", True
        if current >= 80:
            return "medium", True
        return "low", False
    if key == "total_cholesterol_mg_dl":
        if current >= 240:
            return "high", True
        if current >= 200:
            return "medium", True
        return "low", False
    if key == "total_cholesterol_mmol_l":
        if current >= 6.2:
            return "high", True
        if current >= 5.2:
            return "medium", True
        return "low", False
    if key == "pulse_mean":
        if current < 50 or current > 120:
            return "high", True
        if current < 60 or current > 100:
            return "medium", True
        return "low", False
    if key == "insulin_uU_ml":
        if current < 2 or current > 25:
            return "high", True
        if current > 18:
            return "medium", True
        return "low", False
    if key == "insulin_pmol_l":
        if current < 14 or current > 174:
            return "high", True
        if current > 125:
            return "medium", True
        return "low", False

    abs_percent = abs(delta_percent or 0)
    if abs_percent >= 15:
        return "high", True
    if abs_percent >= 5:
        return "medium", True
    return "low", False


def _float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_json_loads(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        payload = json.loads(cleaned)
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            return None
        try:
            payload = json.loads(match.group(0))
            return payload if isinstance(payload, dict) else None
        except json.JSONDecodeError:
            return None


def _classify_metric(metric: dict[str, Any]) -> dict[str, Any] | None:
    current = _float(metric.get("current_value"))
    baseline = _float(metric.get("baseline_value"))
    delta = _float(metric.get("delta"))
    delta_percent = _float(metric.get("delta_percent"))
    if current is None or baseline is None or delta is None:
        return None

    key = str(metric.get("key") or "")
    label = str(metric.get("label") or METRIC_LABELS.get(key) or key)
    label = METRIC_LABELS.get(key, label)
    unit = str(metric.get("unit") or "")
    lower_is_better = key in LOWER_IS_BETTER
    is_worse = delta > 0 if lower_is_better else abs(delta_percent or 0) >= 8
    severity, is_abnormal = _metric_level(key, current, delta_percent)
    display_current = _format_value(current, unit)
    display_baseline = _format_value(baseline, unit)
    explanation = TERM_EXPLANATIONS.get(key, "Đây là chỉ số sức khỏe cần được theo dõi theo thời gian.")

    if is_worse:
        reason = (
            f"{label} hiện tại là {display_current}, tăng {delta:+.2f} {unit} so với chỉ số ban đầu ({display_baseline})."
            if lower_is_better
            else f"{label} hiện tại là {display_current}, thay đổi {delta:+.2f} {unit} so với chỉ số ban đầu ({display_baseline})."
        )
    else:
        reason = f"{label} hiện tại là {display_current}, đang cải thiện hoặc ổn định so với chỉ số ban đầu ({delta:+.2f} {unit})."

    return {
        "key": key,
        "label": label,
        "unit": unit,
        "baseline_value": baseline,
        "current_value": current,
        "display_value": display_current,
        "delta": delta,
        "delta_percent": delta_percent,
        "severity": severity,
        "direction": "worse" if is_worse else "better_or_stable",
        "reason": reason,
        "explanation": explanation,
        "is_abnormal": is_abnormal,
    }


def _latest_assessment_and_prediction(user_id: int) -> tuple[HealthAssessment | None, RiskPrediction | None, list[dict[str, Any]]]:
    assessment = (
        HealthAssessment.objects.filter(user_id=user_id)
        .order_by("-created_at", "-id")
        .first()
    )
    if assessment is None:
        return None, None, []

    predictions = list(
        RiskPrediction.objects.filter(user_id=user_id, assessment_id=assessment.id)
        .order_by("-risk_percent", "prediction_type")
    )
    prediction_payload = [
        {
            "prediction_type": item.prediction_type,
            "risk_percent": float(item.risk_percent),
            "risk_band": item.risk_band,
            "high_risk_flag": item.high_risk_flag,
            "model_name": item.model_name,
        }
        for item in predictions
    ]
    return assessment, predictions[0] if predictions else None, prediction_payload


def _build_local_context(user: User, period_type: str, intent: str) -> dict[str, Any]:
    dashboard = dashboard_payload(user.id, period_type)
    assessment, top_prediction, predictions = _latest_assessment_and_prediction(user.id)

    metrics = [
        classified
        for metric in dashboard.get("baseline_tracking", [])
        for classified in [_classify_metric(metric)]
        if classified is not None
    ]
    metrics.sort(
        key=lambda item: (
            item["direction"] != "worse",
            -(abs(item.get("delta_percent") or 0)),
        )
    )

    worsening = [item for item in metrics if item["direction"] == "worse"]
    improving = [item for item in metrics if item["direction"] != "worse"]
    data_quality = dashboard.get("data_quality") or {}
    drivers = worsening[:4] or improving[:3]

    missing_groups = data_quality.get("missing_groups") or []
    if missing_groups:
        drivers.append(
            {
                "key": "data_quality",
                "label": "Độ đầy đủ dữ liệu",
                "unit": "",
                "baseline_value": None,
                "current_value": data_quality.get("coverage_percent"),
                "delta": None,
                "delta_percent": None,
                "severity": "medium",
                "direction": "missing_data",
                "reason": f"Thiếu dữ liệu: {', '.join(str(item) for item in missing_groups[:4])}.",
                "explanation": "Một số nhóm dữ liệu còn thiếu nên phân tích có thể chưa phản ánh đầy đủ tình trạng hiện tại.",
                "is_abnormal": True,
            }
        )

    if predictions:
        top = predictions[0]
        prediction_type = str(top.get("prediction_type") or "")
        prediction_band = str(top.get("risk_band") or "").upper()
        prediction_label = PREDICTION_LABELS.get(prediction_type, f"Nguy cơ {prediction_type}".strip())
        prediction_explanation = PREDICTION_EXPLANATIONS.get(
            prediction_type,
            "Đây là mức nguy cơ do mô hình dự đoán từ các chỉ số sức khỏe hiện có.",
        )
        prediction_severity = "high" if prediction_band == "HIGH" else "medium" if prediction_band == "WARNING" else "low"
        drivers.insert(
            0,
            {
                "key": "risk_prediction",
                "label": prediction_label,
                "unit": "%",
                "baseline_value": None,
                "current_value": top.get("risk_percent"),
                "delta": None,
                "delta_percent": None,
                "severity": prediction_severity,
                "direction": "risk_signal",
                "reason": f"{prediction_label} đang ở mức {top.get('risk_percent')}% ({top.get('risk_band')}).",
                "explanation": prediction_explanation,
                "display_value": f"{top.get('risk_percent')}%",
                "is_abnormal": prediction_severity != "low",
            },
        )

    return {
        "intent": intent,
        "period_type": dashboard.get("period_type"),
        "overview": dashboard.get("overview") or {},
        "data_quality": data_quality,
        "drivers": drivers[:5],
        "all_metrics": metrics[:8],
        "predictions": predictions,
        "issues": dashboard.get("issues") or [],
        "achievements": dashboard.get("achievements") or [],
        "baseline": dashboard.get("baseline") or {},
        "latest_assessment_id": assessment.id if assessment else None,
        "top_prediction_id": top_prediction.id if top_prediction else None,
    }


def _gateway_headers(user: User) -> dict[str, str]:
    payload = {
        "userId": user.id,
        "user_id": user.id,
        "email": user.email,
        "roles": ["USER"],
        "tokenId": "health-ai-insights",
    }
    encoded = base64.b64encode(json.dumps(payload, ensure_ascii=False).encode("utf-8")).decode("utf-8")
    signature = base64.b64encode(
        hmac.new(
            settings.GATEWAY_INTERNAL_SECRET.encode("utf-8"),
            encoded.encode("utf-8"),
            sha256,
        ).digest()
    ).decode("utf-8")
    return {"X-User-Context": encoded, "X-User-Context-Signature": signature}


def _rag_context(user: User, local_context: dict[str, Any]) -> dict[str, Any]:
    rag_url = getattr(settings, "RAG_SERVICE_URL", "").rstrip("/")
    if not rag_url:
        return {"used": False, "summary": "", "sources": [], "error": "RAG_SERVICE_URL is not configured"}

    driver_text = "; ".join(str(item.get("reason")) for item in local_context.get("drivers", []) if item.get("reason"))
    if not driver_text:
        driver_text = "người dùng cần lời khuyên kiểm soát tiểu đường cá nhân hóa dựa trên chỉ số sức khỏe"

    prompt = (
        "Tìm tài liệu y khoa liên quan để giải thích ngắn gọn và an toàn cho bệnh nhân tiểu đường. "
        "Chỉ tóm tắt khuyến nghị y khoa, không đưa chẩn đoán chắc chắn. Dữ liệu người dùng: "
        f"{driver_text}"
    )
    try:
        response = requests.post(
            f"{rag_url}/chat",
            json={
                "query": prompt,
                "top_k": 4,
                "patient_context": {
                    "drivers": local_context.get("drivers", []),
                    "overview": local_context.get("overview", {}),
                    "predictions": local_context.get("predictions", []),
                },
            },
            headers=_gateway_headers(user),
            timeout=getattr(settings, "AI_INSIGHT_RAG_TIMEOUT", 12),
        )
        response.raise_for_status()
        data = response.json()
        return {
            "used": True,
            "summary": str(data.get("response") or "")[:2200],
            "sources": data.get("sources") or [],
            "chunks_used": data.get("chunks_used") or 0,
        }
    except Exception as exc:
        return {"used": False, "summary": "", "sources": [], "error": str(exc)}


def _gemini_keys() -> list[str]:
    keys: list[str] = []
    for name in ("GEMINI_API_KEY", "GEMINI_API_KEY_1", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3", "GEMINI_API_KEY_4", "GEMINI_API_KEY_5", "GEMINI_API_KEY_6"):
        value = os.getenv(name, "").strip()
        if value and value not in keys:
            keys.append(value)
    return keys


def _fallback_payload(local_context: dict[str, Any], rag_context: dict[str, Any]) -> dict[str, Any]:
    drivers = local_context.get("drivers") or []
    intent = local_context.get("intent")
    primary = drivers[0] if drivers else None
    title = "Chỉ số nên ưu tiên cải thiện" if intent == "improve_metrics" else "Phân tích chỉ số"

    if primary:
        summary = f"Dựa vào những chỉ số của bạn, mình thấy điểm nên chú ý trước là {primary.get('reason')}"
        if primary.get("explanation"):
            summary = f"{summary} Nói đơn giản, {primary.get('explanation')}"
        summary = f"{summary} Bạn chưa cần quá lo lắng ngay, nhưng nên theo dõi đều và ưu tiên cải thiện từng bước nhỏ."
    else:
        summary = "Dựa vào những chỉ số của bạn, hiện mình chưa thấy một điểm bất thường thật nổi bật. Bạn cứ tiếp tục ghi nhận các lần đo mới để phần phân tích sau chính xác và hữu ích hơn."

    recommendations = [
        "Theo dõi lại các chỉ số nổi bật trong 1-4 tuần và ghi rõ thời điểm đo.",
        "Ưu tiên chế độ ăn cân bằng lượng carbohydrate, vận động, tập thể dục thường xuyên và dùng thuốc đúng hướng dẫn của bác sĩ.",
        "Nên chia nhỏ các bữa ăn (3 bữa chính - 2 bữa phụ) để giảm tránh tình trạng tụt đường huyết và hạn chế lượng tinh bột khi ăn hàng ngày ",
        "Hạn chế các loại bánh kẹo ngọt chứa nhiều đường, các loại quả sấy khô, rượu, bia, nước chè, nước ngọt có đường...",
        "Nên ăn các loại hoa quả có hàm lượng đường ít, trung bình: dưa chuột, gioi, thanh long trắng, bưởi, ổi, cam,... (hoa quả nên ăn nguyên tép, múi miếng)",
        "Gợi ý một số loại sữa có chỉ số đường huyết thấp phù hợp cho người tiểu đường: Glucerna, Nutricare cerna, Nutrien diabetes...",
        "Nếu chỉ số tăng nhanh, có triệu chứng bất thường hoặc đường huyết quá cao/quá thấp, hãy liên hệ nhân viên y tế.",
    ]
    focus_metrics = [
        {
            "key": item.get("key"),
            "label": item.get("label"),
            "why": " ".join(
                part
                for part in (str(item.get("reason") or "").strip(), str(item.get("explanation") or "").strip())
                if part
            ),
            "priority": item.get("severity"),
            "is_abnormal": bool(item.get("is_abnormal")),
        }
        for item in drivers[:4]
    ]
    return {
        "title": title,
        "summary": summary,
        "drivers": drivers,
        "recommendations": recommendations,
        "focus_metrics": focus_metrics,
        "disclaimer": "Thông tin này chỉ hỗ trợ theo dõi sức khỏe, không thay thế chẩn đoán hoặc phác đồ điều trị của bác sĩ.",
    }


def _normalise_ai_payload(payload: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    def list_of_strings(value: Any, default: list[str]) -> list[str]:
        if isinstance(value, list):
            items = [str(item).strip() for item in value if str(item).strip()]
            return items[:6] if items else default
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return default

    drivers = fallback["drivers"]
    focus_metrics = fallback["focus_metrics"]
    title = str(payload.get("title") or fallback["title"])
    if "nguyên nhân" in title.lower():
        title = "Phân tích chỉ số"
    summary = str(payload.get("summary") or fallback["summary"])
    summary = summary.replace("Tham chiếu y khoa từ RAG nhấn mạnh:", "Dựa vào những chỉ số của bạn,")
    summary = summary.replace("Các khuyến nghị bên dưới được đối chiếu với tài liệu y khoa liên quan.", "")
    summary = re.sub(r"\s{2,}", " ", summary).strip()

    return {
        "title": title[:180],
        "summary": summary[:2400],
        "drivers": drivers[:6],
        "recommendations": list_of_strings(payload.get("recommendations"), fallback["recommendations"]),
        "focus_metrics": focus_metrics[:6],
        "disclaimer": str(payload.get("disclaimer") or fallback["disclaimer"])[:500],
    }


def _gemini_payload(local_context: dict[str, Any], rag_context: dict[str, Any]) -> tuple[dict[str, Any], str]:
    fallback = _fallback_payload(local_context, rag_context)
    keys = _gemini_keys()
    if not keys:
        return fallback, "local-fallback"

    model = getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash-lite")
    prompt = f"""
Bạn là trợ lý AI y khoa cho ứng dụng theo dõi tiểu đường. Hãy giải thích bằng tiếng Việt, thân thiện, rõ ý, dựa trên dữ liệu đã được backend tính sẵn. Không tự bịa chỉ số, không chẩn đoán chắc chắn.

Yêu cầu bắt buộc:
- Không dùng cụm "Tham chiếu y khoa từ RAG nhấn mạnh".
- Không dùng câu "Các khuyến nghị bên dưới được đối chiếu với tài liệu y khoa liên quan".
- Mở đầu summary bằng "Dựa vào những chỉ số của bạn".
- Giải thích ngắn gọn các thuật ngữ khó như Diabetes/tiểu đường, Glucose, HbA1c nếu chúng xuất hiện.
- Viết thân thiện như đang động viên người dùng: dễ hiểu, nhẹ nhàng, không làm họ hoang mang.
- Viết câu hoàn chỉnh, không dừng giữa câu. Ưu tiên 3-5 câu ngắn thay vì một đoạn quá dài.
- Nếu chỉ số cao hoặc tăng, nói rõ tên chỉ số, giá trị và vì sao cần chú ý.

Ý định người dùng: {local_context.get('intent')}
Dữ liệu đã tính sẵn:
{json.dumps(local_context, ensure_ascii=False, indent=2)}

Ngữ cảnh y khoa truy xuất từ RAG, chỉ dùng để đối chiếu khuyến nghị:
{rag_context.get('summary') or 'Không có ngữ cảnh RAG khả dụng.'}

Trả về DUY NHẤT JSON hợp lệ theo schema:
{{
  "title": "Phân tích chỉ số",
  "summary": "Dựa vào những chỉ số của bạn, ...",
  "drivers": [{{"label":"...", "reason":"...", "explanation":"...", "severity":"low|medium|high", "is_abnormal": true}}],
  "recommendations": ["3-5 lời khuyên hành động cụ thể"],
  "focus_metrics": [{{"key":"...", "label":"...", "why":"...", "priority":"low|medium|high", "is_abnormal": true}}],
  "disclaimer": "câu nhắc không thay thế bác sĩ"
}}
""".strip()

    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 1800,
            "responseMimeType": "application/json",
        },
    }

    last_error = ""
    for key in keys:
        try:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": key},
                json=body,
                timeout=getattr(settings, "AI_INSIGHT_LLM_TIMEOUT", 24),
            )
            response.raise_for_status()
            data = response.json()
            text = (
                data.get("candidates", [{}])[0]
                .get("content", {})
                .get("parts", [{}])[0]
                .get("text", "")
            )
            parsed = _safe_json_loads(text)
            if parsed:
                return _normalise_ai_payload(parsed, fallback), model
            last_error = "Gemini returned non-json response"
        except Exception as exc:
            last_error = str(exc)
            continue

    payload = dict(fallback)
    payload["llm_error"] = last_error
    return payload, "local-fallback"


def _response_payload(
    ai_payload: dict[str, Any],
    local_context: dict[str, Any],
    rag: dict[str, Any],
    model: str,
    intent: str,
    cached: bool = False,
) -> dict[str, Any]:
    return {
        **ai_payload,
        "intent": intent,
        "period_type": local_context.get("period_type"),
        "llm_model": model,
        "rag_context": {
            "used": bool(rag.get("used")),
            "sources": rag.get("sources") or [],
            "chunks_used": rag.get("chunks_used") or 0,
            "error": rag.get("error", ""),
            "cached": cached,
        },
        "generated_at": now().isoformat(),
        "request_id": str(uuid4()),
    }


def _cached_ai_payload(user: User, local_context: dict[str, Any], intent: str, period_type: str) -> tuple[dict[str, Any], str] | None:
    assessment_id = local_context.get("latest_assessment_id")
    insight_type = f"{intent}:{period_type}"
    if not assessment_id:
        return None

    cached = (
        AiInsight.objects.filter(
            user_id=user.id,
            assessment_id=assessment_id,
            insight_type__in=[insight_type, intent],
        )
        .order_by("-created_at", "-id")
        .first()
    )
    if cached is None:
        return None

    fallback = _fallback_payload(local_context, {"used": False, "summary": "", "sources": []})
    payload = {
        **fallback,
        "summary": cached.explanation or fallback["summary"],
    }
    return payload, cached.llm_model or "cached"


def _save_ai_insight(user: User, local_context: dict[str, Any], insight_type: str, ai_payload: dict[str, Any], model: str) -> None:
    try:
        AiInsight.objects.create(
            user_id=user.id,
            assessment_id=local_context.get("latest_assessment_id"),
            risk_prediction_id=local_context.get("top_prediction_id"),
            insight_type=insight_type,
            explanation=ai_payload.get("summary", ""),
            recommendation="\n".join(ai_payload.get("recommendations", [])),
            llm_model=model,
            created_at=now(),
        )
    except DatabaseError:
        pass


def generate_ai_insight(user: User, period_type: str, intent: str, force_refresh: bool = False) -> dict[str, Any]:
    local_context = _build_local_context(user, period_type, intent)
    insight_type = f"{intent}:{period_type}"
    if not force_refresh:
        cached = _cached_ai_payload(user, local_context, intent, period_type)
        if cached:
            cached_payload, cached_model = cached
            return _response_payload(
                cached_payload,
                local_context,
                {"used": False, "summary": "", "sources": [], "cached": True},
                cached_model,
                intent,
                cached=True,
            )

        rag_stub = {"used": False, "summary": "", "sources": [], "error": "", "auto_fast": True}
        ai_payload = _fallback_payload(local_context, rag_stub)
        model = "local-fast-cache"
        _save_ai_insight(user, local_context, insight_type, ai_payload, model)
        return _response_payload(ai_payload, local_context, rag_stub, model, intent)

    rag = _rag_context(user, local_context)
    ai_payload, model = _gemini_payload(local_context, rag)
    _save_ai_insight(user, local_context, insight_type, ai_payload, model)

    return _response_payload(ai_payload, local_context, rag, model, intent)
