export interface IngredientResponseRaw {
  id: number;
  foodName?: string | null;
  normalizedName?: string | null;
  calories?: number | string | null;
  protein?: number | string | null;
  fat?: number | string | null;
  carbs?: number | string | null;
}

export interface IngredientPageResponseRaw {
  items?: IngredientResponseRaw[] | null;
  page?: number | null;
  size?: number | null;
  totalPages?: number | null;
  totalItems?: number | null;
  hasNext?: boolean | null;
  hasPrevious?: boolean | null;
}
