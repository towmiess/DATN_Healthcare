export const API_URL = import.meta.env.VITE_API_URL;

// Base URL của service Healthcare RAG (chatbot) - service Python/FastAPI độc lập,
// không dùng chung auth với API chính. Mặc định trỏ localhost:8000 khi dev.
export const RAG_API_URL =
  import.meta.env.VITE_RAG_API_URL ?? "http://localhost:8000";