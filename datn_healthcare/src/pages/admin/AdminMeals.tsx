import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  Edit3,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Flame,
  PlusCircle,
  Search,
  Soup,
  Trash2,
  UtensilsCrossed,
} from "lucide-react";
import Swal from "sweetalert2";
import { toast } from "sonner";
import { createAdminMealTemplate, getAdminMealTemplates } from "@/services/nutritionservices/adminMeals";
import {
  deleteAdminMealTemplate,
  updateAdminMealTemplate,
  type AdminMealTemplateUpdatePayload,
} from "@/services/nutritionservices/adminMeals";
import { NutritionMealTemplatePageResponseRaw, NutritionMealTemplateResponseRaw } from "@/types/NutritionType";
import { getApiErrorMessage } from "@/utils/apiErrorMessage";
import "./AdminMeals.scss";

type MealTypeFilter = "ALL" | "bữa sáng" | "bữa trưa" | "bữa tối" | "ăn nhẹ";

type MealRow = {
  id: number;
  name: string;
  category: string;
  mealType: string;
  difficulty: string;
  totalTime: string;
  calories: number;
  protein: string;
  description: string;
};

type CreateMealFormState = {
  name: string;
  category: string;
  cuisine: string;
  keywords: string;
  description: string;
  prep_time: string;
  cook_time: string;
  total_time: string;
  servings: string;
  serving_size: string;
  glycemic_index: string;
  glycemic_load: string;
  calories: string;
  total_fat_g: string;
  saturated_fat_g: string;
  trans_fat_g: string;
  cholesterol_mg: string;
  sodium_mg: string;
  total_carbohydrate_g: string;
  dietary_fiber_g: string;
  sugars_g: string;
  added_sugars_g: string;
  protein_g: string;
  potassium_mg: string;
  phosphorus_mg: string;
  magnesium_mg: string;
  vitamin_d_mcg: string;
  calcium_mg: string;
  iron_mg: string;
  omega3_g: string;
  suitable_type1: boolean;
  suitable_type2: boolean;
  suitable_gestational: boolean;
  suitable_neuropathy: boolean;
  suitable_cardiovascular: boolean;
  suitable_stroke: boolean;
  suitability_notes: string;
  portion_advice: string;
  contraindications: string;
  meal_type: string;
  difficulty: string;
  cost_level: string;
  ingredients: string;
  instructions: string;
};

const createMealToggleFields = [
  ["suitable_type1", "Phù hợp type 1"],
  ["suitable_type2", "Phù hợp type 2"],
  ["suitable_gestational", "Phù hợp thai kỳ"],
  ["suitable_neuropathy", "Phù hợp neuropathy"],
  ["suitable_cardiovascular", "Phù hợp tim mạch"],
  ["suitable_stroke", "Phù hợp đột quỵ"],
] as const;

const PAGE_SIZE = 8;

const mealTypeOptions: Array<{ value: MealTypeFilter; label: string }> = [
  { value: "ALL", label: "Tất cả" },
  { value: "bữa sáng", label: "Bữa sáng" },
  { value: "bữa trưa", label: "Bữa trưa" },
  { value: "bữa tối", label: "Bữa tối" },
  { value: "ăn nhẹ", label: "Ăn nhẹ" },
];

const safeText = (value: string | null | undefined, fallback: string) => {
  const trimmed = value?.trim();
  return trimmed ? trimmed : fallback;
};

const cleanDisplayText = (value: string | null | undefined, fallback: string) => {
  const raw = value?.trim();
  if (!raw) return fallback;

  const cleaned = raw
    .replace(/^[\[\(]+/, "")
    .replace(/[\]\)]+$/, "")
    .replace(/['"]/g, "")
    .replace(/\s+/g, " ")
    .trim();

  return cleaned || fallback;
};

const toNumericString = (value: number | string | null | undefined) => {
  if (value === null || value === undefined || value === "") {
    return "0";
  }
  return String(value);
};

const emptyCreateMealForm = (): CreateMealFormState => ({
  name: "",
  category: "",
  cuisine: "",
  keywords: "",
  description: "",
  prep_time: "",
  cook_time: "",
  total_time: "",
  servings: "",
  serving_size: "",
  glycemic_index: "",
  glycemic_load: "",
  calories: "",
  total_fat_g: "",
  saturated_fat_g: "",
  trans_fat_g: "",
  cholesterol_mg: "",
  sodium_mg: "",
  total_carbohydrate_g: "",
  dietary_fiber_g: "",
  sugars_g: "",
  added_sugars_g: "",
  protein_g: "",
  potassium_mg: "",
  phosphorus_mg: "",
  magnesium_mg: "",
  vitamin_d_mcg: "",
  calcium_mg: "",
  iron_mg: "",
  omega3_g: "",
  suitable_type1: false,
  suitable_type2: false,
  suitable_gestational: false,
  suitable_neuropathy: false,
  suitable_cardiovascular: false,
  suitable_stroke: false,
  suitability_notes: "",
  portion_advice: "",
  contraindications: "",
  meal_type: "",
  difficulty: "",
  cost_level: "",
  ingredients: "",
  instructions: "",
});

const fillMealFormFromResponse = (meal: NutritionMealTemplateResponseRaw): CreateMealFormState => ({
  name: meal.name ?? "",
  category: meal.category ?? "",
  cuisine: meal.cuisine ?? "",
  keywords: meal.keywords ?? "",
  description: meal.description ?? "",
  prep_time: meal.prep_time ?? "",
  cook_time: meal.cook_time ?? "",
  total_time: meal.total_time ?? "",
  servings: meal.servings == null ? "" : String(meal.servings),
  serving_size: meal.serving_size ?? "",
  glycemic_index: meal.glycemic_index ?? "",
  glycemic_load: meal.glycemic_load == null ? "" : String(meal.glycemic_load),
  calories: meal.calories == null ? "" : String(meal.calories),
  total_fat_g: meal.total_fat_g == null ? "" : String(meal.total_fat_g),
  saturated_fat_g: meal.saturated_fat_g == null ? "" : String(meal.saturated_fat_g),
  trans_fat_g: meal.trans_fat_g == null ? "" : String(meal.trans_fat_g),
  cholesterol_mg: meal.cholesterol_mg == null ? "" : String(meal.cholesterol_mg),
  sodium_mg: meal.sodium_mg == null ? "" : String(meal.sodium_mg),
  total_carbohydrate_g: meal.total_carbohydrate_g == null ? "" : String(meal.total_carbohydrate_g),
  dietary_fiber_g: meal.dietary_fiber_g == null ? "" : String(meal.dietary_fiber_g),
  sugars_g: meal.sugars_g == null ? "" : String(meal.sugars_g),
  added_sugars_g: meal.added_sugars_g == null ? "" : String(meal.added_sugars_g),
  protein_g: meal.protein_g == null ? "" : String(meal.protein_g),
  potassium_mg: meal.potassium_mg == null ? "" : String(meal.potassium_mg),
  phosphorus_mg: meal.phosphorus_mg == null ? "" : String(meal.phosphorus_mg),
  magnesium_mg: meal.magnesium_mg == null ? "" : String(meal.magnesium_mg),
  vitamin_d_mcg: meal.vitamin_d_mcg == null ? "" : String(meal.vitamin_d_mcg),
  calcium_mg: meal.calcium_mg == null ? "" : String(meal.calcium_mg),
  iron_mg: meal.iron_mg == null ? "" : String(meal.iron_mg),
  omega3_g: meal.omega3_g == null ? "" : String(meal.omega3_g),
  suitable_type1: Boolean(meal.suitable_type1),
  suitable_type2: Boolean(meal.suitable_type2),
  suitable_gestational: Boolean(meal.suitable_gestational),
  suitable_neuropathy: Boolean(meal.suitable_neuropathy),
  suitable_cardiovascular: Boolean(meal.suitable_cardiovascular),
  suitable_stroke: Boolean(meal.suitable_stroke),
  suitability_notes: meal.suitability_notes ?? "",
  portion_advice: meal.portion_advice ?? "",
  contraindications: meal.contraindications ?? "",
  meal_type: meal.meal_type ?? "",
  difficulty: meal.difficulty ?? "",
  cost_level: meal.cost_level ?? "",
  ingredients: meal.ingredients ?? "",
  instructions: meal.instructions ?? "",
});

const mapMealRow = (meal: NutritionMealTemplateResponseRaw): MealRow => ({
  id: meal.id,
  name: safeText(meal.name, "Chưa có tên món"),
  category: cleanDisplayText(meal.category, "Chưa phân loại"),
  mealType: cleanDisplayText(meal.meal_type, "Khác"),
  difficulty: safeText(meal.difficulty, "Dễ"),
  totalTime: safeText(meal.total_time, "Chưa rõ"),
  calories: meal.calories ?? 0,
  protein: toNumericString(meal.protein_g),
  description: safeText(meal.description, "Chưa có mô tả."),
});

const formatMealTypeBadge = (value: string) => {
  const normalized = value.toLowerCase();
  if (normalized.includes("ăn nhẹ")) return "snack";
  if (normalized.includes("bữa sáng")) return "breakfast";
  if (normalized.includes("bữa trưa") || normalized.includes("bữa tối")) return "main";
  return "other";
};

const AdminMeals: React.FC = () => {
  const [response, setResponse] = useState<NutritionMealTemplatePageResponseRaw | null>(null);
  const [keyword, setKeyword] = useState("");
  const [page, setPage] = useState(0);
  const [mealType, setMealType] = useState<MealTypeFilter>("ALL");
  const [loading, setLoading] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateMealFormState>(() => emptyCreateMealForm());
  const [isCreating, setIsCreating] = useState(false);
  const [editingMeal, setEditingMeal] = useState<NutritionMealTemplateResponseRaw | null>(null);
  const [editForm, setEditForm] = useState<CreateMealFormState>(() => emptyCreateMealForm());
  const [isSaving, setIsSaving] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  const loadMeals = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getAdminMealTemplates({
        page,
        size: PAGE_SIZE,
        keyword: keyword.trim() || undefined,
        mealType: mealType === "ALL" ? undefined : mealType,
      });
      setResponse(result);
    } catch (error) {
      console.error("Load admin meals error:", error);
      toast.error(
        getApiErrorMessage(error, "Không tải được danh sách món ăn.", {
          forbiddenMessage: "Bạn không có quyền truy cập danh sách món ăn.",
          unauthorizedMessage: "Phiên đăng nhập không hợp lệ. Vui lòng đăng nhập lại.",
        })
      );
      setResponse({
        items: [],
        page,
        size: PAGE_SIZE,
        totalPages: 0,
        totalItems: 0,
        hasNext: false,
        hasPrevious: false,
      });
    } finally {
      setLoading(false);
    }
  }, [keyword, mealType, page]);

  useEffect(() => {
    loadMeals();
  }, [loadMeals]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) {
        setIsMenuOpen(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsMenuOpen(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  useEffect(() => {
    const modalOpen = isCreateOpen || editingMeal !== null;
    if (!modalOpen) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isCreateOpen, editingMeal]);

  const rawMeals = response?.items ?? [];
  const meals = useMemo(() => rawMeals.map(mapMealRow), [rawMeals]);
  const totalItems = response?.totalItems ?? 0;
  const totalPages = response?.totalPages ?? 0;
  const currentPage = response?.page ?? page;
  const hasNext = Boolean(response?.hasNext);
  const hasPrevious = Boolean(response?.hasPrevious);
  const avgCalories = meals.length ? Math.round(meals.reduce((sum, meal) => sum + meal.calories, 0) / meals.length) : 0;
  const breakfastCount = meals.filter((meal) => meal.mealType.toLowerCase().includes("bữa sáng")).length;
  const snackCount = meals.filter((meal) => meal.mealType.toLowerCase().includes("ăn nhẹ")).length;

  const selectedMealTypeLabel = useMemo(
    () => mealTypeOptions.find((option) => option.value === mealType)?.label ?? mealTypeOptions[0].label,
    [mealType]
  );

  const paginationItems = useMemo(() => {
    if (totalPages <= 1) return [];
    const start = Math.max(0, currentPage - 1);
    const end = Math.min(totalPages - 1, start + 2);
    const items: number[] = [];
    for (let value = start; value <= end; value += 1) {
      items.push(value);
    }
    return items;
  }, [currentPage, totalPages]);

  const openCreateModal = () => {
    setCreateForm(emptyCreateMealForm());
    setIsCreateOpen(true);
  };

  const closeCreateModal = () => {
    if (isCreating) return;
    setIsCreateOpen(false);
  };

  const toOptionalNumber = (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) return null;
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
  };

  const handleCreateSubmit = async () => {
    const mealName = createForm.name.trim();
    if (!mealName) {
      toast.error("Vui lòng nhập tên món ăn.");
      return;
    }

    setIsCreating(true);
    try {
      await createAdminMealTemplate({
        name: mealName,
        category: createForm.category.trim() || undefined,
        cuisine: createForm.cuisine.trim() || undefined,
        keywords: createForm.keywords.trim() || undefined,
        description: createForm.description.trim() || undefined,
        prep_time: createForm.prep_time.trim() || undefined,
        cook_time: createForm.cook_time.trim() || undefined,
        total_time: createForm.total_time.trim() || undefined,
        servings: toOptionalNumber(createForm.servings),
        serving_size: createForm.serving_size.trim() || undefined,
        glycemic_index: createForm.glycemic_index.trim() || undefined,
        glycemic_load: toOptionalNumber(createForm.glycemic_load),
        calories: toOptionalNumber(createForm.calories),
        total_fat_g: toOptionalNumber(createForm.total_fat_g),
        saturated_fat_g: toOptionalNumber(createForm.saturated_fat_g),
        trans_fat_g: toOptionalNumber(createForm.trans_fat_g),
        cholesterol_mg: toOptionalNumber(createForm.cholesterol_mg),
        sodium_mg: toOptionalNumber(createForm.sodium_mg),
        total_carbohydrate_g: toOptionalNumber(createForm.total_carbohydrate_g),
        dietary_fiber_g: toOptionalNumber(createForm.dietary_fiber_g),
        sugars_g: toOptionalNumber(createForm.sugars_g),
        added_sugars_g: toOptionalNumber(createForm.added_sugars_g),
        protein_g: toOptionalNumber(createForm.protein_g),
        potassium_mg: toOptionalNumber(createForm.potassium_mg),
        phosphorus_mg: toOptionalNumber(createForm.phosphorus_mg),
        magnesium_mg: toOptionalNumber(createForm.magnesium_mg),
        vitamin_d_mcg: toOptionalNumber(createForm.vitamin_d_mcg),
        calcium_mg: toOptionalNumber(createForm.calcium_mg),
        iron_mg: toOptionalNumber(createForm.iron_mg),
        omega3_g: toOptionalNumber(createForm.omega3_g),
        suitable_type1: createForm.suitable_type1,
        suitable_type2: createForm.suitable_type2,
        suitable_gestational: createForm.suitable_gestational,
        suitable_neuropathy: createForm.suitable_neuropathy,
        suitable_cardiovascular: createForm.suitable_cardiovascular,
        suitable_stroke: createForm.suitable_stroke,
        suitability_notes: createForm.suitability_notes.trim() || undefined,
        portion_advice: createForm.portion_advice.trim() || undefined,
        contraindications: createForm.contraindications.trim() || undefined,
        meal_type: createForm.meal_type.trim() || undefined,
        difficulty: createForm.difficulty.trim() || undefined,
        cost_level: createForm.cost_level.trim() || undefined,
        ingredients: createForm.ingredients.trim() || undefined,
        instructions: createForm.instructions.trim() || undefined,
      });

      toast.success("Đã thêm món ăn mới.");
      setIsCreateOpen(false);
      setCreateForm(emptyCreateMealForm());
      await loadMeals();
    } catch (error) {
      console.error("Create meal error:", error);
      toast.error(
        getApiErrorMessage(error, "Không thể thêm món ăn.", {
          forbiddenMessage: "Bạn không có quyền thêm món ăn.",
          unauthorizedMessage: "Phiên đăng nhập không hợp lệ. Vui lòng đăng nhập lại.",
        })
      );
    } finally {
      setIsCreating(false);
    }
  };

  const openEditModal = (meal: NutritionMealTemplateResponseRaw) => {
    setEditingMeal(meal);
    setEditForm(fillMealFormFromResponse(meal));
  };

  const closeEditModal = () => {
    if (isSaving) return;
    setEditingMeal(null);
  };

  const handleEditSubmit = async () => {
    if (!editingMeal) return;

    const payload: AdminMealTemplateUpdatePayload = {
      name: editForm.name.trim(),
      category: editForm.category.trim() || undefined,
      cuisine: editForm.cuisine.trim() || undefined,
      keywords: editForm.keywords.trim() || undefined,
      description: editForm.description.trim() || undefined,
      prep_time: editForm.prep_time.trim() || undefined,
      cook_time: editForm.cook_time.trim() || undefined,
      total_time: editForm.total_time.trim() || undefined,
      servings: editForm.servings ? Number(editForm.servings) : null,
      serving_size: editForm.serving_size.trim() || undefined,
      glycemic_index: editForm.glycemic_index.trim() || undefined,
      glycemic_load: editForm.glycemic_load ? Number(editForm.glycemic_load) : null,
      calories: editForm.calories ? Number(editForm.calories) : null,
      total_fat_g: editForm.total_fat_g ? Number(editForm.total_fat_g) : null,
      saturated_fat_g: editForm.saturated_fat_g ? Number(editForm.saturated_fat_g) : null,
      trans_fat_g: editForm.trans_fat_g ? Number(editForm.trans_fat_g) : null,
      cholesterol_mg: editForm.cholesterol_mg ? Number(editForm.cholesterol_mg) : null,
      sodium_mg: editForm.sodium_mg ? Number(editForm.sodium_mg) : null,
      total_carbohydrate_g: editForm.total_carbohydrate_g ? Number(editForm.total_carbohydrate_g) : null,
      dietary_fiber_g: editForm.dietary_fiber_g ? Number(editForm.dietary_fiber_g) : null,
      sugars_g: editForm.sugars_g ? Number(editForm.sugars_g) : null,
      added_sugars_g: editForm.added_sugars_g ? Number(editForm.added_sugars_g) : null,
      protein_g: editForm.protein_g ? Number(editForm.protein_g) : null,
      potassium_mg: editForm.potassium_mg ? Number(editForm.potassium_mg) : null,
      phosphorus_mg: editForm.phosphorus_mg ? Number(editForm.phosphorus_mg) : null,
      magnesium_mg: editForm.magnesium_mg ? Number(editForm.magnesium_mg) : null,
      vitamin_d_mcg: editForm.vitamin_d_mcg ? Number(editForm.vitamin_d_mcg) : null,
      calcium_mg: editForm.calcium_mg ? Number(editForm.calcium_mg) : null,
      iron_mg: editForm.iron_mg ? Number(editForm.iron_mg) : null,
      omega3_g: editForm.omega3_g ? Number(editForm.omega3_g) : null,
      suitable_type1: editForm.suitable_type1,
      suitable_type2: editForm.suitable_type2,
      suitable_gestational: editForm.suitable_gestational,
      suitable_neuropathy: editForm.suitable_neuropathy,
      suitable_cardiovascular: editForm.suitable_cardiovascular,
      suitable_stroke: editForm.suitable_stroke,
      meal_type: editForm.meal_type.trim() || undefined,
      difficulty: editForm.difficulty.trim() || undefined,
      cost_level: editForm.cost_level.trim() || undefined,
      ingredients: editForm.ingredients.trim() || undefined,
      instructions: editForm.instructions.trim() || undefined,
    };

    setIsSaving(true);
    try {
      await updateAdminMealTemplate(editingMeal.id, payload);
      toast.success("Đã cập nhật món ăn.");
      setEditingMeal(null);
      await loadMeals();
    } catch (error) {
      console.error("Update meal error:", error);
      toast.error(
        getApiErrorMessage(error, "Không thể cập nhật món ăn.", {
          forbiddenMessage: "Bạn không có quyền sửa món ăn.",
          unauthorizedMessage: "Phiên đăng nhập không hợp lệ. Vui lòng đăng nhập lại.",
        })
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteMeal = async (meal: MealRow) => {
    const confirmResult = await Swal.fire({
      title: "Xóa món ăn này?",
      text: `${meal.name} sẽ bị xóa khỏi danh sách quản lý.`,
      icon: "warning",
      showCancelButton: true,
      confirmButtonText: "Xóa",
      cancelButtonText: "Hủy",
      reverseButtons: true,
      confirmButtonColor: "#ef4444",
      cancelButtonColor: "#64748b",
    });

    if (!confirmResult.isConfirmed) {
      return;
    }

    try {
      await deleteAdminMealTemplate(meal.id);
      toast.success("Đã xóa món ăn.");
      await loadMeals();
    } catch (error) {
      console.error("Delete meal error:", error);
      toast.error(
        getApiErrorMessage(error, "Không thể xóa món ăn.", {
          forbiddenMessage: "Bạn không có quyền xóa món ăn.",
          unauthorizedMessage: "Phiên đăng nhập không hợp lệ. Vui lòng đăng nhập lại.",
        })
      );
    }
  };

  return (
    <section className="admin-page admin-meals">
      <div className="admin-page__head">
        <div>
          <h1 className="admin-page__title">Quản lý món ăn</h1>
        </div>

        <div className="admin-page__head-actions">
          <label className="admin-meals__search admin-meals__search--compact">
            <Search size={17} />
            <input
              value={keyword}
              onChange={(event) => {
                setKeyword(event.target.value);
                setPage(0);
              }}
              placeholder="Tìm theo tên món, danh mục hoặc ẩm thực..."
            />
          </label>

          <div className="admin-meals__filter-wrap" ref={menuRef}>
            <button
              type="button"
              className={`admin-meals__filter ${isMenuOpen ? "admin-meals__filter--open" : ""}`}
              onClick={() => setIsMenuOpen((prev) => !prev)}
            >
              <span>{selectedMealTypeLabel}</span>
              <ChevronDown size={16} />
            </button>

            {isMenuOpen ? (
              <div className="admin-meals__filter-menu">
                {mealTypeOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    className={`admin-meals__filter-option ${mealType === option.value ? "admin-meals__filter-option--active" : ""}`}
                    onClick={() => {
                      setMealType(option.value);
                      setPage(0);
                      setIsMenuOpen(false);
                    }}
                  >
                    <span>{option.label}</span>
                    {mealType === option.value ? <span className="admin-meals__filter-dot" /> : null}
                  </button>
                ))}
              </div>
            ) : null}
          </div>

          <button type="button" className="admin-meals__refresh" onClick={openCreateModal}>
            <PlusCircle size={16} />
            Thêm mới
          </button>
        </div>
      </div>

      <div className="admin-meals__summary">
        <article className="admin-meals__summary-card admin-meals__summary-card--blue">
          <span><UtensilsCrossed size={20} /></span>
          <div>
            <p>Tổng món ăn</p>
            <strong>{totalItems}</strong>
          </div>
        </article>
        <article className="admin-meals__summary-card admin-meals__summary-card--amber">
          <span><Flame size={20} /></span>
          <div>
            <p>Kcal trung bình trang này</p>
            <strong>{avgCalories}</strong>
          </div>
        </article>
        <article className="admin-meals__summary-card admin-meals__summary-card--green">
          <span><Clock3 size={20} /></span>
          <div>
            <p>Bữa sáng đang hiển thị</p>
            <strong>{breakfastCount}</strong>
          </div>
        </article>
        <article className="admin-meals__summary-card admin-meals__summary-card--rose">
          <span><Soup size={20} /></span>
          <div>
            <p>Ăn nhẹ đang hiển thị</p>
            <strong>{snackCount}</strong>
          </div>
        </article>
      </div>

      <div className="admin-panel admin-meals__panel">
        <div className="admin-meals__table-wrap">
          <table className="admin-table admin-meals__table">
            <thead>
              <tr>
                <th>Món ăn</th>
                <th>Loại bữa</th>
                <th>Danh mục</th>
                <th>Kcal</th>
                <th>Protein</th>
                <th>Thời gian</th>
                <th>Độ khó</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {meals.map((meal, index) => {
                const mealSource = rawMeals[index];

                return (
                  <tr key={meal.id}>
                  <td>
                    <div className="admin-meals__name-cell">
                      <strong>{meal.name}</strong>
                    </div>
                  </td>
                  <td>
                    <span className={`admin-meals__badge admin-meals__badge--${formatMealTypeBadge(meal.mealType)}`}>
                      {meal.mealType}
                    </span>
                  </td>
                  <td>{meal.category}</td>
                  <td className="admin-mono">{meal.calories}</td>
                  <td className="admin-mono">{meal.protein} g</td>
                  <td>{meal.totalTime}</td>
                  <td>{meal.difficulty}</td>
                  <td>
                    <div className="admin-meals__actions">
                      <button
                        type="button"
                        className="admin-meals__action-btn admin-meals__action-btn--edit"
                        onClick={() => mealSource && openEditModal(mealSource)}
                        aria-label={`Sửa ${meal.name}`}
                      >
                        <Edit3 size={15} />
                      </button>
                      <button
                        type="button"
                        className="admin-meals__action-btn admin-meals__action-btn--delete"
                        onClick={() => handleDeleteMeal(meal)}
                        aria-label={`Xóa ${meal.name}`}
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          {!loading && meals.length === 0 ? (
            <div className="admin-meals__empty">
              <Soup size={42} />
              <strong>Chưa có món ăn nào phù hợp bộ lọc hiện tại</strong>
              <span>Hãy thử đổi từ khóa hoặc loại bữa để xem thêm dữ liệu.</span>
            </div>
          ) : null}
        </div>

        <div className="admin-meals__footer">
          <div className="admin-meals__result">
            {totalItems > 0
              ? `Hiển thị trang ${currentPage + 1}/${Math.max(totalPages, 1)} • ${totalItems} món ăn`
              : "Chưa có dữ liệu món ăn"}
          </div>

          <div className="admin-meals__pagination">
            <button type="button" onClick={() => setPage((prev) => Math.max(prev - 1, 0))} disabled={!hasPrevious}>
              <ChevronLeft size={16} />
            </button>

            {paginationItems.map((pageNumber) => (
              <button
                key={pageNumber}
                type="button"
                className={pageNumber === currentPage ? "is-active" : ""}
                onClick={() => setPage(pageNumber)}
              >
                {pageNumber + 1}
              </button>
            ))}

            <button type="button" onClick={() => setPage((prev) => prev + 1)} disabled={!hasNext}>
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      </div>

      {editingMeal ? (
        <div className="admin-meals__modal-backdrop" onClick={closeEditModal} role="presentation">
          <div
            className="admin-meals__modal"
            role="dialog"
            aria-modal="true"
            aria-label={`Sửa món ăn ${editingMeal.name}`}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="admin-meals__modal-head">
              <div>
                <p className="admin-meals__modal-eyebrow">Sửa món ăn</p>
                <h2>{editingMeal.name}</h2>
              </div>
              <button type="button" className="admin-meals__modal-close" onClick={closeEditModal} aria-label="Đóng">
                ×
              </button>
            </div>

            <div className="admin-meals__modal-body">
              <div className="admin-meals__section">
                <h3 className="admin-meals__section-title">Thông tin chung</h3>
                <div className="admin-meals__form-grid">
                <label className="admin-meals__form-field--full">
                  <span>Tên món *</span>
                  <input
                    value={editForm.name}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, name: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Danh mục</span>
                  <input
                    value={editForm.category}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, category: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Ẩm thực</span>
                  <input
                    value={editForm.cuisine}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, cuisine: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Loại bữa</span>
                  <input
                    value={editForm.meal_type}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, meal_type: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Độ khó</span>
                  <input
                    value={editForm.difficulty}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, difficulty: event.target.value }))}
                  />
                </label>
                <label className="admin-meals__form-field--full">
                  <span>Keywords</span>
                  <input
                    value={editForm.keywords}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, keywords: event.target.value }))}
                  />
                </label>
                <label className="admin-meals__form-field--full">
                  <span>Mô tả</span>
                  <textarea
                    rows={3}
                    value={editForm.description}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, description: event.target.value }))}
                  />
                </label>
                </div>
              </div>

              <div className="admin-meals__section">
                <h3 className="admin-meals__section-title">Thời gian và khẩu phần</h3>
                <div className="admin-meals__form-grid">
                <label>
                  <span>Chuẩn bị</span>
                  <input
                    value={editForm.prep_time}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, prep_time: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Chế biến</span>
                  <input
                    value={editForm.cook_time}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, cook_time: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Tổng thời gian</span>
                  <input
                    value={editForm.total_time}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, total_time: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Số phần</span>
                  <input
                    type="number"
                    min="0"
                    value={editForm.servings}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, servings: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Khẩu phần</span>
                  <input
                    value={editForm.serving_size}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, serving_size: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Chỉ số GI</span>
                  <input
                    value={editForm.glycemic_index}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, glycemic_index: event.target.value }))}
                  />
                </label>
                <label>
                  <span>GL</span>
                  <input
                    type="number"
                    step="0.01"
                    value={editForm.glycemic_load}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, glycemic_load: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Chi phí</span>
                  <input
                    value={editForm.cost_level}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, cost_level: event.target.value }))}
                  />
                </label>
                </div>
              </div>

              <div className="admin-meals__section">
                <h3 className="admin-meals__section-title">Dinh dưỡng</h3>
                <div className="admin-meals__form-grid">
                <label>
                  <span>Kcal</span>
                  <input
                    type="number"
                    value={editForm.calories}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, calories: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Protein (g)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={editForm.protein_g}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, protein_g: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Fat (g)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={editForm.total_fat_g}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, total_fat_g: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Sat fat (g)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={editForm.saturated_fat_g}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, saturated_fat_g: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Trans fat (g)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={editForm.trans_fat_g}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, trans_fat_g: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Cholesterol (mg)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={editForm.cholesterol_mg}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, cholesterol_mg: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Sodium (mg)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={editForm.sodium_mg}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, sodium_mg: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Carbs (g)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={editForm.total_carbohydrate_g}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, total_carbohydrate_g: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Fiber (g)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={editForm.dietary_fiber_g}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, dietary_fiber_g: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Đường (g)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={editForm.sugars_g}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, sugars_g: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Đường thêm (g)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={editForm.added_sugars_g}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, added_sugars_g: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Kali (mg)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={editForm.potassium_mg}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, potassium_mg: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Phosphorus (mg)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={editForm.phosphorus_mg}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, phosphorus_mg: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Magnesium (mg)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={editForm.magnesium_mg}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, magnesium_mg: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Vitamin D (mcg)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={editForm.vitamin_d_mcg}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, vitamin_d_mcg: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Calcium (mg)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={editForm.calcium_mg}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, calcium_mg: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Iron (mg)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={editForm.iron_mg}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, iron_mg: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Omega-3 (g)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={editForm.omega3_g}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, omega3_g: event.target.value }))}
                  />
                </label>
                </div>
              </div>

              <div className="admin-meals__section">
                <h3 className="admin-meals__section-title">Phù hợp sức khỏe</h3>
                <div className="admin-meals__toggle-grid">
                {createMealToggleFields.map(([key, label]) => (
                  <label key={key} className="admin-meals__checkbox">
                    <input
                      type="checkbox"
                      checked={editForm[key]}
                      onChange={(event) =>
                        setEditForm((prev) => ({
                          ...prev,
                          [key]: event.target.checked,
                        }))
                      }
                    />
                    <span>{label}</span>
                  </label>
                ))}
                </div>
                <div className="admin-meals__form-grid">
                <label className="admin-meals__form-field--full">
                  <span>Ghi chú phù hợp</span>
                  <textarea
                    rows={3}
                    value={editForm.suitability_notes}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, suitability_notes: event.target.value }))}
                  />
                </label>
                <label className="admin-meals__form-field--full">
                  <span>Khẩu phần gợi ý</span>
                  <textarea
                    rows={2}
                    value={editForm.portion_advice}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, portion_advice: event.target.value }))}
                  />
                </label>
                <label className="admin-meals__form-field--full">
                  <span>Chống chỉ định</span>
                  <textarea
                    rows={2}
                    value={editForm.contraindications}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, contraindications: event.target.value }))}
                  />
                </label>
                </div>
              </div>

              <div className="admin-meals__section">
                <h3 className="admin-meals__section-title">Nội dung món ăn</h3>
                <div className="admin-meals__form-grid">
                <label className="admin-meals__form-field--full">
                  <span>Nguyên liệu</span>
                  <textarea
                    rows={4}
                    value={editForm.ingredients}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, ingredients: event.target.value }))}
                  />
                </label>
                <label className="admin-meals__form-field--full">
                  <span>Hướng dẫn</span>
                  <textarea
                    rows={4}
                    value={editForm.instructions}
                    onChange={(event) => setEditForm((prev) => ({ ...prev, instructions: event.target.value }))}
                  />
                </label>
                </div>
              </div>
            </div>

            <div className="admin-meals__modal-actions">
              <button type="button" className="admin-meals__modal-secondary" onClick={closeEditModal} disabled={isSaving}>
                Hủy
              </button>
              <button type="button" className="admin-meals__modal-primary" onClick={handleEditSubmit} disabled={isSaving}>
                {isSaving ? "Đang lưu..." : "Lưu thay đổi"}
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {isCreateOpen ? (
        <div className="admin-meals__modal-backdrop" onClick={closeCreateModal} role="presentation">
          <div
            className="admin-meals__modal admin-meals__modal--create"
            role="dialog"
            aria-modal="true"
            aria-label="Thêm mới món ăn"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="admin-meals__modal-head">
              <div>
                <p className="admin-meals__modal-eyebrow">Thêm món ăn mới</p>
                <h2>Nhập đầy đủ thông tin món ăn</h2>
              </div>
              <button type="button" className="admin-meals__modal-close" onClick={closeCreateModal} aria-label="Đóng">
                ×
              </button>
            </div>

            <div className="admin-meals__modal-body">
              <div className="admin-meals__section">
                <h3 className="admin-meals__section-title">Thông tin chung</h3>
                <div className="admin-meals__form-grid">
                <label className="admin-meals__form-field--full">
                  <span>Tên món *</span>
                  <input
                    value={createForm.name}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, name: event.target.value }))}
                    placeholder="Ví dụ: Cơm chiên dương châu"
                  />
                </label>
                <label>
                  <span>Danh mục</span>
                  <input
                    value={createForm.category}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, category: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Ẩm thực</span>
                  <input
                    value={createForm.cuisine}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, cuisine: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Loại bữa</span>
                  <input
                    value={createForm.meal_type}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, meal_type: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Độ khó</span>
                  <input
                    value={createForm.difficulty}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, difficulty: event.target.value }))}
                  />
                </label>
                <label className="admin-meals__form-field--full">
                  <span>Keywords</span>
                  <input
                    value={createForm.keywords}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, keywords: event.target.value }))}
                    placeholder="Từ khóa tìm kiếm, cách nhau bằng dấu phẩy"
                  />
                </label>
                <label className="admin-meals__form-field--full">
                  <span>Mô tả</span>
                  <textarea
                    rows={3}
                    value={createForm.description}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, description: event.target.value }))}
                  />
                </label>
                </div>
              </div>

              <div className="admin-meals__section">
                <h3 className="admin-meals__section-title">Thời gian và khẩu phần</h3>
                <div className="admin-meals__form-grid">
                <label>
                  <span>Chuẩn bị</span>
                  <input
                    value={createForm.prep_time}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, prep_time: event.target.value }))}
                    placeholder="Ví dụ: 15 phút"
                  />
                </label>
                <label>
                  <span>Chế biến</span>
                  <input
                    value={createForm.cook_time}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, cook_time: event.target.value }))}
                    placeholder="Ví dụ: 20 phút"
                  />
                </label>
                <label>
                  <span>Tổng thời gian</span>
                  <input
                    value={createForm.total_time}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, total_time: event.target.value }))}
                    placeholder="Ví dụ: 35 phút"
                  />
                </label>
                <label>
                  <span>Số phần</span>
                  <input
                    type="number"
                    min="0"
                    value={createForm.servings}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, servings: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Khẩu phần</span>
                  <input
                    value={createForm.serving_size}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, serving_size: event.target.value }))}
                    placeholder="Ví dụ: 1 tô (~300g)"
                  />
                </label>
                <label>
                  <span>Chỉ số GI</span>
                  <input
                    value={createForm.glycemic_index}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, glycemic_index: event.target.value }))}
                  />
                </label>
                <label>
                  <span>GL</span>
                  <input
                    type="number"
                    step="0.01"
                    value={createForm.glycemic_load}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, glycemic_load: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Chi phí</span>
                  <input
                    value={createForm.cost_level}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, cost_level: event.target.value }))}
                  />
                </label>
                </div>
              </div>

              <div className="admin-meals__section">
                <h3 className="admin-meals__section-title">Dinh dưỡng</h3>
                <div className="admin-meals__form-grid">
                <label>
                  <span>Kcal</span>
                  <input
                    type="number"
                    value={createForm.calories}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, calories: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Protein (g)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={createForm.protein_g}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, protein_g: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Fat (g)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={createForm.total_fat_g}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, total_fat_g: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Sat fat (g)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={createForm.saturated_fat_g}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, saturated_fat_g: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Trans fat (g)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={createForm.trans_fat_g}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, trans_fat_g: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Cholesterol (mg)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={createForm.cholesterol_mg}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, cholesterol_mg: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Sodium (mg)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={createForm.sodium_mg}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, sodium_mg: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Carbs (g)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={createForm.total_carbohydrate_g}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, total_carbohydrate_g: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Fiber (g)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={createForm.dietary_fiber_g}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, dietary_fiber_g: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Đường (g)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={createForm.sugars_g}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, sugars_g: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Đường thêm (g)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={createForm.added_sugars_g}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, added_sugars_g: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Kali (mg)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={createForm.potassium_mg}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, potassium_mg: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Phosphorus (mg)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={createForm.phosphorus_mg}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, phosphorus_mg: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Magnesium (mg)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={createForm.magnesium_mg}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, magnesium_mg: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Vitamin D (mcg)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={createForm.vitamin_d_mcg}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, vitamin_d_mcg: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Calcium (mg)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={createForm.calcium_mg}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, calcium_mg: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Iron (mg)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={createForm.iron_mg}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, iron_mg: event.target.value }))}
                  />
                </label>
                <label>
                  <span>Omega-3 (g)</span>
                  <input
                    type="number"
                    step="0.01"
                    value={createForm.omega3_g}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, omega3_g: event.target.value }))}
                  />
                </label>
                </div>
              </div>

              <div className="admin-meals__section">
                <h3 className="admin-meals__section-title">Phù hợp sức khỏe</h3>
                <div className="admin-meals__toggle-grid">
                {createMealToggleFields.map(([key, label]) => (
                  <label key={key} className="admin-meals__checkbox">
                    <input
                      type="checkbox"
                      checked={createForm[key]}
                      onChange={(event) =>
                        setCreateForm((prev) => ({
                          ...prev,
                          [key]: event.target.checked,
                        }))
                      }
                    />
                    <span>{label}</span>
                  </label>
                ))}
                </div>
                <div className="admin-meals__form-grid">
                <label className="admin-meals__form-field--full">
                  <span>Ghi chú phù hợp</span>
                  <textarea
                    rows={3}
                    value={createForm.suitability_notes}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, suitability_notes: event.target.value }))}
                  />
                </label>
                <label className="admin-meals__form-field--full">
                  <span>Khẩu phần gợi ý</span>
                  <textarea
                    rows={2}
                    value={createForm.portion_advice}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, portion_advice: event.target.value }))}
                  />
                </label>
                <label className="admin-meals__form-field--full">
                  <span>Chống chỉ định</span>
                  <textarea
                    rows={2}
                    value={createForm.contraindications}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, contraindications: event.target.value }))}
                  />
                </label>
                </div>
              </div>

              <div className="admin-meals__section">
                <h3 className="admin-meals__section-title">Nội dung món ăn</h3>
                <div className="admin-meals__form-grid">
                <label className="admin-meals__form-field--full">
                  <span>Nguyên liệu</span>
                  <textarea
                    rows={4}
                    value={createForm.ingredients}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, ingredients: event.target.value }))}
                    placeholder="Nhập danh sách nguyên liệu dạng text"
                  />
                </label>
                <label className="admin-meals__form-field--full">
                  <span>Hướng dẫn</span>
                  <textarea
                    rows={4}
                    value={createForm.instructions}
                    onChange={(event) => setCreateForm((prev) => ({ ...prev, instructions: event.target.value }))}
                    placeholder="Nhập hướng dẫn chế biến"
                  />
                </label>
                </div>
              </div>
            </div>

            <div className="admin-meals__modal-actions">
              <button type="button" className="admin-meals__modal-secondary" onClick={closeCreateModal} disabled={isCreating}>
                Hủy
              </button>
              <button type="button" className="admin-meals__modal-primary" onClick={handleCreateSubmit} disabled={isCreating}>
                {isCreating ? "Đang tạo..." : "Thêm món ăn"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
};

export default AdminMeals;
