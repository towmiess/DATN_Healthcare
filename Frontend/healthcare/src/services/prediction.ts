import { apiClient } from "@/api/Fetcher";
import axios from "axios";

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

export type DiagnosisSnapshot = {
  has_data: boolean;
  values: Partial<Record<string, number>>;
  latest_result: PredictionResult | null;
  latest_assessment: {
    id: number;
    created_at: string;
    risk_level?: string | null;
    health_score?: number | null;
  } | null;
};

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
  const response = await apiClient.post<PredictionResult>("/diagnosis/predict/", payload);
  return response.data;
};

export const getDiagnosisSnapshot = async (): Promise<DiagnosisSnapshot> => {
  const response = await apiClient.get<DiagnosisSnapshot>("/diagnosis/profile/");
  return response.data;
};

export const ocrWithGoogleVision = async (file: File): Promise<string> => {
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 12000);

  try {
    const imageBase64 = await fileToBase64(file);
    const response = await apiClient.post<{ text?: string }>(
      "/ocr/google-vision/",
      {
        image_base64: imageBase64,
        mime_type: file.type || "image/jpeg",
      },
      { signal: controller.signal }
    );

    return response.data.text ?? "";
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const message =
        typeof error.response?.data === "object" &&
        error.response?.data &&
        "message" in error.response.data &&
        typeof error.response.data.message === "string"
          ? error.response.data.message
          : error.message;
      throw new Error(message || "Google Vision OCR request failed");
    }

    if (error instanceof Error) {
      throw error;
    }

    throw new Error("Google Vision OCR request failed");
  } finally {
    window.clearTimeout(timeoutId);
  }
};
