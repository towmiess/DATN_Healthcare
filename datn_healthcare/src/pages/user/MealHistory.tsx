import React, { useEffect, useMemo, useRef, useState } from "react";
import { Camera, Clock3, Flame, Image as ImageIcon, Link2, Send, Sparkles, Upload, X } from "lucide-react";
import { toast } from "sonner";
import { apiClient } from "@/api/Fetcher";
import { uploadImageToCloudinary } from "@/services/cloudinary/upload";
import "./MealHistory.scss";

type MealHistoryItem = {
  id: number;
  image: string;
  name: string;
  totalCalories: number;
  totalProtein: number;
  totalFat: number;
  totalCarbs: number;
  created_at: string;
};

type GroupedHistory = {
  dateKey: string;
  latestAt: number;
  items: MealHistoryItem[];
};

const MealHistory: React.FC = () => {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploadedImageUrl, setUploadedImageUrl] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [mealHistory, setMealHistory] = useState<MealHistoryItem[]>([]);
  const [isLoadingHistory, setIsLoadingHistory] = useState(false);
  const [historyError, setHistoryError] = useState("");

  useEffect(() => {
    if (!isUploadModalOpen) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isUploadModalOpen]);

  const resetModalState = () => {
    setSelectedFile(null);
    setUploadedImageUrl("");
    setIsUploading(false);
    setIsSubmitting(false);
    setUploadError("");

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const loadMealHistory = async () => {
    setIsLoadingHistory(true);
    setHistoryError("");

    try {
      const response = await apiClient.get<MealHistoryItem[]>("/meal-history");
      setMealHistory(Array.isArray(response.data) ? response.data : []);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Không tải được lịch sử bữa ăn.";
      setHistoryError(message);
      console.error("Load meal history error:", error);
    } finally {
      setIsLoadingHistory(false);
    }
  };

  useEffect(() => {
    void loadMealHistory();
  }, []);

  const handleUploadClick = () => {
    setUploadError("");
    setIsUploadModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsUploadModalOpen(false);
    resetModalState();
  };

  const handleSelectFileClick = () => {
    fileInputRef.current?.click();
  };

  const handleUploadZoneKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      handleSelectFileClick();
    }
  };

  const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];

    if (!file) {
      resetModalState();
      return;
    }

    setSelectedFile(file);
    setUploadedImageUrl("");
    setUploadError("");
    setIsUploading(true);

    try {
      const result = await uploadImageToCloudinary(file);
      setUploadedImageUrl(result.secure_url);
      console.log("Cloudinary image URL:", result.secure_url);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Cloudinary upload failed";
      setUploadError(message);
      console.error("Cloudinary upload error:", error);
    } finally {
      setIsUploading(false);
    }
  };

  const handleSendClick = async () => {
    if (!selectedFile || !uploadedImageUrl) {
      setUploadError("Vui lòng chọn ảnh và chờ upload hoàn tất trước khi gửi.");
      return;
    }

    setUploadError("");
    setIsSubmitting(true);

    const loadingToastId = toast.loading("Đang lưu ảnh vào lịch sử...", {
      description: "Hệ thống đang phân tích và ghi nhận món ăn.",
    });

    try {
      const formData = new FormData();
      formData.append("image", selectedFile);
      formData.append("url", uploadedImageUrl);

      await apiClient.post("/vision/analyze", formData);
      await loadMealHistory();

      toast.dismiss(loadingToastId);
      toast.success("Món ăn đã được lưu thành công.", {
      });
      handleCloseModal();
    } catch (error) {
      toast.dismiss(loadingToastId);
      const message = error instanceof Error ? error.message : "Gửi ảnh thất bại";
      setUploadError(message);
      toast.error("Không thể lưu ảnh.", {
        description: "Vui lòng kiểm tra lại ảnh hoặc thử lại sau.",
      });
      console.error("Vision analyze error:", error);
    } finally {
      setIsSubmitting(false);
    }
  };

  const mealHistoryGroups = useMemo<GroupedHistory[]>(() => {
    const groups = new Map<string, MealHistoryItem[]>();

    mealHistory.forEach((item) => {
      const date = new Date(item.created_at);
      const key = Number.isNaN(date.getTime()) ? "unknown" : toDateKey(date);
      const existing = groups.get(key) ?? [];
      existing.push(item);
      groups.set(key, existing);
    });

    return Array.from(groups.entries())
      .map(([dateKey, items]) => {
        const sortedItems = items
          .slice()
          .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime());

        return {
          dateKey,
          items: sortedItems,
          latestAt: sortedItems.length > 0 ? new Date(sortedItems[0].created_at).getTime() : Number.NEGATIVE_INFINITY,
        };
      })
      .sort((left, right) => right.latestAt - left.latestAt);
  }, [mealHistory]);

  function toDateKey(date: Date) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const day = String(date.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  function formatDateLabel(dateKey: string) {
    if (dateKey === "unknown") {
      return "Không rõ ngày";
    }

    const date = new Date(`${dateKey}T00:00:00`);
    return new Intl.DateTimeFormat("vi-VN", {
      weekday: "long",
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    }).format(date);
  }

  function formatTime(value: string) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "";
    }

    return new Intl.DateTimeFormat("vi-VN", {
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  }

  const getMacroPillClassName = (key: "kcal" | "protein" | "fat" | "carbs") => {
    return `pill ${key}`;
  };

  const todayStats = useMemo(() => {
    const todayKey = toDateKey(new Date());
    const todayItems = mealHistory.filter((item) => {
      const date = new Date(item.created_at);
      return !Number.isNaN(date.getTime()) && toDateKey(date) === todayKey;
    });

    const todayCalories = todayItems.reduce((sum, item) => sum + Number(item.totalCalories ?? 0), 0);

    return {
      count: todayItems.length,
      calories: todayCalories,
    };
  }, [mealHistory]);

  const formatNumeric = (value: number) => {
    return new Intl.NumberFormat("vi-VN", {
      maximumFractionDigits: 1,
      minimumFractionDigits: 0,
    }).format(value);
  };

  return (
    <section className="meal-history">
      <header className="meal-history__hero">
        <div className="meal-history__copy">
          <p className="meal-history__eyebrow">
            <Clock3 size={16} />
            Lịch sử bữa ăn
          </p>
          <h1 className="meal-history__title">Theo dõi lại các bữa ăn đã ghi nhận</h1>
          <p className="meal-history__description">
            Bạn có thể tải ảnh món ăn lên để lưu kèm lịch sử và chuẩn bị cho bước nhận diện dinh dưỡng sau này.
          </p>

          <div className="meal-history__actions">
            <button type="button" className="meal-history__upload" onClick={handleUploadClick}>
              <Upload size={16} />
              Upload ảnh
            </button>
          </div>
        </div>

        <div className="meal-history__panel">
          <article className="meal-history-card">
            <span className="meal-history-card__icon meal-history-card__icon--amber">
              <Clock3 size={15} />
            </span>
            <div>
              <strong>Gần đây</strong>
              <span>{todayStats.count} món ăn hôm nay</span>
            </div>
          </article>

          <article className="meal-history-card meal-history-card--accent">
            <span className="meal-history-card__icon meal-history-card__icon--blue">
              <Flame size={15} />
            </span>
            <div>
              <strong>Tổng kcal hôm nay</strong>
              <span className="meal-history-card__value">
                <span className="meal-history-card__value-number meal-history-card__value-number--kcal">
                  {formatNumeric(todayStats.calories)}
                </span>
                {"Kcal"}
              </span>
            </div>
          </article>
        </div>
      </header>

      <section className="meal-history__history">
        {isLoadingHistory ? (
          <div className="meal-history__history-empty">Đang tải lịch sử...</div>
        ) : historyError ? (
          <div className="meal-history__history-empty meal-history__history-empty--error">{historyError}</div>
        ) : mealHistoryGroups.length === 0 ? (
          <div className="meal-history__history-empty">Chưa có món ăn nào được lưu.</div>
        ) : (
          <div className="meal-history__history-groups">
            {mealHistoryGroups.map((group) => (
              <article className="meal-history__history-group" key={group.dateKey}>
                <div className="meal-history__history-group-head">
                  <div>
                    <h3>{formatDateLabel(group.dateKey)}</h3>
                    <span>{group.items.length} món ăn</span>
                  </div>
                </div>

                <div className="meal-history__history-list">
                  {group.items.map((item) => (
                    <article className="meal-history__history-item" key={item.id}>
                      <div className="meal-history__history-thumb">
                        {item.image ? <img src={item.image} alt={item.name} /> : <ImageIcon size={20} />}
                      </div>

                      <div className="meal-history__history-info">
                        <div className="meal-history__history-title-row">
                          <h4>{item.name}</h4>
                          <span>{formatTime(item.created_at)}</span>
                        </div>

                        <div className="meal-history__history-metrics">
                          <span className={getMacroPillClassName("kcal")}>
                            <i />
                            {item.totalCalories} kcal
                          </span>
                          <span className={getMacroPillClassName("protein")}>
                            <i />
                            {item.totalProtein} protein
                          </span>
                          <span className={getMacroPillClassName("fat")}>
                            <i />
                            {item.totalFat} fat
                          </span>
                          <span className={getMacroPillClassName("carbs")}>
                            <i />
                            {item.totalCarbs} carbs
                          </span>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      {isUploadModalOpen && (
        <div className="meal-history__modal" role="dialog" aria-modal="true" onClick={handleCloseModal}>
          <div className="meal-history__modal-content" onClick={(event) => event.stopPropagation()}>
            <div className="meal-history__modal-header">
              <div>
                <div className="meal-history__modal-badge">
                  <Sparkles size={14} />
                  Tải ảnh món ăn
                </div>
                <h2>Chọn ảnh để nhận diện dinh dưỡng</h2>
                <p>
                  Hãy tải ảnh món ăn rõ nét. Ảnh sẽ được đẩy lên Cloudinary để lấy link và lưu vào lịch sử ngay sau khi
                  gửi thành công.
                </p>
              </div>

              <button type="button" className="meal-history__modal-close" onClick={handleCloseModal} aria-label="Đóng">
                <X size={20} />
              </button>
            </div>

            <div className="meal-history__modal-body">
              <div
                className="meal-history__upload-zone"
                onClick={handleSelectFileClick}
                onKeyDown={handleUploadZoneKeyDown}
                role="button"
                tabIndex={0}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  className="meal-history__input"
                  onChange={handleFileChange}
                />

                {uploadedImageUrl ? (
                  <div className="meal-history__upload-preview">
                    <div className="meal-history__upload-preview-media">
                      <img src={uploadedImageUrl} alt="Ảnh món ăn đã upload" />
                    </div>
                    <div className="meal-history__upload-preview-info">
                      <strong>{selectedFile?.name ?? "Ảnh đã upload"}</strong>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="meal-history__upload-zone-icon">
                      <ImageIcon size={28} />
                    </div>
                    <h3>{isUploading ? "Đang upload ảnh..." : "Kéo thả hoặc bấm để chọn ảnh"}</h3>
                    <p>
                      {selectedFile
                        ? selectedFile.name
                        : "Hỗ trợ jpg, png, webp. Ảnh càng rõ thì bước nhận diện sau này càng chính xác."}
                    </p>
                    <button
                      type="button"
                      className="meal-history__browse"
                      onClick={(event) => {
                        event.stopPropagation();
                        handleSelectFileClick();
                      }}
                    >
                      Chọn ảnh từ máy
                    </button>
                  </>
                )}
              </div>

              <div className="meal-history__modal-side">
                <article className="meal-history-card">
                  <Clock3 size={18} />
                  <div>
                    <strong>Quy trình</strong>
                    <span className="meal-history__process">
                      1. Chọn ảnh
                      <br />
                      2. Upload
                      <br />
                      3. Gửi ảnh để phân tích
                    </span>
                  </div>
                </article>

                <article className="meal-history-card meal-history-card--accent">
                  <Camera size={18} />
                  <div>
                    <strong>Ghi chú</strong>
                    <span>Nút Gửi sẽ lưu ảnh lên backend sau khi Cloudinary trả link thành công.</span>
                  </div>
                </article>

                {uploadedImageUrl ? (
                  <div className="meal-history__preview">
                    <span className="meal-history__preview-label">
                      <Link2 size={12} />
                      Link ảnh
                    </span>
                    <a href={uploadedImageUrl} target="_blank" rel="noreferrer">
                      {uploadedImageUrl}
                    </a>
                  </div>
                ) : (
                  <div className="meal-history__preview meal-history__preview--empty">
                    <span className="meal-history__preview-label">Chưa có link ảnh</span>
                    <p>Chọn một file ảnh để upload và lấy link tự động.</p>
                  </div>
                )}
              </div>
            </div>

            {uploadError && <p className="meal-history__error">{uploadError}</p>}

            <div className="meal-history__modal-footer">
              <button type="button" className="meal-history__secondary" onClick={handleCloseModal}>
                Đóng
              </button>
              <button
                type="button"
                className="meal-history__primary"
                onClick={handleSendClick}
                disabled={!selectedFile || !uploadedImageUrl || isUploading || isSubmitting}
              >
                <Send size={16} />
                {isUploading ? "Đang upload..." : isSubmitting ? "Đang lưu..." : "Gửi ảnh"}
              </button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};

export default MealHistory;
