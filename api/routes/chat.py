"""
Chat API Routes

Endpoints for AI chat assistant functionality.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import logging

from services.chat_assistant import ChatAssistant
from storage.database import get_db, ChatHistory
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# Initialize chat assistant
chat_assistant = ChatAssistant()


class ChatMessageRequest(BaseModel):
    """Request model for sending a chat message."""
    message: str
    session_id: Optional[str] = None
    user_id: Optional[int] = None


class ChatMessageResponse(BaseModel):
    """Response model for chat message."""
    response: str
    session_id: str
    timestamp: datetime


class ChatHistoryResponse(BaseModel):
    """Response model for chat history."""
    messages: List[dict]
    session_id: str


@router.post("/message", response_model=ChatMessageResponse)
async def send_message(
    request: ChatMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message to the AI chat assistant.
    
    Args:
        request: Chat message request
        db: Database session
        
    Returns:
        AI response with session info
    """
    try:
        # Generate session ID if not provided
        session_id = request.session_id or f"session_{datetime.now().timestamp()}"
        
        # Get chat history for context
        result = await db.execute(
            select(ChatHistory)
            .where(ChatHistory.session_id == session_id)
            .order_by(ChatHistory.created_at)
        )
        history = result.scalars().all()
        
        history_dicts = [
            {"role": msg.role, "message": msg.message}
            for msg in history
        ]
        
        # Get AI response
        ai_response = await chat_assistant.get_response(
            user_message=request.message,
            chat_history=history_dicts,
            user_id=request.user_id
        )
        
        # Save user message to database
        user_msg = ChatHistory(
            user_id=request.user_id,
            session_id=session_id,
            role="user",
            message=request.message
        )
        db.add(user_msg)
        
        # Save AI response to database
        ai_msg = ChatHistory(
            user_id=request.user_id,
            session_id=session_id,
            role="assistant",
            message=ai_response
        )
        db.add(ai_msg)
        db.add(ai_msg)
        await db.commit()
        
        return ChatMessageResponse(
            response=ai_response,
            session_id=session_id,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get chat history for a session.
    
    Args:
        session_id: Chat session ID
        db: Database session
        
    Returns:
        List of messages in the session
    """
    try:
        result = await db.execute(
            select(ChatHistory)
            .where(ChatHistory.session_id == session_id)
            .order_by(ChatHistory.created_at)
        )
        messages = result.scalars().all()
        
        message_dicts = [
            {
                "id": msg.id,
                "role": msg.role,
                "message": msg.message,
                "created_at": msg.created_at.isoformat()
            }
            for msg in messages
        ]
        
        return ChatHistoryResponse(
            messages=message_dicts,
            session_id=session_id
        )
        
    except Exception as e:
        logger.error(f"Error retrieving chat history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/suggestions")
async def get_suggestions():
    """
    Get suggested questions for quick replies.
    
    Returns:
        List of suggested questions
    """
    try:
        suggestions = await chat_assistant.get_suggested_questions()
        return {"suggestions": suggestions}
        
    except Exception as e:
        logger.error(f"Error getting suggestions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/history/{session_id}")
async def delete_chat_history(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete chat history for a session.
    
    Args:
        session_id: Chat session ID
        db: Database session
        
    Returns:
        Success message
    """
    try:
        await db.execute(
            delete(ChatHistory)
            .where(ChatHistory.session_id == session_id)
        )
        await db.commit()
        
        return {"message": "Chat history deleted successfully"}
        
    except Exception as e:
        logger.error(f"Error deleting chat history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
