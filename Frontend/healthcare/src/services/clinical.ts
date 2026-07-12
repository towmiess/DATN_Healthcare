import { apiClient } from "@/api/Fetcher";

export type ClinicalCandidate = {
  test_code?: string;
  test_name?: string;
  observation_code?: string;
  observation_name?: string;
  value: number;
  unit: string;
  canonical_value?: number | null;
  canonical_unit?: string;
  reference_min?: number | null;
  reference_max?: number | null;
  reference_text?: string;
  abnormal_flag?: string;
  confidence_score?: number | null;
};

export type ClinicalBaselineExtraction = {
  metadata: {
    provider_name?: string;
    sampled_at?: string | null;
    reported_at?: string | null;
    sex?: number;
    age_years?: number;
  };
  observations: ClinicalCandidate[];
  results: ClinicalCandidate[];
  confidence_score: number;
  raw_ocr_text: string;
  ocr_engine: string;
  original_filename: string;
  mime_type: string;
};

export type BaselineValue = {
  feature_key: string;
  code: string;
  label: string;
  value: number;
  unit: string;
  original_value: number;
  original_unit: string;
  reference_text: string;
  abnormal_flag: string;
  source: string;
};

export type ActiveClinicalBaseline = {
  has_baseline: boolean;
  id?: number;
  label?: string;
  effective_at?: string;
  status?: string;
  provider_name?: string | null;
  document?: {
    id: number;
    original_filename?: string | null;
    file_url?: string | null;
    verification_status?: string;
  } | null;
  values?: Record<string, BaselineValue>;
};

const fileToBase64 = (file: File) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result ?? "");
      resolve(result.includes(",") ? result.split(",")[1] : result);
    };
    reader.onerror = () => reject(new Error("Không thể đọc ảnh hồ sơ."));
    reader.readAsDataURL(file);
  });

export const extractClinicalBaseline = async (file: File) => {
  const imageBase64 = await fileToBase64(file);
  const response = await apiClient.post<ClinicalBaselineExtraction>(
    "/clinical/baselines/extract/",
    {
      image_base64: imageBase64,
      mime_type: file.type || "image/jpeg",
      mode: "document",
      original_filename: file.name,
    }
  );
  return response.data;
};

export const createClinicalBaseline = async (
  file: File | null,
  extraction: ClinicalBaselineExtraction
) => {
  const imageBase64 = file ? await fileToBase64(file) : "";
  const response = await apiClient.post("/clinical/baselines/", {
    label: `${extraction.metadata.provider_name || "Hồ sơ xét nghiệm"}`,
    provider_name: extraction.metadata.provider_name || "Cơ sở xét nghiệm",
    sampled_at: extraction.metadata.sampled_at,
    reported_at: extraction.metadata.reported_at || null,
    confirmed: true,
    original_filename: extraction.original_filename,
    mime_type: extraction.mime_type,
    ocr_engine: extraction.ocr_engine,
    raw_ocr_text: extraction.raw_ocr_text,
    confidence_score: extraction.confidence_score,
    image_base64: imageBase64,
    results: extraction.results,
    observations: extraction.observations,
  });
  return response.data;
};

export const getActiveClinicalBaseline = async (): Promise<ActiveClinicalBaseline> => {
  const response = await apiClient.get<ActiveClinicalBaseline>("/clinical/baselines/active/");
  return response.data;
};
