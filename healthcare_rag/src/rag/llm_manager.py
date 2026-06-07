"""
================================================================
LLM MANAGER — Quản lý nhiều LLM backend
================================================================

Khi Gemini API vượt quota, tự động fallback sang:
1. Ollama (local, miễn phí, có thể cài offline)
2. Mock response (demo mode, không cần API key)

SETUP OLLAMA:
  1. Cài từ https://ollama.ai
  2. Chạy: ollama pull mistral (hoặc neural-chat, dolphin-mixtral)
  3. Ollama sẽ chạy ở http://localhost:11434
================================================================
"""

import os
import requests
from typing import List, Dict, Optional
from loguru import logger
from dotenv import load_dotenv

load_dotenv()


class LLMManager:
    """Quản lý LLM với fallback strategies."""

    def __init__(self):
        self.primary = "gemini"
        self.fallback_order = ["ollama", "mock"]
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "mistral")
        self.primary_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    def is_gemini_available(self) -> bool:
        """Kiểm tra Gemini API key."""
        return bool(self.primary_key and not self.primary_key.lower().startswith("xxx"))

    def is_ollama_available(self) -> bool:
        """Kiểm tra Ollama có chạy không."""
        try:
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            return resp.status_code == 200
        except:
            return False

    def get_available_backends(self) -> List[str]:
        """Danh sách LLM backend khả dụng."""
        available = []
        if self.is_gemini_available():
            available.append("gemini")
        if self.is_ollama_available():
            available.append("ollama")
        available.append("mock")  # Luôn có mock fallback
        return available

    def generate(self, system_prompt: str, user_query: str, context: str) -> str:
        """Sinh câu trả lời từ available backend."""
        
        backends = self.get_available_backends()
        logger.info(f"Available LLM backends: {backends}")

        # Thử Gemini trước
        if "gemini" in backends:
            result = self._try_gemini(system_prompt, user_query, context)
            if result:
                return result

        # Fallback sang Ollama
        if "ollama" in backends:
            logger.warning("⚠ Gemini không available, fallback sang Ollama...")
            result = self._try_ollama(system_prompt, user_query, context)
            if result:
                return result

        # Cuối cùng dùng mock
        logger.warning("⚠ Cả Gemini và Ollama đều không available, dùng mock response...")
        return self._mock_response(user_query, context)

    def _try_gemini(self, system_prompt: str, user_query: str, context: str) -> Optional[str]:
        """Cố gắng gọi Gemini API."""
        try:
            from src.rag.pipeline import RAGPipeline
            # Sử dụng pipeline hiện tại nếu khả dụng
            pipeline = RAGPipeline()
            # Tạo full prompt
            full_prompt = f"{system_prompt}\n\nContext:\n{context}\n\nUser: {user_query}"
            response = pipeline.query(user_query)
            return response
        except Exception as e:
            logger.error(f"❌ Gemini error: {e}")
            return None

    def _try_ollama(self, system_prompt: str, user_query: str, context: str) -> Optional[str]:
        """Cố gắng gọi Ollama."""
        try:
            prompt = f"{system_prompt}\n\nContext:\n{context}\n\nUser: {user_query}\n\nAnswer:"
            
            resp = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": 0.2,
                },
                timeout=60,
            )
            
            if resp.status_code == 200:
                data = resp.json()
                return data.get("response", "").strip()
            
            logger.error(f"Ollama error: {resp.text}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Ollama error: {e}")
            return None

    def _mock_response(self, user_query: str, context: str) -> str:
        """Mock response cho demo mode."""
        query_lower = user_query.lower()
        
        mock_responses = {
            "phở": "Phở có chỉ số GI cao (65-70), làm tăng đường huyết nhanh. Bạn nên:\n1. Đo đường huyết ngay\n2. Ăn chậm, nhai kỹ\n3. Kết hợp rau xanh, protein\n4. Uống nước nhiều\nNếu đường huyết quá cao (>250 mg/dL), liên hệ bác sĩ.",
            "ăn": "Chế độ ăn tiểu đường nên:\n• Ưu tiên: rau xanh, cá, dùu, trứng\n• Hạn chế: bánh, mì, nước ngọt\n• Chia nhỏ bữa ăn (5-6 lần/ngày)\n• Uống 2-3L nước/ngày",
            "uống thuốc": "Bạn nên tuân thủ đơn của bác sĩ:\n• Uống đúng giờ, đúng liều\n• Không tự ý ngừng hoặc tăng liều\n• Theo dõi tác dụng phụ\n• Kiểm tra định kỳ HbA1c hàng 3 tháng",
            "chỉ số": "Chỉ số glucose bình thường:\n• Lúc đói: < 100 mg/dL\n• Sau ăn 2h: < 140 mg/dL\n• HbA1c: < 5.7% (bình thường), 5.7-6.4% (tiền tiểu đường)",
        }
        
        for keyword, response in mock_responses.items():
            if keyword in query_lower:
                return response
        
        # Default response
        return (
            "Xin lỗi, hiện tại hệ thống đang trong chế độ offline. "
            "Dữ liệu có sẵn:\n"
            f"- Bạn hỏi: {user_query[:100]}\n"
            f"- Có {len(context)} ký tự tài liệu liên quan\n\n"
            "Vui lòng cài Ollama hoặc chờ Gemini API reset quota (24h)."
        )


def create_llm_manager() -> LLMManager:
    """Factory function."""
    return LLMManager()
