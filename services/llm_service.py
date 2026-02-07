"""
Simple LLM Service Wrapper

Provides a simple interface to call LLM (Gemini) for chat and analysis.
Includes fallback to local Ollama if Gemini is unavailable.
"""

import os
import logging
import asyncio
from typing import List, Dict, Optional
import google.generativeai as genai
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

from config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """Simple LLM service using Gemini with Ollama fallback."""
    
    def __init__(self):
        """Initialize LLM service."""
        # 1. Setup Gemini
        api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning("GEMINI_API_KEY not found, LLM features will use Ollama only")
            self.gemini_available = False
        else:
            genai.configure(api_key=api_key)
            self.gemini_available = True
        
        self.model_name = settings.gemini_model
        self.gemini_model = genai.GenerativeModel(self.model_name)
        
        # 2. Setup Ollama (Fallback)
        self.ollama_llm = ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=0.7
        )
    
    async def chat(self, messages: List[Dict]) -> str:
        """
        Send chat messages to LLM.
        Tries Gemini first, falls back to Ollama if it fails (e.g. Quota Exceeded).
        """
        # Convert messages to string for Gemini and LangChain objects for Ollama
        prompt_parts = []
        lc_messages = []
        
        for msg in messages:
            if hasattr(msg, 'content'):
                # Already a LangChain message
                role = msg.__class__.__name__.replace('Message', '').lower()
                content = msg.content
                lc_messages.append(msg)
            else:
                # Dict format
                role = msg.get('role', 'user')
                content = msg.get('content', '')
                if role == 'system':
                    lc_messages.append(SystemMessage(content=content))
                elif role == 'assistant' or role == 'ai':
                    lc_messages.append(AIMessage(content=content))
                else:
                    lc_messages.append(HumanMessage(content=content))
            
            # Format for Gemini string prompt
            if role == 'system':
                prompt_parts.append(f"System Instructions:\n{content}\n")
            elif role == 'human' or role == 'user':
                prompt_parts.append(f"User: {content}")
            elif role == 'ai' or role == 'assistant':
                prompt_parts.append(f"Assistant: {content}")
        
        full_prompt = "\n\n".join(prompt_parts)

        # 1. Try Gemini
        if self.gemini_available:
            try:
                # Run Gemini call in a thread to keep it async friendly
                response = self.gemini_model.generate_content(full_prompt)
                if response and hasattr(response, 'text'):
                    return response.text
            except Exception as e:
                logger.warning(f"Gemini error, falling back to Ollama: {e}")
        
        # 2. Fallback to Ollama
        try:
            logger.info(f"Using Ollama fallback ({settings.ollama_model})...")
            response = await self.ollama_llm.ainvoke(lc_messages)
            return response.content
        except Exception as e:
            logger.error(f"Both Gemini and Ollama failed: {e}")
            return f"Xin lỗi, tôi gặp sự cố khi xử lý yêu cầu (LLM Error): {str(e)}"

