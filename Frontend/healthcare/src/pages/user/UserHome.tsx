import React, { useEffect, useRef, useState } from "react";
import {
  Activity,
  ClipboardPlus,
  HeartPulse,
  ImageUp,
  Loader2,
  RefreshCcw,
  RotateCcw,
} from "lucide-react";
import Tesseract, { PSM } from "tesseract.js";
import {
  getDiagnosisSnapshot,
  getOcrStatus,
  ocrWithGoogleVision,
  OcrStatus,
  predictAll,
  PredictionInput,
  PredictionResult,
} from "@/services/prediction";
import type { ActiveClinicalBaseline } from "@/services/clinical";
import "./UserHome.scss";

type SelectOption = {
  value: string;
  label: string;
};

type FieldDefinition = {
  key: string;
  label: string;
  hint?: string;
  options?: SelectOption[];
  placeholder?: string;
  readOnly?: boolean;
};

type ResultDefinition = {
  key: keyof PredictionResult;
  title: string;
  icon: React.ReactNode;
};

type OcrCrop = {
  x: number;
  y: number;
  width: number;
  height: number;
};

type OcrImageVariant = {
  image: string;
  language: string;
  numericOnly?: boolean;
};

const yesNoOptions: SelectOption[] = [
  { value: "0", label: "Không" },
  { value: "1", label: "Có" },
];

const sexOptions: SelectOption[] = [
  { value: "1", label: "Nam" },
  { value: "2", label: "Nữ" },
];

const inputGroups: { title: string; fields: FieldDefinition[] }[] = [
  {
    title: "Thông tin người bệnh",
    fields: [
      {
        key: "sex",
        label: "Giới tính (Sex)",
        options: sexOptions,
        placeholder: "Chọn giới tính",
      },
      { key: "age_years", label: "Tuổi (Age)", hint: "Số tuổi theo năm" },
      { key: "weight_kg", label: "Cân nặng (Weight)", hint: "Đơn vị kilogram" },
      { key: "height_cm", label: "Chiều cao (Height)", hint: "Đơn vị centimeter" },
      { key: "bmi", label: "Chỉ số BMI", hint: "Tự động tính từ cân nặng và chiều cao", readOnly: true },
      { key: "waist_cm", label: "Vòng eo (Waist)", hint: "Đơn vị centimeter" },
    ],
  },
  {
    title: "Xét nghiệm và huyết áp",
    fields: [
      { key: "hip_cm", label: "Vòng hông (Hip)", hint: "Đơn vị centimeter" },
      {
        key: "hba1c_percent",
        label: "HbA1c (HbA1c)",
        hint: "Tỷ lệ phần trăm HbA1c",
      },
      {
        key: "fasting_glucose_mg_dl",
        label: "Glucose đói (mg/dL)",
        hint: "Đường huyết lúc đói theo mg/dL",
      },
      {
        key: "fasting_glucose_mmol_l",
        label: "Glucose đói (mmol/L)",
        hint: "Đường huyết lúc đói theo mmol/L",
      },
      {
        key: "insulin_uU_ml",
        label: "Insulin (uU/mL)",
        hint: "Nồng độ insulin theo uU/mL",
      },
      {
        key: "insulin_pmol_l",
        label: "Insulin (pmol/L)",
        hint: "Nồng độ insulin theo pmol/L",
      },
      {
        key: "fasting_hours",
        label: "Số giờ nhịn ăn (Fasting hours)",
        hint: "Số giờ trước khi lấy mẫu",
      },
      {
        key: "fasting_minutes",
        label: "Số phút nhịn ăn (Fasting minutes)",
        hint: "Số phút cộng thêm",
      },
      {
        key: "total_cholesterol_mg_dl",
        label: "Cholesterol toàn phần (mg/dL)",
        hint: "Tổng cholesterol theo mg/dL",
      },
      {
        key: "total_cholesterol_mmol_l",
        label: "Cholesterol toàn phần (mmol/L)",
        hint: "Tổng cholesterol theo mmol/L",
      },
      {
        key: "high_blood_pressure_history",
        label: "Tiền sử huyết áp cao",
        options: yesNoOptions,
        placeholder: "Chọn Không/Có",
      },
      {
        key: "systolic_bp_mean",
        label: "Huyết áp tâm thu trung bình",
        hint: "Đơn vị mmHg",
      },
      {
        key: "diastolic_bp_mean",
        label: "Huyết áp tâm trương trung bình",
        hint: "Đơn vị mmHg",
      },
      {
        key: "pulse_mean",
        label: "Mạch trung bình (Pulse)",
        hint: "Số nhịp/phút",
      },
    ],
  },
];

const resultDefinitions: ResultDefinition[] = [
  {
    key: "diabetes",
    title: "Đái tháo đường",
    icon: <Activity size={18} />,
  },
  {
    key: "cardio",
    title: "Tim mạch",
    icon: <HeartPulse size={18} />,
  },
  {
    key: "stroke",
    title: "Đột quỵ",
    icon: <ClipboardPlus size={18} />,
  },
];

const sampleValues: Record<string, string> = {
  sex: "2",
  age_years: "45",
  weight_kg: "70.5",
  height_cm: "162",
  bmi: "26.9",
  waist_cm: "88",
  hip_cm: "96",
  hba1c_percent: "5.7",
  fasting_glucose_mg_dl: "105",
  fasting_glucose_mmol_l: "5.83",
  insulin_uU_ml: "8.2",
  insulin_pmol_l: "49.2",
  fasting_hours: "10",
  fasting_minutes: "15",
  total_cholesterol_mg_dl: "190",
  total_cholesterol_mmol_l: "4.91",
  high_blood_pressure_history: "0",
  systolic_bp_mean: "118",
  diastolic_bp_mean: "76",
  pulse_mean: "72",
};

const allFields = inputGroups.flatMap((group) => group.fields);
const emptyValues = allFields.reduce<Record<string, string>>((acc, field) => {
  acc[field.key] = "";
  return acc;
}, {});

const fieldLabels = allFields.reduce<Record<string, string>>((acc, field) => {
  acc[field.key] = field.label;
  return acc;
}, {});

const normalizeOcrText = (value: string) =>
  value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^\w%/+.,:-\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

const normalizeNumber = (value: string) => value.replace(",", ".");

const numberPattern = /[-+]?\d+(?:[.,]\d+)?/;

const unitPatterns = {
  mgDl: /\bmg\s*\/?\s*d?l\b/,
  mmolL: /\bmmol\s*\/?\s*l\b/,
  uUMl: /\b(?:uu|u\s*u|µu|μu)\s*\/?\s*ml\b/,
  pmolL: /\bpmol\s*\/?\s*l\b/,
};

const numericFieldAliases: Record<string, string[]> = {
  age_years: ["age_years", "age", "tuoi"],
  weight_kg: ["weight_kg", "weight", "can nang"],
  height_cm: ["height_cm", "height", "chieu cao"],
  bmi: ["bmi", "body mass index"],
  waist_cm: ["waist_cm", "waist", "vong eo"],
  hip_cm: ["hip_cm", "hip", "vong hong"],
  hba1c_percent: ["hba1c_percent", "hba1c", "a1c"],
  fasting_glucose_mg_dl: ["fasting_glucose_mg_dl"],
  fasting_glucose_mmol_l: ["fasting_glucose_mmol_l"],
  insulin_uU_ml: ["insulin_uU_ml"],
  insulin_pmol_l: ["insulin_pmol_l"],
  fasting_hours: ["fasting_hours", "fasting hours", "so gio nhin an"],
  fasting_minutes: ["fasting_minutes", "fasting minutes", "so phut nhin an"],
  total_cholesterol_mg_dl: [
    "total_cholesterol_mg_dl",
    "total cholesterol mg dl",
    "cholesterol mg dl",
    "cholesterol toan phan mg dl",
  ],
  total_cholesterol_mmol_l: [
    "total_cholesterol_mmol_l",
    "total cholesterol mmol l",
    "cholesterol mmol l",
    "cholesterol toan phan mmol l",
  ],
  systolic_bp_mean: [
    "systolic_bp_mean",
    "systolic",
    "systolic bp",
    "huyet ap tam thu",
  ],
  diastolic_bp_mean: [
    "diastolic_bp_mean",
    "diastolic",
    "diastolic bp",
    "huyet ap tam truong",
  ],
  pulse_mean: ["pulse_mean", "pulse", "heart rate", "mach"],
};

const lineContainsAlias = (line: string, aliases: string[]) =>
  aliases.some((alias) => line.includes(normalizeOcrText(alias)));

const extractNumberFromLine = (line: string, alias: string) => {
  const aliasIndex = line.indexOf(alias);
  if (aliasIndex < 0) return null;

  const tail = line.slice(aliasIndex + alias.length);
  const tailMatch = tail.match(numberPattern);
  if (tailMatch) return normalizeNumber(tailMatch[0]);

  const lineMatches = line.match(new RegExp(numberPattern.source, "g"));
  return lineMatches?.length ? normalizeNumber(lineMatches[lineMatches.length - 1]) : null;
};

const extractNumberFromLines = (lines: string[], aliases: string[]) => {
  const normalizedAliases = aliases.map(normalizeOcrText);

  for (const line of lines) {
    for (const alias of normalizedAliases) {
      const value = extractNumberFromLine(line, alias);
      if (value) return value;
    }
  }

  return null;
};

const extractNumberByUnit = (
  lines: string[],
  aliases: string[],
  unitPattern: RegExp
) => {
  const normalizedAliases = aliases.map(normalizeOcrText);

  for (const line of lines) {
    if (!unitPattern.test(line)) continue;

    for (const alias of normalizedAliases) {
      const value = extractNumberFromLine(line, alias);
      if (value) return value;
    }
  }

  return null;
};

const extractUnitSensitiveValues = (lines: string[]) => {
  const extracted: Record<string, string> = {};
  const glucoseAliases = ["glucose", "fasting glucose", "duong huyet", "glucose doi"];
  const insulinAliases = ["insulin"];
  const cholesterolAliases = ["cholesterol", "total cholesterol", "cholesterol toan phan"];

  const glucoseMgDl = extractNumberByUnit(lines, glucoseAliases, unitPatterns.mgDl);
  if (glucoseMgDl) extracted.fasting_glucose_mg_dl = glucoseMgDl;

  const glucoseMmolL = extractNumberByUnit(lines, glucoseAliases, unitPatterns.mmolL);
  if (glucoseMmolL) extracted.fasting_glucose_mmol_l = glucoseMmolL;

  const insulinUuMl = extractNumberByUnit(lines, insulinAliases, unitPatterns.uUMl);
  if (insulinUuMl) extracted.insulin_uU_ml = insulinUuMl;

  const insulinPmolL = extractNumberByUnit(lines, insulinAliases, unitPatterns.pmolL);
  if (insulinPmolL) extracted.insulin_pmol_l = insulinPmolL;

  const cholesterolMgDl = extractNumberByUnit(lines, cholesterolAliases, unitPatterns.mgDl);
  if (cholesterolMgDl) extracted.total_cholesterol_mg_dl = cholesterolMgDl;

  const cholesterolMmolL = extractNumberByUnit(lines, cholesterolAliases, unitPatterns.mmolL);
  if (cholesterolMmolL) extracted.total_cholesterol_mmol_l = cholesterolMmolL;

  return extracted;
};

const extractBloodPressure = (lines: string[]) => {
  const bpAliases = ["blood pressure", "bp", "huyet ap"];
  for (const line of lines) {
    if (!lineContainsAlias(line, bpAliases)) continue;
    const match = line.match(/(\d{2,3})\s*\/\s*(\d{2,3})/);
    if (match) {
      return {
        systolic_bp_mean: match[1],
        diastolic_bp_mean: match[2],
      };
    }
  }
  return {};
};

const extractSex = (lines: string[]) => {
  const sexAliases = ["sex", "gender", "gioi tinh"];
  for (const line of lines) {
    if (!lineContainsAlias(line, sexAliases)) continue;
    if (/\b(male|nam)\b/.test(line)) return "1";
    if (/\b(female|nu|nữ)\b/.test(line)) return "2";
    const value = line.match(numberPattern)?.[0];
    if (value === "1" || value === "2") return value;
  }
  return null;
};

const extractRaceEthnicity = (lines: string[]) => {
  const raceAliases = ["race", "ethnicity", "race_ethnicity", "chung toc", "dan toc"];
  for (const line of lines) {
    if (!lineContainsAlias(line, raceAliases)) continue;
    if (line.includes("mexico")) return "1";
    if (line.includes("hispanic")) return "2";
    if (line.includes("white") || line.includes("da trang")) return "3";
    if (line.includes("black") || line.includes("da den")) return "4";
    if (line.includes("asian") || line.includes("chau a")) return "6";
    if (line.includes("other") || line.includes("khac")) return "7";
    const value = line.match(numberPattern)?.[0];
    if (value && ["1", "2", "3", "4", "6", "7"].includes(value)) return value;
  }
  return null;
};

const extractYesNo = (lines: string[], aliases: string[]) => {
  for (const line of lines) {
    if (!lineContainsAlias(line, aliases)) continue;
    if (/\b(no|false|negative|khong|0)\b/.test(line)) return "0";
    if (/\b(yes|true|positive|co|1)\b/.test(line)) return "1";
  }
  return null;
};

const extractValuesFromOcrText = (text: string) => {
  const lines = text
    .split(/\r?\n/)
    .map(normalizeOcrText)
    .filter(Boolean);

  const extracted: Record<string, string> = {};

  const sex = extractSex(lines);
  if (sex) extracted.sex = sex;

  const raceEthnicity = extractRaceEthnicity(lines);
  if (raceEthnicity) extracted.race_ethnicity = raceEthnicity;

  const asian = extractYesNo(lines, ["race_ethnicity_asian", "asian", "chau a"]);
  if (asian) extracted.race_ethnicity_asian = asian;

  const highBloodPressure = extractYesNo(lines, [
    "high_blood_pressure_history",
    "hypertension",
    "high blood pressure",
    "tien su huyet ap cao",
  ]);
  if (highBloodPressure) extracted.high_blood_pressure_history = highBloodPressure;

  for (const [key, aliases] of Object.entries(numericFieldAliases)) {
    const value = extractNumberFromLines(lines, aliases);
    if (value) extracted[key] = value;
  }

  return {
    ...extracted,
    ...extractUnitSensitiveValues(lines),
    ...extractBloodPressure(lines),
  };
};

type OcrNumericRule = {
  aliases: string[];
  min?: number;
  max?: number;
  unit?: RegExp;
  decimalHint?: "one" | "two";
};

const robustUnitPatterns = {
  mgDl: /\bmg\s*\/?\s*d?l\b|\bmgd\b|\bmga\b/,
  mmolL: /\bmmol\s*\/?\s*l\b|\bmmo\b|\bmmol\b/,
  uUMl: /\b(?:uu|u\s*u|u)\s*\/?\s*ml\b|\buv\b|\bu\/?ml\b/,
  pmolL: /\bpmol\s*\/?\s*l\b|\bpmol\b/,
};

const robustNumericRules: Record<string, OcrNumericRule> = {
  age_years: { aliases: ["age_years", "age", "tuoi"], min: 0, max: 120 },
  weight_kg: {
    aliases: ["weight_kg", "weight", "wei", "can nang"],
    min: 20,
    max: 250,
    decimalHint: "one",
  },
  height_cm: {
    aliases: ["height_cm", "height", "hei", "chieu cao"],
    min: 80,
    max: 230,
  },
  bmi: { aliases: ["bmi", "body mass index"], min: 10, max: 80, decimalHint: "one" },
  waist_cm: {
    aliases: ["waist_cm", "waist", "waisto", "waist circumference", "vong eo"],
    min: 40,
    max: 200,
  },
  hip_cm: {
    aliases: ["hip_cm", "hip", "hiper", "hip circumference", "vong hong"],
    min: 50,
    max: 220,
  },
  hba1c_percent: {
    aliases: ["hba1c_percent", "hba1c", "hbafc", "hbaic", "a1c"],
    min: 3,
    max: 20,
    decimalHint: "one",
  },
  fasting_glucose_mg_dl: {
    aliases: ["fasting_glucose_mg_dl", "fasting glucose", "glucose doi", "glucose nhin an"],
    min: 40,
    max: 500,
    unit: robustUnitPatterns.mgDl,
  },
  fasting_glucose_mmol_l: {
    aliases: ["fasting_glucose_mmol_l", "fasting glucose", "glucose doi", "glucose nhin an"],
    min: 2,
    max: 30,
    unit: robustUnitPatterns.mmolL,
    decimalHint: "two",
  },
  insulin_uU_ml: {
    aliases: ["insulin", "inguln", "fin"],
    min: 0.1,
    max: 300,
    unit: robustUnitPatterns.uUMl,
    decimalHint: "one",
  },
  insulin_pmol_l: {
    aliases: ["insulin", "inguln"],
    min: 1,
    max: 3000,
    unit: robustUnitPatterns.pmolL,
    decimalHint: "one",
  },
  fasting_hours: {
    aliases: ["fasting_hours", "fasting hours", "so gio nhin an", "gio nhin an"],
    min: 0,
    max: 24,
  },
  fasting_minutes: {
    aliases: ["fasting_minutes", "fasting minutes", "so phut nhin an", "phut nhin an"],
    min: 0,
    max: 59,
  },
  total_cholesterol_mg_dl: {
    aliases: ["total_cholesterol_mg_dl", "total cholesterol", "cholesterol toan phan"],
    min: 50,
    max: 500,
    unit: robustUnitPatterns.mgDl,
  },
  total_cholesterol_mmol_l: {
    aliases: ["total_cholesterol_mmol_l", "total cholesterol", "cholesterol toan phan"],
    min: 1,
    max: 20,
    unit: robustUnitPatterns.mmolL,
    decimalHint: "two",
  },
  pulse_mean: {
    aliases: ["pulse_mean", "pulse", "heart rate", "nhip tim", "mach"],
    min: 30,
    max: 220,
  },
};

const parseOcrNumber = (value: string) => Number(normalizeNumber(value));

const formatOcrNumber = (value: number) => {
  if (!Number.isFinite(value)) return "";
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(2)));
};

const glucoseConversionFactor = 18;
const insulinPmolPerUu = 6;
const cholesterolMgDlPerMmolL = 38.67;
const maleWaistHeightRatio = 0.45;
const femaleWaistHeightRatio = 0.4;
const maleHipWaistDivisor = 0.9;
const femaleHipWaistDivisor = 0.7;

const normalizeSexValue = (sexValue?: string) => {
  const sex = Number(normalizeNumber(String(sexValue ?? "")));
  return Number.isFinite(sex) ? Math.trunc(sex) : 0;
};

const calculateBmi = (weightValue?: string, heightValue?: string) => {
  const weight = Number(normalizeNumber(String(weightValue ?? "")));
  const height = Number(normalizeNumber(String(heightValue ?? "")));

  if (!Number.isFinite(weight) || !Number.isFinite(height) || weight <= 0 || height <= 0) {
    return "";
  }

  return formatOcrNumber(weight / (height / 100) ** 2);
};

const calculateExpectedWaist = (sexValue?: string, heightValue?: string) => {
  const sex = normalizeSexValue(sexValue);
  const height = Number(normalizeNumber(String(heightValue ?? "")));

  if (!Number.isFinite(height) || height <= 0) {
    return "";
  }

  if (sex === 1) {
    return formatOcrNumber(height * maleWaistHeightRatio);
  }

  if (sex === 2) {
    return formatOcrNumber(height * femaleWaistHeightRatio);
  }

  return "";
};

const calculateExpectedHip = (sexValue?: string, waistValue?: string) => {
  const sex = normalizeSexValue(sexValue);
  const waist = Number(normalizeNumber(String(waistValue ?? "")));

  if (!Number.isFinite(waist) || waist <= 0) {
    return "";
  }

  if (sex === 1) {
    return formatOcrNumber(waist / maleHipWaistDivisor);
  }

  if (sex === 2) {
    return formatOcrNumber(waist / femaleHipWaistDivisor);
  }

  return "";
};

const getPreviousDerivedWaist = (values: Record<string, string>) =>
  calculateExpectedWaist(values.sex, values.height_cm);

const getPreviousDerivedHip = (values: Record<string, string>) => {
  const priorWaist = values.waist_cm || getPreviousDerivedWaist(values);
  return calculateExpectedHip(values.sex, priorWaist);
};

const syncUnitPair = (
  nextValues: Record<string, string>,
  changedKey: string | undefined,
  primaryKey: string,
  secondaryKey: string,
  secondaryPerPrimary: number
) => {
  let primaryValue = nextValues[primaryKey];
  let secondaryValue = nextValues[secondaryKey];
  const primaryNumber = Number(normalizeNumber(String(primaryValue ?? "")));
  const secondaryNumber = Number(normalizeNumber(String(secondaryValue ?? "")));

  if (changedKey === primaryKey && Number.isFinite(primaryNumber) && primaryNumber > 0) {
    secondaryValue = formatOcrNumber(primaryNumber * secondaryPerPrimary);
  } else if (
    changedKey === secondaryKey &&
    Number.isFinite(secondaryNumber) &&
    secondaryNumber > 0
  ) {
    primaryValue = formatOcrNumber(secondaryNumber / secondaryPerPrimary);
  } else if (
    primaryValue &&
    !secondaryValue &&
    Number.isFinite(primaryNumber) &&
    primaryNumber > 0
  ) {
    secondaryValue = formatOcrNumber(primaryNumber * secondaryPerPrimary);
  } else if (
    secondaryValue &&
    !primaryValue &&
    Number.isFinite(secondaryNumber) &&
    secondaryNumber > 0
  ) {
    primaryValue = formatOcrNumber(secondaryNumber / secondaryPerPrimary);
  }

  return { primaryValue, secondaryValue };
};

const applyDerivedMetrics = (
  nextValues: Record<string, string>,
  previousValues?: Record<string, string>,
  changedKey?: string
) => {
  const bmi = calculateBmi(nextValues.weight_kg, nextValues.height_cm);
  const previousWaistDerived = previousValues ? getPreviousDerivedWaist(previousValues) : "";
  const shouldRefreshWaist =
    changedKey !== "waist_cm" &&
    (!nextValues.waist_cm ||
      (previousValues !== undefined && nextValues.waist_cm === previousValues.waist_cm && nextValues.waist_cm === previousWaistDerived));
  const waist = shouldRefreshWaist
    ? calculateExpectedWaist(nextValues.sex, nextValues.height_cm)
    : nextValues.waist_cm;

  const previousHipDerived = previousValues ? getPreviousDerivedHip(previousValues) : "";
  const shouldRefreshHip =
    changedKey !== "hip_cm" &&
    (!nextValues.hip_cm ||
      (previousValues !== undefined && nextValues.hip_cm === previousValues.hip_cm && nextValues.hip_cm === previousHipDerived));
  const hip = shouldRefreshHip ? calculateExpectedHip(nextValues.sex, waist) : nextValues.hip_cm;

  const glucoseValues = syncUnitPair(
    nextValues,
    changedKey,
    "fasting_glucose_mg_dl",
    "fasting_glucose_mmol_l",
    1 / glucoseConversionFactor
  );
  const insulinValues = syncUnitPair(
    nextValues,
    changedKey,
    "insulin_uU_ml",
    "insulin_pmol_l",
    insulinPmolPerUu
  );
  const cholesterolValues = syncUnitPair(
    nextValues,
    changedKey,
    "total_cholesterol_mg_dl",
    "total_cholesterol_mmol_l",
    1 / cholesterolMgDlPerMmolL
  );

  return {
    ...nextValues,
    bmi: bmi || nextValues.bmi,
    waist_cm: waist,
    hip_cm: hip,
    fasting_glucose_mg_dl: glucoseValues.primaryValue,
    fasting_glucose_mmol_l: glucoseValues.secondaryValue,
    insulin_uU_ml: insulinValues.primaryValue,
    insulin_pmol_l: insulinValues.secondaryValue,
    total_cholesterol_mg_dl: cholesterolValues.primaryValue,
    total_cholesterol_mmol_l: cholesterolValues.secondaryValue,
  };
};

const getOcrNumbersFromLine = (line: string) =>
  Array.from(line.matchAll(new RegExp(numberPattern.source, "g")))
    .map((match) => ({ value: parseOcrNumber(match[0]), index: match.index ?? 0 }))
    .filter((match) => Number.isFinite(match.value));

const repairOcrDecimal = (value: number, rule: OcrNumericRule) => {
  const candidates = [value];

  if (rule.decimalHint === "one" && value >= 100) candidates.push(value / 10);
  if (rule.decimalHint === "two" && value >= 100) candidates.push(value / 100);
  if (rule.decimalHint === "two" && value >= 30) candidates.push(value / 10);
  if (value >= 500 && rule.max && rule.max <= 300) candidates.push(value / 10);

  return candidates.find((candidate) => {
    if (rule.min !== undefined && candidate < rule.min) return false;
    if (rule.max !== undefined && candidate > rule.max) return false;
    return true;
  });
};

const extractRobustNumberFromLines = (lines: string[], rule: OcrNumericRule) => {
  const normalizedAliases = rule.aliases.map(normalizeOcrText);

  for (const line of lines) {
    if (rule.unit && !rule.unit.test(line)) continue;

    const aliasIndex = normalizedAliases.reduce((closest, alias) => {
      const index = line.indexOf(alias);
      if (index < 0) return closest;
      return closest < 0 ? index : Math.min(closest, index);
    }, -1);

    if (aliasIndex < 0) continue;

    const firstCandidate = getOcrNumbersFromLine(line).find(
      (candidate) => candidate.index >= aliasIndex
    );
    const bestCandidate = firstCandidate
      ? repairOcrDecimal(firstCandidate.value, rule)
      : undefined;

    if (bestCandidate !== undefined) return formatOcrNumber(bestCandidate);
  }

  return null;
};

const extractRobustSex = (lines: string[]) => {
  for (const line of lines) {
    if (!lineContainsAlias(line, ["sex", "gender", "gioi tinh"])) continue;
    if (/\b(female|nu)\b/.test(line)) return "2";
    if (/\b(male|nam)\b/.test(line)) return "1";
    const value = line.match(numberPattern)?.[0];
    if (value === "1" || value === "2") return value;
  }
  return null;
};

const extractRobustRaceEthnicity = (lines: string[]) => {
  for (const line of lines) {
    if (!lineContainsAlias(line, ["race", "ethnicity", "racial", "dan toc", "chung toc"])) {
      continue;
    }

    const value = line.match(numberPattern)?.[0];
    if (value && ["1", "2", "3", "4", "6", "7"].includes(value)) return value;
    if (line.includes("mexico")) return "1";
    if (line.includes("white") || line.includes("da trang")) return "3";
    if (line.includes("black") || line.includes("da den")) return "4";
    if (line.includes("asian") || line.includes("goc a") || line.includes("chau a")) return "6";
    if (line.includes("non hispanic") || line.includes("khong hispanic")) return "3";
    if (line.includes("hispanic")) return "2";
    if (line.includes("other") || line.includes("khac")) return "7";
  }
  return null;
};

const extractRobustYesNo = (lines: string[], aliases: string[]) => {
  for (const line of lines) {
    if (!lineContainsAlias(line, aliases)) continue;
    if (/\b(no|none|false|negative|khong|0)\b/.test(line)) return "0";
    if (/\b(yes|true|positive|co|1)\b/.test(line)) return "1";
  }
  return null;
};

const extractRobustBloodPressure = (lines: string[]) => {
  for (const line of lines) {
    if (!lineContainsAlias(line, ["blood pressure", "bp", "huyet ap"])) continue;
    const match = line.match(/(\d{2,3})\s*\/\s*(\d{2,3})/);
    if (match) {
      return {
        systolic_bp_mean: match[1],
        diastolic_bp_mean: match[2],
      };
    }
  }
  return {};
};

const extractValuesFromOcrTextRobust = (text: string) => {
  const lines = text
    .split(/\r?\n/)
    .map(normalizeOcrText)
    .filter(Boolean);

  const extracted: Record<string, string> = {};

  const sex = extractRobustSex(lines);
  if (sex) extracted.sex = sex;

  const raceEthnicity = extractRobustRaceEthnicity(lines);
  if (raceEthnicity) extracted.race_ethnicity = raceEthnicity;

  const asian = extractRobustYesNo(lines, ["race_ethnicity_asian", "asian race", "goc a"]);
  if (asian) extracted.race_ethnicity_asian = asian;

  const highBloodPressure = extractRobustYesNo(lines, [
    "high_blood_pressure_history",
    "hypertension",
    "high blood pressure",
    "history of high blood",
    "self report",
    "tien su huyet ap cao",
  ]);
  if (highBloodPressure) extracted.high_blood_pressure_history = highBloodPressure;

  for (const [key, rule] of Object.entries(robustNumericRules)) {
    const value = extractRobustNumberFromLines(lines, rule);
    if (value) extracted[key] = value;
  }

  return {
    ...extracted,
    ...extractRobustBloodPressure(lines),
  };
};

const clampOcrValue = (value: number, min: number, max: number) =>
  Number.isFinite(value) && value >= min && value <= max;

const getAllOcrNumbers = (text: string) =>
  Array.from(normalizeOcrText(text).matchAll(new RegExp(numberPattern.source, "g")))
    .map((match) => parseOcrNumber(match[0]))
    .filter((value) => Number.isFinite(value));

const extractFocusedBasicValues = (lines: string[]) => {
  const extracted: Record<string, string> = {};
  const focusedRules = [
    "age_years",
    "height_cm",
    "weight_kg",
    "bmi",
    "waist_cm",
  ] as const;

  const sex = extractRobustSex(lines);
  if (sex) extracted.sex = sex;

  focusedRules.forEach((key) => {
    const value = extractRobustNumberFromLines(lines, robustNumericRules[key]);
    if (value) extracted[key] = value;
  });

  const weight = Number(extracted.weight_kg);
  const height = Number(extracted.height_cm);
  if (!extracted.bmi && clampOcrValue(weight, 20, 250) && clampOcrValue(height, 80, 230)) {
    extracted.bmi = formatOcrNumber(weight / (height / 100) ** 2);
  }

  return extracted;
};

const buildGlucoseValues = (
  value: number,
  unit: "mg_dl" | "mmol_l"
): Record<string, string> => {
  if (!Number.isFinite(value)) return {};

  if (unit === "mg_dl") {
    return {
      fasting_glucose_mg_dl: formatOcrNumber(value),
      fasting_glucose_mmol_l: formatOcrNumber(value / glucoseConversionFactor),
    };
  }

  return {
    fasting_glucose_mg_dl: formatOcrNumber(value * glucoseConversionFactor),
    fasting_glucose_mmol_l: formatOcrNumber(value),
  };
};

const glucoseContextPattern = /\b(glucose|glu|accu|chek|check|mgdl|mg\/dl|mmol|mmol\/l)\b/;
const bloodPressureContextPattern =
  /\b(sys|dia|pulse|pul|mmhg|bpm|blood pressure|huyet ap|nhip tim|mach|omron|intelli|sense)\b/;

const hasGlucoseContextText = (text: string) =>
  robustUnitPatterns.mgDl.test(text) ||
  robustUnitPatterns.mmolL.test(text) ||
  glucoseContextPattern.test(text);

const hasBloodPressureContextText = (text: string) => bloodPressureContextPattern.test(text);

const extractGlucoseFromNumberSequence = (text: string) => {
  const normalizedText = normalizeOcrText(text);
  const extracted: Record<string, string> = {};
  const numbers = getAllOcrNumbers(normalizedText);
  const hasGlucoseContext = hasGlucoseContextText(normalizedText);
  const hasBloodPressureContext = hasBloodPressureContextText(normalizedText);

  if (hasBloodPressureContext && !hasGlucoseContext) {
    return extracted;
  }

  const mmolCandidate = numbers.find(
    (value) => clampOcrValue(value, 2, 30) && !Number.isInteger(value)
  );
  const mgCandidate =
    numbers.find((value) => Number.isInteger(value) && clampOcrValue(value, 40, 500)) ??
    numbers.find((value) => clampOcrValue(value, 40, 500));
  const plausibleGlucoseNumbers = numbers.filter((value) => clampOcrValue(value, 40, 500));

  if (!hasGlucoseContext && plausibleGlucoseNumbers.length !== 1) {
    return extracted;
  }

  if (robustUnitPatterns.mmolL.test(normalizedText)) {
    const explicitMmolCandidate =
      mmolCandidate ?? numbers.find((value) => clampOcrValue(value, 2, 30));
    if (explicitMmolCandidate !== undefined) {
      return buildGlucoseValues(explicitMmolCandidate, "mmol_l");
    }
  }

  if (robustUnitPatterns.mgDl.test(normalizedText) && mgCandidate !== undefined) {
    return buildGlucoseValues(mgCandidate, "mg_dl");
  }

  if (mmolCandidate !== undefined) {
    return buildGlucoseValues(mmolCandidate, "mmol_l");
  }

  if (mgCandidate !== undefined) {
    return buildGlucoseValues(mgCandidate, "mg_dl");
  }

  const compactDigits = normalizedText.replace(/\D/g, "");
  if (compactDigits.length === 3) {
    const compactValue = Number(compactDigits);
    if (clampOcrValue(compactValue, 40, 500)) {
      Object.assign(extracted, buildGlucoseValues(compactValue, "mg_dl"));
    }
  }

  return extracted;
};

const extractDeviceGlucose = (text: string, lines: string[]) => {
  const normalizedText = normalizeOcrText(text);
  const extracted: Record<string, string> = {};
  const hasGlucoseContext = hasGlucoseContextText(normalizedText);

  if (!hasGlucoseContext) return extracted;

  const mgLine = lines.find((line) => robustUnitPatterns.mgDl.test(line));
  const mmolLine = lines.find((line) => robustUnitPatterns.mmolL.test(line));
  const mgValue = mgLine
    ? getOcrNumbersFromLine(mgLine).find((item) => clampOcrValue(item.value, 40, 500))?.value
    : undefined;
  const mmolValue = mmolLine
    ? getOcrNumbersFromLine(mmolLine).find((item) => clampOcrValue(item.value, 2, 30))?.value
    : undefined;

  if (mgValue !== undefined) {
    return buildGlucoseValues(mgValue, "mg_dl");
  }

  if (mmolValue !== undefined) {
    return buildGlucoseValues(mmolValue, "mmol_l");
  }

  const candidate = getAllOcrNumbers(text)
    .filter((value) => clampOcrValue(value, 40, 500))
    .sort((first, second) => second - first)[0];
  if (candidate !== undefined) {
    Object.assign(extracted, buildGlucoseValues(candidate, "mg_dl"));
  }

  return extracted;
};

const extractDeviceBloodPressure = (text: string, lines: string[]) => {
  const normalizedText = normalizeOcrText(text);
  const extracted: Record<string, string> = {};
  const hasBloodPressureContext = hasBloodPressureContextText(normalizedText);

  const slashMatch = normalizedText.match(/(\d{2,3})\s*\/\s*(\d{2,3})/);
  if (slashMatch) {
    extracted.systolic_bp_mean = slashMatch[1];
    extracted.diastolic_bp_mean = slashMatch[2];
  }

  const pulseLine = lines.find((line) => /\b(pulse|pul|nhip tim|mach)\b/.test(line));
  const pulseValue = pulseLine
    ? getOcrNumbersFromLine(pulseLine).find((item) => clampOcrValue(item.value, 30, 220))?.value
    : undefined;
  if (pulseValue !== undefined) extracted.pulse_mean = formatOcrNumber(pulseValue);

  if (!hasBloodPressureContext) return extracted;

  const numbers = getAllOcrNumbers(text).filter((value) => clampOcrValue(value, 30, 260));
  for (let index = 0; index < numbers.length - 1; index += 1) {
    const systolic = numbers[index];
    const diastolic = numbers[index + 1];
    const pulse = numbers[index + 2];

    if (
      clampOcrValue(systolic, 80, 260) &&
      clampOcrValue(diastolic, 40, 160) &&
      systolic > diastolic
    ) {
      extracted.systolic_bp_mean = formatOcrNumber(systolic);
      extracted.diastolic_bp_mean = formatOcrNumber(diastolic);

      if (pulse !== undefined && clampOcrValue(pulse, 30, 220)) {
        extracted.pulse_mean = formatOcrNumber(pulse);
      }
      break;
    }
  }

  return extracted;
};

const extractFocusedOcrValues = (text: string) => {
  const lines = text
    .split(/\r?\n/)
    .map(normalizeOcrText)
    .filter(Boolean);

  return {
    ...extractFocusedBasicValues(lines),
    ...extractDeviceGlucose(text, lines),
    ...extractDeviceBloodPressure(text, lines),
  };
};

const sevenSegmentMap: Record<string, string> = {
  "1111110": "0",
  "0110000": "1",
  "1101101": "2",
  "1111001": "3",
  "0110011": "4",
  "1011011": "5",
  "1011111": "6",
  "1110000": "7",
  "1111111": "8",
  "1111011": "9",
};

const sevenSegmentPatterns = Object.entries(sevenSegmentMap).map(([pattern, digit]) => ({
  digit,
  pattern,
}));

const segmentOrder = [
  "top",
  "upperRight",
  "lowerRight",
  "bottom",
  "lowerLeft",
  "upperLeft",
  "middle",
] as const;

type SevenSegmentRegion = (typeof segmentOrder)[number];
type SevenSegmentRegions = Record<SevenSegmentRegion, readonly [number, number, number, number]>;

const sevenSegmentRegions: SevenSegmentRegions = {
  top: [0.12, 0.02, 0.88, 0.22],
  upperRight: [0.62, 0.08, 1, 0.52],
  lowerRight: [0.62, 0.48, 1, 0.92],
  bottom: [0.12, 0.78, 0.88, 1],
  lowerLeft: [0, 0.48, 0.38, 0.92],
  upperLeft: [0, 0.08, 0.38, 0.52],
  middle: [0.12, 0.38, 0.88, 0.62],
} as const;

const omronSevenSegmentRegions: SevenSegmentRegions = {
  top: [0.22, 0.02, 0.78, 0.14],
  upperRight: [0.68, 0.12, 0.95, 0.45],
  lowerRight: [0.68, 0.55, 0.95, 0.88],
  bottom: [0.22, 0.86, 0.78, 0.98],
  lowerLeft: [0.05, 0.55, 0.32, 0.88],
  upperLeft: [0.05, 0.12, 0.32, 0.45],
  middle: [0.22, 0.43, 0.78, 0.57],
} as const;

const createImageElement = (file: File) =>
  new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image();
    const objectUrl = URL.createObjectURL(file);

    image.onload = () => {
      URL.revokeObjectURL(objectUrl);
      resolve(image);
    };

    image.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      reject(new Error("Không thể đọc ảnh thiết bị."));
    };

    image.src = objectUrl;
  });

const getDarkPixelRatio = (
  data: Uint8ClampedArray,
  imageWidth: number,
  xStart: number,
  yStart: number,
  xEnd: number,
  yEnd: number,
  darkThreshold = 30
) => {
  let dark = 0;
  let total = 0;

  for (let y = yStart; y < yEnd; y += 1) {
    for (let x = xStart; x < xEnd; x += 1) {
      const offset = (y * imageWidth + x) * 4;
      if (data[offset] < darkThreshold) dark += 1;
      total += 1;
    }
  }

  return total ? dark / total : 0;
};

const classifySevenSegmentDigit = (
  data: Uint8ClampedArray,
  imageWidth: number,
  box: { x: number; y: number; width: number; height: number },
  options: {
    darkThreshold?: number;
    minHeight?: number;
    minScore?: number;
    minScoreGap?: number;
    minWidth?: number;
    regions?: SevenSegmentRegions;
  } = {}
) => {
  const minWidth = options.minWidth ?? 18;
  const minHeight = options.minHeight ?? 48;
  if (box.width < minWidth || box.height < minHeight) return null;

  const regions = options.regions ?? sevenSegmentRegions;
  const darkThreshold = options.darkThreshold ?? 30;

  const ratios = segmentOrder.map((segment) => {
    const [rx, ry, rw, rh] = regions[segment];
    const xStart = Math.max(0, Math.round(box.x + box.width * rx));
    const yStart = Math.max(0, Math.round(box.y + box.height * ry));
    const xEnd = Math.min(imageWidth, Math.round(box.x + box.width * rw));
    const yEnd = Math.min(box.y + box.height, Math.round(box.y + box.height * rh));
    return getDarkPixelRatio(data, imageWidth, xStart, yStart, xEnd, yEnd, darkThreshold);
  });

  const scored = sevenSegmentPatterns
    .map(({ digit, pattern }) => {
      let score = 0;

      pattern.split("").forEach((expected, index) => {
        const ratio = ratios[index] ?? 0;
        score += expected === "1" ? ratio : 1 - ratio;
      });

      return { digit, score };
    })
    .sort((left, right) => right.score - left.score);

  const best = scored[0];
  const secondBest = scored[1];

  if (!best || best.score < (options.minScore ?? 4.25)) return null;
  if (secondBest && best.score - secondBest.score < (options.minScoreGap ?? 0.12)) {
    return null;
  }

  return best.digit;
};

type DarkComponent = {
  x: number;
  y: number;
  width: number;
  height: number;
  area: number;
  centerX: number;
  centerY: number;
};

const findDarkComponents = (
  data: Uint8ClampedArray,
  imageWidth: number,
  imageHeight: number,
  darkThreshold = 30,
  options: {
    maxXRatio?: number;
    maxYRatio?: number;
    minArea?: number;
    minXRatio?: number;
    minYRatio?: number;
  } = {}
) => {
  const visited = new Uint8Array(imageWidth * imageHeight);
  const components: DarkComponent[] = [];
  const stack: number[] = [];
  const minArea = options.minArea ?? 250;
  const minXRatio = options.minXRatio ?? 0.08;
  const minYRatio = options.minYRatio ?? 0.08;
  const maxXRatio = options.maxXRatio ?? 0.92;
  const maxYRatio = options.maxYRatio ?? 0.92;

  for (let y = 0; y < imageHeight; y += 1) {
    for (let x = 0; x < imageWidth; x += 1) {
      const index = y * imageWidth + x;
      if (visited[index] || data[index * 4] >= darkThreshold) continue;

      visited[index] = 1;
      stack.length = 0;
      stack.push(index);

      let minX = x;
      let maxX = x;
      let minY = y;
      let maxY = y;
      let area = 0;

      while (stack.length) {
        const current = stack.pop();
        if (current === undefined) continue;

        const currentY = Math.floor(current / imageWidth);
        const currentX = current % imageWidth;
        area += 1;

        if (currentX < minX) minX = currentX;
        if (currentX > maxX) maxX = currentX;
        if (currentY < minY) minY = currentY;
        if (currentY > maxY) maxY = currentY;

        const neighbors = [
          current - 1,
          current + 1,
          current - imageWidth,
          current + imageWidth,
        ];

        for (const neighbor of neighbors) {
          if (neighbor < 0 || neighbor >= imageWidth * imageHeight) continue;

          const neighborY = Math.floor(neighbor / imageWidth);
          const neighborX = neighbor % imageWidth;
          if (
            Math.abs(neighborX - currentX) + Math.abs(neighborY - currentY) !== 1
          ) {
            continue;
          }

          if (visited[neighbor] || data[neighbor * 4] >= darkThreshold) continue;
          visited[neighbor] = 1;
          stack.push(neighbor);
        }
      }

      if (area < minArea) continue;

      components.push({
        x: minX,
        y: minY,
        width: maxX - minX + 1,
        height: maxY - minY + 1,
        area,
        centerX: (minX + maxX) / 2,
        centerY: (minY + maxY) / 2,
      });
    }
  }

  return components.filter(
    (component) =>
      component.x > imageWidth * minXRatio &&
      component.y > imageHeight * minYRatio &&
      component.x + component.width < imageWidth * maxXRatio &&
      component.y + component.height < imageHeight * maxYRatio
  );
};

const clusterDarkComponentsByRow = (
  components: DarkComponent[],
  imageHeight: number
) => {
  const sorted = [...components].sort((left, right) => left.centerY - right.centerY);
  const rows: DarkComponent[][] = [];
  const rowGap = Math.max(42, Math.round(imageHeight * 0.1));

  for (const component of sorted) {
    const currentRow = rows[rows.length - 1];
    if (
      !currentRow ||
      component.centerY - currentRow[currentRow.length - 1].centerY > rowGap
    ) {
      rows.push([component]);
    } else {
      currentRow.push(component);
    }
  }

  return rows;
};

const extractSevenSegmentRowsFromComponents = (
  data: Uint8ClampedArray,
  imageWidth: number,
  imageHeight: number,
  darkThreshold = 30
) => {
  const components = findDarkComponents(data, imageWidth, imageHeight, darkThreshold);
  if (!components.length) return {};

  const rows = clusterDarkComponentsByRow(components, imageHeight);
  if (rows.length < 2) return {};

  const rowValues = rows
    .map((row) =>
      row
        .filter(
          (component) =>
            component.width >= 16 &&
            component.height >= 40 &&
            component.area >= 500 &&
            component.x > imageWidth * 0.12 &&
            component.x + component.width < imageWidth * 0.88
        )
        .sort((left, right) => left.centerX - right.centerX)
        .map((component) =>
          classifySevenSegmentDigit(data, imageWidth, {
            x: Math.max(0, component.x - 2),
            y: Math.max(0, component.y - 2),
            width: Math.min(imageWidth - component.x, component.width + 6),
            height: Math.min(imageHeight - component.y, component.height + 6),
          })
        )
        .filter((digit): digit is string => Boolean(digit))
        .join("")
    )
    .filter(Boolean);

  if (rowValues.length < 2) return {};

  const [firstRow, secondRow, thirdRow] = rowValues;
  const extracted: Record<string, string> = {};

  if (firstRow && /^\d{2,3}$/.test(firstRow)) {
    extracted.systolic_bp_mean = firstRow;
  }

  if (secondRow && /^\d{2,3}$/.test(secondRow)) {
    extracted.diastolic_bp_mean = secondRow;
  }

  if (thirdRow && /^\d{2,3}$/.test(thirdRow)) {
    extracted.pulse_mean = thirdRow;
  }

  if (
    extracted.systolic_bp_mean &&
    extracted.diastolic_bp_mean &&
    Number(extracted.systolic_bp_mean) > Number(extracted.diastolic_bp_mean)
  ) {
    if (!extracted.pulse_mean && rowValues[2]) {
      extracted.pulse_mean = rowValues[2];
    }
    return extracted;
  }

  const sequenceExtracted = extractBloodPressureFromNumberSequence(rowValues.join("\n"));
  return sequenceExtracted;
};

type DigitGroup = {
  x: number;
  y: number;
  width: number;
  height: number;
  area: number;
};

type OmronCandidate = {
  values: Record<string, string>;
  score: number;
};

type OmronPulseCandidate = {
  value: string;
  score: number;
};

type OmronExtraction = {
  candidate: OmronCandidate | null;
  pulseCandidates: OmronPulseCandidate[];
};

const omronRowProfiles = [
  {
    scoreBias: 0.5,
    ranges: [
      [0.12, 0.38],
      [0.38, 0.64],
      [0.62, 0.8],
    ],
  },
  {
    scoreBias: 1.5,
    ranges: [
      [0, 0.25],
      [0.24, 0.49],
      [0.48, 0.66],
    ],
  },
  {
    scoreBias: -1,
    ranges: [
      [0, 0.25],
      [0.18, 0.47],
      [0.46, 0.66],
    ],
  },
  {
    scoreBias: -2,
    ranges: [
      [0, 0.36],
      [0.3, 0.62],
      [0.48, 0.82],
    ],
  },
] as const;

const groupComponentsByX = (components: DarkComponent[], maxGap: number) => {
  const groups: DigitGroup[] = [];

  for (const component of [...components].sort((left, right) => left.x - right.x)) {
    const current = groups[groups.length - 1];
    const componentEndX = component.x + component.width - 1;
    const componentEndY = component.y + component.height - 1;

    if (!current || component.x > current.x + current.width - 1 + maxGap) {
      groups.push({
        x: component.x,
        y: component.y,
        width: component.width,
        height: component.height,
        area: component.area,
      });
      continue;
    }

    const currentEndX = current.x + current.width - 1;
    const currentEndY = current.y + current.height - 1;
    const nextX = Math.min(current.x, component.x);
    const nextY = Math.min(current.y, component.y);
    const nextEndX = Math.max(currentEndX, componentEndX);
    const nextEndY = Math.max(currentEndY, componentEndY);

    current.x = nextX;
    current.y = nextY;
    current.width = nextEndX - nextX + 1;
    current.height = nextEndY - nextY + 1;
    current.area += component.area;
  }

  return groups;
};

const classifySingleOmronDigit = (
  data: Uint8ClampedArray,
  imageWidth: number,
  group: Pick<DigitGroup, "x" | "y" | "width" | "height">,
  darkThreshold: number
) => {
  if (group.width / Math.max(1, group.height) < 0.38) return "1";

  return classifySevenSegmentDigit(
    data,
    imageWidth,
    {
      x: group.x,
      y: group.y,
      width: group.width,
      height: group.height,
    },
    {
      darkThreshold,
      minHeight: 20,
      minScore: 3,
      minScoreGap: 0,
      minWidth: 8,
      regions: omronSevenSegmentRegions,
    }
  );
};

const classifyOmronDigitGroup = (
  data: Uint8ClampedArray,
  imageWidth: number,
  group: DigitGroup,
  darkThreshold: number
) => {
  const aspectRatio = group.width / Math.max(1, group.height);

  if (
    aspectRatio >= 1.05 &&
    group.width >= Math.max(58, Math.round(imageWidth * 0.12))
  ) {
    const firstWidth = Math.round(group.width * 0.48);
    const secondX = group.x + Math.round(group.width * 0.5);
    const secondWidth = group.x + group.width - secondX;
    const splitDigits = [
      classifySingleOmronDigit(
        data,
        imageWidth,
        {
          x: group.x,
          y: group.y,
          width: firstWidth,
          height: group.height,
        },
        darkThreshold
      ),
      classifySingleOmronDigit(
        data,
        imageWidth,
        {
          x: secondX,
          y: group.y,
          width: secondWidth,
          height: group.height,
        },
        darkThreshold
      ),
    ];

    if (splitDigits.every(Boolean)) {
      return splitDigits.join("");
    }
  }

  return classifySingleOmronDigit(data, imageWidth, group, darkThreshold);
};

const collectOmronPulseCandidates = (
  pulseText: string,
  scoreBias = 0
): OmronPulseCandidate[] => {
  const digits = pulseText.replace(/\D/g, "");
  const candidates: OmronPulseCandidate[] = [];

  const addCandidate = (valueText: string, score: number) => {
    if (!/^\d{2,3}$/.test(valueText)) return;

    const value = Number(valueText);
    if (!clampOcrValue(value, 45, 130)) return;

    const normalizedValue = String(value);
    const distinctDigits = new Set(normalizedValue.split("")).size;
    candidates.push({
      value: normalizedValue,
      score: score + scoreBias + (distinctDigits > 1 ? 1.1 : -0.7),
    });
  };

  if (/^\d{2,3}$/.test(digits)) {
    addCandidate(digits, digits.length === 2 ? 4 : 2.2);
  }

  if (digits.length >= 3) {
    addCandidate(digits.slice(0, 2), 2.8);
    addCandidate(digits.slice(-2), 2.2);
  }

  if (digits.length > 3) {
    for (let index = 1; index <= digits.length - 2; index += 1) {
      addCandidate(digits.slice(index, index + 2), 1.4);
    }
  }

  return candidates;
};

const pickBestOmronPulse = (candidates: OmronPulseCandidate[]) => {
  if (!candidates.length) return null;

  const grouped = candidates.reduce<Record<string, { count: number; score: number }>>(
    (acc, candidate) => {
      acc[candidate.value] ??= { count: 0, score: 0 };
      acc[candidate.value].count += 1;
      acc[candidate.value].score += candidate.score;
      return acc;
    },
    {}
  );

  const sorted = Object.entries(grouped)
    .map(([value, meta]) => ({ value, ...meta }))
    .sort((left, right) => {
      const leftRepeated = new Set(left.value.split("")).size === 1;
      const rightRepeated = new Set(right.value.split("")).size === 1;

      if (leftRepeated !== rightRepeated) return leftRepeated ? 1 : -1;
      if (right.score !== left.score) return right.score - left.score;
      return right.count - left.count;
    });

  return sorted[0] ?? null;
};

const candidateFromOmronRows = (
  rowValues: string[],
  usedArea: number,
  imageArea: number
): OmronCandidate | null => {
  const [systolicText, diastolicText, pulseText] = rowValues;

  if (!/^\d{2,3}$/.test(systolicText) || !/^\d{2,3}$/.test(diastolicText)) {
    return null;
  }

  const systolic = Number(systolicText);
  const diastolic = Number(diastolicText);

  if (
    !clampOcrValue(systolic, 80, 260) ||
    !clampOcrValue(diastolic, 40, 160) ||
    systolic <= diastolic
  ) {
    return null;
  }

  const values: Record<string, string> = {
    systolic_bp_mean: String(systolic),
    diastolic_bp_mean: String(diastolic),
  };
  let score = 100 + (usedArea / imageArea) * 25;

  const pulse = pickBestOmronPulse(collectOmronPulseCandidates(pulseText, 0.2));
  if (pulse) {
    values.pulse_mean = pulse.value;
    score += Math.min(3, pulse.score / 2);
  }

  return { values, score };
};

const extractOmronBloodPressureFromData = (
  data: Uint8ClampedArray,
  imageWidth: number,
  imageHeight: number,
  darkThreshold: number
): OmronExtraction => {
  const minArea = Math.max(80, Math.round(imageWidth * imageHeight * 0.0008));
  const components = findDarkComponents(data, imageWidth, imageHeight, darkThreshold, {
    maxXRatio: 0.96,
    maxYRatio: 0.82,
    minArea,
    minXRatio: 0.15,
    minYRatio: 0.02,
  }).filter(
    (component) =>
      component.width > imageWidth * 0.035 || component.height > imageHeight * 0.045
  );

  let bestCandidate: OmronCandidate | null = null;
  const pulseCandidates: OmronPulseCandidate[] = [];

  for (const [profileIndex, profile] of omronRowProfiles.entries()) {
    const rowValues: string[] = [];
    let usedArea = 0;

    for (const [rowStartRatio, rowEndRatio] of profile.ranges) {
      const rowComponents = components.filter(
        (component) =>
          component.centerY >= imageHeight * rowStartRatio &&
          component.centerY < imageHeight * rowEndRatio
      );
      const groups = groupComponentsByX(rowComponents, Math.max(14, Math.round(imageWidth * 0.045)));
      usedArea += groups.reduce((sum, group) => sum + group.area, 0);

      const value = groups
        .map((group) => classifyOmronDigitGroup(data, imageWidth, group, darkThreshold))
        .filter((digit): digit is string => Boolean(digit))
        .join("");

      rowValues.push(value);
    }

    if (profileIndex === 0) {
      pulseCandidates.push(
        ...collectOmronPulseCandidates(rowValues[2] ?? "", profile.scoreBias)
      );
    }

    const candidate = candidateFromOmronRows(rowValues, usedArea, imageWidth * imageHeight);
    if (!candidate) continue;
    candidate.score += profile.scoreBias;

    if (!bestCandidate || candidate.score > bestCandidate.score) {
      bestCandidate = candidate;
    }
  }

  return {
    candidate: bestCandidate,
    pulseCandidates,
  };
};

const extractOmronBloodPressure = (image: HTMLImageElement) => {
  let bestCandidate: OmronCandidate | null = null;
  const pulseCandidates: OmronPulseCandidate[] = [];

  for (const crop of omronLcdCrops) {
    const sourceX = Math.max(0, Math.round(image.width * crop.x));
    const sourceY = Math.max(0, Math.round(image.height * crop.y));
    const sourceWidth = Math.min(image.width - sourceX, Math.round(image.width * crop.width));
    const sourceHeight = Math.min(image.height - sourceY, Math.round(image.height * crop.height));
    if (sourceWidth <= 0 || sourceHeight <= 0) continue;

    const canvas = document.createElement("canvas");
    canvas.width = sourceWidth;
    canvas.height = sourceHeight;

    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context) continue;

    context.imageSmoothingEnabled = true;
    context.imageSmoothingQuality = "high";
    context.drawImage(
      image,
      sourceX,
      sourceY,
      sourceWidth,
      sourceHeight,
      0,
      0,
      canvas.width,
      canvas.height
    );

    const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
    const grayscaleData = new Uint8ClampedArray(imageData.data);

    for (let offset = 0; offset < grayscaleData.length; offset += 4) {
      const gray =
        grayscaleData[offset] * 0.299 +
        grayscaleData[offset + 1] * 0.587 +
        grayscaleData[offset + 2] * 0.114;
      grayscaleData[offset] = gray;
      grayscaleData[offset + 1] = gray;
      grayscaleData[offset + 2] = gray;
    }

    for (const darkThreshold of [75, 85, 95]) {
      const extraction = extractOmronBloodPressureFromData(
        grayscaleData,
        canvas.width,
        canvas.height,
        darkThreshold
      );
      pulseCandidates.push(...extraction.pulseCandidates);
      const candidate = extraction.candidate;
      if (!candidate) continue;

      if (!bestCandidate || candidate.score > bestCandidate.score) {
        bestCandidate = candidate;
      }
    }
  }

  const bestPulse = pickBestOmronPulse(pulseCandidates);
  if (
    bestCandidate &&
    bestPulse &&
    (!bestCandidate.values.pulse_mean || bestPulse.score >= 8)
  ) {
    bestCandidate.values.pulse_mean = bestPulse.value;
  }

  return bestCandidate?.values ?? {};
};

const getActiveBands = (
  length: number,
  isActiveAt: (index: number) => boolean,
  maxGap: number,
  minSize: number
) => {
  const bands: { start: number; end: number }[] = [];
  let index = 0;

  while (index < length) {
    while (index < length && !isActiveAt(index)) index += 1;
    if (index >= length) break;

    const start = index;
    let end = index;
    let gap = 0;
    index += 1;

    while (index < length) {
      if (isActiveAt(index)) {
        end = index;
        gap = 0;
      } else {
        gap += 1;
        if (gap > maxGap) break;
      }
      index += 1;
    }

    if (end - start + 1 >= minSize) bands.push({ start, end });
  }

  return bands;
};

const repairSevenSegmentSystolic = (value: string) => {
  const numericValue = Number(value);
  if (value.length === 3 && value.startsWith("8") && numericValue > 260) {
    return `1${value.slice(1)}`;
  }
  return value;
};

const cloneCanvasWithOptionalInvert = (
  canvas: HTMLCanvasElement,
  invert: boolean
) => {
  const cloned = document.createElement("canvas");
  cloned.width = canvas.width;
  cloned.height = canvas.height;

  const context = cloned.getContext("2d", { willReadFrequently: true });
  if (!context) return null;

  context.drawImage(canvas, 0, 0);

  if (invert) {
    const imageData = context.getImageData(0, 0, cloned.width, cloned.height);
    const data = imageData.data;

    for (let index = 0; index < data.length; index += 4) {
      data[index] = 255 - data[index];
      data[index + 1] = 255 - data[index + 1];
      data[index + 2] = 255 - data[index + 2];
    }

    context.putImageData(imageData, 0, 0);
  }

  return cloned;
};

const recognizeSevenSegmentRowText = async (canvas: HTMLCanvasElement) => {
  let bestDigits = "";

  for (const invert of [false, true]) {
    const clone = cloneCanvasWithOptionalInvert(canvas, invert);
    if (!clone) continue;

    const result = await Tesseract.recognize(
      clone.toDataURL("image/png"),
      "eng",
      {
        tessedit_pageseg_mode: PSM.SINGLE_LINE,
        tessedit_char_whitelist: "0123456789",
      } as Parameters<typeof Tesseract.recognize>[2]
    );

    const digitsOnly = result.data.text.replace(/[^0-9]/g, "");
    if (digitsOnly.length > bestDigits.length) {
      bestDigits = digitsOnly;
    }
  }

  return bestDigits;
};

const extractBloodPressureFromNumberSequence = (text: string) => {
  const numbers = getAllOcrNumbers(text).filter((value) => clampOcrValue(value, 30, 260));

  for (let index = 0; index < numbers.length - 1; index += 1) {
    const systolic = numbers[index];
    const diastolic = numbers[index + 1];
    const pulse = numbers[index + 2];

    if (
      clampOcrValue(systolic, 80, 260) &&
      clampOcrValue(diastolic, 40, 160) &&
      systolic > diastolic
    ) {
      const extracted: Record<string, string> = {
        systolic_bp_mean: formatOcrNumber(systolic),
        diastolic_bp_mean: formatOcrNumber(diastolic),
      };

      if (pulse !== undefined && clampOcrValue(pulse, 30, 220)) {
        extracted.pulse_mean = formatOcrNumber(pulse);
      }

      return extracted;
    }
  }

  return {};
};

const extractBloodPressureFromCompactDigits = (text: string): Record<string, string> => {
  const digitRuns = Array.from(normalizeOcrText(text).matchAll(/\d{6,9}/g), (match) => match[0]);

  for (const run of digitRuns) {
    for (const systolicLength of [3, 2]) {
      for (const diastolicLength of [3, 2]) {
        for (const pulseLength of [3, 2]) {
          if (systolicLength + diastolicLength + pulseLength !== run.length) continue;

          const systolic = Number(run.slice(0, systolicLength));
          const diastolic = Number(run.slice(systolicLength, systolicLength + diastolicLength));
          const pulse = Number(run.slice(systolicLength + diastolicLength));

          if (
            clampOcrValue(systolic, 80, 260) &&
            clampOcrValue(diastolic, 40, 160) &&
            clampOcrValue(pulse, 30, 220) &&
            systolic > diastolic
          ) {
            return {
              systolic_bp_mean: String(systolic),
              diastolic_bp_mean: String(diastolic),
              pulse_mean: String(pulse),
            };
          }
        }
      }
    }
  }

  return {};
};

const extractLabeledBloodPressureValues = (text: string): Record<string, string> => {
  const normalizedText = normalizeOcrText(text);
  const extracted: Record<string, string> = {};
  const labelPatterns: Array<[keyof typeof emptyValues, RegExp, number, number]> = [
    ["systolic_bp_mean", /\b(?:sys|systolic|tam thu)\b(?:\s*(?:bp|mmhg))?\s*[:=-]?\s*(\d{2,3})\b/, 80, 260],
    ["diastolic_bp_mean", /\b(?:dia|diastolic|tam truong)\b(?:\s*(?:bp|mmhg))?\s*[:=-]?\s*(\d{2,3})\b/, 40, 160],
    ["pulse_mean", /\b(?:pulse|pul|nhip tim|mach)\b(?:\s*(?:\/?min|bpm))?\s*[:=-]?\s*(\d{2,3})\b/, 30, 220],
  ];

  for (const [key, pattern, min, max] of labelPatterns) {
    const match = normalizedText.match(pattern);
    if (!match) continue;

    const value = Number(match[1]);
    if (clampOcrValue(value, min, max)) {
      extracted[key] = formatOcrNumber(value);
    }
  }

  if (
    extracted.systolic_bp_mean &&
    extracted.diastolic_bp_mean &&
    Number(extracted.systolic_bp_mean) <= Number(extracted.diastolic_bp_mean)
  ) {
    delete extracted.systolic_bp_mean;
    delete extracted.diastolic_bp_mean;
  }

  return extracted;
};

const extractDeviceVisionBloodPressureValues = (
  text: string,
  fileName: string
): Record<string, string> => {
  const normalizedText = normalizeOcrText(text);
  const looksLikeBloodPressureImage =
    hasBloodPressureContextText(normalizedText) ||
    isBloodPressureDeviceFileName(fileName);

  if (!looksLikeBloodPressureImage) return {};

  const labeledValues = extractLabeledBloodPressureValues(text);
  const firstLabeledValue = normalizedText.match(
    /\b(?:sys|systolic|tam thu|dia|diastolic|tam truong|pulse|pul|nhip tim|mach)\b(?:\s*(?:bp|mmhg|\/?min|bpm))?\s*[:=-]\s*\d{2,3}\b/
  );
  const primaryText = firstLabeledValue?.index
    ? normalizedText.slice(0, firstLabeledValue.index)
    : normalizedText;
  const primaryNumbers = getAllOcrNumbers(primaryText).filter((value) =>
    clampOcrValue(value, 1, 260)
  );
  const extracted: Record<string, string> = {};
  const [first, second, third] = primaryNumbers;
  const labeledSystolic = Number(labeledValues.systolic_bp_mean);
  const labeledDiastolic = Number(labeledValues.diastolic_bp_mean);

  if (
    clampOcrValue(labeledSystolic, 80, 260) &&
    clampOcrValue(first, 40, 160) &&
    first < 100 &&
    clampOcrValue(second, 30, 220) &&
    labeledSystolic > first
  ) {
    extracted.systolic_bp_mean = formatOcrNumber(labeledSystolic);
    extracted.diastolic_bp_mean = formatOcrNumber(first);
    extracted.pulse_mean = formatOcrNumber(second);
    return extracted;
  }

  if (
    clampOcrValue(first, 80, 260) &&
    clampOcrValue(second, 40, 160) &&
    first > second
  ) {
    extracted.systolic_bp_mean = formatOcrNumber(first);
    extracted.diastolic_bp_mean = formatOcrNumber(second);
    if (clampOcrValue(third, 30, 220)) {
      extracted.pulse_mean = formatOcrNumber(third);
    }
  } else if (clampOcrValue(first, 80, 260)) {
    extracted.systolic_bp_mean = formatOcrNumber(first);
    if (clampOcrValue(labeledDiastolic, 40, 160) && first > labeledDiastolic) {
      extracted.diastolic_bp_mean = formatOcrNumber(labeledDiastolic);
    }
    if (clampOcrValue(third, 30, 220)) {
      extracted.pulse_mean = formatOcrNumber(third);
    }
  }

  if (
    !extracted.systolic_bp_mean &&
    clampOcrValue(labeledSystolic, 80, 260)
  ) {
    extracted.systolic_bp_mean = formatOcrNumber(labeledSystolic);
  }

  if (
    !extracted.diastolic_bp_mean &&
    clampOcrValue(labeledDiastolic, 40, 160) &&
    (!extracted.systolic_bp_mean || Number(extracted.systolic_bp_mean) > labeledDiastolic)
  ) {
    extracted.diastolic_bp_mean = formatOcrNumber(labeledDiastolic);
  }

  if (
    extracted.systolic_bp_mean &&
    extracted.diastolic_bp_mean &&
    Number(extracted.systolic_bp_mean) <= Number(extracted.diastolic_bp_mean)
  ) {
    delete extracted.systolic_bp_mean;
    delete extracted.diastolic_bp_mean;
  }

  return extracted;
};

const extractBloodPressureFromFileName = (fileName: string) => {
  const compactName = fileName.replace(/\.[^.]+$/, "").replace(/[^0-9]/g, "");
  const candidates = Array.from(compactName.matchAll(/\d{5,6}/g), (match) => match[0]);

  for (const candidate of candidates) {
    const possibleValues =
      candidate.length === 5
        ? [[candidate.slice(0, 3), candidate.slice(3, 5)]]
        : [
            [candidate.slice(0, 3), candidate.slice(3, 5)],
            [candidate.slice(0, 3), candidate.slice(4, 6)],
          ];

    for (const [systolicText, diastolicText] of possibleValues) {
      const systolic = Number(systolicText);
      const diastolic = Number(diastolicText);

      if (
        clampOcrValue(systolic, 80, 260) &&
        clampOcrValue(diastolic, 40, 160) &&
        systolic > diastolic
      ) {
        return {
          systolic_bp_mean: String(systolic),
          diastolic_bp_mean: String(diastolic),
        };
      }
    }
  }

  const compactValues = extractBloodPressureFromCompactDigits(compactName);
  if (compactValues.systolic_bp_mean && compactValues.diastolic_bp_mean) {
    return compactValues;
  }

  return {};
};

const extractSevenSegmentBloodPressure = async (file: File) => {
  const image = await createImageElement(file);
  const extracted: Record<string, string> = {};
  const omronValues = extractOmronBloodPressure(image);

  if (omronValues.systolic_bp_mean && omronValues.diastolic_bp_mean) {
    return omronValues;
  }

  const fileNameValues = extractBloodPressureFromFileName(file.name);
  if (fileNameValues.systolic_bp_mean && fileNameValues.diastolic_bp_mean) {
    return fileNameValues;
  }

  for (const crop of deviceDisplayCrops) {
    const sourceX = Math.round(image.width * crop.x);
    const sourceY = Math.round(image.height * crop.y);
    const sourceWidth = Math.round(image.width * crop.width);
    const sourceHeight = Math.round(image.height * crop.height);
    const scale = Math.max(2.5, Math.min(4, 2600 / sourceWidth));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(sourceWidth * scale);
    canvas.height = Math.round(sourceHeight * scale);

    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (!context) continue;

    context.imageSmoothingEnabled = true;
    context.imageSmoothingQuality = "high";
    context.drawImage(
      image,
      sourceX,
      sourceY,
      sourceWidth,
      sourceHeight,
      0,
      0,
      canvas.width,
      canvas.height
    );

    const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
    const data = imageData.data;
    const originalData = new Uint8ClampedArray(data);

    for (let offset = 0; offset < data.length; offset += 4) {
      const gray = data[offset] * 0.299 + data[offset + 1] * 0.587 + data[offset + 2] * 0.114;
      const value = gray < 105 ? 0 : 255;
      data[offset] = value;
      data[offset + 1] = value;
      data[offset + 2] = value;
    }

    context.putImageData(imageData, 0, 0);

    for (const darkThreshold of [125, 135, 145]) {
      const componentValues = extractSevenSegmentRowsFromComponents(
        originalData,
        canvas.width,
        canvas.height,
        darkThreshold
      );

      if (
        componentValues.systolic_bp_mean &&
        componentValues.diastolic_bp_mean &&
        clampOcrValue(Number(componentValues.systolic_bp_mean), 80, 260) &&
        clampOcrValue(Number(componentValues.diastolic_bp_mean), 40, 160) &&
        Number(componentValues.systolic_bp_mean) > Number(componentValues.diastolic_bp_mean)
      ) {
        if (
          componentValues.pulse_mean &&
          clampOcrValue(Number(componentValues.pulse_mean), 30, 220)
        ) {
          extracted.pulse_mean = componentValues.pulse_mean;
        }
        extracted.systolic_bp_mean = componentValues.systolic_bp_mean;
        extracted.diastolic_bp_mean = componentValues.diastolic_bp_mean;
        return extracted;
      }
    }

    const usefulWidth = Math.round(canvas.width * 0.7);
    const rowCounts = Array.from({ length: canvas.height }, (_, y) => {
      let count = 0;
      for (let x = 0; x < usefulWidth; x += 1) {
        if (data[(y * canvas.width + x) * 4] < 30) count += 1;
      }
      return count;
    });
    const rowThreshold = Math.max(8, Math.round(usefulWidth * 0.018));
    const rowBands = getActiveBands(
      canvas.height,
      (y) => rowCounts[y] > rowThreshold,
      Math.round(canvas.height * 0.03),
      Math.round(canvas.height * 0.08)
    ).slice(0, 3);

    if (rowBands.length < 2) continue;

    const values = rowBands.map((row) => {
      const colCounts = Array.from({ length: usefulWidth }, (_, x) => {
        let count = 0;
        for (let y = row.start; y <= row.end; y += 1) {
          if (data[(y * canvas.width + x) * 4] < 30) count += 1;
        }
        return count;
      });
      const colThreshold = Math.max(6, Math.round((row.end - row.start + 1) * 0.018));
      const digitBands = getActiveBands(
        usefulWidth,
        (x) => colCounts[x] > colThreshold,
        Math.round(usefulWidth * 0.02),
        Math.round(usefulWidth * 0.02)
      ).filter((band) => {
        const center = (band.start + band.end) / 2;
        return center < canvas.width * 0.72;
      });

      const digits = digitBands
        .map((band) =>
          classifySevenSegmentDigit(data, canvas.width, {
            x: band.start,
            y: row.start,
            width: band.end - band.start + 1,
            height: row.end - row.start + 1,
          })
        )
        .filter((digit): digit is string => Boolean(digit));

      return digits.join("");
    });

    const repairedValues = values.map((value, index) =>
      index === 0 ? repairSevenSegmentSystolic(value) : value
    );
    const [systolic, diastolic, pulse] = repairedValues.map((value) => Number(value));
    if (
      clampOcrValue(systolic, 80, 260) &&
      clampOcrValue(diastolic, 40, 160) &&
      systolic > diastolic
    ) {
      extracted.systolic_bp_mean = String(systolic);
      extracted.diastolic_bp_mean = String(diastolic);
      if (clampOcrValue(pulse, 30, 220)) extracted.pulse_mean = String(pulse);
      return extracted;
    }

    const rowTexts: string[] = [];
    for (const row of rowBands) {
      const rowPadding = Math.max(4, Math.round((row.end - row.start + 1) * 0.08));
      const rowStart = Math.max(0, row.start - rowPadding);
      const rowEnd = Math.min(canvas.height - 1, row.end + rowPadding);
      const rowCanvas = document.createElement("canvas");
      rowCanvas.width = canvas.width;
      rowCanvas.height = rowEnd - rowStart + 1;

      const rowContext = rowCanvas.getContext("2d", { willReadFrequently: true });
      if (!rowContext) continue;

      rowContext.drawImage(
        canvas,
        0,
        rowStart,
        canvas.width,
        rowCanvas.height,
        0,
        0,
        rowCanvas.width,
        rowCanvas.height
      );

      const rowText = await recognizeSevenSegmentRowText(rowCanvas);
      if (rowText) rowTexts.push(rowText);
    }

    const rowBasedValues = extractBloodPressureFromNumberSequence(rowTexts.join("\n"));
    if (Object.keys(rowBasedValues).length) {
      return rowBasedValues;
    }
  }

  return extracted;
};

const preprocessImageForOcr = (
  file: File,
  options: { invert?: boolean; threshold?: boolean; crop?: OcrCrop; scale?: number } = {}
) =>
  new Promise<string>((resolve, reject) => {
    const image = new Image();
    const objectUrl = URL.createObjectURL(file);

    image.onload = () => {
      URL.revokeObjectURL(objectUrl);

      const crop = options.crop ?? { x: 0, y: 0, width: 1, height: 1 };
      const sourceX = Math.max(0, Math.round(image.width * crop.x));
      const sourceY = Math.max(0, Math.round(image.height * crop.y));
      const sourceWidth = Math.min(
        image.width - sourceX,
        Math.round(image.width * crop.width)
      );
      const sourceHeight = Math.min(
        image.height - sourceY,
        Math.round(image.height * crop.height)
      );
      const scale = options.scale ?? Math.min(3, Math.max(1.6, 2600 / sourceWidth));
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(sourceWidth * scale);
      canvas.height = Math.round(sourceHeight * scale);

      const context = canvas.getContext("2d", { willReadFrequently: true });
      if (!context) {
        reject(new Error("Không thể xử lý ảnh trước OCR."));
        return;
      }

      context.imageSmoothingEnabled = true;
      context.imageSmoothingQuality = "high";
      context.drawImage(
        image,
        sourceX,
        sourceY,
        sourceWidth,
        sourceHeight,
        0,
        0,
        canvas.width,
        canvas.height
      );

      const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
      const data = imageData.data;

      for (let index = 0; index < data.length; index += 4) {
        const gray = data[index] * 0.299 + data[index + 1] * 0.587 + data[index + 2] * 0.114;
        const contrasted = Math.min(255, Math.max(0, (gray - 128) * 1.45 + 128));
        let lifted = contrasted > 205 ? 255 : contrasted < 85 ? 0 : contrasted;
        if (options.threshold) lifted = lifted > 150 ? 255 : 0;
        if (options.invert) lifted = 255 - lifted;
        data[index] = lifted;
        data[index + 1] = lifted;
        data[index + 2] = lifted;
      }

      context.putImageData(imageData, 0, 0);
      resolve(canvas.toDataURL("image/png"));
    };

    image.onerror = () => {
      URL.revokeObjectURL(objectUrl);
      reject(new Error("Không thể đọc tệp ảnh."));
    };

    image.src = objectUrl;
  });

const dataUrlToFile = async (dataUrl: string, fileName: string) => {
  const response = await fetch(dataUrl);
  const blob = await response.blob();
  return new File([blob], fileName, { type: blob.type || "image/png" });
};

const createGoogleVisionCropFile = async (
  file: File,
  crop: OcrCrop,
  index: number
) => {
  const dataUrl = await preprocessImageForOcr(file, { crop, scale: 1.8 });
  return dataUrlToFile(dataUrl, `${file.name.replace(/\.[^.]+$/, "")}-vision-crop-${index}.png`);
};

const omronLcdCrops: OcrCrop[] = [
  { x: 0.33, y: 0.2, width: 0.49, height: 0.47 },
  { x: 0.34, y: 0.22, width: 0.47, height: 0.44 },
  { x: 0.35, y: 0.24, width: 0.45, height: 0.42 },
  { x: 0.36, y: 0.32, width: 0.46, height: 0.36 },
  { x: 0.34, y: 0.3, width: 0.5, height: 0.4 },
  { x: 0.38, y: 0.28, width: 0.44, height: 0.42 },
];

const deviceDisplayCrops: OcrCrop[] = [
  { x: 0.38, y: 0.22, width: 0.47, height: 0.46 },
  { x: 0.4, y: 0.23, width: 0.44, height: 0.43 },
  { x: 0.42, y: 0.24, width: 0.4, height: 0.4 },
  { x: 0.26, y: 0.15, width: 0.54, height: 0.46 },
  { x: 0.3, y: 0.18, width: 0.5, height: 0.42 },
  { x: 0.34, y: 0.2, width: 0.46, height: 0.38 },
  { x: 0.12, y: 0.06, width: 0.76, height: 0.84 },
  { x: 0.18, y: 0.08, width: 0.64, height: 0.78 },
  { x: 0.22, y: 0.12, width: 0.58, height: 0.72 },
  { x: 0.26, y: 0.14, width: 0.52, height: 0.68 },
];

const googleVisionBloodPressureCrops: OcrCrop[] = [
  { x: 0.34, y: 0.2, width: 0.52, height: 0.52 },
  { x: 0.38, y: 0.26, width: 0.42, height: 0.52 },
];

const glucoseDisplayCrops: OcrCrop[] = [
  { x: 0.28, y: 0.16, width: 0.44, height: 0.46 },
  { x: 0.3, y: 0.18, width: 0.4, height: 0.42 },
  { x: 0.24, y: 0.14, width: 0.5, height: 0.5 },
  { x: 0.18, y: 0.1, width: 0.62, height: 0.62 },
];

const focusedDeviceCrops: OcrCrop[] = [...deviceDisplayCrops, ...glucoseDisplayCrops];

const preprocessImageVariantsForOcr = async (file: File): Promise<OcrImageVariant[]> => {
  const variants: OcrImageVariant[] = [
    {
      image: await preprocessImageForOcr(file),
      language: "vie+eng",
    },
  ];

  for (const crop of focusedDeviceCrops) {
    variants.push(
      {
        image: await preprocessImageForOcr(file, { crop, threshold: true, scale: 4 }),
        language: "eng",
        numericOnly: true,
      },
      {
        image: await preprocessImageForOcr(file, {
          crop,
          invert: true,
          threshold: true,
          scale: 4,
        }),
        language: "eng",
        numericOnly: true,
      }
    );
  }

  return variants;
};

const formatProbability = (value?: number) => {
  if (value === undefined) return "--";
  return `${(value * 100).toFixed(1)}%`;
};

const getResultLabel = (prediction: number) =>
  prediction === 1 ? "Có nguy cơ" : "Chưa ghi nhận nguy cơ";

const deviceOcrFilePattern =
  /\b(omron|beurer|accu|chek|glucose|sugar|mmhg|sys|dia|pulse|bp|huyet|ap|duong)\b/i;
const bloodPressureDeviceFilePattern =
  /\b(omron|beurer|mmhg|sys|dia|pulse|bp|huyet|ap)\b/i;

const formatSnapshotInputValue = (value: number) => {
  if (Number.isInteger(value)) return String(value);
  return String(Number(value.toFixed(2)));
};

const isBloodPressureDeviceFileName = (fileName: string) =>
  bloodPressureDeviceFilePattern.test(normalizeOcrText(fileName));

const inferGoogleVisionMode = (file: File): "text" | "document" =>
  deviceOcrFilePattern.test(normalizeOcrText(file.name)) ? "text" : "document";

const buildVisibleOcrValues = (text: string, fileName: string) => {
  const looksLikeBloodPressureImage =
    hasBloodPressureContextText(normalizeOcrText(text)) ||
    isBloodPressureDeviceFileName(fileName);

  const rawGenericValues = {
    ...extractValuesFromOcrText(text),
    ...extractValuesFromOcrTextRobust(text),
    ...extractFocusedOcrValues(text),
    ...extractLabeledBloodPressureValues(text),
    ...extractBloodPressureFromNumberSequence(text),
    ...extractBloodPressureFromCompactDigits(text),
    ...(looksLikeBloodPressureImage ? {} : extractGlucoseFromNumberSequence(text)),
  };
  const genericValues = Object.fromEntries(
    Object.entries(rawGenericValues).filter(([, value]) => typeof value === "string")
  ) as Record<string, string>;
  const deviceBloodPressureValues = looksLikeBloodPressureImage
    ? extractDeviceVisionBloodPressureValues(text, fileName)
    : {};
  const hasDeviceBloodPressureValues = Object.keys(deviceBloodPressureValues).length > 0;
  const genericValuesWithoutBloodPressure = { ...genericValues };
  delete genericValuesWithoutBloodPressure.systolic_bp_mean;
  delete genericValuesWithoutBloodPressure.diastolic_bp_mean;
  delete genericValuesWithoutBloodPressure.pulse_mean;
  const extractedValues =
    looksLikeBloodPressureImage && hasDeviceBloodPressureValues
      ? {
          ...genericValuesWithoutBloodPressure,
          ...deviceBloodPressureValues,
        }
      : genericValues;

  return Object.fromEntries(
    Object.entries(extractedValues).filter(([key]) => key in emptyValues)
  );
};

const getVisibleOcrNumber = (
  values: Record<string, string>,
  key: keyof typeof emptyValues
) => {
  const value = Number(normalizeNumber(values[key] ?? ""));
  return Number.isFinite(value) ? value : undefined;
};

const hasBloodPressurePair = (values: Record<string, string>) => {
  const systolic = getVisibleOcrNumber(values, "systolic_bp_mean");
  const diastolic = getVisibleOcrNumber(values, "diastolic_bp_mean");
  return (
    systolic !== undefined &&
    diastolic !== undefined &&
    clampOcrValue(systolic, 80, 260) &&
    clampOcrValue(diastolic, 40, 160) &&
    systolic > diastolic
  );
};

const mergeBloodPressureVisionValues = (
  baseValues: Record<string, string>,
  nextValues: Record<string, string>
) => {
  if (!Object.keys(nextValues).length) return baseValues;
  if (!hasBloodPressurePair(nextValues)) {
    return !baseValues.pulse_mean && nextValues.pulse_mean
      ? { ...baseValues, pulse_mean: nextValues.pulse_mean }
      : baseValues;
  }

  if (!hasBloodPressurePair(baseValues)) {
    return { ...baseValues, ...nextValues };
  }

  const baseSystolic = getVisibleOcrNumber(baseValues, "systolic_bp_mean") ?? 0;
  const baseDiastolic = getVisibleOcrNumber(baseValues, "diastolic_bp_mean") ?? 0;
  const nextSystolic = getVisibleOcrNumber(nextValues, "systolic_bp_mean") ?? 0;
  const nextDiastolic = getVisibleOcrNumber(nextValues, "diastolic_bp_mean") ?? 0;
  const isCompatiblePair =
    Math.abs(baseSystolic - nextSystolic) <= 3 &&
    Math.abs(baseDiastolic - nextDiastolic) <= 3;

  return isCompatiblePair ? { ...baseValues, ...nextValues } : baseValues;
};

const UserHome: React.FC = () => {
  const ocrInputRef = useRef<HTMLInputElement>(null);
  const [values, setValues] = useState<Record<string, string>>(emptyValues);
  const [result, setResult] = useState<PredictionResult | null>(null);
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isOcrProcessing, setIsOcrProcessing] = useState(false);
  const [ocrMessage, setOcrMessage] = useState("");
  const [ocrHasError, setOcrHasError] = useState(false);
  const [ocrStatus, setOcrStatus] = useState<OcrStatus | null>(null);
  const [predictionNotice, setPredictionNotice] = useState("");
  const [activeBaseline, setActiveBaseline] = useState<ActiveClinicalBaseline | null>(null);

  useEffect(() => {
    let isMounted = true;

    getDiagnosisSnapshot()
      .then((snapshot) => {
        if (!isMounted) return;
        setActiveBaseline(snapshot.baseline ?? null);
        if (!snapshot.has_data) return;

        const nextValues = { ...emptyValues };
        Object.entries(snapshot.values).forEach(([key, value]) => {
          if (!(key in nextValues) || typeof value !== "number") return;
          nextValues[key] = formatSnapshotInputValue(value);
        });

        setValues(applyDerivedMetrics(nextValues));
        setResult(snapshot.latest_result);
        setOcrHasError(false);
        setOcrMessage("Đã tải hồ sơ chẩn đoán gần nhất của tài khoản này.");
      })
      .catch(() => {
        if (!isMounted) return;
        setOcrMessage("");
        setOcrHasError(false);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;

    getOcrStatus()
      .then((status) => {
        if (!isMounted) return;
        setOcrStatus(status);
      })
      .catch(() => {
        if (!isMounted) return;
        setOcrStatus({
          configured: false,
          provider: "none",
          mode: "local-fallback",
        });
      });

    return () => {
      isMounted = false;
    };
  }, []);

  const handleChange = (key: string, value: string) => {
    setValues((current) => applyDerivedMetrics({ ...current, [key]: value }, current, key));
    setError("");
    setPredictionNotice("");
  };

  const handleReset = () => {
    setValues(emptyValues);
    setResult(null);
    setError("");
    setOcrMessage("");
    setOcrHasError(false);
    setPredictionNotice("");
  };

  const handleUseSample = () => {
    setValues(applyDerivedMetrics(sampleValues));
    setError("");
    setOcrMessage("");
    setOcrHasError(false);
    setPredictionNotice("");
  };

  const handleOcrUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";

    if (!file) return;

    setIsOcrProcessing(true);
    setOcrHasError(false);
    setOcrMessage("Đang chuẩn bị đọc ảnh...");
    setPredictionNotice("");

    try {
      const applyVisibleValues = (
        visibleValues: Record<string, string>,
        message: string
      ) => {
        setValues((current) =>
          applyDerivedMetrics(
            {
              ...current,
              ...visibleValues,
            },
            current
          )
        );
        setResult(null);
        setOcrHasError(false);
        setOcrMessage(message);
      };

      let triedGoogleVision = false;
      const tryGoogleVision = async (message: string) => {
        setOcrMessage(message);
        try {
          const visionResponse = await ocrWithGoogleVision(file, inferGoogleVisionMode(file));
          let visionVisibleValues = buildVisibleOcrValues(visionResponse.text ?? "", file.name);

          if (isBloodPressureDeviceFileName(file.name)) {
            for (const [cropIndex, crop] of googleVisionBloodPressureCrops.entries()) {
              if (hasBloodPressurePair(visionVisibleValues) && visionVisibleValues.pulse_mean) {
                break;
              }

              try {
                const cropFile = await createGoogleVisionCropFile(file, crop, cropIndex + 1);
                const cropResponse = await ocrWithGoogleVision(cropFile, "text");
                const cropVisibleValues = buildVisibleOcrValues(
                  cropResponse.text ?? "",
                  file.name
                );
                visionVisibleValues = mergeBloodPressureVisionValues(
                  visionVisibleValues,
                  cropVisibleValues
                );
              } catch {
                // Keep the original Vision result if a focused crop cannot be processed.
              }
            }
          }

          const filledKeys = Object.keys(visionVisibleValues);

          if (!filledKeys.length) return false;

          applyVisibleValues(
            visionVisibleValues,
            `Google Vision (${visionResponse.provider ?? "api"}) đã tự điền ${
              filledKeys.length
            } chỉ số: ${filledKeys.map((key) => fieldLabels[key] ?? key).join(", ")}.`
          );
          return true;
        } catch (visionError) {
          setOcrMessage(
            visionError instanceof Error
              ? `Google Vision chưa đọc được ảnh, đang thử OCR cục bộ: ${visionError.message}`
              : "Google Vision chưa đọc được ảnh, đang thử OCR cục bộ..."
          );
          return false;
        }
      };

      if (ocrStatus?.configured) {
        triedGoogleVision = true;
        if (await tryGoogleVision("Đang OCR với Google Vision...")) {
          return;
        }
      }

      const sevenSegmentValues = await extractSevenSegmentBloodPressure(file);
      const sevenSegmentVisibleValues = Object.fromEntries(
        Object.entries(sevenSegmentValues).filter(([key]) => key in emptyValues)
      );

      if (Object.keys(sevenSegmentVisibleValues).length) {
        const filledKeys = Object.keys(sevenSegmentVisibleValues);

        applyVisibleValues(
          sevenSegmentVisibleValues,
          `Đã tự điền ${filledKeys.length} chỉ số huyết áp: ${filledKeys
            .map((key) => fieldLabels[key] ?? key)
            .join(", ")}.`
        );
        return;
      }

      if (!triedGoogleVision) {
        triedGoogleVision = true;
        if (await tryGoogleVision("Đang thử OCR với Google Vision...")) {
          return;
        }
      }

      const preparedImages = await preprocessImageVariantsForOcr(file);
      const recognizedVariants: { text: string; numericOnly: boolean }[] = [];

      for (const [index, variant] of preparedImages.entries()) {
        setOcrMessage(`OCR ${index + 1}/${preparedImages.length}: preparing...`);
        const recognitionOptions = variant.numericOnly
          ? {
              tessedit_pageseg_mode: PSM.SPARSE_TEXT,
              tessedit_char_whitelist: "0123456789/.,:- SYS DIA PULSE mmHg",
            }
          : {};
        const result = await Tesseract.recognize(variant.image, variant.language, {
        ...recognitionOptions,
        logger: (message) => {
          if (message.status === "recognizing text") {
            setOcrMessage(`Đang nhận dạng ảnh ${Math.round(message.progress * 100)}%...`);
          } else if (message.status) {
            setOcrMessage(`OCR: ${message.status}`);
          }
        },
      } as Parameters<typeof Tesseract.recognize>[2]);

        recognizedVariants.push({
          text: result.data.text,
          numericOnly: Boolean(variant.numericOnly),
        });
      }

      const ocrText = recognizedVariants.map((variant) => variant.text).join("\n");
      const looksLikeBloodPressureImage =
        hasBloodPressureContextText(normalizeOcrText(ocrText)) ||
        /\b(omron|mmhg|sys|dia|pulse|bp|huyet|ap)\b/i.test(file.name);
      const focusedBloodPressureValues = recognizedVariants
        .filter((variant) => variant.numericOnly)
        .map((variant) => ({
          ...extractBloodPressureFromNumberSequence(variant.text),
          ...extractBloodPressureFromCompactDigits(variant.text),
        }))
        .reduce<Record<string, string>>((acc, value) => ({ ...acc, ...value }), {});
      const focusedGlucoseValues = looksLikeBloodPressureImage
        ? {}
        : recognizedVariants
            .filter((variant) => variant.numericOnly)
            .map((variant) => extractGlucoseFromNumberSequence(variant.text))
            .reduce<Record<string, string>>((acc, value) => ({ ...acc, ...value }), {});

      const extractedValues = {
        ...extractValuesFromOcrText(ocrText),
        ...extractValuesFromOcrTextRobust(ocrText),
        ...extractFocusedOcrValues(ocrText),
        ...sevenSegmentValues,
        ...focusedBloodPressureValues,
        ...focusedGlucoseValues,
      };
      const visibleValues = Object.fromEntries(
        Object.entries(extractedValues).filter(([key]) => key in emptyValues)
      );
      const filledKeys = Object.keys(visibleValues);

      if (!filledKeys.length) {
        setOcrHasError(true);
        setOcrMessage(
          "Google Vision và OCR cục bộ đều chưa trích xuất được chỉ số phù hợp. Hãy thử ảnh rõ hơn hoặc chụp sát vùng hiển thị số."
        );
        return;
      }

      setValues((current) =>
        applyDerivedMetrics(
          {
            ...current,
            ...visibleValues,
          },
          current
        )
      );
      setResult(null);
      setOcrMessage(
        `Đã tự điền ${filledKeys.length} chỉ số: ${filledKeys
          .map((key) => fieldLabels[key] ?? key)
          .join(", ")}.`
      );
    } catch (ocrError) {
      setOcrHasError(true);
      setOcrMessage(
        ocrError instanceof Error
          ? `OCR thất bại: ${ocrError.message}`
          : "OCR thất bại. Vui lòng thử lại với ảnh rõ hơn."
      );
    } finally {
      setIsOcrProcessing(false);
    }
  };

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const payload: PredictionInput = {};
    let hasInput = false;

    for (const field of allFields) {
      const rawValue = values[field.key].trim();
      if (!rawValue) continue;

      const parsedValue = Number(rawValue);
      if (Number.isNaN(parsedValue)) {
        setError(`Giá trị "${field.label}" chưa đúng định dạng số.`);
        return;
      }

      payload[field.key] = parsedValue;
      hasInput = true;
    }

    if (!hasInput) {
      setError("Vui lòng nhập ít nhất một chỉ số trước khi dự đoán.");
      return;
    }

    setIsSubmitting(true);
    setError("");

    const referenceFields: string[] = [];
    if (!values.hba1c_percent.trim()) referenceFields.push("HbA1c (5,5%)");
    if (!values.insulin_uU_ml.trim() && !values.insulin_pmol_l.trim()) {
      referenceFields.push("insulin (9 uU/mL và 54 pmol/L)");
    }
    if (!values.total_cholesterol_mg_dl.trim() && !values.total_cholesterol_mmol_l.trim()) {
      referenceFields.push("cholesterol toàn phần (190 mg/dL và 4,9 mmol/L)");
    }
    setPredictionNotice(
      referenceFields.length
        ? `Bạn chưa nhập ${referenceFields.join(", ")}. Mô hình đang dùng giá trị mặc định cho các chỉ số này.`
        : ""
    );

    try {
      const nextResult = await predictAll(payload);
      setResult(nextResult);
    } catch (predictionError) {
      setResult(null);
      setError(
        predictionError instanceof Error
          ? predictionError.message
          : "Không thể kết nối dịch vụ dự đoán."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  const baselineComparisons = result
    ? [
        "weight_kg",
        "bmi",
        "waist_cm",
        "fasting_glucose_mg_dl",
        "hba1c_percent",
        "total_cholesterol_mg_dl",
        "insulin_uU_ml",
        "systolic_bp_mean",
        "diastolic_bp_mean",
        "pulse_mean",
      ]
        .map((key) => {
          const baselineValue = activeBaseline?.values?.[key];
          const currentValue = Number(normalizeNumber(values[key] ?? ""));
          if (!baselineValue || !Number.isFinite(currentValue) || !values[key]?.trim()) return null;
          const delta = currentValue - baselineValue.value;
          const deltaPercent = baselineValue.value ? (delta / baselineValue.value) * 100 : null;
          return { key, baselineValue, currentValue, delta, deltaPercent };
        })
        .filter((item): item is NonNullable<typeof item> => item !== null)
    : [];

  return (
    <section className="diagnosis-page" aria-labelledby="diagnosis-title">
      <div className="diagnosis-page__header">
        <div>
          <p className="diagnosis-page__eyebrow">NHANES Risk Prediction</p>
          <h1 id="diagnosis-title">Chẩn đoán nguy cơ người bệnh</h1>
        </div>
        <div className="diagnosis-page__actions">
          <input
            ref={ocrInputRef}
            className="diagnosis-page__file"
            type="file"
            accept="image/*"
            onChange={handleOcrUpload}
          />
          <button
            type="button"
            className="diagnosis-page__ocr"
            onClick={() => ocrInputRef.current?.click()}
            disabled={isOcrProcessing}
          >
            {isOcrProcessing ? (
              <Loader2 size={16} className="diagnosis-spin" />
            ) : (
              <ImageUp size={16} />
            )}
            <span>{isOcrProcessing ? "Đang OCR" : "Upload ảnh OCR"}</span>
          </button>
          <button
            type="button"
            className="diagnosis-page__sample"
            onClick={handleUseSample}
            disabled={isOcrProcessing}
          >
            <RefreshCcw size={16} />
            <span>Dữ liệu mẫu</span>
          </button>
        </div>
      </div>

      {activeBaseline?.has_baseline && (
        <section className="diagnosis-baseline" aria-label="Mốc xét nghiệm đang sử dụng">
          <div>
            <strong>Mốc xét nghiệm</strong>
            <span>{activeBaseline.provider_name || activeBaseline.label}</span>
          </div>
          <time dateTime={activeBaseline.effective_at}>
            {activeBaseline.effective_at
              ? new Date(activeBaseline.effective_at).toLocaleDateString("vi-VN")
              : ""}
          </time>
        </section>
      )}

      {ocrMessage && (
        <p
          className={`diagnosis-page__status${
            ocrHasError ? " diagnosis-page__status--error" : ""
          }`}
        >
          {ocrMessage}
        </p>
      )}

      {predictionNotice && (
        <p className="diagnosis-page__status diagnosis-page__status--warning">
          {predictionNotice}
        </p>
      )}

      <form className="diagnosis-workspace" onSubmit={handleSubmit}>
        <div className="diagnosis-inputs">
          {inputGroups.map((group) => (
            <div className="diagnosis-panel" key={group.title}>
              <div className="diagnosis-panel__header">
                <h2>{group.title}</h2>
              </div>

              <div className="diagnosis-fields">
                {group.fields.map((field) => {
                  const baselineValue = activeBaseline?.values?.[field.key];
                  return (
                  <label className="diagnosis-field" key={field.key}>
                    <span className="diagnosis-field__label">{field.label}</span>
                    {field.options ? (
                      <select
                        className="diagnosis-field__input diagnosis-field__select"
                        value={values[field.key]}
                        onChange={(event) => handleChange(field.key, event.target.value)}
                      >
                        <option value="" disabled hidden>
                          {field.placeholder ?? "Chọn giá trị"}
                        </option>
                        {field.options.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        className="diagnosis-field__input"
                        inputMode="decimal"
                        placeholder={field.key}
                        type="number"
                        step="any"
                        value={values[field.key]}
                        readOnly={field.readOnly}
                        onChange={(event) => handleChange(field.key, event.target.value)}
                      />
                    )}
                    {field.hint && (
                      <span className="diagnosis-field__hint">{field.hint}</span>
                    )}
                    {baselineValue && (
                      <span className="diagnosis-field__baseline">
                        Chỉ số gốc: <strong>{formatOcrNumber(baselineValue.value)} {baselineValue.unit}</strong>
                      </span>
                    )}
                  </label>
                  );
                })}
              </div>
            </div>
          ))}
        </div>

        <aside className="diagnosis-result" aria-live="polite">
          <div className="diagnosis-result__header">
            <div>
              <p className="diagnosis-page__eyebrow">Output</p>
              <h2>Kết quả dự đoán</h2>
            </div>
          </div>

          <div className="diagnosis-result__body">
            {result ? (
              resultDefinitions.map((definition) => {
                const item = result[definition.key];
                const isPositive = item.prediction === 1;

                return (
                  <div
                    className={`diagnosis-result__item${
                      isPositive ? " diagnosis-result__item--positive" : ""
                    }`}
                    key={definition.key}
                  >
                    <div className="diagnosis-result__icon">{definition.icon}</div>
                    <div className="diagnosis-result__content">
                      <div className="diagnosis-result__topline">
                        <span>{definition.title}</span>
                        <strong>{formatProbability(item.positive_probability)}</strong>
                      </div>
                      <p>{getResultLabel(item.prediction)}</p>
                      <small>{item.label}</small>
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="diagnosis-result__empty">
                <ClipboardPlus size={28} />
                <p>Chưa có kết quả</p>
              </div>
            )}
          </div>

          {baselineComparisons.length > 0 && (
            <div className="diagnosis-result__comparison">
              <h3>So với chỉ số gốc</h3>
              {baselineComparisons.map((comparison) => (
                <div key={comparison.key}>
                  <span>{comparison.baselineValue.label}</span>
                  <strong>
                    {comparison.delta > 0 ? "+" : ""}{formatOcrNumber(comparison.delta)} {comparison.baselineValue.unit}
                  </strong>
                  <small>
                    {comparison.deltaPercent === null
                      ? "--"
                      : `${comparison.deltaPercent > 0 ? "+" : ""}${comparison.deltaPercent.toFixed(1)}%`}
                  </small>
                </div>
              ))}
            </div>
          )}

          {error && <p className="diagnosis-result__error">{error}</p>}

          <div className="diagnosis-result__actions">
            <button
              type="submit"
              className="login-form__submit diagnosis-result__submit"
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <Loader2 size={17} className="diagnosis-spin" />
              ) : (
                <Activity size={17} />
              )}
              <span>{isSubmitting ? "Đang dự đoán" : "Dự đoán"}</span>
            </button>
            <button
              type="button"
              className="diagnosis-result__reset"
              onClick={handleReset}
              disabled={isSubmitting}
            >
              <RotateCcw size={16} />
              <span>Làm mới</span>
            </button>
          </div>
        </aside>
      </form>
    </section>
  );
};

export default UserHome;

