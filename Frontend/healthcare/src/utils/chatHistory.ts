import type { ChatMessage, StoredChatSession, StoredChatState } from "@/types/ChatType";

export const CHAT_HISTORY_KEY = "healthcare_chat_history";

const decodeBase64Url = (input: string) => {
  const padded = input.replace(/-/g, "+").replace(/_/g, "/");
  const padLength = (4 - (padded.length % 4)) % 4;
  const base64 = padded + "=".repeat(padLength);
  try {
    return atob(base64);
  } catch {
    return null;
  }
};

const decodeJwtPayload = (token: string | null) => {
  if (!token) return null;
  const parts = token.split(".");
  if (parts.length < 2) return null;
  const decoded = decodeBase64Url(parts[1]);
  if (!decoded) return null;
  try {
    return JSON.parse(decoded) as Record<string, unknown>;
  } catch {
    return null;
  }
};

export const createChatId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `id-${Date.now()}-${Math.random().toString(16).slice(2)}`;

export const getChatUserKey = () => {
  const payload = decodeJwtPayload(localStorage.getItem("accessToken"));
  const userId = payload?.user_id;
  const email = payload?.sub;
  return String(userId ?? email ?? "guest");
};

export const getChatStorageKey = (userKey = getChatUserKey()) => {
  return `${CHAT_HISTORY_KEY}:${userKey}`;
};

export const summarizeText = (text: string, limit = 96) => {
  const compact = text.replace(/\s+/g, " ").trim();
  if (!compact) return "";
  return compact.length > limit ? `${compact.slice(0, limit - 1)}…` : compact;
};

export const buildSessionTitle = (messages: ChatMessage[]) => {
  const firstUser = [...messages].find((msg) => msg.role === "user")?.content;
  return summarizeText(firstUser ?? "Cuộc trò chuyện mới", 42) || "Cuộc trò chuyện mới";
};

export const buildSessionPreview = (messages: ChatMessage[]) => {
  const lastMessage = [...messages].reverse().find((msg) => msg.role === "assistant" || msg.role === "user");
  return summarizeText(lastMessage?.content ?? "", 110);
};

export const readChatState = (storageKey: string): StoredChatState => {
  try {
    const raw = localStorage.getItem(storageKey);
    if (!raw) return { activeSessionId: "", sessions: [] };
    const parsed = JSON.parse(raw) as Partial<StoredChatState>;
    const sessions = Array.isArray(parsed.sessions)
      ? parsed.sessions.filter((session): session is StoredChatSession => Boolean(session && session.sessionId))
      : [];
    return {
      activeSessionId: typeof parsed.activeSessionId === "string" ? parsed.activeSessionId : "",
      sessions,
    };
  } catch {
    return { activeSessionId: "", sessions: [] };
  }
};

export const writeChatState = (storageKey: string, state: StoredChatState) => {
  localStorage.setItem(storageKey, JSON.stringify(state));
};

export const mergeChatStates = (localState: StoredChatState, remoteState: StoredChatState): StoredChatState => {
  const sessionMap = new Map<string, StoredChatSession>();
  [...localState.sessions, ...remoteState.sessions].forEach((session) => {
    const existing = sessionMap.get(session.sessionId);
    if (!existing || session.updatedAt >= existing.updatedAt) {
      sessionMap.set(session.sessionId, session);
    }
  });

  return {
    activeSessionId: remoteState.activeSessionId || localState.activeSessionId,
    sessions: [...sessionMap.values()]
      .sort((a, b) => b.updatedAt - a.updatedAt)
      .slice(0, 50),
  };
};

