import React, { useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Maximize2, MessageCirclePlus, Send, Sparkles, Stethoscope, User, X } from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";
import {
  getChatHistory,
  getRagHealth,
  normalizeSources,
  saveChatHistory,
  sendChatMessage,
} from "@/services/chatservices/ragChat";
import type { ChatMessage, RagHealth, StoredChatSession, StoredChatState } from "@/types/ChatType";
import { formatChatAnswer } from "@/utils/formatChatAnswer";
import {
  buildSessionPreview,
  buildSessionTitle,
  createChatId,
  getChatStorageKey,
  getChatUserKey,
  mergeChatStates,
  readChatState,
  writeChatState,
} from "@/utils/chatHistory";
import { WELCOME_TOPICS, getContextualFollowups } from "@/pages/user/Chatbot/chatData";
import "./FloatingChatWidget.scss";

const BUBBLE_POS_KEY = "diabecare_widget_bubble_pos";
const BUBBLE_SIZE = 62;
const VIEWPORT_PADDING = 14;
const POPUP_GAP = 14;
const POPUP_BOTTOM_OFFSET = 20;
const DEFAULT_POPUP_SIZE = { width: 456, height: 560 };
const MIN_POPUP_SIZE = { width: 320, height: 420 };
const DRAG_CLICK_THRESHOLD = 4;

type Point = {
  x: number;
  y: number;
};

type Size = {
  width: number;
  height: number;
};

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

const getRightEdgeBubbleX = () => {
  if (typeof window === "undefined") return 24;
  return window.innerWidth - BUBBLE_SIZE - 28;
};

const getDefaultBubblePos = (): Point => {
  if (typeof window === "undefined") return { x: 24, y: 24 };
  return {
    x: getRightEdgeBubbleX(),
    y: window.innerHeight - BUBBLE_SIZE - 28,
  };
};

const clampBubblePos = (pos: Point): Point => {
  if (typeof window === "undefined") return pos;
  return {
    x: getRightEdgeBubbleX(),
    y: clamp(pos.y, VIEWPORT_PADDING, window.innerHeight - BUBBLE_SIZE - VIEWPORT_PADDING),
  };
};

const readBubblePos = (): Point => {
  try {
    const raw = localStorage.getItem(BUBBLE_POS_KEY);
    if (!raw) return clampBubblePos(getDefaultBubblePos());
    const parsed = JSON.parse(raw) as Partial<Point>;
    if (typeof parsed.x !== "number" || typeof parsed.y !== "number") {
      return clampBubblePos(getDefaultBubblePos());
    }
    return clampBubblePos({ x: getRightEdgeBubbleX(), y: parsed.y });
  } catch {
    return clampBubblePos(getDefaultBubblePos());
  }
};

const persistBubblePos = (pos: Point) => {
  localStorage.setItem(BUBBLE_POS_KEY, JSON.stringify(pos));
};

const clampPopupSize = (size: Size): Size => {
  if (typeof window === "undefined") return size;
  const maxWidth = Math.max(MIN_POPUP_SIZE.width, window.innerWidth - VIEWPORT_PADDING * 2);
  const maxHeight = Math.max(MIN_POPUP_SIZE.height, window.innerHeight - VIEWPORT_PADDING * 2);
  return {
    width: clamp(size.width, MIN_POPUP_SIZE.width, maxWidth),
    height: clamp(size.height, MIN_POPUP_SIZE.height, maxHeight),
  };
};

const getPopupPosition = (bubblePos: Point, popupSize: Size): Point => {
  if (typeof window === "undefined") return { x: 24, y: 24 };
  const centerX = bubblePos.x + BUBBLE_SIZE / 2;
  const preferredTop = bubblePos.y + BUBBLE_SIZE + POPUP_GAP;

  return {
    x: clamp(centerX - popupSize.width / 2, VIEWPORT_PADDING, window.innerWidth - popupSize.width - VIEWPORT_PADDING),
    y: clamp(
      preferredTop,
      VIEWPORT_PADDING,
      window.innerHeight - popupSize.height - VIEWPORT_PADDING - POPUP_BOTTOM_OFFSET
    ),
  };
};

const FloatingChatWidget: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const [isOpen, setIsOpen] = useState(false);
  const [isPopupClosing, setIsPopupClosing] = useState(false);
  const [bubblePos, setBubblePos] = useState<Point>(() => readBubblePos());
  const [popupSize, setPopupSize] = useState<Size>(() => clampPopupSize(DEFAULT_POPUP_SIZE));
  const [userKey, setUserKey] = useState("guest");
  const [storageKey, setStorageKey] = useState(() => getChatStorageKey("guest"));
  const [sessionId, setSessionId] = useState(() => createChatId());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState<RagHealth | null>(null);
  const [hydrated, setHydrated] = useState(false);

  const bottomRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const savedSessionsRef = useRef<StoredChatSession[]>([]);
  const dragRef = useRef<{
    pointerId: number;
    startPointer: Point;
    startPos: Point;
    moved: boolean;
  } | null>(null);
  const resizeRef = useRef<{
    pointerId: number;
    startPointer: Point;
    startSize: Size;
  } | null>(null);

  const popupPos = useMemo(() => getPopupPosition(bubblePos, popupSize), [bubblePos, popupSize]);
  const statusOnline = Boolean(health);
  const ragReady = Boolean(health?.rag_ready);
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
        .find((message) => message.role === "user")?.content ?? "";

    return getContextualFollowups(lastUserQuestion, lastAssistantAnswer).slice(0, 3);
  }, [lastAssistantIndex, messages]);

  const hydrateChatHistory = async () => {
    const nextUserKey = getChatUserKey();
    const nextStorageKey = getChatStorageKey(nextUserKey);
    const localState = readChatState(nextStorageKey);
    const remoteState = await getChatHistory(nextUserKey);
    const nextState = remoteState ? mergeChatStates(localState, remoteState) : localState;

    setUserKey(nextUserKey);
    setStorageKey(nextStorageKey);

    if (nextState.sessions.length > 0) {
      const active =
        nextState.sessions.find((session) => session.sessionId === nextState.activeSessionId) ?? nextState.sessions[0];
      setSessionId(active.sessionId);
      setMessages(active.messages ?? []);
      savedSessionsRef.current = nextState.sessions;
      writeChatState(nextStorageKey, nextState);
      if (remoteState) {
        void saveChatHistory(nextUserKey, nextState);
      }
    } else {
      const nextSessionId = createChatId();
      setSessionId(nextSessionId);
      setMessages([]);
      savedSessionsRef.current = [];
      writeChatState(nextStorageKey, { activeSessionId: nextSessionId, sessions: [] });
    }

    setHydrated(true);
  };

  useEffect(() => {
    let mounted = true;
    getRagHealth().then((data) => {
      if (mounted) setHealth(data);
    });
    hydrateChatHistory();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    void hydrateChatHistory();
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    bottomRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [isOpen, messages, loading]);

  useEffect(() => {
    if (!hydrated || messages.length === 0) return;

    const nextSessions = [...savedSessionsRef.current];
    const existingIndex = nextSessions.findIndex((session) => session.sessionId === sessionId);
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

    const nextState: StoredChatState = {
      activeSessionId: sessionId,
      sessions: nextSessions.sort((a, b) => b.updatedAt - a.updatedAt).slice(0, 50),
    };

    savedSessionsRef.current = nextState.sessions;
    writeChatState(storageKey, nextState);
    void saveChatHistory(userKey, nextState);
  }, [hydrated, messages, sessionId, storageKey, userKey]);

  useEffect(() => {
    const handleWindowResize = () => {
      setBubblePos((prev) => {
        const next = clampBubblePos(prev);
        persistBubblePos(next);
        return next;
      });
      setPopupSize((prev) => clampPopupSize(prev));
    };

    window.addEventListener("resize", handleWindowResize);
    return () => window.removeEventListener("resize", handleWindowResize);
  }, []);

  useEffect(() => {
    const handlePointerMove = (event: PointerEvent) => {
      const currentResize = resizeRef.current;
      if (!currentResize || event.pointerId !== currentResize.pointerId) return;
      event.preventDefault();
      const dx = event.clientX - currentResize.startPointer.x;
      const dy = event.clientY - currentResize.startPointer.y;
      setPopupSize(
        clampPopupSize({
          width: currentResize.startSize.width - dx,
          height: currentResize.startSize.height + dy,
        })
      );
    };

    const handlePointerUp = (event: PointerEvent) => {
      if (resizeRef.current?.pointerId === event.pointerId) {
        resizeRef.current = null;
      }
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    window.addEventListener("pointercancel", handlePointerUp);
    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
      window.removeEventListener("pointercancel", handlePointerUp);
    };
  }, []);

  const handleBubblePointerDown = (event: React.PointerEvent<HTMLButtonElement>) => {
    if (event.button !== 0) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = {
      pointerId: event.pointerId,
      startPointer: { x: event.clientX, y: event.clientY },
      startPos: bubblePos,
      moved: false,
    };
  };

  const handleBubblePointerMove = (event: React.PointerEvent<HTMLButtonElement>) => {
    const currentDrag = dragRef.current;
    if (!currentDrag || event.pointerId !== currentDrag.pointerId) return;
    const dy = event.clientY - currentDrag.startPointer.y;
    const dx = event.clientX - currentDrag.startPointer.x;
    if (Math.hypot(dx, dy) > DRAG_CLICK_THRESHOLD) {
      currentDrag.moved = true;
    }
    if (!currentDrag.moved) return;
    setBubblePos(clampBubblePos({ x: getRightEdgeBubbleX(), y: currentDrag.startPos.y + dy }));
  };

  const handleBubblePointerUp = (event: React.PointerEvent<HTMLButtonElement>) => {
    const currentDrag = dragRef.current;
    if (!currentDrag || event.pointerId !== currentDrag.pointerId) return;
    dragRef.current = null;
    const dy = event.clientY - currentDrag.startPointer.y;
    const nextPos = clampBubblePos({ x: getRightEdgeBubbleX(), y: currentDrag.startPos.y + dy });
    setBubblePos(nextPos);
    persistBubblePos(nextPos);

    if (!currentDrag.moved) {
      if (isOpen) {
        handleClosePopup();
      } else {
        setIsPopupClosing(false);
        setIsOpen(true);
      }
    }
  };

  const handleNewChat = () => {
    setSessionId(createChatId());
    setMessages([]);
    setInput("");
    inputRef.current?.focus();
  };

  const handleOpenFullChat = () => {
    setIsPopupClosing(true);
    window.setTimeout(() => {
      setIsOpen(false);
      setIsPopupClosing(false);
      navigate("/user/chat", { state: { from: location.pathname } });
    }, 150);
  };

  const handleClosePopup = () => {
    setIsPopupClosing(true);
    window.setTimeout(() => {
      setIsOpen(false);
      setIsPopupClosing(false);
    }, 170);
  };

  const handleResizePointerDown = (event: React.PointerEvent<HTMLButtonElement>) => {
    if (event.button !== 0) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    resizeRef.current = {
      pointerId: event.pointerId,
      startPointer: { x: event.clientX, y: event.clientY },
      startSize: popupSize,
    };
  };

  const handleSend = async (rawPrompt?: string) => {
    const prompt = (rawPrompt ?? input).trim();
    if (!prompt || loading || prompt.length < 3) return;

    const userMessage: ChatMessage = { id: createChatId(), role: "user", content: prompt };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);
    const startedAt = Date.now();

    try {
      const res = await sendChatMessage({
        session_id: sessionId,
        message: prompt,
        top_k: 6,
        remember_knowledge: false,
      });
      const data = res.data;
      const assistantMessage: ChatMessage = {
        id: createChatId(),
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
        ? "Quá thời gian chờ. Thử lại hoặc kiểm tra kết nối RAG."
        : isNetwork
        ? "Không kết nối được tới dịch vụ chatbot. Vui lòng kiểm tra API RAG."
        : `Lỗi: ${error?.response?.data?.detail ?? error?.message ?? "Không xác định"}`;
      setMessages((prev) => [...prev, { id: createChatId(), role: "assistant", content }]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    handleSend();
  };

  const handleInputKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="floating-chat-widget" aria-live="polite">
      {(isOpen || isPopupClosing) && (
        <section
          className={`floating-chat-widget__popup${isPopupClosing ? " is-closing" : ""}`}
          style={{
            left: popupPos.x,
            top: popupPos.y,
            width: popupSize.width,
            height: popupSize.height,
          }}
          aria-label="Chatbot tư vấn nhanh"
        >
          <header className="floating-chat-widget__header">
            <div className="floating-chat-widget__identity">
              <span className="floating-chat-widget__icon">
                <Stethoscope size={20} />
              </span>
              <span>
                <strong>DiabeCare</strong>
                <small>
                  <span className={statusOnline && ragReady ? "is-online" : "is-offline"} />
                  {statusOnline ? (ragReady ? "Sẵn sàng" : "Đang khởi tạo") : "Ngoại tuyến"}
                </small>
              </span>
            </div>

            <div className="floating-chat-widget__actions">
              <button type="button" onClick={handleNewChat} title="Cuộc trò chuyện mới">
                <MessageCirclePlus size={16} />
              </button>
              <button type="button" onClick={handleOpenFullChat} title="Mở trang đầy đủ">
                <Maximize2 size={16} />
              </button>
              <button type="button" onClick={handleClosePopup} title="Đóng">
                <X size={16} />
              </button>
            </div>
          </header>

          <div className="floating-chat-widget__messages">
            {messages.length === 0 && (
              <div className="floating-chat-widget__empty">
                <Stethoscope size={28} />
                <strong>Xin chào, mình có thể giúp gì?</strong>
                <span>Hỏi nhanh về tiểu đường, thuốc, biến chứng hoặc chế độ ăn.</span>
                <div className="floating-chat-widget__topics">
                  {WELCOME_TOPICS.slice(0, 4).map((topic) => (
                    <div className="floating-chat-widget__topic" key={topic.label}>
                      <div className="floating-chat-widget__topic-label">
                        <span>{topic.icon}</span>
                        {topic.label}
                      </div>
                      {topic.questions.slice(0, 2).map((question) => (
                        <button
                          type="button"
                          key={question}
                          onClick={() => handleSend(question)}
                          disabled={loading}
                        >
                          {question}
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {messages.map((message, index) => (
              <div
                className={`floating-chat-widget__message floating-chat-widget__message--${message.role}`}
                key={message.id}
              >
                <span className="floating-chat-widget__avatar" aria-hidden="true">
                  {message.role === "user" ? <User size={14} /> : <Stethoscope size={14} />}
                </span>
                <div className="floating-chat-widget__message-body">
                  <div
                    className="floating-chat-widget__bubble"
                    dangerouslySetInnerHTML={
                      message.role === "assistant" ? { __html: formatChatAnswer(message.content) } : undefined
                    }
                  >
                    {message.role === "user" ? message.content : undefined}
                  </div>

                  {index === lastAssistantIndex && followups.length > 0 && (
                    <div className="floating-chat-widget__followups">
                      <div className="floating-chat-widget__followups-title">
                        <Sparkles size={12} />
                        Gợi ý tiếp
                      </div>
                      {followups.map((question) => (
                        <button
                          type="button"
                          key={question}
                          onClick={() => handleSend(question)}
                          disabled={loading}
                        >
                          {question}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="floating-chat-widget__message floating-chat-widget__message--assistant">
                <span className="floating-chat-widget__avatar" aria-hidden="true">
                  <Stethoscope size={14} />
                </span>
                <div className="floating-chat-widget__message-body">
                  <div className="floating-chat-widget__bubble floating-chat-widget__bubble--loading">
                    <Loader2 size={15} className="floating-chat-widget__spin" />
                    Đang phân tích...
                  </div>
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          <form className="floating-chat-widget__input" onSubmit={handleSubmit}>
            <textarea
              ref={inputRef}
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={handleInputKeyDown}
              placeholder="Nhập câu hỏi..."
              rows={1}
              disabled={loading}
            />
            <button type="submit" disabled={loading || input.trim().length === 0} aria-label="Gửi">
              {loading ? <Loader2 size={17} className="floating-chat-widget__spin" /> : <Send size={17} />}
            </button>
          </form>

          <button
            type="button"
            className="floating-chat-widget__resize"
            onPointerDown={handleResizePointerDown}
            aria-label="Kéo giãn khung chat"
          />
        </section>
      )}

      {!isOpen && !isPopupClosing && (
        <button
          type="button"
          className={`floating-chat-widget__launcher${dragRef.current?.moved ? " is-dragging" : ""}`}
          style={{ left: bubblePos.x, top: bubblePos.y }}
          onPointerDown={handleBubblePointerDown}
          onPointerMove={handleBubblePointerMove}
          onPointerUp={handleBubblePointerUp}
          onPointerCancel={() => {
            dragRef.current = null;
          }}
          aria-label="Mở chatbot tư vấn nhanh"
          aria-expanded={false}
        >
          <Stethoscope size={27} />
        </button>
      )}
    </div>
  );
};

export default FloatingChatWidget;
