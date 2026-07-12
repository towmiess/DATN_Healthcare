import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  BrainCircuit,
  ChevronDown,
  History,
  Loader2,
  MessageCirclePlus,
  Send,
  Sparkles,
  Stethoscope,
  Trash2,
  User,
  X,
} from "lucide-react";
import {
  bestSourceTitle,
  deleteChatHistorySession,
  getChatHistory,
  getRagHealth,
  normalizeSources,
  saveChatHistory,
  sendChatMessage,
} from "@/services/chatservices/ragChat";
import type { ChatMessage, ChatSource, RagHealth, StoredChatSession, StoredChatState } from "@/types/ChatType";
import { formatChatAnswer } from "@/utils/formatChatAnswer";
import {
  EXAMPLE_QUESTIONS,
  ROUTE_ICON,
  WELCOME_TOPICS,
  detectTeachIntent,
  getContextualFollowups,
} from "./chatData";
import "./Chatbot.scss";

const createId = () =>
  typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `id-${Date.now()}-${Math.random().toString(16).slice(2)}`;

const CHAT_HISTORY_KEY = "healthcare_chat_history";

// Chiều cao tối đa (px) của ô nhập trước khi bật cuộn dọc bên trong.
// Phải khớp với giá trị max-height của .chat-input-bar textarea trong Chatbot.scss.
const MAX_INPUT_HEIGHT = 160;

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

const getChatUserKey = () => {
  const payload = decodeJwtPayload(localStorage.getItem("accessToken"));
  const userId = payload?.user_id;
  const email = payload?.sub;
  return String(userId ?? email ?? "guest");
};

const getChatStorageKey = (userKey = getChatUserKey()) => {
  return `${CHAT_HISTORY_KEY}:${userKey}`;
};

const summarizeText = (text: string, limit = 96) => {
  const compact = text.replace(/\s+/g, " ").trim();
  if (!compact) return "";
  return compact.length > limit ? `${compact.slice(0, limit - 1)}…` : compact;
};

const buildSessionTitle = (messages: ChatMessage[]) => {
  const firstUser = [...messages].find((msg) => msg.role === "user")?.content;
  return summarizeText(firstUser ?? "Cuộc trò chuyện mới", 42) || "Cuộc trò chuyện mới";
};

const buildSessionPreview = (messages: ChatMessage[]) => {
  const lastMessage = [...messages].reverse().find((msg) => msg.role === "assistant" || msg.role === "user");
  return summarizeText(lastMessage?.content ?? "", 110);
};

const readChatState = (storageKey: string): StoredChatState => {
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

const writeChatState = (storageKey: string, state: StoredChatState) => {
  localStorage.setItem(storageKey, JSON.stringify(state));
};

const mergeChatStates = (localState: StoredChatState, remoteState: StoredChatState): StoredChatState => {
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

const Chatbot: React.FC = () => {
  const [userKey, setUserKey] = useState<string>("guest");
  const [storageKey, setStorageKey] = useState<string>(CHAT_HISTORY_KEY);
  const [sessionId, setSessionId] = useState<string>(createId());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [rememberKnowledge, setRememberKnowledge] = useState(false);
  const [health, setHealth] = useState<RagHealth | null>(null);
  const [activeSources, setActiveSources] = useState<ChatSource[] | null>(null);
  const [savedSessions, setSavedSessions] = useState<StoredChatSession[]>([]);
  const [historyPanelOpen, setHistoryPanelOpen] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const stickToBottomRef = useRef(true);
  const savedSessionsRef = useRef<StoredChatSession[]>([]);

  useEffect(() => {
    let mounted = true;
    getRagHealth().then((data) => {
      if (mounted) setHealth(data);
    });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;

    const hydrateChatHistory = async () => {
      const nextUserKey = getChatUserKey();
      const nextStorageKey = getChatStorageKey(nextUserKey);
      const localState = readChatState(nextStorageKey);
      const remoteState = await getChatHistory(nextUserKey);
      const nextState = remoteState ? mergeChatStates(localState, remoteState) : localState;

      if (!mounted) return;

      setUserKey(nextUserKey);
      setStorageKey(nextStorageKey);

      if (nextState.sessions.length > 0) {
        const active =
          nextState.sessions.find((session) => session.sessionId === nextState.activeSessionId) ??
          nextState.sessions[0];
        setSessionId(active.sessionId);
        setMessages(active.messages ?? []);
        setSavedSessions(nextState.sessions);
        savedSessionsRef.current = nextState.sessions;
        writeChatState(nextStorageKey, nextState);
        if (remoteState) {
          void saveChatHistory(nextUserKey, nextState);
        }
      } else {
        setSessionId(createId());
        setMessages([]);
        setSavedSessions([]);
        savedSessionsRef.current = [];
      }
      setHydrated(true);
    };

    hydrateChatHistory();

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!stickToBottomRef.current) return;
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, loading]);

  useEffect(() => {
    if (!hydrated) return;

    const hasMessages = messages.length > 0;
    const nextSessions = [...savedSessionsRef.current];
    const existingIndex = nextSessions.findIndex((session) => session.sessionId === sessionId);

    if (hasMessages) {
      const snapshot: StoredChatSession = {
        sessionId,
        title: buildSessionTitle(messages),
        preview: buildSessionPreview(messages),
        updatedAt: Date.now(),
        messages,
      };

      if (existingIndex >= 0) {
        nextSessions[existingIndex] = snapshot;
      } else {
        nextSessions.unshift(snapshot);
      }
    }

    const nextState: StoredChatState = {
      activeSessionId: sessionId,
      sessions: nextSessions,
    };

    savedSessionsRef.current = nextSessions;
    setSavedSessions(nextSessions);
    writeChatState(storageKey, nextState);
    void saveChatHistory(userKey, nextState);
  }, [hydrated, messages, sessionId, storageKey, userKey]);

  // Tự động điều chỉnh chiều cao ô nhập theo nội dung: giãn cao dần khi câu hỏi
  // dài, tối đa MAX_INPUT_HEIGHT rồi mới bật thanh cuộn bên trong (không đẩy
  // layout tràn ra ngoài).
  const resizeInput = () => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    const nextHeight = Math.min(el.scrollHeight, MAX_INPUT_HEIGHT);
    el.style.height = `${nextHeight}px`;
    el.style.overflowY = el.scrollHeight > MAX_INPUT_HEIGHT ? "auto" : "hidden";
  };

  useEffect(() => {
    resizeInput();
  }, [input]);

  const syncSavedSessions = (nextSessions: StoredChatSession[], nextActiveSessionId = sessionId) => {
    const nextState = {
      activeSessionId: nextActiveSessionId,
      sessions: nextSessions,
    };
    savedSessionsRef.current = nextSessions;
    setSavedSessions(nextSessions);
    writeChatState(storageKey, nextState);
    void saveChatHistory(userKey, nextState);
  };

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    stickToBottomRef.current = distanceFromBottom < 120;
  };

  const lastAssistantIndex = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
      if (messages[i].role === "assistant") return i;
    }
    return -1;
  }, [messages]);

  const followups = useMemo(() => {
    if (lastAssistantIndex < 0 || messages.length < 2) return [];
    const lastAssistantAnswer = messages[lastAssistantIndex]?.content ?? "";
    const lastUserQuestion =
      messages
        .slice(0, lastAssistantIndex)
        .reverse()
        .find((m) => m.role === "user")?.content ?? "";
    return getContextualFollowups(lastUserQuestion, lastAssistantAnswer);
  }, [lastAssistantIndex, messages]);

  const orderedSessions = useMemo(
    () => [...savedSessions].sort((a, b) => b.updatedAt - a.updatedAt),
    [savedSessions]
  );

  const handleNewChat = () => {
    setSessionId(createId());
    setMessages([]);
    setActiveSources(null);
    setInput("");
    stickToBottomRef.current = true;
  };

  /*
  const handleDeleteCurrentChat = async () => {
    const nextSessionId = createId();
    const nextSessions = savedSessions.filter((session) => session.sessionId !== sessionId);
    try {
      await deleteChatSession(sessionId);
    } catch {
      // Xóa local vẫn tiếp tục để người dùng không bị kẹt UI.
    }
    syncSavedSessions(nextSessions, nextSessionId);
    setSessionId(nextSessionId);
    setMessages([]);
    setActiveSources(null);
    setInput("");
    stickToBottomRef.current = true;
  };
  */

  const handleOpenSession = (nextSession: StoredChatSession) => {
    setSessionId(nextSession.sessionId);
    setMessages(nextSession.messages ?? []);
    setActiveSources(null);
    stickToBottomRef.current = true;
  };

  const handleDeleteHistorySession = async (sessionToRemove: StoredChatSession) => {
    const nextSessions = savedSessions.filter((session) => session.sessionId !== sessionToRemove.sessionId);
    const isActive = sessionToRemove.sessionId === sessionId;
    const nextSessionId = isActive ? createId() : sessionId;
    try {
      await deleteChatHistorySession(userKey, sessionToRemove.sessionId);
    } catch {
      // Nếu backend chưa có session này nữa thì vẫn xóa local như bình thường.
    }
    syncSavedSessions(nextSessions, nextSessionId);
    if (isActive) {
      setSessionId(nextSessionId);
      setMessages([]);
      setActiveSources(null);
      stickToBottomRef.current = true;
    }
  };

  const handleSend = async (rawPrompt?: string) => {
    const prompt = (rawPrompt ?? input).trim();
    if (!prompt || loading) return;
    if (prompt.length < 3) return;

    const remember = rememberKnowledge || detectTeachIntent(prompt);

    const userMessage: ChatMessage = { id: createId(), role: "user", content: prompt };
    stickToBottomRef.current = true;
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);
    // Reset chiều cao textarea về mặc định ngay khi gửi, không đợi effect chạy
    // ở lần render kế (tránh giật hình 1 nhịp khi câu hỏi dài vừa gửi xong).
    requestAnimationFrame(() => resizeInput());

    const startedAt = Date.now();

    try {
      const res = await sendChatMessage({
        session_id: sessionId,
        message: prompt,
        top_k: 6,
        remember_knowledge: remember,
      });
      const data = res.data;
      const assistantMessage: ChatMessage = {
        id: createId(),
        role: "assistant",
        content: data.response || "Không có phản hồi",
        meta: {
          ms: data.response_time_ms ?? Date.now() - startedAt,
          chunks: data.chunks_used ?? 0,
          sources: normalizeSources(data.sources),
          route: data.route_type ?? "document",
        },
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (error: any) {
      const isTimeout = error?.code === "ECONNABORTED";
      const isNetwork = error?.message === "Network Error" || !error?.response;
      const content = isTimeout
        ? "⏱ Quá thời gian chờ. Thử lại hoặc kiểm tra lại kết nối."
        : isNetwork
        ? "❌ Không kết nối được tới dịch vụ chatbot. Vui lòng kiểm tra API RAG."
        : `❌ Lỗi: ${error?.response?.data?.detail ?? error?.message ?? "Không xác định"}`;
      setMessages((prev) => [...prev, { id: createId(), role: "assistant", content }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSend();
  };

  // Enter để gửi, Shift+Enter để xuống dòng (giữ hành vi quen thuộc của các ô
  // chat khác thay vì Enter luôn xuống dòng như textarea mặc định).
  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const statusOnline = Boolean(health);
  const ragReady = Boolean(health?.rag_ready);

  return (
    <div className="chat-page">
      <div className="chat-layout">
        <div className="chat-left-column">
          <div className="chat-header">
            <div className="chat-header__icon">
              <Stethoscope size={22} />
            </div>
            <div className="chat-header__content">
              <h1>DiabeCare</h1>
              <div className={`chat-status ${statusOnline ? "chat-status--on" : "chat-status--off"}`}>
                <span className="chat-status__dot" />
                {statusOnline ? (ragReady ? "Sẵn sàng" : "Đang khởi tạo") : "Ngoại tuyến"}
              </div>
            </div>
          </div>

          <aside className="chat-aside">
            <div className="chat-aside__actions">
              <button type="button" className="chat-new-btn" onClick={handleNewChat}>
                <MessageCirclePlus size={17} />
                Cuộc trò chuyện mới
              </button>

              <button
                type="button"
                className="chat-history-toggle"
                onClick={() => setHistoryPanelOpen((open) => !open)}
                aria-expanded={historyPanelOpen}
              >
                <span className="chat-history-toggle__label">
                  <History size={16} />
                  Lịch sử
                  {orderedSessions.length > 0 && (
                    <span className="chat-history-toggle__count">{orderedSessions.length}</span>
                  )}
                </span>
                <ChevronDown
                  size={16}
                  className={`chat-history-toggle__chevron ${historyPanelOpen ? "is-open" : ""}`}
                />
              </button>

              {historyPanelOpen && (
                <div className="chat-history-inline">
                  {orderedSessions.length === 0 ? (
                    <div className="chat-history-empty">
                      Chưa có lịch sử nào. Hãy bắt đầu một cuộc trò chuyện mới.
                    </div>
                  ) : (
                    orderedSessions.map((session) => (
                      <div
                        className={`chat-history-item ${session.sessionId === sessionId ? "is-active" : ""}`}
                        key={session.sessionId}
                      >
                        <button
                          type="button"
                          className="chat-history-item__main"
                          onClick={() => handleOpenSession(session)}
                        >
                          <div className="chat-history-item__title">{session.title}</div>
                          <div className="chat-history-item__meta">
                            <span>{new Date(session.updatedAt).toLocaleString("vi-VN")}</span>
                            {/**session.sessionId === sessionId && <span>Đang mở</span> */}
                          </div>
                        </button>
                        <button
                          type="button"
                          className="chat-history-item__delete"
                          title="Xóa cuộc trò chuyện này"
                          onClick={() => handleDeleteHistorySession(session)}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    ))
                  )}
                </div>
              )}
              {/*
              <button type="button" className="chat-delete-btn" onClick={handleDeleteCurrentChat}>
                <Trash2 size={16} />
                Xóa đoạn chat hiện tại
              </button>
              */}
            </div>

            {/*
            <p className="chat-aside__hint">
              Mẹo: bắt đầu câu bằng <code>/nho</code> hoặc <code>nhớ rằng…</code> để lưu ngay.
            </p>
            */}
            <div className="chat-aside__section-title">Các câu hỏi thường gặp</div>
            <div className="chat-examples">
              {EXAMPLE_QUESTIONS.map((q) => (
                <button
                  type="button"
                  key={q}
                  className="chat-example-btn"
                  onClick={() => handleSend(q)}
                  disabled={loading}
                >
                  {q}
                </button>
              ))}
            </div>
          </aside>
        </div>

        <section className="chat-main">
          <div className="chat-scroll" ref={scrollRef} onScroll={handleScroll}>
            {messages.length === 0 && (
              <div className="chat-welcome">
                <div className="chat-welcome__emoji">👋</div>
                <div className="chat-welcome__title">Xin chào! Tôi có thể giúp gì cho bạn?</div>
                <div className="chat-welcome__subtitle">
                  Hỏi về tiểu đường, biến chứng, thuốc, chế độ ăn và nhiều hơn nữa.
                </div>
                <div className="chat-topics">
                  {WELCOME_TOPICS.map((topic) => (
                    <div className="chat-topic-card" key={topic.label}>
                      <div className="chat-topic-card__label">
                        <span>{topic.icon}</span> {topic.label}
                      </div>
                      {topic.questions.map((q) => (
                        <button
                          type="button"
                          key={q}
                          className="chat-topic-card__q"
                          onClick={() => handleSend(q)}
                          disabled={loading}
                        >
                          → {q}
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {messages.map((msg, idx) => (
              <div key={msg.id} className={`chat-bubble-row chat-bubble-row--${msg.role}`}>
                <div className="chat-avatar">
                  {msg.role === "user" ? <User size={16} /> : <Stethoscope size={16} />}
                </div>
                <div className="chat-bubble-col">
                  <div className={`chat-bubble chat-bubble--${msg.role}`}>
                    {msg.role === "assistant" ? (
                      <div dangerouslySetInnerHTML={{ __html: formatChatAnswer(msg.content) }} />
                    ) : (
                      msg.content
                    )}
                  </div>

                  {msg.meta && (
                    <div className="chat-meta">
                      <span>⏱ {msg.meta.ms.toLocaleString()}ms</span>
                      {msg.meta.route && (
                        <span>
                          {ROUTE_ICON[msg.meta.route] ?? "🔀"} {msg.meta.route}
                        </span>
                      )}
                      {msg.meta.sources.length > 0 && (
                        <button
                          type="button"
                          className="chat-meta__sources-btn"
                          onClick={() => setActiveSources(msg.meta!.sources)}
                        >
                          📚 Sources ({msg.meta.sources.length})
                        </button>
                      )}
                    </div>
                  )}

                  {idx === lastAssistantIndex && followups.length > 0 && (
                    <div className="chat-followups">
                      <div className="chat-followups__title">
                        <Sparkles size={13} /> Câu hỏi liên quan
                      </div>
                      {followups.map((fq) => (
                        <button
                          type="button"
                          key={fq}
                          className="chat-followups__item"
                          onClick={() => handleSend(fq)}
                          disabled={loading}
                        >
                          {fq}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="chat-bubble-row chat-bubble-row--assistant">
                <div className="chat-avatar">
                  <Stethoscope size={16} />
                </div>
                <div className="chat-bubble chat-bubble--assistant chat-bubble--loading">
                  <Loader2 size={15} className="chat-spin" />
                  Đang phân tích tài liệu và soạn câu trả lời…
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          <form className="chat-input-bar" onSubmit={onSubmit}>
            <div className="chat-input-box">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleInputKeyDown}
                placeholder="Nhập câu hỏi về tiểu đường, biến chứng, thuốc, chế độ ăn…"
                disabled={loading}
                rows={1}
              />
              <button
                type="button"
                className={`chat-remember-toggle chat-remember-toggle--input ${rememberKnowledge ? "is-active" : ""}`}
                onClick={() => setRememberKnowledge((value) => !value)}
                aria-pressed={rememberKnowledge}
                title="Ghi nhớ câu này vào tri thức"
                disabled={loading}
              >
                <BrainCircuit size={18} />
              </button>
            </div>
            <button className="chat-send-btn" type="submit" disabled={loading || input.trim().length === 0}>
              {loading ? <Loader2 size={17} className="chat-spin" /> : <Send size={17} />}
            </button>
          </form>
        </section>
      </div>

      {activeSources && (
        <div className="chat-modal-overlay" onClick={() => setActiveSources(null)}>
          <div className="chat-modal" onClick={(e) => e.stopPropagation()}>
            <div className="chat-modal__header">
              <h3>Nguồn tài liệu</h3>
              <button type="button" onClick={() => setActiveSources(null)}>
                <X size={18} />
              </button>
            </div>
            <p className="chat-modal__caption">{activeSources.length} nguồn khớp với câu trả lời</p>
            <div className="chat-modal__list">
              {activeSources.map((source, index) => (
                <div className="chat-source-card" key={`${source.source}-${index}`}>
                  <div className="chat-source-card__meta">
                    {index + 1}. {source.category}
                    {source.similarity ? ` • ${source.similarity.toFixed(3)}` : ""}
                  </div>
                  <div className="chat-source-card__title">
                    {bestSourceTitle(source, index)}
                  </div>
                  {source.url ? (
                    <a href={source.url} target="_blank" rel="noreferrer">
                      {source.url}
                    </a>
                  ) : (
                    <span className="chat-source-card__no-url">Không có URL web gốc</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Chatbot;
