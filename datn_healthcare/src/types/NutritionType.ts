export interface NutritionMealTemplateResponseRaw {
  id: number;
  name: string;
  category?: string | null;
  cuisine?: string | null;
  keywords?: string | null;
  description?: string | null;
  prep_time?: string | null;
  cook_time?: string | null;
  total_time?: string | null;
  servings?: number | null;
  serving_size?: string | null;
  glycemic_index?: string | null;
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
  suitable_type1?: boolean | null;
  suitable_type2?: boolean | null;
  suitable_gestational?: boolean | null;
  suitable_neuropathy?: boolean | null;
  suitable_cardiovascular?: boolean | null;
  suitable_stroke?: boolean | null;
  suitability_notes?: string | null;
  portion_advice?: string | null;
  contraindications?: string | null;
  meal_type?: string | null;
  difficulty?: string | null;
  cost_level?: string | null;
  ingredients?: string | null;
  instructions?: string | null;
}

export interface MealRecommendationResponseRaw {
  user_id?: number | null;
  user_types?: string[] | null;
  count?: number | null;
  meals?: NutritionMealTemplateResponseRaw[] | null;
}

export interface NutritionMealTemplatePageResponseRaw {
  items?: NutritionMealTemplateResponseRaw[] | null;
  page?: number | null;
  size?: number | null;
  totalPages?: number | null;
  totalItems?: number | null;
  hasNext?: boolean | null;
  hasPrevious?: boolean | null;
}
