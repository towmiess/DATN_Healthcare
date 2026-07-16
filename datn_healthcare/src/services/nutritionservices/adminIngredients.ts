import { fetcher } from "@/api/Fetcher";
import { IngredientPageResponseRaw, IngredientResponseRaw } from "@/types/IngredientType";

type AdminIngredientQuery = {
  page?: number;
  size?: number;
  keyword?: string;
};

export type AdminIngredientCreatePayload = {
  foodName: string;
  normalizedName?: string;
  calories?: number | string | null;
  protein?: number | string | null;
  fat?: number | string | null;
  carbs?: number | string | null;
};

export type AdminIngredientUpdatePayload = Partial<AdminIngredientCreatePayload>;

export const getAdminIngredients = async (params: AdminIngredientQuery) => {
  return fetcher<IngredientPageResponseRaw>({
    url: "/nutrition/ingredients",
    method: "GET",
    params,
  });
};

export const createAdminIngredient = async (data: AdminIngredientCreatePayload) => {
  return fetcher<{ message: string; ingredient: IngredientResponseRaw }>({
    url: "/nutrition/ingredients",
    method: "POST",
    data,
    unwrapData: true,
  });
};

export const updateAdminIngredient = async (id: number, data: AdminIngredientUpdatePayload) => {
  return fetcher<{ message: string; ingredient: IngredientResponseRaw }>({
    url: `/nutrition/ingredients/${id}`,
    method: "PUT",
    data,
    unwrapData: true,
  });
};

export const deleteAdminIngredient = async (id: number) => {
  return fetcher<{ message: string; id: number }>({
    url: `/nutrition/ingredients/${id}`,
    method: "DELETE",
    unwrapData: true,
  });
};
