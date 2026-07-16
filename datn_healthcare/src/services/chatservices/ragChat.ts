import { apiClient } from "@/api/Fetcher";
import type {
  ChatSessionRequest,
  ChatSessionResponse,
  ChatSource,
  RagHealth,
  RawChatSource,
  StoredChatState,
} from "@/types/ChatType";

const RAG_PREFIX = "/rag";

export const getRagHealth = async (): Promise<RagHealth | null> => {
  try {
    const res = await apiClient.get<RagHealth>(`${RAG_PREFIX}/health`, { timeout: 4000 });
    return res.data;
  } catch {
    return null;
  }
};

export const sendChatMessage = (payload: ChatSessionRequest) => {
  return apiClient.post<ChatSessionResponse>(`${RAG_PREFIX}/chat/session`, payload, {
    timeout: 240000,
  });
};

export const deleteChatSession = (sessionId: string) => {
  return apiClient
    .delete(`${RAG_PREFIX}/chat/session/${sessionId}`, { timeout: 5000 })
    .catch(() => undefined);
};

export const getChatHistory = async (userKey: string): Promise<StoredChatState | null> => {
  try {
    const res = await apiClient.get<StoredChatState>(
      `${RAG_PREFIX}/chat/history/${encodeURIComponent(userKey)}`,
      { timeout: 5000 }
    );
    return res.data;
  } catch {
    return null;
  }
};

export const saveChatHistory = (userKey: string, state: StoredChatState) => {
  return apiClient
    .put<StoredChatState>(`${RAG_PREFIX}/chat/history/${encodeURIComponent(userKey)}`, state, {
      timeout: 5000,
    })
    .catch(() => undefined);
};

export const deleteChatHistorySession = (userKey: string, sessionId: string) => {
  return apiClient
    .delete<StoredChatState>(
      `${RAG_PREFIX}/chat/history/${encodeURIComponent(userKey)}/sessions/${encodeURIComponent(sessionId)}`,
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
    if (/^[0-9a-f]{6,}$/i.test(decoded) || /^\d+$/.test(decoded)) return "";
    return humanizeSlug(decoded);
  } catch {
    return "";
  }
};

const looksLikeFilename = (title: string): boolean => {
  if (!title) return false;
  if (/_(com|org|net|vn|edu|gov)_/i.test(title)) return true;
  if (title.includes("__")) return true;
  const hasSpaces = /\s/.test(title);
  const separatorCount = (title.match(/[_-]/g) || []).length;
  if (!hasSpaces && separatorCount >= 3) return true;
  return false;
};

const humanizeFilenameTitle = (title: string): string => {
  const parts = title.split("__").filter(Boolean);
  const lastPart = parts[parts.length - 1] || title;
  return humanizeSlug(lastPart);
};

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
