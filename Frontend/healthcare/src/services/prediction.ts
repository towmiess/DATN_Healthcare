import { PREDICTION_API_URL } from "@/config";

export type PredictionInput = Partial<Record<string, number>>;

export type PredictionTargetResult = {
  prediction: number;
  label: string;
  positive_probability?: number;
};

export type PredictionResult = Record<
  "diabetes" | "cardio" | "stroke",
  PredictionTargetResult
>;

const normalizeBaseUrl = (raw: string) => raw.replace(/\/$/, "");

const fileToBase64 = (file: File) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result ?? "");
      resolve(result.includes(",") ? result.split(",")[1] : result);
    };
    reader.onerror = () => reject(new Error("Unable to read image file"));
    reader.readAsDataURL(file);
  });

export const predictAll = async (
  payload: PredictionInput
): Promise<PredictionResult> => {
  const response = await fetch(`${normalizeBaseUrl(PREDICTION_API_URL)}/predict/all`, {
    method: "POST",
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Prediction request failed");
  }

  return response.json();
};

export const ocrWithGoogleVision = async (file: File): Promise<string> => {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 5000);

  try {
    const imageBase64 = await fileToBase64(file);
    const response = await fetch(`${normalizeBaseUrl(PREDICTION_API_URL)}/ocr/google-vision`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        image_base64: imageBase64,
        mime_type: file.type || "image/jpeg",
      }),
      signal: controller.signal,
    });

    if (!response.ok) {
      const message = await response.text();
      throw new Error(message || "Google Vision OCR request failed");
    }

    const data = (await response.json()) as { text?: string };
    return data.text ?? "";
  } finally {
    window.clearTimeout(timeoutId);
  }
};
