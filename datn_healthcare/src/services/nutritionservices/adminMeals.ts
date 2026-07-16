import { fetcher } from "@/api/Fetcher";
import { NutritionMealTemplatePageResponseRaw } from "@/types/NutritionType";

type AdminMealTemplateQuery = {
  page?: number;
  size?: number;
  keyword?: string;
  mealType?: string;
};

export type AdminMealTemplateUpdatePayload = {
  name?: string;
  category?: string;
  cuisine?: string;
  keywords?: string;
  description?: string;
  prep_time?: string;
  cook_time?: string;
  total_time?: string;
  servings?: number | null;
  serving_size?: string;
  glycemic_index?: string;
  glycemic_load?: number | string | null;
  calories?: number | null;
  total_fat_g?: number | string | null;
  saturated_fat_g?: number | string | null;
  trans_fat_g?: number | string | null;
  cholesterol_mg?: number | string | null;
  sodium_mg?: number | string | null;
  total_carbohydrate_g?: number | string | null;
  dietary_fiber_g?: number | string | null;
  sugars_g?: number | string | null;
  added_sugars_g?: number | string | null;
  protein_g?: number | string | null;
  potassium_mg?: number | string | null;
  phosphorus_mg?: number | string | null;
  magnesium_mg?: number | string | null;
  vitamin_d_mcg?: number | string | null;
  calcium_mg?: number | string | null;
  iron_mg?: number | string | null;
  omega3_g?: number | string | null;
  suitable_type1?: boolean;
  suitable_type2?: boolean;
  suitable_gestational?: boolean;
  suitable_neuropathy?: boolean;
  suitable_cardiovascular?: boolean;
  suitable_stroke?: boolean;
  suitability_notes?: string;
  portion_advice?: string;
  contraindications?: string;
  meal_type?: string;
  difficulty?: string;
  cost_level?: string;
  ingredients?: string;
  instructions?: string;
};

export type AdminMealTemplateCreatePayload = AdminMealTemplateUpdatePayload & {
  suitable_type1: boolean;
  suitable_type2: boolean;
  suitable_gestational: boolean;
  suitable_neuropathy: boolean;
  suitable_cardiovascular: boolean;
  suitable_stroke: boolean;
};

export const getAdminMealTemplates = async (params: AdminMealTemplateQuery) => {
  return fetcher<NutritionMealTemplatePageResponseRaw>({
    url: "/nutrition/meal-templates",
    method: "GET",
    params,
  });
};

export const createAdminMealTemplate = async (data: AdminMealTemplateCreatePayload) => {
  return fetcher<{ message: string; id: number; name: string }>({
    url: "/nutrition/meal-templates",
    method: "POST",
    data,
    unwrapData: true,
  });
};

export const updateAdminMealTemplate = async (id: number, data: AdminMealTemplateUpdatePayload) => {
  return fetcher<{ message: string; id: number; name: string }>({
    url: `/nutrition/meal-templates/${id}`,
    method: "PUT",
    data,
    unwrapData: true,
  });
};

export const deleteAdminMealTemplate = async (id: number) => {
  return fetcher<{ message: string; id: number }>({
    url: `/nutrition/meal-templates/${id}`,
    method: "DELETE",
    unwrapData: true,
  });
};
