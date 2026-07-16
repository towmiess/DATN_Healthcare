import React, { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ChefHat,
  CircleFadingPlus,
  Clock3,
  Flame,
  Leaf,
  RefreshCw,
  Sparkles,
  UtensilsCrossed,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { getMealRecommendations } from "@/services/nutritionservices/recommendations";
import { MealRecommendationResponseRaw, NutritionMealTemplateResponseRaw } from "@/types/NutritionType";
import { getAccessToken } from "@/utils/auth";
import "./MealRecommendations.scss";

type MealTypeFilter = "all" | "breakfast" | "lunch" | "dinner" | "snack";

type MealViewModel = {
  id: number;
  name: string;
  category: string;
  categoryLabel: string;
  mealTypeLabel: string;
  cuisine: string;
  keywords: string;
  description: string;
  prepTime: string;
  cookTime: string;
  totalTime: string;
  servings: string;
  servingSize: string;
  glycemicIndex: string;
  glycemicLoad: string;
  calories: number;
  totalFatG: string;
  saturatedFatG: string;
  transFatG: string;
  cholesterolMg: string;
  sodiumMg: string;
  totalCarbohydrateG: string;
  dietaryFiberG: string;
  sugarsG: string;
  addedSugarsG: string;
  proteinG: string;
  potassiumMg: string;
  phosphorusMg: string;
  magnesiumMg: string;
  vitaminDMcg: string;
  calciumMg: string;
  ironMg: string;
  omega3G: string;
  suitabilityNotes: string;
  portionAdvice: string;
  contraindications: string;
  mealType: MealTypeFilter;
  difficulty: string;
  costLevel: string;
  ingredients: string;
  instructions: string;
};

const mealTypeLabels: Record<MealTypeFilter, string> = {
  all: "Tổng quan",
  breakfast: "Sáng",
  lunch: "Trưa",
  dinner: "Tối",
  snack: "Snack",
};

const safeText = (value?: string | number | null, fallback = "Chưa cập nhật") => {
  if (value === undefined || value === null) return fallback;
  const text = String(value).trim();
  return text.length > 0 ? text : fallback;
};

const capitalizeFirstLetter = (value?: string | number | null, fallback = "Chưa cập nhật") => {
  const text = safeText(value, fallback);
  if (!text || text === fallback) return text;
  return text.charAt(0).toUpperCase() + text.slice(1);
};

const formatCategory = (value?: string | number | null) => {
  const text = safeText(value, "ChÆ°a cáº­p nháº­t");
  return text
    .replace(/^\[\s*['"]?/, "")
    .replace(/['"]?\s*\]$/, "")
    .replace(/["']/g, "")
    .trim();
};

const toNumericString = (value?: string | number | null) => {
  if (value === undefined || value === null || value === "") return "0";
  const numberValue = Number(value);
  if (Number.isNaN(numberValue)) return String(value);
  return Number.isInteger(numberValue) ? String(numberValue) : numberValue.toFixed(1);
};

const toMealType = (value?: string | null): MealTypeFilter => {
  const normalized = String(value ?? "").toLowerCase().trim();
  if (normalized === "breakfast" || normalized === "lunch" || normalized === "dinner" || normalized === "snack") {
    return normalized;
  }
  return "snack";
};

const mapMeal = (meal: NutritionMealTemplateResponseRaw): MealViewModel => ({
  id: meal.id,
  name: capitalizeFirstLetter(meal.name),
  category: formatCategory(meal.category),
  categoryLabel: formatCategory(meal.category),
  mealTypeLabel: formatCategory(meal.meal_type),
  cuisine: safeText(meal.cuisine, "Ẩm thực Việt"),
  keywords: safeText(meal.keywords, "Dinh dưỡng cân bằng"),
  description: capitalizeFirstLetter(meal.description, "Món ăn được tối ưu theo hồ sơ dinh dưỡng hiện tại."),
  prepTime: safeText(meal.prep_time, "10 phút"),
  cookTime: safeText(meal.cook_time, "15 phút"),
  totalTime: safeText(meal.total_time, "25 phút"),
  servings: safeText(meal.servings, "1"),
  servingSize: safeText(meal.serving_size, "1 khẩu phần"),
  glycemicIndex: safeText(meal.glycemic_index, "Chưa rõ"),
  glycemicLoad: toNumericString(meal.glycemic_load),
  calories: meal.calories ?? 0,
  totalFatG: toNumericString(meal.total_fat_g),
  saturatedFatG: toNumericString(meal.saturated_fat_g),
  transFatG: toNumericString(meal.trans_fat_g),
  cholesterolMg: toNumericString(meal.cholesterol_mg),
  sodiumMg: toNumericString(meal.sodium_mg),
  totalCarbohydrateG: toNumericString(meal.total_carbohydrate_g),
  dietaryFiberG: toNumericString(meal.dietary_fiber_g),
  sugarsG: toNumericString(meal.sugars_g),
  addedSugarsG: toNumericString(meal.added_sugars_g),
  proteinG: toNumericString(meal.protein_g),
  potassiumMg: toNumericString(meal.potassium_mg),
  phosphorusMg: toNumericString(meal.phosphorus_mg),
  magnesiumMg: toNumericString(meal.magnesium_mg),
  vitaminDMcg: toNumericString(meal.vitamin_d_mcg),
  calciumMg: toNumericString(meal.calcium_mg),
  ironMg: toNumericString(meal.iron_mg),
  omega3G: toNumericString(meal.omega3_g),
  suitabilityNotes: safeText(meal.suitability_notes, "Món này phù hợp cho đa số người dùng có cùng nhóm dinh dưỡng."),
  portionAdvice: safeText(meal.portion_advice, "Ăn đúng khẩu phần được gợi ý."),
  contraindications: safeText(meal.contraindications, "Không có ghi chú đặc biệt."),
  mealType: toMealType(meal.meal_type),
  difficulty: safeText(meal.difficulty, "Dễ"),
  costLevel: safeText(meal.cost_level, "Trung bình"),
  ingredients: safeText(meal.ingredients, "Chưa có danh sách nguyên liệu."),
  instructions: safeText(meal.instructions, "Chưa có hướng dẫn chế biến."),
});

const MealRecommendations: React.FC = () => {
  const [data, setData] = useState<MealRecommendationResponseRaw | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const activeFilter: MealTypeFilter = "all";
  const [selectedMealId, setSelectedMealId] = useState<number | null>(null);

  const loadRecommendations = async () => {
    setError(null);
    setSubmitting(true);

    if (!getAccessToken()) {
      setError("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
      toast.error("Phiên đăng nhập đã hết hạn. Vui lòng đăng nhập lại.");
      setLoading(false);
      setSubmitting(false);
      return;
    }

    try {
      const response = await getMealRecommendations();
      setData(response);
    } catch {
      setError("Không tải được gợi ý món ăn. Vui lòng thử lại.");
      toast.error("Không tải được gợi ý món ăn.");
    } finally {
      setLoading(false);
      setSubmitting(false);
    }
  };

  useEffect(() => {
    void loadRecommendations();
  }, []);

  const meals = useMemo(() => (data?.meals ?? []).map(mapMeal), [data]);

  const filteredMeals = useMemo(() => {
    if (activeFilter === "all") return meals;
    return meals.filter((meal) => meal.mealType === activeFilter);
  }, [activeFilter, meals]);

  const selectedMeal = useMemo(
    () => meals.find((meal) => meal.id === selectedMealId) ?? null,
    [meals, selectedMealId]
  );

  const totalCalories = useMemo(
    () => meals.reduce((sum, meal) => sum + (meal.calories || 0), 0),
    [meals]
  );

  const avgCalories = meals.length ? Math.round(totalCalories / meals.length) : 0;
  const userTypes = data?.user_types ?? [];
  const summaryChips = [
    `User #${data?.user_id ?? "?"}`,
    userTypes.length > 0 ? userTypes.join(" · ") : "Chưa có nhóm người dùng",
    `${data?.count ?? meals.length} món gợi ý`,
  ];

  return (
    <section className="nutrition-page">
      <div className="nutrition-page__glow nutrition-page__glow--left" />
      <div className="nutrition-page__glow nutrition-page__glow--right" />

      <header className="nutrition-hero">
        <div className="nutrition-hero__copy">
          <p className="nutrition-hero__eyebrow">
            <Sparkles size={16} />
            Nutrition suggestions
          </p>
          <h1 className="nutrition-hero__title">Gợi ý món ăn cho hồ sơ của bạn</h1>
          <p className="nutrition-hero__description">
            Giao diện này lấy dữ liệu thật từ <strong>nutrition-service</strong>, hiển thị các món phù hợp
            theo nhóm người dùng, khẩu phần, năng lượng và hướng dẫn chế biến.
          </p>

          <div className="nutrition-hero__chips">
            {summaryChips.map((chip) => (
              <span key={chip} className="nutrition-chip">
                {chip}
              </span>
            ))}
          </div>
        </div>

        <div className="nutrition-hero__panel">
          <div className="nutrition-stat">
            <span className="nutrition-stat__label">Tổng kcal</span>
            <strong className="nutrition-stat__value">{totalCalories}</strong>
          </div>
          <div className="nutrition-stat">
            <span className="nutrition-stat__label">Trung bình / món</span>
            <strong className="nutrition-stat__value">{avgCalories}</strong>
          </div>
          <div className="nutrition-stat">
            <span className="nutrition-stat__label">Bữa đang chọn</span>
            <strong className="nutrition-stat__value">{mealTypeLabels[activeFilter]}</strong>
          </div>

          <button
            type="button"
            className="nutrition-refresh"
            onClick={loadRecommendations}
            disabled={submitting}
          >
            <RefreshCw size={16} className={submitting ? "spin" : ""} />
            {submitting ? "Đang làm mới..." : "Làm mới gợi ý"}
          </button>
        </div>
      </header>

      {error && (
        <div className="nutrition-alert">
          <AlertTriangle size={18} />
          <span>{error}</span>
          <button type="button" className="nutrition-alert__action" onClick={loadRecommendations}>
            Thử lại
          </button>
        </div>
      )}

      <section className="nutrition-grid" aria-busy={loading}>
        {loading ? (
          Array.from({ length: 6 }).map((_, index) => (
            <article key={index} className="nutrition-card nutrition-card--skeleton">
              <div className="skeleton skeleton--line skeleton--short" />
              <div className="skeleton skeleton--line" />
              <div className="skeleton skeleton--line skeleton--wide" />
              <div className="skeleton skeleton--box" />
            </article>
          ))
        ) : filteredMeals.length > 0 ? (
          filteredMeals.map((meal) => (
            <article key={meal.id} className="nutrition-card">
              <div className="nutrition-card__top">
                <div className={`nutrition-badge nutrition-badge--${meal.mealType}`}>
                  {meal.mealTypeLabel}
                </div>
                <div className="nutrition-card__kcal">
                  <Flame size={14} />
                  <span>{meal.calories} kcal</span>
                </div>
              </div>

              <h2 className="nutrition-card__title">{meal.name}</h2>
              <p className="nutrition-card__description">{meal.description}</p>

              <div className="nutrition-card__category">
                <span>Danh mục</span>
                <strong>{meal.categoryLabel}</strong>
              </div>

              <div className="nutrition-card__meta">
                <span>
                  <Clock3 size={14} />
                  {meal.totalTime}
                </span>
                <span>
                  <ChefHat size={14} />
                  {meal.difficulty}
                </span>
                <span>
                  <CircleFadingPlus size={14} />
                  {meal.costLevel}
                </span>
              </div>

              <div className="nutrition-macros">
                <div className="macro macro--protein">
                  <span>Protein</span>
                  <strong>{meal.proteinG}g</strong>
                </div>
                <div className="macro macro--carbs">
                  <span>Carbs</span>
                  <strong>{meal.totalCarbohydrateG}g</strong>
                </div>
                <div className="macro macro--fat">
                  <span>Fat</span>
                  <strong>{meal.totalFatG}g</strong>
                </div>
              </div>

              <button type="button" className="nutrition-card__action" onClick={() => setSelectedMealId(meal.id)}>
                <UtensilsCrossed size={16} />
                Xem chi tiết
              </button>
            </article>
          ))
        ) : (
          <div className="nutrition-empty">
            <Leaf size={24} />
            <h3>Không có món phù hợp ở bộ lọc này</h3>
            <p>Hãy chọn nhóm bữa khác hoặc làm mới gợi ý để tải lại dữ liệu.</p>
          </div>
        )}
      </section>

      {selectedMeal && (
        <div className="nutrition-modal" role="dialog" aria-modal="true" onClick={() => setSelectedMealId(null)}>
          <div className="nutrition-modal__content" onClick={(event) => event.stopPropagation()}>
            <div className="nutrition-modal__header">
              <div>
                <div className={`nutrition-badge nutrition-badge--${selectedMeal.mealType}`}>
                  {selectedMeal.mealTypeLabel}
                </div>
                <h2>{selectedMeal.name}</h2>
                <p>{selectedMeal.description}</p>
              </div>
              <button type="button" className="nutrition-modal__close" onClick={() => setSelectedMealId(null)}>
                <X size={22} />
              </button>
            </div>

            <div className="nutrition-modal__grid">
              <div className="nutrition-modal__stat">
                <span>Kcal</span>
                <strong>{selectedMeal.calories}</strong>
              </div>
              <div className="nutrition-modal__stat">
                <span>Protein</span>
                <strong>{selectedMeal.proteinG}g</strong>
              </div>
              <div className="nutrition-modal__stat">
                <span>Carbs</span>
                <strong>{selectedMeal.totalCarbohydrateG}g</strong>
              </div>
              <div className="nutrition-modal__stat">
                <span>Fat</span>
                <strong>{selectedMeal.totalFatG}g</strong>
              </div>
              <div className="nutrition-modal__stat">
                <span>GI</span>
                <strong>{selectedMeal.glycemicIndex}</strong>
              </div>
              <div className="nutrition-modal__stat">
                <span>GL</span>
                <strong>{selectedMeal.glycemicLoad}</strong>
              </div>
            </div>

            <div className="nutrition-modal__sections">
              <section className="nutrition-modal__section">
                <h3>Thông tin chung</h3>
                <p>
                  <strong>Loại bữa:</strong> {selectedMeal.mealTypeLabel}<br />
                  <strong>Ẩm thực:</strong> {selectedMeal.cuisine}<br />
                  <strong>Danh mục:</strong> {selectedMeal.category}<br />
                  <strong>Khẩu phần:</strong> {selectedMeal.servings} · {selectedMeal.servingSize}<br />
                  <strong>Thời gian:</strong> {selectedMeal.prepTime} chuẩn bị, {selectedMeal.cookTime} nấu
                </p>
              </section>

              <section className="nutrition-modal__section">
                <h3>Nguyên liệu</h3>
                <p>{selectedMeal.ingredients}</p>
              </section>

              <section className="nutrition-modal__section">
                <h3>Hướng dẫn chế biến</h3>
                <p>{selectedMeal.instructions}</p>
              </section>

              <section className="nutrition-modal__section">
                <h3>Lưu ý dinh dưỡng</h3>
                <p>
                  <strong>Phù hợp:</strong> {selectedMeal.suitabilityNotes}<br />
                  <strong>Khẩu phần khuyên dùng:</strong> {selectedMeal.portionAdvice}<br />
                  <strong>Chống chỉ định:</strong> {selectedMeal.contraindications}
                </p>
              </section>

              <section className="nutrition-modal__section">
                <h3>Vi chất nổi bật</h3>
                <p>
                  <strong>Chất xơ:</strong> {selectedMeal.dietaryFiberG}g ·{" "}
                  <strong>Muối:</strong> {selectedMeal.sodiumMg}mg ·{" "}
                  <strong>Canxi:</strong> {selectedMeal.calciumMg}mg ·{" "}
                  <strong>Sắt:</strong> {selectedMeal.ironMg}mg
                </p>
              </section>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};

export default MealRecommendations;
