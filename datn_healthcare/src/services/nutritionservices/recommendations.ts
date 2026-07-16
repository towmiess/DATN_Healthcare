import { fetcher } from "@/api/Fetcher";
import { MealRecommendationResponseRaw } from "@/types/NutritionType";

export const getMealRecommendations = () => {
  return fetcher<MealRecommendationResponseRaw>({
    url: "/nutrition/meal-templates/recommendations",
    method: "GET",
  });
};
