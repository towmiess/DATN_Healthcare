import axios from "axios";
import { RAG_API_URL } from "@/config";
import type {
  ChatSessionRequest,
  ChatSessionResponse,
  ChatSource,
  RagHealth,
  RawChatSource,
  StoredChatState,
} from "@/types/ChatType";

// Client riêng cho service RAG (FastAPI độc lập, không xác thực bằng JWT của hệ thống chính)
export const ragClient = axios.create({
  baseURL: RAG_API_URL,
  timeout: 240000,
});

export const getRagHealth = async (): Promise<RagHealth | null> => {
  try {
    const res = await ragClient.get<RagHealth>("/health", { timeout: 4000 });
    return res.data;
  } catch {
    return null;
  }
};

export const sendChatMessage = (payload: ChatSessionRequest) => {
  return ragClient.post<ChatSessionResponse>("/chat/session", payload);
};

export const deleteChatSession = (sessionId: string) => {
  return ragClient
    .delete(`/chat/session/${sessionId}`, { timeout: 5000 })
    .catch(() => undefined);
};

export const getChatHistory = async (userKey: string): Promise<StoredChatState | null> => {
  try {
    const res = await ragClient.get<StoredChatState>(`/chat/history/${encodeURIComponent(userKey)}`, {
      timeout: 5000,
    });
    return res.data;
  } catch {
    return null;
  }
};

export const saveChatHistory = (userKey: string, state: StoredChatState) => {
  return ragClient
    .put<StoredChatState>(`/chat/history/${encodeURIComponent(userKey)}`, state, { timeout: 5000 })
    .catch(() => undefined);
};

export const deleteChatHistorySession = (userKey: string, sessionId: string) => {
  return ragClient
    .delete<StoredChatState>(
      `/chat/history/${encodeURIComponent(userKey)}/sessions/${encodeURIComponent(sessionId)}`,
      { timeout: 5000 }
    )
    .then((res) => res.data)
    .catch(() => null);
};

const USER_KNOWLEDGE_CATEGORIES = new Set(["user_knowledge", "user_response_rule"]);

export const normalizeSources = (sources?: RawChatSource[]): ChatSource[] => {
  if (!sources) return [];
  return sources
    .filter((item) => !USER_KNOWLEDGE_CATEGORIES.has(item.category ?? ""))
    .map((item) => ({
      source: item.source ?? "",
      // Không fallback title về item.source nữa — để nguyên giá trị API trả (có thể là title thật
      // hoặc filename), bestSourceTitle() sẽ tự phân biệt và xử lý khi hiển thị.
      title: item.title ?? item.document_title ?? "",
      url: item.url ?? item.source_url ?? "",
      filename: item.filename ?? "",
      category: item.category ?? "",
      similarity: item.similarity ?? 0,
    }));
};

const humanizeSlug = (slug: string) =>
  slug
    .replace(/\.(html?|php|aspx?)$/i, "")
    .replace(/[-_]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());

const deriveTitleFromUrl = (url?: string): string => {
  if (!url) return "";
  try {
    const { pathname } = new URL(url);
    const segments = pathname.split("/").filter(Boolean);
    const last = segments[segments.length - 1];
    if (!last) return "";
    const decoded = decodeURIComponent(last);
    // Bỏ qua nếu là ID/hash vô nghĩa (toàn số hoặc chuỗi hex dài)
    if (/^[0-9a-f]{6,}$/i.test(decoded) || /^\d+$/.test(decoded)) return "";
    return humanizeSlug(decoded);
  } catch {
    return "";
  }
};

/**
 * Nhận diện title dạng "tên file lưu trong máy" thay vì tiêu đề bài viết thật.
 * Dấu hiệu: có domain nhúng bên trong (vd "_com_", "_org_"), dùng "__" để phân tách
 * các phần (category__domain__slug), hoặc hoàn toàn không có khoảng trắng nhưng
 * có nhiều dấu _ / - liên tiếp.
 */
const looksLikeFilename = (title: string): boolean => {
  if (!title) return false;
  if (/_(com|org|net|vn|edu|gov)_/i.test(title)) return true;
  if (title.includes("__")) return true;
  const hasSpaces = /\s/.test(title);
  const separatorCount = (title.match(/[_-]/g) || []).length;
  if (!hasSpaces && separatorCount >= 3) return true;
  return false;
};

/**
 * Nếu title là dạng filename, cố gắng "làm sạch" nó: bỏ phần category/domain phía
 * trước (trước dấu "__" cuối cùng) rồi humanize phần slug còn lại.
 */
const humanizeFilenameTitle = (title: string): string => {
  const parts = title.split("__").filter(Boolean);
  const lastPart = parts[parts.length - 1] || title;
  return humanizeSlug(lastPart);
};

/**
 * Trả về tiêu đề tốt nhất có thể cho một nguồn:
 * 1. title thật từ API (nếu không có dấu hiệu là tên file)
 * 2. suy từ slug cuối cùng của URL
 * 3. làm sạch từ title dạng filename (nếu URL không suy ra được)
 * 4. filename / source / "Nguồn N"
 */
export const bestSourceTitle = (source: ChatSource, index = 0): string => {
  const rawTitle = source.title?.trim();
  const isFilenameLike = rawTitle ? looksLikeFilename(rawTitle) : false;

  if (rawTitle && !isFilenameLike) return rawTitle;

  const fromUrl = deriveTitleFromUrl(source.url);
  if (fromUrl) return fromUrl;

  if (rawTitle && isFilenameLike) return humanizeFilenameTitle(rawTitle);
  if (rawTitle) return rawTitle;

  if (source.filename?.trim()) return source.filename.trim();
  if (source.source?.trim()) return source.source.trim();
  return `Nguồn ${index + 1}`;
};

export const sourceLabel = (source: ChatSource, maxLength = 34): string => {
  const label = bestSourceTitle(source);
  return label.length <= maxLength ? label : `${label.slice(0, maxLength - 1)}…`;
};
