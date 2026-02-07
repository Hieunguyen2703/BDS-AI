"""
Valuation API Routes

Endpoints for AI-powered property valuation.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import logging

from services.valuation_service import AIValuationService
from storage.database import get_db, ValuationHistoryCRUD, get_session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/valuation", tags=["valuation"])

# Initialize valuation service
valuation_service = AIValuationService()


class ValuationRequest(BaseModel):
    """Request model for property valuation."""
    property_type: str
    area_m2: float
    district: str
    bedrooms: Optional[int] = None
    direction: Optional[str] = None
    legal_status: Optional[str] = None


class ValuationResponse(BaseModel):
    """Response model for valuation."""
    price_min: Optional[int] = None
    price_max: Optional[int] = None
    price_suggested: Optional[int] = None
    price_per_m2: Optional[int] = None
    confidence: Optional[int] = None
    reasoning: Optional[str] = None
    market_comparison: Optional[str] = None
    market_samples: Optional[int] = None
    district: Optional[str] = None
    timestamp: Optional[str] = None
    error: Optional[str] = None
    ml_estimate: Optional[float] = None # Added raw ML estimate


@router.post("/estimate", response_model=ValuationResponse)
async def estimate_property_value(
    request: ValuationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Estimate property value using AI analysis.
    
    Args:
        request: Valuation request with property details
        db: Database session
        
    Returns:
        Valuation result with price range and reasoning
    """
    try:
        result = await valuation_service.estimate_price(
            property_type=request.property_type,
            area_m2=request.area_m2,
            district=request.district,
            bedrooms=request.bedrooms,
            direction=request.direction,
            legal_status=request.legal_status,
            db=db
        )
        
        response = ValuationResponse(**result)

        # Record valuation history
        try:
            async with get_session() as session:
                await ValuationHistoryCRUD.create(session, {
                    "property_type": request.property_type,
                    "area_m2": request.area_m2,
                    "district": request.district,
                    "bedrooms": request.bedrooms,
                    "direction": request.direction,
                    "legal_status": request.legal_status,
                    "price_suggested": result.get("price_suggested"),
                    "price_min": result.get("price_min"),
                    "price_max": result.get("price_max"),
                    "confidence": result.get("confidence"),
                    "user_id": None # Connect when auth is implemented
                })
        except Exception as e:
            logger.warning(f"Failed to record valuation history: {e}")

        return response
        
    except Exception as e:
        logger.error(f"Valuation endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train")
async def train_valuation_model(
    db: AsyncSession = Depends(get_db)
):
    """
    Trigger training of the AutoGluon valuation model.
    """
    try:
        result = await valuation_service.ml_service.train_model(db)
        return result
    except Exception as e:
        logger.error(f"Training error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/districts")
async def get_available_districts(db: AsyncSession = Depends(get_db)):
    """
    Get list of districts with available data.
    
    Returns:
        List of district names
    """
    try:
        from storage.database import Listing
        from sqlalchemy import distinct
        
        result = await db.execute(
            select(distinct(Listing.district))
            .where(Listing.district.isnot(None))
        )
        districts = result.all()
        
        return {
            "districts": sorted([d[0] for d in districts if d[0]])
        }
        
    except Exception as e:
        logger.error(f"Error fetching districts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history")
async def get_valuation_history(limit: int = 20, db: AsyncSession = Depends(get_db)):
    """Get recent valuation history."""
    try:
        history = await ValuationHistoryCRUD.list_by_user(db, limit=limit)
        return [
            {
                "id": h.id,
                "property_type": h.property_type,
                "area_m2": h.area_m2,
                "district": h.district,
                "bedrooms": h.bedrooms,
                "price_suggested": h.price_suggested,
                "price_min": h.price_min,
                "price_max": h.price_max,
                "confidence": h.confidence,
                "created_at": h.created_at.isoformat()
            }
            for h in history
        ]
    except Exception as e:
        logger.error(f"Error fetching valuation history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
