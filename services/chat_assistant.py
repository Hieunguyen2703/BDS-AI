"""
AI Chat Assistant Service for Real Estate Consultation

This service provides RAG-based conversational AI to help users with:
- Property recommendations
- Market analysis
- Real estate terminology
- Location comparisons
"""

from typing import List, Dict, Optional
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from storage.vector_db import semantic_search
from config import settings

logger = logging.getLogger(__name__)


class ChatAssistant:
    """AI Chat Assistant for real estate consultation."""
    
    SYSTEM_PROMPT = """Bạn là trợ lý AI thân thiện và hữu ích có khả năng:

1. **Trả lời câu hỏi chung**: Bạn có thể trò chuyện về nhiều chủ đề khác nhau (thời tiết, công nghệ, cuộc sống hàng ngày, v.v.)

2. **Tư vấn bất động sản**: Khi được hỏi về BĐS tại Hà Nội, bạn sẽ dựa vào dữ liệu thực từ hệ thống để:
   - Tư vấn mua/bán nhà đất dựa trên ngân sách
   - Giải thích thuật ngữ bất động sản (sổ hồng, sổ đỏ, pháp lý...)
   - So sánh các quận/khu vực về giá cả, tiện ích
   - Phân tích xu hướng thị trường

Quy tắc:
- Luôn trả lời bằng tiếng Việt, thân thiện và dễ hiểu
- Nếu không chắc chắn, hãy thừa nhận và đề xuất cách tìm thêm
- Khi có context BĐS, ưu tiên dựa vào dữ liệu thực
- Giữ câu trả lời ngắn gọn (2-3 đoạn văn)

Context từ database BĐS (nếu có):
{context}

Lịch sử hội thoại:
{chat_history}
"""

    def __init__(self):
        """Initialize chat assistant."""
        self.llm = ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=0.7
        )
        
    async def get_response(
        self,
        user_message: str,
        chat_history: List[Dict[str, str]] = None,
        user_id: Optional[int] = None
    ) -> str:
        """
        Generate AI response for user message.
        
        Args:
            user_message: User's question/message
            chat_history: Previous conversation history
            user_id: Optional user ID for personalization
            
        Returns:
            AI-generated response
        """
        try:
            # 1. Try to retrieve relevant context from vector DB (real estate queries)
            context = await self._get_relevant_context(user_message)
            
            # 2. Format chat history
            history_text = self._format_chat_history(chat_history or [])
            
            # 3. Build prompt
            prompt = self.SYSTEM_PROMPT.format(
                context=context,
                chat_history=history_text
            )
            
            # 4. Generate response
            messages = [
                SystemMessage(content=prompt),
                HumanMessage(content=user_message)
            ]
            
            response = self.llm.invoke(messages)
            
            logger.info(f"Chat response generated for user {user_id}")
            return response.content
            
        except Exception as e:
            logger.error(f"Error generating chat response: {e}")
            return f"Xin lỗi, tôi gặp sự cố khi xử lý câu hỏi của bạn: {str(e)}"
    
    async def _get_relevant_context(self, query: str, top_k: int = 3) -> str:
        """
        Retrieve relevant listings/data from vector store.
        
        Args:
            query: User's query
            top_k: Number of results to retrieve
            
        Returns:
            Formatted context string
        """
        try:
            # Check if query is related to real estate
            real_estate_keywords = ['nhà', 'bds', 'bất động sản', 'chung cư', 'căn hộ', 
                                   'giá', 'mua', 'bán', 'quận', 'phòng', 'tỷ']
            is_re_query = any(keyword in query.lower() for keyword in real_estate_keywords)
            
            if not is_re_query:
                return "Không có dữ liệu BĐS liên quan."
            
            # Search vector DB for relevant listings
            results = await semantic_search(query, n_results=top_k)
            
            if not results:
                return "Không tìm thấy dữ liệu BĐS phù hợp trong hệ thống."
            
            # Format results as context
            context_parts = []
            for i, result in enumerate(results, 1):
                context_parts.append(
                    f"{i}. {result.get('title', 'N/A')}\n"
                    f"   - Giá: {result.get('price_text', 'N/A')}\n"
                    f"   - Diện tích: {result.get('area_m2', 'N/A')} m²\n"
                    f"   - Quận: {result.get('district', 'N/A')}\n"
                    f"   - Loại: {result.get('property_type', 'N/A')}"
                )
            
            return "\n\n".join(context_parts)
            
        except Exception as e:
            logger.warning(f"Error retrieving context (non-critical): {e}")
            return "Không có dữ liệu BĐS liên quan."
    
    def _format_chat_history(self, history: List[Dict[str, str]]) -> str:
        """
        Format chat history for prompt.
        
        Args:
            history: List of message dicts with 'role' and 'message'
            
        Returns:
            Formatted history string
        """
        if not history:
            return "Chưa có lịch sử hội thoại."
        
        formatted = []
        for msg in history[-5:]:  # Only last 5 messages for context
            role = "Người dùng" if msg['role'] == 'user' else "Trợ lý"
            formatted.append(f"{role}: {msg['message']}")
        
        return "\n".join(formatted)
    
    async def get_suggested_questions(self) -> List[str]:
        """
        Get suggested questions for quick replies.
        
        Returns:
            List of suggested question strings
        """
        return [
            "Tôi có 5 tỷ, nên mua nhà ở quận nào?",
            "Sổ hồng và sổ đỏ khác nhau như thế nào?",
            "Giá nhà ở Cầu Giấy hiện tại ra sao?",
            "So sánh Thanh Xuân và Đống Đa",
            "Chung cư 2 phòng ngủ giá bao nhiêu?",
        ]
