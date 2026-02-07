"""
Listings API Routes.
CRUD endpoints for real estate listings.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Path
from loguru import logger

from api.models import (
    ListingCreate,
    ListingUpdate,
    ListingResponse,
    ListingListResponse,
    LocationSchema,
    ContactSchema,
    SuccessResponse,
    ErrorResponse,
)
from storage.database import get_session, ListingCRUD
from storage.vector_db import index_listing, get_vector_db
from services.validator import get_validator


router = APIRouter(prefix="/listings", tags=["Listings"])


def db_listing_to_response(listing) -> ListingResponse:
    """Convert database listing to response model."""
    return ListingResponse(
        id=listing.id,
        title=listing.title,
        description=listing.description,
        price_text=listing.price_text,
        price_number=listing.price_number,
        price_per_m2=listing.price_per_m2,
        area_m2=listing.area_m2,
        property_type=listing.property_type,
        bedrooms=listing.bedrooms,
        bathrooms=listing.bathrooms,
        direction=listing.direction,
        legal_status=listing.legal_status,
        location=LocationSchema(
            address=listing.address,
            ward=listing.ward,
            district=listing.district,
            city=listing.city,
            latitude=listing.latitude,
            longitude=listing.longitude,
        ),
        contact=ContactSchema(
            name=listing.contact_name,
            phone=listing.contact_phone,
            phone_clean=listing.contact_phone_clean,
        ),
        images=listing.images or [],
        thumbnail=listing.thumbnail,
        source_url=listing.source_url,
        source_platform=listing.source_platform,
        posted_at=listing.posted_at,
        scraped_at=listing.scraped_at,
        status=listing.status,
        is_verified=listing.is_verified,
        features=listing.features or [],
        tags=listing.tags or [],
    )


@router.get("", response_model=ListingListResponse)
async def list_listings(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    district: Optional[str] = Query(None),
    property_type: Optional[str] = Query(None),
    min_price: Optional[int] = Query(None),
    max_price: Optional[int] = Query(None),
    platform: Optional[str] = Query(None),
) -> ListingListResponse:
    """
    List listings with pagination and filters.
    """
    skip = (page - 1) * page_size

    async with get_session() as session:
        listings = await ListingCRUD.list_all(
            session,
            skip=skip,
            limit=page_size + 1,  # Get one extra to check has_more
            status=status,
            district=district,
            property_type=property_type,
            price_min=min_price,
            price_max=max_price,
            platform=platform,
        )

        total = await ListingCRUD.count(
            session,
            status=status,
            district=district,
        )

    has_more = len(listings) > page_size
    listings = listings[:page_size]

    return ListingListResponse(
        listings=[db_listing_to_response(l) for l in listings],
        total=total,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


@router.get("/{listing_id}", response_model=ListingResponse)
async def get_listing(
    listing_id: str = Path(..., min_length=32, max_length=32),
) -> ListingResponse:
    """
    Get a single listing by ID.
    """
    async with get_session() as session:
        listing = await ListingCRUD.get_by_id(session, listing_id)

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    return db_listing_to_response(listing)


@router.post("", response_model=ListingResponse, status_code=201)
async def create_listing(data: ListingCreate) -> ListingResponse:
    """
    Create a new listing manually.
    """
    validator = get_validator()

    # Build listing dict
    listing_dict = {
        "title": data.title,
        "description": data.description,
        "price_text": data.price_text,
        "price_number": data.price_number,
        "area_m2": data.area_m2,
        "property_type": data.property_type,
        "bedrooms": data.bedrooms,
        "bathrooms": data.bathrooms,
        "direction": data.direction,
        "legal_status": data.legal_status,
        "source_url": data.source_url,
        "source_platform": data.source_platform,
        "images": data.images,
        "features": data.features,
    }

    if data.location:
        listing_dict["address"] = data.location.address
        listing_dict["ward"] = data.location.ward
        listing_dict["district"] = data.location.district
        listing_dict["city"] = data.location.city
        listing_dict["latitude"] = data.location.latitude
        listing_dict["longitude"] = data.location.longitude

    if data.contact:
        listing_dict["contact_name"] = data.contact.name
        listing_dict["contact_phone"] = data.contact.phone
        listing_dict["contact_phone_clean"] = data.contact.phone_clean

    # Generate ID
    listing_dict["id"] = validator.generate_listing_id(
        data.source_url,
        data.contact.phone if data.contact else None,
        data.title,
    )

    # Calculate price per m2
    if data.price_number and data.area_m2 and data.area_m2 > 0:
        listing_dict["price_per_m2"] = int(data.price_number / data.area_m2)

    listing_dict["scraped_at"] = datetime.utcnow()

    # Validate
    validation_result = validator.validate_listing({
        "source_url": data.source_url,
        "title": data.title,
        "price_number": data.price_number,
        "area_m2": data.area_m2,
        "location": {"district": data.location.district if data.location else None},
        "contact": {"phone": data.contact.phone if data.contact else None},
    })

    if not validation_result.is_valid:
        raise HTTPException(
            status_code=400,
            detail=f"Validation failed: {', '.join(validation_result.errors)}"
        )

    listing_dict["validation_warnings"] = validation_result.warnings

    # Save to database
    async with get_session() as session:
        listing = await ListingCRUD.create(session, listing_dict)

    # Index to vector DB
    await index_listing(listing_dict)

    logger.info(f"Created listing: {listing.id}")

    return db_listing_to_response(listing)


@router.put("/{listing_id}", response_model=ListingResponse)
async def update_listing(
    listing_id: str = Path(..., min_length=32, max_length=32),
    data: ListingUpdate = ...,
) -> ListingResponse:
    """
    Update a listing.
    """
    async with get_session() as session:
        # Check exists
        existing = await ListingCRUD.get_by_id(session, listing_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Listing not found")

        # Build update dict
        update_data = data.model_dump(exclude_unset=True)

        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")

        # Recalculate price_per_m2 if needed
        new_price = update_data.get("price_number", existing.price_number)
        new_area = update_data.get("area_m2", existing.area_m2)
        if new_price and new_area and new_area > 0:
            update_data["price_per_m2"] = int(new_price / new_area)

        listing = await ListingCRUD.update(session, listing_id, update_data)

    logger.info(f"Updated listing: {listing_id}")

    return db_listing_to_response(listing)


@router.delete("/{listing_id}", response_model=SuccessResponse)
async def delete_listing(
    listing_id: str = Path(..., min_length=32, max_length=32),
    hard: bool = Query(False, description="Hard delete (permanent)"),
) -> SuccessResponse:
    """
    Delete a listing (soft delete by default).
    """
    async with get_session() as session:
        if hard:
            success = await ListingCRUD.hard_delete(session, listing_id)
        else:
            success = await ListingCRUD.delete(session, listing_id)

    if not success:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Remove from vector DB
    vector_db = get_vector_db()
    await vector_db.delete_listing(listing_id)

    logger.info(f"Deleted listing: {listing_id} (hard={hard})")

    return SuccessResponse(message=f"Listing {listing_id} deleted")


@router.get("/{listing_id}/similar")
async def get_similar_listings(
    listing_id: str = Path(..., min_length=32, max_length=32),
    limit: int = Query(5, ge=1, le=20),
):
    """
    Get listings similar to the given listing.
    """
    from storage.vector_db import find_similar_listings

    similar = await find_similar_listings(listing_id, n_results=limit)

    return {
        "listing_id": listing_id,
        "similar": similar,
        "count": len(similar),
    }


@router.post("/bulk", response_model=dict)
async def bulk_create_listings(listings: list[ListingCreate]):
    """
    Bulk create listings.
    """
    validator = get_validator()
    created = 0
    failed = 0
    errors = []

    for data in listings:
        try:
            listing_dict = {
                "title": data.title,
                "description": data.description,
                "price_text": data.price_text,
                "price_number": data.price_number,
                "area_m2": data.area_m2,
                "property_type": data.property_type,
                "bedrooms": data.bedrooms,
                "bathrooms": data.bathrooms,
                "source_url": data.source_url,
                "source_platform": data.source_platform,
                "images": data.images,
                "features": data.features,
                "scraped_at": datetime.utcnow(),
            }

            if data.location:
                listing_dict["address"] = data.location.address
                listing_dict["ward"] = data.location.ward
                listing_dict["district"] = data.location.district
                listing_dict["city"] = data.location.city

            if data.contact:
                listing_dict["contact_name"] = data.contact.name
                listing_dict["contact_phone"] = data.contact.phone
                listing_dict["contact_phone_clean"] = data.contact.phone_clean

            listing_dict["id"] = validator.generate_listing_id(
                data.source_url,
                data.contact.phone if data.contact else None,
                data.title,
            )

            async with get_session() as session:
                await ListingCRUD.create(session, listing_dict)

            await index_listing(listing_dict)
            created += 1

        except Exception as e:
            failed += 1
            errors.append(f"{data.title[:30]}: {str(e)}")

    return {
        "created": created,
        "failed": failed,
        "errors": errors[:10],  # Limit errors in response
    }
