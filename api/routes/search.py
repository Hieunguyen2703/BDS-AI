"""
Search API Routes.
Implements the main search endpoint with real-time and cached modes.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Depends
from loguru import logger

from api.models import (
    SearchRequest,
    SearchResponse,
    SearchResultItem,
    LocationSchema,
    ContactSchema,
    ErrorResponse,
)
from agents.search_agent import RealEstateSearchAgent
from storage.vector_db import semantic_search, get_vector_db
from storage.database import get_session, get_db, ListingCRUD, SearchHistoryCRUD
from sqlalchemy.ext.asyncio import AsyncSession
from services.validator import get_validator


router = APIRouter(prefix="/search", tags=["Search"])


# Active WebSocket connections for search progress
active_connections: dict[str, WebSocket] = {}


def listing_to_search_result(listing: dict) -> SearchResultItem:
    """Convert listing dict to SearchResultItem."""
    location = listing.get("location", {})
    if isinstance(location, dict):
        location_schema = LocationSchema(
            address=location.get("address"),
            ward=location.get("ward"),
            district=location.get("district"),
            city=location.get("city", "Hà Nội"),
        )
    else:
        location_schema = None

    contact = listing.get("contact", {})
    if isinstance(contact, dict):
        contact_schema = ContactSchema(
            name=contact.get("name"),
            phone=contact.get("phone"),
            phone_clean=contact.get("phone_clean"),
        )
    else:
        contact_schema = None

    return SearchResultItem(
        id=listing.get("id", ""),
        title=listing.get("title", ""),
        price_text=listing.get("price_text"),
        price_number=listing.get("price_number"),
        area_m2=listing.get("area_m2"),
        location=location_schema,
        contact=contact_schema,
        thumbnail=listing.get("thumbnail") or (listing.get("images", [None])[0] if listing.get("images") else None),
        source_url=listing.get("source_url", ""),
        source_platform=listing.get("source_platform", ""),
        property_type=listing.get("property_type"),
        bedrooms=listing.get("bedrooms"),
        similarity_score=listing.get("similarity_score"),
    )


@router.post("", response_model=SearchResponse)
async def search_listings(request: SearchRequest) -> SearchResponse:
    """
    Search for real estate listings.

    - First searches vector DB for cached results
    - If insufficient results and search_realtime=True, performs real-time scraping
    """
    start_time = datetime.now()

    logger.info(f"Search request: query='{request.query}', realtime={request.search_realtime}")

    results = []
    sources = []
    errors = []
    from_cache = True
    synthesis = None

    try:
        # Pre-parsing: Extract intent from query to improve cache relevance
        # We need to know the district/city to filter vector DB results correctly
        parsed_intent = None
        
        # Instantiate agent in headless mode for parsing
        # (Lightweight init, LLM loads lazily)
        parsing_agent = RealEstateSearchAgent(headless=True)
        try:
            parsed_intent = await parsing_agent.parse_query(request.query)
            logger.info(f"🧠 Early intent parsing: {parsed_intent}")
        except Exception as e:
            logger.warning(f"Failed to parse intent early: {e}")

        # Build filters for vector search
        filters = {}
        
        # Priority: Request Filters > Parsed Intent
        if request.filters:
            if request.filters.property_type: filters["property_type"] = request.filters.property_type
            if request.filters.district: filters["district"] = request.filters.district
            if request.filters.min_price: filters["price_min"] = request.filters.min_price
            if request.filters.max_price: filters["price_max"] = request.filters.max_price
            if request.filters.bedrooms: filters["bedrooms"] = request.filters.bedrooms
            if request.filters.source_platform: filters["source_platform"] = request.filters.source_platform
            
        # Backfill from parsed intent if filters are missing
        if parsed_intent:
            if "district" not in filters and parsed_intent.district:
                filters["district"] = parsed_intent.district
            if "property_type" not in filters and parsed_intent.property_type:
                filters["property_type"] = parsed_intent.property_type
            if "bedrooms" not in filters and parsed_intent.bedrooms:
                filters["bedrooms"] = parsed_intent.bedrooms
            if "price_min" not in filters and parsed_intent.price_min:
                filters["price_min"] = parsed_intent.price_min
            if "price_max" not in filters and parsed_intent.price_max:
                filters["price_max"] = parsed_intent.price_max

        # Step 1: Search vector DB
        # Always search cached results, but filter by district to ensure relevance
        if parsed_intent and parsed_intent.district:
             logger.info(f"🔍 Vector Search with enforced district: {parsed_intent.district}")
        
        vector_results = await semantic_search(
            request.query,
            n_results=request.max_results,
            filters=filters if filters else None,
        )

        if vector_results:
            sources.append("vector_db")
            for r in vector_results:
                results.append(listing_to_search_result(r))

        # Step 2: Real-time scraping if requested
        # Always scrape when realtime=True to get fresh results
        if request.search_realtime:
            from_cache = False
            logger.info(f"🔴 Starting real-time scraping for: {request.query}")

            # Use visible browser (headless=False) for debugging
            agent = RealEstateSearchAgent(headless=False)
            try:
                # Pass the already parsed intent to avoid re-parsing
                search_result = await agent.search(
                    request.query,
                    max_results=request.max_results,
                    platforms=request.platforms or ["chotot", "batdongsan"],
                    intent=parsed_intent # Pass optimized intent
                )

                sources.extend(search_result.sources_searched)
                errors.extend(search_result.errors)
                synthesis = search_result.synthesis

                # Add real-time results (prioritize over cached)
                # Save to PostgreSQL
                from storage.database import get_session, ListingCRUD
                
                async with get_session() as session:
                    saved_count = 0
                    for listing in search_result.listings:
                        # Ensure ID is present (hash of URL if missing)
                        if not listing.get("id"):
                            import hashlib
                            listing["id"] = hashlib.md5(listing.get("source_url", "").encode()).hexdigest()
                        
                        # Prepare data for DB (flatten location)
                        db_listing = listing.copy()
                        if "location" in db_listing and isinstance(db_listing["location"], dict):
                            loc = db_listing.pop("location")
                            db_listing["address"] = loc.get("address")
                            db_listing["ward"] = loc.get("ward")
                            db_listing["district"] = loc.get("district")
                            db_listing["city"] = loc.get("city")

                        if "contact" in db_listing and isinstance(db_listing["contact"], dict):
                            contact = db_listing.pop("contact")
                            db_listing["contact_name"] = contact.get("name")
                            db_listing["contact_phone"] = contact.get("phone")
                            db_listing["contact_phone_clean"] = contact.get("phone_clean")

                        # Truncate fields to prevent SQL errors
                        if db_listing.get("title"):
                            db_listing["title"] = db_listing["title"][:490]
                        if db_listing.get("address"):
                            db_listing["address"] = db_listing["address"][:490]
                        if db_listing.get("source_url"):
                            db_listing["source_url"] = db_listing["source_url"][:490]
                            
                        # Upsert to DB
                        await ListingCRUD.upsert(session, db_listing)
                        saved_count += 1
                        
                        # Add to results list
                        results.insert(0, listing_to_search_result(listing))
                        
                    logger.info(f"💾 Saved {saved_count} listings to PostgreSQL")

                # Save to vector DB for future searches
                if search_result.listings:
                    from storage.vector_db import index_listings
                    await index_listings(search_result.listings)
                    logger.info(f"✅ Indexed {len(search_result.listings)} new listings")

            finally:
                await agent.close()

        # Step 3: Local Data Fallback (If scraping matched nothing)
        # If we have 0 results but we know the district, search Vector DB for that district ignoring other keywords
        if not results and parsed_intent and parsed_intent.district:
            logger.info(f"⚠️ Scraping yielded 0 results. Triggering fallback for district: {parsed_intent.district}")
            
            fallback_filters = {"district": parsed_intent.district}
            if parsed_intent.property_type:
                fallback_filters["property_type"] = parsed_intent.property_type

            # Search widely in that district
            fallback_results = await semantic_search(
                query=parsed_intent.district, # Query is just the district name for broad match
                n_results=request.max_results,
                filters=fallback_filters
            )
            
            if fallback_results:
                logger.info(f"✅ Fallback found {len(fallback_results)} cached listings in {parsed_intent.district}")
                sources.append("vector_db_fallback")
                synthesis = f"Không tìm thấy kết quả mới nhất. Dưới đây là các tin đăng đã lưu tại {parsed_intent.district}."
                for r in fallback_results:
                    results.append(listing_to_search_result(r))

        # Deduplicate by ID
        seen_ids = set()
        unique_results = []
        for r in results:
            if r.id not in seen_ids:
                seen_ids.add(r.id)
                unique_results.append(r)

        results = unique_results[:request.max_results]

    except Exception as e:
        logger.error(f"Search error: {e}")
        errors.append(str(e))

    execution_time = int((datetime.now() - start_time).total_seconds() * 1000)

    response = SearchResponse(
        results=results,
        total=len(results),
        from_cache=from_cache,
        sources=list(set(sources)),
        execution_time_ms=execution_time,
        synthesis=synthesis,
        errors=errors,
        applied_filters=filters,
    )

    # Record search history (Background task or just await)
    try:
        async with get_session() as session:
            await SearchHistoryCRUD.create(session, {
                "query": request.query,
                "filters": filters,
                "results_count": len(results),
                "user_id": None # Connect when auth is implemented
            })
    except Exception as e:
        logger.warning(f"Failed to record search history: {e}")

    return response


@router.get("/quick")
async def quick_search(
    q: str,
    limit: int = 10,
    district: Optional[str] = None,
    property_type: Optional[str] = None,
) -> SearchResponse:
    """
    Quick search endpoint for autocomplete/suggestions.
    Only searches cached data, no real-time scraping.
    """
    start_time = datetime.now()

    filters = {}
    if district:
        filters["district"] = district
    if property_type:
        filters["property_type"] = property_type

    vector_results = await semantic_search(
        q,
        n_results=limit,
        filters=filters if filters else None,
    )

    results = [listing_to_search_result(r) for r in vector_results]

    execution_time = int((datetime.now() - start_time).total_seconds() * 1000)

    return SearchResponse(
        results=results,
        total=len(results),
        from_cache=True,
        sources=["vector_db"],
        execution_time_ms=execution_time,
    )


@router.websocket("/ws")
async def websocket_search(websocket: WebSocket):
    """
    WebSocket endpoint for real-time search with progress updates.

    Send: {"query": "...", "filters": {...}}
    Receive: progress updates and final results
    """
    await websocket.accept()

    try:
        while True:
            # Receive search request
            data = await websocket.receive_json()
            query = data.get("query")

            if not query:
                await websocket.send_json({
                    "type": "error",
                    "error": "Query is required",
                })
                continue

            logger.info(f"WebSocket search: {query}")

            # Progress callback
            async def send_progress(update: dict):
                await websocket.send_json({
                    "type": "progress",
                    **update,
                })

            # Perform search with progress
            agent = RealEstateSearchAgent(headless=True)

            try:
                result = await agent.search_with_progress(
                    query,
                    progress_callback=send_progress,
                    max_results=data.get("max_results", 20),
                    platforms=data.get("platforms"),
                )

                # Send final result
                await websocket.send_json({
                    "type": "result",
                    "data": {
                        "results": [
                            listing_to_search_result(l).model_dump()
                            for l in result.listings
                        ],
                        "total": result.total_found,
                        "sources": result.sources_searched,
                        "errors": result.errors,
                    },
                })

            finally:
                await agent.close()

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "error": str(e),
            })
        except:
            pass


@router.get("/stats")
async def get_search_stats():
    """Get search/vector DB statistics."""
    db = get_vector_db()
    stats = await db.get_stats()
    return stats


@router.get("/history")
async def get_search_history(limit: int = 20, db: AsyncSession = Depends(get_db)):
    """Get recent search history."""
    try:
        history = await SearchHistoryCRUD.list_by_user(db, limit=limit)
        return [
            {
                "id": h.id,
                "query": h.query,
                "filters": h.filters,
                "results_count": h.results_count,
                "created_at": h.created_at.isoformat()
            }
            for h in history
        ]
    except Exception as e:
        logger.error(f"Error fetching search history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
