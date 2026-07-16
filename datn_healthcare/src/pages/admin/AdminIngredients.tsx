import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Edit3,
  Flame,
  Leaf,
  PackagePlus,
  Search,
  Trash2,
  CircleAlert,
  Beaker,
} from "lucide-react";
import Swal from "sweetalert2";
import { toast } from "sonner";
import { getApiErrorMessage } from "@/utils/apiErrorMessage";
import { deleteAdminIngredient, createAdminIngredient, getAdminIngredients, updateAdminIngredient, type AdminIngredientCreatePayload } from "@/services/nutritionservices/adminIngredients";
import { IngredientPageResponseRaw, IngredientResponseRaw } from "@/types/IngredientType";
import "./AdminMeals.scss";

type IngredientRow = {
  id: number;
  foodName: string;
  normalizedName: string;
  calories: number;
  protein: string;
  fat: string;
  carbs: string;
};

type IngredientFormState = {
  foodName: string;
  normalizedName: string;
  calories: string;
  protein: string;
  fat: string;
  carbs: string;
};

const PAGE_SIZE = 8;

const emptyIngredientForm = (): IngredientFormState => ({
  foodName: "",
  normalizedName: "",
  calories: "",
  protein: "",
  fat: "",
  carbs: "",
});

const safeText = (value: string | null | undefined, fallback: string) => {
  const trimmed = value?.trim();
  return trimmed ? trimmed : fallback;
};

const toNumberString = (value: number | string | null | undefined) => {
  if (value === null || value === undefined || value === "") return "0";
  return String(value);
};

const toNumberOrNull = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : null;
};

const normalizeIngredientName = (value: string) => value.trim().replace(/\s+/g, " ");

const mapIngredientRow = (ingredient: IngredientResponseRaw): IngredientRow => ({
  id: ingredient.id,
  foodName: safeText(ingredient.foodName, "Chưa có tên"),
  normalizedName: safeText(ingredient.normalizedName, "Chưa chuẩn hóa"),
  calories: Number(ingredient.calories ?? 0),
  protein: toNumberString(ingredient.protein),
  fat: toNumberString(ingredient.fat),
  carbs: toNumberString(ingredient.carbs),
});

const fillFormFromIngredient = (ingredient: IngredientResponseRaw): IngredientFormState => ({
  foodName: ingredient.foodName ?? "",
  normalizedName: ingredient.normalizedName ?? "",
  calories: ingredient.calories == null ? "" : String(ingredient.calories),
  protein: ingredient.protein == null ? "" : String(ingredient.protein),
  fat: ingredient.fat == null ? "" : String(ingredient.fat),
  carbs: ingredient.carbs == null ? "" : String(ingredient.carbs),
});

const AdminIngredients: React.FC = () => {
  const [response, setResponse] = useState<IngredientPageResponseRaw | null>(null);
  const [keyword, setKeyword] = useState("");
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isEditingOpen, setIsEditingOpen] = useState(false);
  const [createForm, setCreateForm] = useState<IngredientFormState>(() => emptyIngredientForm());
  const [editForm, setEditForm] = useState<IngredientFormState>(() => emptyIngredientForm());
  const [editingIngredient, setEditingIngredient] = useState<IngredientResponseRaw | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  const loadIngredients = useCallback(async () => {
    setLoading(true);
    try {
      const result = await getAdminIngredients({
        page,
        size: PAGE_SIZE,
        keyword: keyword.trim() || undefined,
      });
      setResponse(result);
    } catch (error) {
      console.error("Load ingredients error:", error);
      toast.error(
        getApiErrorMessage(error, "Không tải được danh sách nguyên liệu.", {
          forbiddenMessage: "Bạn không có quyền truy cập danh sách nguyên liệu.",
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
  }, [keyword, page]);

  useEffect(() => {
    loadIngredients();
  }, [loadIngredients]);

  useEffect(() => {
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsCreateOpen(false);
        setIsEditingOpen(false);
      }
    };
    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, []);

  useEffect(() => {
    const modalOpen = isCreateOpen || isEditingOpen;
    if (!modalOpen) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isCreateOpen, isEditingOpen]);

  const rawIngredients = response?.items ?? [];
  const ingredients = useMemo(() => rawIngredients.map(mapIngredientRow), [rawIngredients]);
  const totalItems = response?.totalItems ?? 0;
  const totalPages = response?.totalPages ?? 0;
  const currentPage = response?.page ?? page;
  const hasNext = Boolean(response?.hasNext);
  const hasPrevious = Boolean(response?.hasPrevious);
  const avgCalories = ingredients.length ? Math.round(ingredients.reduce((sum, item) => sum + item.calories, 0) / ingredients.length) : 0;
  const avgProtein = ingredients.length
    ? (ingredients.reduce((sum, item) => sum + Number(item.protein), 0) / ingredients.length).toFixed(1)
    : "0.0";
  const avgFat = ingredients.length
    ? (ingredients.reduce((sum, item) => sum + Number(item.fat), 0) / ingredients.length).toFixed(1)
    : "0.0";
  const avgCarbs = ingredients.length
    ? (ingredients.reduce((sum, item) => sum + Number(item.carbs), 0) / ingredients.length).toFixed(1)
    : "0.0";

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
    setCreateForm(emptyIngredientForm());
    setIsCreateOpen(true);
  };

  const openEditModal = (ingredient: IngredientResponseRaw) => {
    setEditingIngredient(ingredient);
    setEditForm(fillFormFromIngredient(ingredient));
    setIsEditingOpen(true);
  };

  const closeCreateModal = () => {
    if (isCreating) return;
    setIsCreateOpen(false);
  };

  const closeEditModal = () => {
    if (isSaving) return;
    setIsEditingOpen(false);
    setEditingIngredient(null);
  };

  const handleCreate = async () => {
    const foodName = normalizeIngredientName(createForm.foodName);
    if (!foodName) {
      toast.error("Vui lòng nhập tên nguyên liệu.");
      return;
    }

    setIsCreating(true);
    try {
      const payload: AdminIngredientCreatePayload = {
        foodName,
        normalizedName: createForm.normalizedName.trim() || undefined,
        calories: toNumberOrNull(createForm.calories),
        protein: toNumberOrNull(createForm.protein),
        fat: toNumberOrNull(createForm.fat),
        carbs: toNumberOrNull(createForm.carbs),
      };

      await createAdminIngredient(payload);
      toast.success("Đã thêm nguyên liệu mới.");
      setIsCreateOpen(false);
      await loadIngredients();
    } catch (error) {
      console.error("Create ingredient error:", error);
      toast.error(
        getApiErrorMessage(error, "Không thể thêm nguyên liệu.", {
          forbiddenMessage: "Bạn không có quyền thêm nguyên liệu.",
          unauthorizedMessage: "Phiên đăng nhập không hợp lệ. Vui lòng đăng nhập lại.",
        })
      );
    } finally {
      setIsCreating(false);
    }
  };

  const handleSave = async () => {
    if (!editingIngredient) return;

    const foodName = normalizeIngredientName(editForm.foodName);
    if (!foodName) {
      toast.error("Vui lòng nhập tên nguyên liệu.");
      return;
    }

    setIsSaving(true);
    try {
      await updateAdminIngredient(editingIngredient.id, {
        foodName,
        normalizedName: editForm.normalizedName.trim() || undefined,
        calories: toNumberOrNull(editForm.calories),
        protein: toNumberOrNull(editForm.protein),
        fat: toNumberOrNull(editForm.fat),
        carbs: toNumberOrNull(editForm.carbs),
      });
      toast.success("Đã cập nhật nguyên liệu.");
      setIsEditingOpen(false);
      setEditingIngredient(null);
      await loadIngredients();
    } catch (error) {
      console.error("Update ingredient error:", error);
      toast.error(
        getApiErrorMessage(error, "Không thể cập nhật nguyên liệu.", {
          forbiddenMessage: "Bạn không có quyền sửa nguyên liệu.",
          unauthorizedMessage: "Phiên đăng nhập không hợp lệ. Vui lòng đăng nhập lại.",
        })
      );
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (ingredient: IngredientRow) => {
    const confirm = await Swal.fire({
      title: "Xóa nguyên liệu này?",
      text: `${ingredient.foodName} sẽ bị xóa khỏi danh sách quản lý.`,
      icon: "warning",
      showCancelButton: true,
      confirmButtonText: "Xóa",
      cancelButtonText: "Hủy",
      reverseButtons: true,
      confirmButtonColor: "#ef4444",
      cancelButtonColor: "#64748b",
    });

    if (!confirm.isConfirmed) return;

    try {
      await deleteAdminIngredient(ingredient.id);
      toast.success("Đã xóa nguyên liệu.");
      await loadIngredients();
    } catch (error) {
      console.error("Delete ingredient error:", error);
      toast.error(
        getApiErrorMessage(error, "Không thể xóa nguyên liệu.", {
          forbiddenMessage: "Bạn không có quyền xóa nguyên liệu.",
          unauthorizedMessage: "Phiên đăng nhập không hợp lệ. Vui lòng đăng nhập lại.",
        })
      );
    }
  };

  return (
    <section className="admin-page admin-meals">
      <div className="admin-page__head">
        <div>
          <h1 className="admin-page__title">Quản lý nguyên liệu</h1>
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
              placeholder="Tìm theo tên nguyên liệu hoặc tên chuẩn..."
            />
          </label>

          <button type="button" className="admin-meals__refresh" onClick={openCreateModal}>
            <PackagePlus size={16} />
            Thêm mới
          </button>
        </div>
      </div>

      <div className="admin-meals__summary admin-meals__summary--ingredients">
        <article className="admin-meals__summary-card admin-meals__summary-card--blue">
          <span><Leaf size={20} /></span>
          <div>
            <p>Tổng nguyên liệu</p>
            <strong>{totalItems}</strong>
          </div>
        </article>
        <article className="admin-meals__summary-card admin-meals__summary-card--amber">
          <span><Flame size={20} /></span>
          <div>
            <p>Kcal trung bình</p>
            <strong>{avgCalories}</strong>
          </div>
        </article>
        <article className="admin-meals__summary-card admin-meals__summary-card--green">
          <span><Beaker size={20} /></span>
          <div>
            <p>Protein trung bình</p>
            <strong>{avgProtein} g</strong>
          </div>
        </article>
        <article className="admin-meals__summary-card admin-meals__summary-card--rose">
          <span><CircleAlert size={20} /></span>
          <div>
            <p>Fat trung bình</p>
            <strong>{avgFat} g</strong>
          </div>
        </article>
        <article className="admin-meals__summary-card admin-meals__summary-card--amber">
          <span><Flame size={20} /></span>
          <div>
            <p>Carbs trung bình</p>
            <strong>{avgCarbs} g</strong>
          </div>
        </article>
      </div>

      <div className="admin-panel admin-meals__panel">
        <div className="admin-meals__table-wrap">
          <table className="admin-table admin-meals__table">
            <thead>
              <tr>
                <th>Nguyên liệu</th>
                <th>Tên chuẩn</th>
                <th>Kcal</th>
                <th>Protein</th>
                <th>Fat</th>
                <th>Carbs</th>
                <th>Thao tác</th>
              </tr>
            </thead>
            <tbody>
              {ingredients.map((ingredient, index) => {
                const source = rawIngredients[index];
                return (
                  <tr key={ingredient.id}>
                    <td>
                      <div className="admin-meals__name-cell">
                        <strong>{ingredient.foodName}</strong>
                      </div>
                    </td>
                    <td>{ingredient.normalizedName}</td>
                    <td className="admin-mono">{ingredient.calories}</td>
                    <td className="admin-mono">{ingredient.protein} g</td>
                    <td className="admin-mono">{ingredient.fat} g</td>
                    <td className="admin-mono">{ingredient.carbs} g</td>
                    <td>
                      <div className="admin-meals__actions">
                        <button
                          type="button"
                          className="admin-meals__action-btn admin-meals__action-btn--edit"
                          onClick={() => source && openEditModal(source)}
                          aria-label={`Sửa ${ingredient.foodName}`}
                        >
                          <Edit3 size={15} />
                        </button>
                        <button
                          type="button"
                          className="admin-meals__action-btn admin-meals__action-btn--delete"
                          onClick={() => handleDelete(ingredient)}
                          aria-label={`Xóa ${ingredient.foodName}`}
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

          {!loading && ingredients.length === 0 ? (
            <div className="admin-meals__empty">
              <Leaf size={42} />
              <strong>Chưa có nguyên liệu nào phù hợp bộ lọc hiện tại</strong>
              <span>Hãy thử đổi từ khóa để xem thêm dữ liệu.</span>
            </div>
          ) : null}
        </div>

        <div className="admin-meals__footer">
          <div className="admin-meals__result">
            {totalItems > 0
              ? `Hiển thị trang ${currentPage + 1}/${Math.max(totalPages, 1)} • ${totalItems} nguyên liệu`
              : "Chưa có dữ liệu nguyên liệu"}
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

      {isEditingOpen && editingIngredient ? (
        <div className="admin-meals__modal-backdrop" onClick={closeEditModal} role="presentation">
          <div
            className="admin-meals__modal"
            role="dialog"
            aria-modal="true"
            aria-label={`Sửa nguyên liệu ${editingIngredient.foodName ?? ""}`}
            onClick={(event) => event.stopPropagation()}
          >
            <div className="admin-meals__modal-head">
              <div>
                <p className="admin-meals__modal-eyebrow">Sửa nguyên liệu</p>
                <h2>{editingIngredient.foodName}</h2>
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
                    <span>Tên nguyên liệu *</span>
                    <input
                      value={editForm.foodName}
                      onChange={(event) => setEditForm((prev) => ({ ...prev, foodName: event.target.value }))}
                    />
                  </label>
                  <label className="admin-meals__form-field--full">
                    <span>Tên chuẩn</span>
                    <input
                      value={editForm.normalizedName}
                      onChange={(event) => setEditForm((prev) => ({ ...prev, normalizedName: event.target.value }))}
                    />
                  </label>
                </div>
              </div>

              <div className="admin-meals__section">
                <h3 className="admin-meals__section-title">Giá trị dinh dưỡng</h3>
                <div className="admin-meals__form-grid">
                  <label>
                    <span>Calories</span>
                    <input
                      type="number"
                      step="0.01"
                      value={editForm.calories}
                      onChange={(event) => setEditForm((prev) => ({ ...prev, calories: event.target.value }))}
                    />
                  </label>
                  <label>
                    <span>Protein</span>
                    <input
                      type="number"
                      step="0.01"
                      value={editForm.protein}
                      onChange={(event) => setEditForm((prev) => ({ ...prev, protein: event.target.value }))}
                    />
                  </label>
                  <label>
                    <span>Fat</span>
                    <input
                      type="number"
                      step="0.01"
                      value={editForm.fat}
                      onChange={(event) => setEditForm((prev) => ({ ...prev, fat: event.target.value }))}
                    />
                  </label>
                  <label>
                    <span>Carbs</span>
                    <input
                      type="number"
                      step="0.01"
                      value={editForm.carbs}
                      onChange={(event) => setEditForm((prev) => ({ ...prev, carbs: event.target.value }))}
                    />
                  </label>
                </div>
              </div>
            </div>

            <div className="admin-meals__modal-actions">
              <button type="button" className="admin-meals__modal-secondary" onClick={closeEditModal} disabled={isSaving}>
                Hủy
              </button>
              <button type="button" className="admin-meals__modal-primary" onClick={handleSave} disabled={isSaving}>
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
            aria-label="Thêm mới nguyên liệu"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="admin-meals__modal-head">
              <div>
                <p className="admin-meals__modal-eyebrow">Thêm nguyên liệu mới</p>
                <h2>Nhập đầy đủ thông tin nguyên liệu</h2>
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
                    <span>Tên nguyên liệu *</span>
                    <input
                      value={createForm.foodName}
                      onChange={(event) => setCreateForm((prev) => ({ ...prev, foodName: event.target.value }))}
                      placeholder="Ví dụ: Thịt bò"
                    />
                  </label>
                  <label className="admin-meals__form-field--full">
                    <span>Tên chuẩn</span>
                    <input
                      value={createForm.normalizedName}
                      onChange={(event) => setCreateForm((prev) => ({ ...prev, normalizedName: event.target.value }))}
                      placeholder="Ví dụ: thit bo"
                    />
                  </label>
                </div>
              </div>

              <div className="admin-meals__section">
                <h3 className="admin-meals__section-title">Giá trị dinh dưỡng</h3>
                <div className="admin-meals__form-grid">
                  <label>
                    <span>Calories</span>
                    <input
                      type="number"
                      step="0.01"
                      value={createForm.calories}
                      onChange={(event) => setCreateForm((prev) => ({ ...prev, calories: event.target.value }))}
                    />
                  </label>
                  <label>
                    <span>Protein</span>
                    <input
                      type="number"
                      step="0.01"
                      value={createForm.protein}
                      onChange={(event) => setCreateForm((prev) => ({ ...prev, protein: event.target.value }))}
                    />
                  </label>
                  <label>
                    <span>Fat</span>
                    <input
                      type="number"
                      step="0.01"
                      value={createForm.fat}
                      onChange={(event) => setCreateForm((prev) => ({ ...prev, fat: event.target.value }))}
                    />
                  </label>
                  <label>
                    <span>Carbs</span>
                    <input
                      type="number"
                      step="0.01"
                      value={createForm.carbs}
                      onChange={(event) => setCreateForm((prev) => ({ ...prev, carbs: event.target.value }))}
                    />
                  </label>
                </div>
              </div>
            </div>

            <div className="admin-meals__modal-actions">
              <button type="button" className="admin-meals__modal-secondary" onClick={closeCreateModal} disabled={isCreating}>
                Hủy
              </button>
              <button type="button" className="admin-meals__modal-primary" onClick={handleCreate} disabled={isCreating}>
                {isCreating ? "Đang tạo..." : "Thêm nguyên liệu"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
};

export default AdminIngredients;
