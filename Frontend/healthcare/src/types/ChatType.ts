export type ChatRole = "user" | "assistant";

export interface ChatSource {
  source: string;
  title: string;
  url: string;
  filename: string;
  category: string;
  similarity: number;
}

export interface ChatMeta {
  ms: number;
  chunks: number;
  sources: ChatSource[];
  route: string;
}

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  meta?: ChatMeta;
}

export interface StoredChatSession {
  sessionId: string;
  title: string;
  preview: string;
  updatedAt: number;
  messages: ChatMessage[];
}

export interface StoredChatState {
  activeSessionId: string;
  sessions: StoredChatSession[];
}

export interface ChatSessionRequest {
  session_id: string;
  message: string;
  top_k?: number;
  remember_knowledge?: boolean;
}

export interface ChatSessionResponse {
  response: string;
  response_time_ms?: number;
  chunks_used?: number;
  sources?: RawChatSource[];
  route_type?: string;
}

export interface RawChatSource {
  source?: string;
  title?: string;
  document_title?: string;
  url?: string;
  source_url?: string;
  filename?: string;
  category?: string;
  similarity?: number;
}

export interface RagHealth {
  rag_ready?: boolean;
  total_chunks?: number;
  session_store?: string;
  [key: string]: unknown;
}
