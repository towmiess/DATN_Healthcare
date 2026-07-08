from __future__ import annotations

import base64
import io
import math
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from PIL import Image, ImageOps


app = FastAPI(title="Diagnosis Model API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class OCRRequest(BaseModel):
    image_base64: str = Field(..., description="Base64 payload without data URI prefix")
    mime_type: str = Field(default="image/jpeg", description="Declared image mime type")


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        text = str(value).strip()
        if not text:
            return None
        return float(text)
    except (TypeError, ValueError):
        return None


def _get_number(payload: dict[str, Any], key: str) -> float | None:
    return _as_float(payload.get(key))


def _sigmoid(value: float) -> float:
    if value >= 0:
        z = math.exp(-value)
        return 1.0 / (1.0 + z)
    z = math.exp(value)
    return z / (1.0 + z)


def _scaled(payload: dict[str, Any], key: str, center: float, spread: float) -> float:
    number = _get_number(payload, key)
    if number is None or spread <= 0:
        return 0.0
    return max(-3.0, min(3.0, (number - center) / spread))


def _binary(payload: dict[str, Any], key: str) -> float:
    number = _get_number(payload, key)
    if number is None:
        return 0.0
    return 1.0 if number >= 0.5 else 0.0


def _risk_result(score: float, label: str) -> dict[str, Any]:
    probability = _sigmoid(score)
    return {
        "prediction": 1 if probability >= 0.5 else 0,
        "label": label,
        "positive_probability": round(probability, 4),
    }


def _predict_diabetes(payload: dict[str, Any]) -> dict[str, Any]:
    score = -2.15
    score += 0.95 * _scaled(payload, "age_years", 45, 15)
    score += 1.20 * _scaled(payload, "bmi", 25, 4)
    score += 0.65 * _scaled(payload, "waist_cm", 88, 10)
    score += 1.95 * _scaled(payload, "hba1c_percent", 5.6, 0.55)
    score += 1.55 * _scaled(payload, "fasting_glucose_mg_dl", 100, 20)
    score += 1.10 * _scaled(payload, "fasting_glucose_mmol_l", 5.5, 0.75)
    score += 0.55 * _scaled(payload, "insulin_uU_ml", 12, 8)
    score += 0.30 * _scaled(payload, "total_cholesterol_mg_dl", 190, 35)
    score += 0.25 * _binary(payload, "high_blood_pressure_history")
    score += 0.12 * _binary(payload, "sex")  # small sex-based bias for baseline parity
    score += 0.12 * _scaled(payload, "fasting_hours", 10, 2)
    score += 0.05 * _scaled(payload, "fasting_minutes", 15, 15)
    return _risk_result(score, "Muc uoc tinh tu 22 chi so dau vao")


def _predict_cardio(payload: dict[str, Any]) -> dict[str, Any]:
    score = -2.40
    score += 1.05 * _scaled(payload, "age_years", 50, 15)
    score += 0.30 * _binary(payload, "sex")
    score += 0.90 * _scaled(payload, "bmi", 26, 4)
    score += 0.75 * _scaled(payload, "waist_cm", 90, 10)
    score += 0.45 * _scaled(payload, "hip_cm", 98, 8)
    score += 1.25 * _scaled(payload, "systolic_bp_mean", 120, 15)
    score += 1.00 * _scaled(payload, "diastolic_bp_mean", 80, 10)
    score += 0.70 * _scaled(payload, "pulse_mean", 75, 12)
    score += 0.75 * _scaled(payload, "total_cholesterol_mg_dl", 200, 35)
    score += 0.35 * _binary(payload, "high_blood_pressure_history")
    score += 0.15 * _scaled(payload, "hba1c_percent", 5.6, 0.55)
    score += 0.05 * _binary(payload, "race_ethnicity_asian")
    return _risk_result(score, "Muc uoc tinh tu 22 chi so dau vao")


def _predict_stroke(payload: dict[str, Any]) -> dict[str, Any]:
    score = -3.10
    score += 1.30 * _scaled(payload, "age_years", 55, 15)
    score += 0.30 * _binary(payload, "sex")
    score += 1.20 * _scaled(payload, "systolic_bp_mean", 125, 15)
    score += 0.95 * _scaled(payload, "diastolic_bp_mean", 80, 10)
    score += 0.65 * _scaled(payload, "pulse_mean", 78, 12)
    score += 0.75 * _binary(payload, "high_blood_pressure_history")
    score += 0.65 * _scaled(payload, "hba1c_percent", 5.7, 0.6)
    score += 0.55 * _scaled(payload, "fasting_glucose_mg_dl", 105, 20)
    score += 0.45 * _scaled(payload, "bmi", 27, 4)
    score += 0.40 * _scaled(payload, "total_cholesterol_mg_dl", 200, 35)
    score += 0.20 * _binary(payload, "race_ethnicity_asian")
    return _risk_result(score, "Muc uoc tinh tu 22 chi so dau vao")


@app.get("/")
def root() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "diagnosis-model-api",
        "endpoints": ["/health", "/predict/all", "/ocr/google-vision"],
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok"}


@app.post("/predict/all")
def predict_all(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Payload must be a JSON object")

    return {
        "diabetes": _predict_diabetes(payload),
        "cardio": _predict_cardio(payload),
        "stroke": _predict_stroke(payload),
    }


def _decode_image(image_base64: str) -> Image.Image:
    try:
        raw = base64.b64decode(image_base64, validate=True)
    except Exception as exc:  # pragma: no cover - defensive validation
        raise HTTPException(status_code=400, detail="Invalid base64 image payload") from exc

    try:
        image = Image.open(io.BytesIO(raw))
        return ImageOps.exif_transpose(image).convert("RGB")
    except Exception as exc:  # pragma: no cover - defensive validation
        raise HTTPException(status_code=400, detail="Unable to decode image") from exc


def _binarize(gray: np.ndarray) -> np.ndarray:
    gray = gray.astype(np.float32)
    mean = float(gray.mean())
    std = float(gray.std())
    threshold = max(70.0, min(240.0, mean - std * 0.35))
    return gray < threshold


def _resize_mask(mask: np.ndarray, size: tuple[int, int] = (60, 100)) -> np.ndarray:
    height, width = mask.shape
    if height <= 0 or width <= 0:
        return np.zeros((size[1], size[0]), dtype=bool)

    canvas = np.zeros((size[1], size[0]), dtype=bool)
    scale = min((size[0] - 6) / width, (size[1] - 6) / height)
    new_width = max(1, int(width * scale))
    new_height = max(1, int(height * scale))

    pil_mask = Image.fromarray((mask.astype(np.uint8) * 255), mode="L")
    pil_mask = pil_mask.resize((new_width, new_height), Image.Resampling.NEAREST)
    resized = np.array(pil_mask, dtype=np.uint8) > 0

    x_offset = (size[0] - new_width) // 2
    y_offset = (size[1] - new_height) // 2
    canvas[y_offset : y_offset + new_height, x_offset : x_offset + new_width] = resized
    return canvas


def _segment_bits(mask: np.ndarray) -> tuple[int, int, int, int, int, int, int]:
    h, w = mask.shape
    segments = [
        (int(w * 0.18), int(h * 0.00), int(w * 0.82), int(h * 0.16)),  # top
        (int(w * 0.00), int(h * 0.10), int(w * 0.22), int(h * 0.48)),  # upper left
        (int(w * 0.78), int(h * 0.10), int(w * 1.00), int(h * 0.48)),  # upper right
        (int(w * 0.18), int(h * 0.42), int(w * 0.82), int(h * 0.58)),  # middle
        (int(w * 0.00), int(h * 0.52), int(w * 0.22), int(h * 0.92)),  # lower left
        (int(w * 0.78), int(h * 0.52), int(w * 1.00), int(h * 0.92)),  # lower right
        (int(w * 0.18), int(h * 0.84), int(w * 0.82), int(h * 1.00)),  # bottom
    ]

    bits: list[int] = []
    for x0, y0, x1, y1 in segments:
        x0 = max(0, min(w, x0))
        y0 = max(0, min(h, y0))
        x1 = max(0, min(w, x1))
        y1 = max(0, min(h, y1))
        region = mask[y0:y1, x0:x1]
        coverage = float(region.mean()) if region.size else 0.0
        bits.append(1 if coverage >= 0.26 else 0)
    return tuple(bits)  # type: ignore[return-value]


SEGMENT_TO_DIGIT: dict[tuple[int, int, int, int, int, int, int], str] = {
    (1, 1, 1, 0, 1, 1, 1): "0",
    (0, 0, 1, 0, 0, 1, 0): "1",
    (1, 0, 1, 1, 1, 0, 1): "2",
    (1, 0, 1, 1, 0, 1, 1): "3",
    (0, 1, 1, 1, 0, 1, 0): "4",
    (1, 1, 0, 1, 0, 1, 1): "5",
    (1, 1, 0, 1, 1, 1, 1): "6",
    (1, 0, 1, 0, 0, 1, 0): "7",
    (1, 1, 1, 1, 1, 1, 1): "8",
    (1, 1, 1, 1, 0, 1, 1): "9",
}


def _recognize_digit(mask: np.ndarray) -> str | None:
    coords = np.argwhere(mask)
    if coords.size == 0:
        return None

    y0, x0 = coords.min(axis=0)
    y1, x1 = coords.max(axis=0) + 1
    crop = mask[y0:y1, x0:x1]
    if crop.shape[0] < 5 or crop.shape[1] < 3:
        return None

    normalized = _resize_mask(crop)
    bits = _segment_bits(normalized)
    digit = SEGMENT_TO_DIGIT.get(bits)
    if digit is not None:
        return digit

    # Fallback for digits like "1" when the crop is thin or the segment
    # coverage is imperfect.
    height, width = crop.shape
    if width <= height * 0.45 and float(crop.mean()) > 0.18:
        return "1"

    return None


def _split_row_into_digits(row_mask: np.ndarray, digit_count: int) -> list[str]:
    if row_mask.size == 0:
        return []

    h, w = row_mask.shape
    left_trim = int(w * 0.02)
    right_trim = int(w * 0.02)
    row_mask = row_mask[:, left_trim : max(left_trim + 1, w - right_trim)]
    h, w = row_mask.shape

    slot_width = w / digit_count
    result: list[str] = []

    for index in range(digit_count):
        x0 = int(index * slot_width + slot_width * 0.05)
        x1 = int((index + 1) * slot_width - slot_width * 0.05)
        x0 = max(0, min(w - 1, x0))
        x1 = max(x0 + 1, min(w, x1))
        slot = row_mask[:, x0:x1]
        digit = _recognize_digit(slot)
        if digit is None:
            # Try a slightly tighter crop if the equal split missed the symbol.
            active = np.argwhere(slot)
            if active.size:
                sy0, sx0 = active.min(axis=0)
                sy1, sx1 = active.max(axis=0) + 1
                digit = _recognize_digit(slot[sy0:sy1, sx0:sx1])
        result.append(digit or "?")

    return result


def _find_mask_components(
    mask: np.ndarray,
    min_area: int,
    max_area: int,
    min_width: int = 4,
    min_height: int = 8,
    min_x_ratio: float = 0.0,
    max_x_ratio: float = 1.0,
) -> list[dict[str, float]]:
    height, width = mask.shape
    visited = np.zeros(height * width, dtype=np.uint8)
    components: list[dict[str, float]] = []

    for y in range(height):
        for x in range(width):
            index = y * width + x
            if visited[index] or not mask[y, x]:
                continue

            stack = [index]
            visited[index] = 1
            min_x = max_x = x
            min_y = max_y = y
            area = 0

            while stack:
                current = stack.pop()
                current_y = current // width
                current_x = current % width
                area += 1

                min_x = min(min_x, current_x)
                max_x = max(max_x, current_x)
                min_y = min(min_y, current_y)
                max_y = max(max_y, current_y)

                for neighbor in (current - 1, current + 1, current - width, current + width):
                    if neighbor < 0 or neighbor >= height * width or visited[neighbor]:
                        continue

                    neighbor_y = neighbor // width
                    neighbor_x = neighbor % width
                    if abs(neighbor_x - current_x) + abs(neighbor_y - current_y) != 1:
                        continue

                    if mask[neighbor_y, neighbor_x]:
                        visited[neighbor] = 1
                        stack.append(neighbor)

            component_width = max_x - min_x + 1
            component_height = max_y - min_y + 1
            if (
                area < min_area
                or area > max_area
                or component_width < min_width
                or component_height < min_height
                or min_x < width * min_x_ratio
                or max_x > width * max_x_ratio
            ):
                continue

            components.append(
                {
                    "x": float(min_x),
                    "y": float(min_y),
                    "width": float(component_width),
                    "height": float(component_height),
                    "area": float(area),
                    "center_x": (min_x + max_x) / 2,
                    "center_y": (min_y + max_y) / 2,
                }
            )

    return components


RAW_SEGMENT_REGIONS = (
    (0.15, 0.00, 0.85, 0.18),  # top
    (0.00, 0.08, 0.35, 0.48),  # upper left
    (0.65, 0.08, 1.00, 0.48),  # upper right
    (0.15, 0.38, 0.85, 0.62),  # middle
    (0.00, 0.52, 0.35, 0.94),  # lower left
    (0.65, 0.52, 1.00, 0.94),  # lower right
    (0.15, 0.82, 0.85, 1.00),  # bottom
)

RAW_SEGMENT_PATTERNS = {
    "0": "1110111",
    "1": "0010010",
    "2": "1011101",
    "3": "1011011",
    "4": "0111010",
    "5": "1101011",
    "6": "1101111",
    "7": "1010010",
    "8": "1111111",
    "9": "1111011",
}


def _classify_digit_group(mask: np.ndarray, group: dict[str, float]) -> str | None:
    x = max(0, int(group["x"]))
    y = max(0, int(group["y"]))
    width = max(1, int(group["width"]))
    height = max(1, int(group["height"]))

    if width / max(1, height) < 0.28:
        return "1"

    crop = mask[y : y + height, x : x + width]
    if crop.size == 0:
        return None

    coverages: list[float] = []
    for rx0, ry0, rx1, ry1 in RAW_SEGMENT_REGIONS:
        x0 = max(0, min(width, int(width * rx0)))
        y0 = max(0, min(height, int(height * ry0)))
        x1 = max(x0 + 1, min(width, int(width * rx1)))
        y1 = max(y0 + 1, min(height, int(height * ry1)))
        region = crop[y0:y1, x0:x1]
        coverages.append(float(region.mean()) if region.size else 0.0)

    top, upper_left, upper_right, middle, lower_left, lower_right, bottom = coverages

    if top > 0.45 and bottom > 0.45 and lower_left > 0.28 and lower_right > 0.14 and middle < 0.18:
        return "0"

    if top > 0.45 and upper_right > 0.25 and lower_right > 0.25 and middle < 0.18 and lower_left < 0.12:
        return "7"

    scored = []
    for digit, pattern in RAW_SEGMENT_PATTERNS.items():
        score = sum(
            coverages[index] if expected == "1" else 1 - coverages[index]
            for index, expected in enumerate(pattern)
        )
        scored.append((score, digit))

    scored.sort(reverse=True)
    return scored[0][1] if scored else None


def _group_components_by_x(components: list[dict[str, float]], max_gap: int) -> list[dict[str, float]]:
    groups: list[dict[str, float]] = []

    for component in sorted(components, key=lambda item: item["x"]):
        current = groups[-1] if groups else None
        component_end_x = component["x"] + component["width"]
        component_end_y = component["y"] + component["height"]

        if current is None or component["x"] > current["x"] + current["width"] + max_gap:
            groups.append(dict(component))
            continue

        current_end_x = current["x"] + current["width"]
        current_end_y = current["y"] + current["height"]
        next_x = min(current["x"], component["x"])
        next_y = min(current["y"], component["y"])
        next_end_x = max(current_end_x, component_end_x)
        next_end_y = max(current_end_y, component_end_y)

        current["x"] = next_x
        current["y"] = next_y
        current["width"] = next_end_x - next_x
        current["height"] = next_end_y - next_y
        current["area"] += component["area"]
        current["center_x"] = current["x"] + current["width"] / 2
        current["center_y"] = current["y"] + current["height"] / 2

    return groups


def _extract_omron_by_components(image: Image.Image) -> str | None:
    image_width, image_height = image.size
    crop_profiles = (
        (0.30, 0.28, 0.52, 0.34),
        (0.31, 0.30, 0.50, 0.33),
        (0.34, 0.31, 0.50, 0.38),
        (0.36, 0.30, 0.48, 0.40),
    )
    row_profiles = (
        ((0.10, 0.38, 3), (0.35, 0.64, 2), (0.59, 0.86, 2)),
        ((0.04, 0.33, 3), (0.30, 0.60, 2), (0.56, 0.82, 2)),
        ((0.14, 0.40, 3), (0.39, 0.63, 2), (0.62, 0.78, 2)),
        ((0.12, 0.39, 3), (0.38, 0.62, 2), (0.61, 0.78, 2)),
        ((0.18, 0.42, 3), (0.42, 0.73, 2), (0.67, 0.96, 2)),
    )

    best_values: list[str] | None = None
    best_score = -1

    for x_ratio, y_ratio, width_ratio, height_ratio in crop_profiles:
        crop = image.crop(
            (
                int(image_width * x_ratio),
                int(image_height * y_ratio),
                int(image_width * (x_ratio + width_ratio)),
                int(image_height * (y_ratio + height_ratio)),
            )
        )
        if crop.width > 380:
            scale = 380 / crop.width
            crop = crop.resize((380, max(1, int(crop.height * scale))), Image.Resampling.BILINEAR)
        gray = np.array(ImageOps.grayscale(crop), dtype=np.uint8)

        for threshold in (55, 65, 75, 95, 105):
            mask = gray < threshold
            height, width = mask.shape
            components = _find_mask_components(
                mask,
                min_area=max(70, int(width * height * 0.00018)),
                max_area=max(2500, int(width * height * 0.012)),
                min_width=4,
                min_height=10,
                min_x_ratio=0.15,
                max_x_ratio=0.96,
            )

            for row_profile in row_profiles:
                row_values: list[str] = []
                score = 0

                for start_ratio, end_ratio, expected_digits in row_profile:
                    row_components = [
                        component
                        for component in components
                        if height * start_ratio <= component["center_y"] < height * end_ratio
                    ]
                    groups = _group_components_by_x(row_components, max(16, int(width * 0.045)))

                    values = [
                        digit
                        for group in groups
                        if (digit := _classify_digit_group(mask, group)) is not None
                    ]
                    value = "".join(values[-expected_digits:])
                    row_values.append(value)

                    if len(value) == expected_digits:
                        score += expected_digits

                systolic, diastolic, pulse = row_values
                if not (systolic.isdigit() and diastolic.isdigit()):
                    continue

                systolic_number = int(systolic)
                diastolic_number = int(diastolic)
                pulse_number = int(pulse) if pulse.isdigit() else 0

                if not (80 <= systolic_number <= 260 and 40 <= diastolic_number <= 160 and systolic_number > diastolic_number):
                    continue

                if pulse_number and 45 <= pulse_number <= 130:
                    score += 2

                if score > best_score:
                    best_score = score
                    best_values = row_values

    if not best_values:
        return None

    systolic, diastolic, pulse = best_values
    lines = [f"SYS: {int(systolic)}", f"DIA: {int(diastolic)}"]
    if pulse.isdigit() and 45 <= int(pulse) <= 130:
        lines.append(f"PULSE: {int(pulse)}")
    return "\n".join(lines)


def _extract_omron_blood_pressure(image: Image.Image) -> str | None:
    component_text = _extract_omron_by_components(image)
    if component_text is not None:
        return component_text

    width, height = image.size
    if width < 100 or height < 100:
        return None

    left = int(width * 0.27)
    right = int(width * 0.89)
    top = int(height * 0.22)
    bottom = int(height * 0.84)

    display = image.crop((left, top, right, bottom))
    gray = np.array(ImageOps.grayscale(display), dtype=np.uint8)
    mask = _binarize(gray)

    display_height, display_width = mask.shape
    rows = {
        "SYS": mask[int(display_height * 0.05) : int(display_height * 0.40), int(display_width * 0.20) : int(display_width * 0.95)],
        "DIA": mask[int(display_height * 0.34) : int(display_height * 0.70), int(display_width * 0.40) : int(display_width * 0.95)],
        "PULSE": mask[int(display_height * 0.60) : int(display_height * 0.95), int(display_width * 0.42) : int(display_width * 0.95)],
    }

    digits = {
        "SYS": _split_row_into_digits(rows["SYS"], 3),
        "DIA": _split_row_into_digits(rows["DIA"], 2),
        "PULSE": _split_row_into_digits(rows["PULSE"], 2),
    }

    sys_value = "".join(digits["SYS"]).replace("?", "")
    dia_value = "".join(digits["DIA"]).replace("?", "")
    pulse_value = "".join(digits["PULSE"]).replace("?", "")

    if not (sys_value.isdigit() and dia_value.isdigit()):
        return None

    sys_number = int(sys_value)
    dia_number = int(dia_value)
    if not (80 <= sys_number <= 260 and 40 <= dia_number <= 160 and sys_number > dia_number):
        return None

    lines: list[str] = []
    lines.append(f"SYS: {sys_number}")
    lines.append(f"DIA: {dia_number}")
    if pulse_value.isdigit() and 30 <= int(pulse_value) <= 220:
        lines.append(f"PULSE: {int(pulse_value)}")

    if not lines:
        return None

    return "\n".join(lines)


@app.post("/ocr/google-vision")
def ocr_google_vision(payload: OCRRequest) -> dict[str, str]:
    image = _decode_image(payload.image_base64)
    text = _extract_omron_blood_pressure(image)

    if text is None:
        raise HTTPException(
            status_code=422,
            detail="Khong nhan dien duoc so tren anh. Hay thu anh ro hon hoac dung anh huyet ap Omron.",
        )

    return {"text": text}
