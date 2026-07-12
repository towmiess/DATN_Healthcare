from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any


NUMBER_PATTERN = re.compile(r"-?\d+(?:[.,]\d+)?")
DATE_PATTERN = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b")


OBSERVATION_RULES = (
    ("HEIGHT_CM", "Chiều cao", ("chieu cao", "height"), 80, 230, "cm"),
    ("WEIGHT_KG", "Cân nặng", ("can nang", "weight"), 20, 300, "kg"),
    ("BMI", "BMI", ("bmi", "body mass index"), 10, 80, "kg/m2"),
    ("WAIST_CM", "Vòng eo", ("vong bung", "vong eo", "waist"), 35, 220, "cm"),
    (
        "SYSTOLIC_BP",
        "Huyết áp tâm thu",
        ("huyet ap tam thu", "systolic", "sys"),
        70,
        280,
        "mmHg",
    ),
    (
        "DIASTOLIC_BP",
        "Huyết áp tâm trương",
        ("huyet ap tam truong", "diastolic", "dist", "dia"),
        35,
        180,
        "mmHg",
    ),
    ("PULSE", "Mạch", ("mach", "nhip tim", "pulse"), 25, 240, "bpm"),
)

LAB_RULES = (
    (
        "FASTING_GLUCOSE",
        "Glucose máu đói",
        ("glucose mau doi", "glucose doi", "duong huyet luc doi", "fasting glucose"),
        20,
        700,
        "mg/dL",
    ),
    ("HBA1C", "HbA1c", ("hba1c", "hbaic", "a1c"), 2, 25, "%"),
    (
        "TOTAL_CHOLESTEROL",
        "Cholesterol toàn phần",
        ("cholesterol toan phan", "total cholesterol"),
        20,
        700,
        "mg/dL",
    ),
    (
        "FASTING_INSULIN",
        "Insulin máu đói",
        ("insulin mau doi", "insulin doi", "fasting insulin", "insulin"),
        0.01,
        1000,
        "uU/mL",
    ),
)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    return re.sub(r"\s+", " ", normalized.replace("đ", "d").replace("Đ", "D")).strip().lower()


def _number(value: str) -> float:
    return float(value.replace(",", "."))


def _find_value(
    original_lines: list[str],
    normalized_lines: list[str],
    aliases: tuple[str, ...],
    minimum: float,
    maximum: float,
) -> tuple[float, str, float] | None:
    normalized_aliases = tuple(normalize_text(alias) for alias in aliases)
    for index, line in enumerate(normalized_lines):
        matched_alias = next((alias for alias in normalized_aliases if alias in line), None)
        if matched_alias is None:
            continue

        alias_end = line.find(matched_alias) + len(matched_alias)
        contexts = [(line[alias_end:], original_lines[index], 0.94, False)]
        for next_index in range(index + 1, min(len(normalized_lines), index + 5)):
            candidate_line = normalized_lines[next_index]
            is_reference_line = bool(
                re.fullmatch(
                    r"\s*(?:[<>]\s*)?\d+(?:[.,]\d+)?\s*(?:[-–]\s*\d+(?:[.,]\d+)?)?\s*",
                    candidate_line,
                )
                and ("-" in candidate_line or "<" in candidate_line or ">" in candidate_line)
            )
            contexts.append((candidate_line, original_lines[next_index], 0.8, is_reference_line))

        contexts.sort(key=lambda item: item[3])
        for candidate_text, original_context, confidence, _ in contexts:
            for match in NUMBER_PATTERN.finditer(candidate_text):
                value = _number(match.group())
                if minimum <= value <= maximum:
                    combined_context = " ".join(original_lines[index : min(len(original_lines), index + 4)])
                    return value, combined_context or original_context, confidence
    return None


def _reference_payload(value: float, context: str) -> dict[str, Any]:
    normalized = context.replace(",", ".")
    value_text = f"{value:g}"
    normalized = re.sub(rf"(?<!\d){re.escape(value_text)}(?!\d)", " ", normalized, count=1)
    less_than = re.search(r"<\s*(\d+(?:\.\d+)?)", normalized)
    greater_than = re.search(r">\s*(\d+(?:\.\d+)?)", normalized)
    range_match = re.search(r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)", normalized)

    minimum = maximum = None
    reference_text = ""
    if less_than:
        maximum = float(less_than.group(1))
        reference_text = f"<{maximum:g}"
    elif greater_than:
        minimum = float(greater_than.group(1))
        reference_text = f">{minimum:g}"
    elif range_match:
        minimum = float(range_match.group(1))
        maximum = float(range_match.group(2))
        reference_text = f"{minimum:g}-{maximum:g}"

    abnormal_flag = ""
    if minimum is not None and value < minimum:
        abnormal_flag = "L"
    if maximum is not None and value > maximum:
        abnormal_flag = "H"
    if less_than and maximum is not None and value >= maximum:
        abnormal_flag = "H"
    if greater_than and minimum is not None and value <= minimum:
        abnormal_flag = "L"

    return {
        "reference_min": minimum,
        "reference_max": maximum,
        "reference_text": reference_text,
        "abnormal_flag": abnormal_flag,
    }


def _canonical_lab_value(code: str, value: float, context: str, default_unit: str) -> tuple[float, str, str]:
    normalized_context = normalize_text(context)
    unit = default_unit
    canonical_value = value
    canonical_unit = default_unit

    if code == "FASTING_GLUCOSE":
        if "mmol/l" in normalized_context or "mmol l" in normalized_context:
            unit = "mmol/L"
            canonical_value = value * 18
        canonical_unit = "mg/dL"
    elif code == "TOTAL_CHOLESTEROL":
        if "mmol/l" in normalized_context or "mmol l" in normalized_context:
            unit = "mmol/L"
            canonical_value = value * 38.67
        canonical_unit = "mg/dL"
    elif code == "FASTING_INSULIN":
        if "pmol/l" in normalized_context or "pmol l" in normalized_context:
            unit = "pmol/L"
            canonical_value = value / 6
        canonical_unit = "uU/mL"

    return round(canonical_value, 4), canonical_unit, unit


def _extract_date(lines: list[str], normalized_lines: list[str], aliases: tuple[str, ...]) -> str | None:
    for line, normalized_line in zip(lines, normalized_lines):
        if not any(normalize_text(alias) in normalized_line for alias in aliases):
            continue
        match = DATE_PATTERN.search(line)
        if match:
            day, month, year = (int(item) for item in match.groups())
            return datetime(year, month, day).isoformat()
    return None


def extract_clinical_baseline(text: str) -> dict[str, Any]:
    original_lines = [line.strip() for line in text.splitlines() if line.strip()]
    normalized_lines = [normalize_text(line) for line in original_lines]

    provider_name = next(
        (line for line, normalized in zip(original_lines, normalized_lines) if "benh vien" in normalized),
        "",
    )
    sampled_at = _extract_date(original_lines, normalized_lines, ("ngày lấy mẫu", "sampling date"))
    reported_at = _extract_date(original_lines, normalized_lines, ("ngày trả kết quả", "reported date"))

    metadata: dict[str, Any] = {
        "provider_name": provider_name,
        "sampled_at": sampled_at,
        "reported_at": reported_at,
    }
    for line in normalized_lines:
        if "gioi tinh" in line or "gender" in line:
            if re.search(r"\b(nu|female)\b", line):
                metadata["sex"] = 2
            elif re.search(r"\b(nam|male)\b", line):
                metadata["sex"] = 1
        if "tuoi" in line or "age" in line:
            age = next((_number(item) for item in NUMBER_PATTERN.findall(line) if 0 <= _number(item) <= 120), None)
            if age is not None:
                metadata["age_years"] = int(age)

    observations = []
    for code, name, aliases, minimum, maximum, unit in OBSERVATION_RULES:
        extracted = _find_value(original_lines, normalized_lines, aliases, minimum, maximum)
        if extracted is None:
            continue
        value, context, confidence = extracted
        observations.append(
            {
                "observation_code": code,
                "observation_name": name,
                "value": value,
                "unit": unit,
                "canonical_value": value,
                "canonical_unit": unit,
                "confidence_score": confidence,
                **_reference_payload(value, context),
            }
        )

    results = []
    for code, name, aliases, minimum, maximum, default_unit in LAB_RULES:
        extracted = _find_value(original_lines, normalized_lines, aliases, minimum, maximum)
        if extracted is None:
            continue
        value, context, confidence = extracted
        canonical_value, canonical_unit, unit = _canonical_lab_value(code, value, context, default_unit)
        results.append(
            {
                "test_code": code,
                "test_name": name,
                "value": value,
                "unit": unit,
                "canonical_value": canonical_value,
                "canonical_unit": canonical_unit,
                "confidence_score": confidence,
                **_reference_payload(value, context),
            }
        )

    confidences = [item["confidence_score"] for item in observations + results]
    return {
        "metadata": metadata,
        "observations": observations,
        "results": results,
        "confidence_score": round(sum(confidences) / len(confidences), 2) if confidences else 0,
    }
