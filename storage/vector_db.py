"""
ChromaDB Vector Database Wrapper.
Provides semantic search capabilities for real estate listings.
"""

import hashlib
from datetime import datetime
from typing import Any, Optional
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings
from chromadb.utils import embedding_functions
from loguru import logger

from config import settings


class VectorDB:
    """
    ChromaDB wrapper for semantic search on listings.
    Uses sentence-transformers for embeddings (free, local).
    """

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        collection_name: Optional[str] = None,
        embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2",
    ):
        """
        Initialize ChromaDB client.

        Args:
            persist_dir: Directory to persist ChromaDB data
            collection_name: Name of the collection
            embedding_model: Sentence-transformer model name (multilingual for Vietnamese)
        """
        self.persist_dir = Path(persist_dir or settings.chroma_persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)

        self.collection_name = collection_name or settings.chroma_collection_name
        self.embedding_model = embedding_model

        # Initialize ChromaDB client with persistence
        self._client = chromadb.PersistentClient(
            path=str(self.persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False)
        )

        # Use sentence-transformers for Vietnamese text
        # This model supports 50+ languages including Vietnamese
        self._embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )

        # Get or create collection
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self._embedding_fn,
            metadata={"description": "Real estate listings for semantic search"}
        )

        logger.info(
            f"Initialized VectorDB: collection={self.collection_name}, "
            f"model={embedding_model}, count={self._collection.count()}"
        )

    @property
    def count(self) -> int:
        """Get number of documents in collection."""
        return self._collection.count()

    def _create_document(self, listing: dict) -> str:
        """
        Create searchable document text from listing.
        Combines relevant fields for semantic search.
        """
        parts = []

        # Title is most important
        if listing.get("title"):
            parts.append(listing["title"])

        # Property type
        if listing.get("property_type"):
            parts.append(f"Loại: {listing['property_type']}")

        # Location
        location = listing.get("location", {})
        if isinstance(location, dict):
            loc_parts = []
            if location.get("address"):
                loc_parts.append(location["address"])
            if location.get("ward"):
                loc_parts.append(location["ward"])
            if location.get("district"):
                loc_parts.append(location["district"])
            if location.get("city"):
                loc_parts.append(location["city"])
            if loc_parts:
                parts.append(f"Địa chỉ: {', '.join(loc_parts)}")
        elif isinstance(location, str):
            parts.append(f"Địa chỉ: {location}")

        # Price
        if listing.get("price_text"):
            parts.append(f"Giá: {listing['price_text']}")

        # Area
        if listing.get("area_m2"):
            parts.append(f"Diện tích: {listing['area_m2']} m²")

        # Bedrooms
        if listing.get("bedrooms"):
            parts.append(f"{listing['bedrooms']} phòng ngủ")

        # Description (truncated)
        if listing.get("description"):
            desc = listing["description"][:500]
            parts.append(desc)

        # Features
        features = listing.get("features", [])
        if features:
            parts.append(f"Đặc điểm: {', '.join(features)}")

        return " | ".join(parts)

    def _create_metadata(self, listing: dict) -> dict:
        """Create metadata dict for ChromaDB storage."""
        location = listing.get("location", {})
        if isinstance(location, dict):
            district = location.get("district", "")
            city = location.get("city", "Hà Nội")
        else:
            district = ""
            city = "Hà Nội"

        m = {
            "listing_id": listing.get("id", ""),
            "title": listing.get("title", "")[:200],
            "property_type": listing.get("property_type", ""),
            "district": district,
            "city": city,
            "price_number": int(listing.get("price_number") or 0),
            "area_m2": float(listing.get("area_m2") or 0.0),
            "bedrooms": int(listing.get("bedrooms") or 0),
            "source_platform": listing.get("source_platform", ""),
            "source_url": listing.get("source_url", "")[:500],
            "scraped_at": listing.get("scraped_at", datetime.utcnow().isoformat()),
        }
        print(f"DEBUG METADATA INTERNAL: {m}")
        return m

    async def add_listing(self, listing: dict) -> str:
        """
        Add a single listing to vector DB.

        Args:
            listing: Listing dict

        Returns:
            Document ID
        """
        doc_id = listing.get("id") or hashlib.md5(
            listing.get("source_url", "").encode()
        ).hexdigest()

        document = self._create_document(listing)
        metadata = self._create_metadata(listing)
        print(f"DEBUG METADATA: {metadata}") 


        self._collection.upsert(
            ids=[doc_id],
            documents=[document],
            metadatas=[metadata],
        )

        logger.debug(f"Added listing to vector DB: {doc_id}")
        return doc_id

    async def add_listings(self, listings: list[dict]) -> list[str]:
        """
        Add multiple listings to vector DB.

        Args:
            listings: List of listing dicts

        Returns:
            List of document IDs
        """
        if not listings:
            return []

        ids = []
        documents = []
        metadatas = []

        for listing in listings:
            doc_id = listing.get("id") or hashlib.md5(
                listing.get("source_url", "").encode()
            ).hexdigest()

            ids.append(doc_id)
            documents.append(self._create_document(listing))
            metadatas.append(self._create_metadata(listing))

        # Batch upsert
        self._collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

        logger.info(f"Added {len(listings)} listings to vector DB")
        return ids

    async def search(
        self,
        query: str,
        n_results: int = 10,
        filters: Optional[dict] = None,
    ) -> list[dict]:
        """
        Semantic search for listings.

        Args:
            query: Natural language search query
            n_results: Number of results to return
            filters: Optional metadata filters

        Returns:
            List of matching listings with scores
        """
        # Build where clause for filtering
        where = None
        where_clauses = []

        if filters:
            if filters.get("district"):
                where_clauses.append({"district": filters["district"]})

            if filters.get("property_type"):
                where_clauses.append({"property_type": filters["property_type"]})

            if filters.get("price_min"):
                where_clauses.append({"price_number": {"$gte": filters["price_min"]}})

            if filters.get("price_max"):
                where_clauses.append({"price_number": {"$lte": filters["price_max"]}})

            if filters.get("bedrooms"):
                where_clauses.append({"bedrooms": filters["bedrooms"]})

            if filters.get("source_platform"):
                where_clauses.append({"source_platform": filters["source_platform"]})

        if len(where_clauses) == 1:
            where = where_clauses[0]
        elif len(where_clauses) > 1:
            where = {"$and": where_clauses}

        # Perform search
        results = self._collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        # Format results
        formatted = []

        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                distance = results["distances"][0][i] if results["distances"] else 0

                # Convert distance to similarity score (0-1)
                # ChromaDB uses L2 distance, lower is better
                similarity = 1 / (1 + distance)

                formatted.append({
                    "id": doc_id,
                    "listing_id": metadata.get("listing_id", doc_id),
                    "title": metadata.get("title", ""),
                    "property_type": metadata.get("property_type"),
                    "district": metadata.get("district"),
                    "price_number": metadata.get("price_number"),
                    "area_m2": metadata.get("area_m2"),
                    "bedrooms": metadata.get("bedrooms"),
                    "source_url": metadata.get("source_url"),
                    "source_platform": metadata.get("source_platform"),
                    "similarity_score": round(similarity, 4),
                    "document": results["documents"][0][i] if results["documents"] else "",
                })

        logger.info(f"Vector search: '{query[:50]}...' -> {len(formatted)} results")
        return formatted

    async def find_similar(
        self,
        listing_id: str,
        n_results: int = 5,
    ) -> list[dict]:
        """
        Find listings similar to a given listing.

        Args:
            listing_id: ID of the listing to find similar for
            n_results: Number of similar listings to return

        Returns:
            List of similar listings
        """
        # Get the listing's document
        try:
            result = self._collection.get(
                ids=[listing_id],
                include=["documents"],
            )

            if not result["documents"]:
                return []

            document = result["documents"][0]

            # Search for similar
            results = await self.search(document, n_results=n_results + 1)

            # Remove the original listing from results
            results = [r for r in results if r["listing_id"] != listing_id]

            return results[:n_results]

        except Exception as e:
            logger.error(f"Error finding similar listings: {e}")
            return []

    async def delete_listing(self, listing_id: str) -> bool:
        """Delete a listing from vector DB."""
        try:
            self._collection.delete(ids=[listing_id])
            logger.debug(f"Deleted from vector DB: {listing_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting from vector DB: {e}")
            return False

    async def delete_listings(self, listing_ids: list[str]) -> int:
        """Delete multiple listings from vector DB."""
        try:
            self._collection.delete(ids=listing_ids)
            logger.info(f"Deleted {len(listing_ids)} from vector DB")
            return len(listing_ids)
        except Exception as e:
            logger.error(f"Error deleting from vector DB: {e}")
            return 0

    def persist(self):
        """Persist ChromaDB to disk."""
        self._client.persist()
        logger.info("ChromaDB persisted to disk")

    async def get_stats(self) -> dict:
        """Get vector DB statistics."""
        return {
            "collection_name": self.collection_name,
            "total_documents": self._collection.count(),
            "embedding_model": self.embedding_model,
            "persist_dir": str(self.persist_dir),
        }

    async def clear(self):
        """Clear all documents from collection."""
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.create_collection(
            name=self.collection_name,
            embedding_function=self._embedding_fn,
        )
        logger.warning("Cleared all documents from vector DB")


# Singleton instance
_vector_db: Optional[VectorDB] = None


def get_vector_db() -> VectorDB:
    """Get or create vector DB instance."""
    global _vector_db
    if _vector_db is None:
        _vector_db = VectorDB()
    return _vector_db


async def index_listing(listing: dict) -> str:
    """Convenience function to index a listing."""
    db = get_vector_db()
    return await db.add_listing(listing)


async def index_listings(listings: list[dict]) -> list[str]:
    """Convenience function to index multiple listings."""
    db = get_vector_db()
    return await db.add_listings(listings)


async def semantic_search(
    query: str,
    n_results: int = 10,
    filters: Optional[dict] = None,
) -> list[dict]:
    """Convenience function for semantic search."""
    db = get_vector_db()
    return await db.search(query, n_results, filters)


async def find_similar_listings(
    listing_id: str,
    n_results: int = 5,
) -> list[dict]:
    """Convenience function to find similar listings."""
    db = get_vector_db()
    return await db.find_similar(listing_id, n_results)
