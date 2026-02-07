"""
Simple Vector Store Service for RAG

Provides search functionality over ChromaDB vector store.
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Simple vector store service for semantic search."""
    
    def __init__(self):
        """Initialize vector store service."""
        try:
            from storage.vector_db import VectorDB
            self.vector_db = VectorDB()
        except Exception as e:
            logger.warning(f"VectorDB not available: {e}")
            self.vector_db = None
    
    async def search(self, query: str, limit: int = 5) -> List[Dict]:
        """
        Search for relevant listings in vector store.
        
        Args:
            query: Search query
            limit: Max results
            
        Returns:
            List of search results with metadata
        """
        try:
            if not self.vector_db:
                logger.warning("VectorDB not initialized")
                return []
            
            # Search vector store
            results = self.vector_db.search(query, limit=limit)
            
            if not results:
                return []
            
            # Format results
            formatted = []
            for result in results:
                formatted.append({
                    'id': result.get('id'),
                    'score': result.get('score', 0),
                    'metadata': result.get('metadata', {})
                })
            
            return formatted
            
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return []
