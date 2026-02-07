"""
Analytics API Routes.
Provides market insights and statistics.
"""

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Query
from sqlalchemy import select, func

from api.models import (
    AnalyticsResponse,
    ScrapeStats,
    PlatformStats,
    DistrictStats,
)
from storage.database import get_session, Listing, ScrapeLog, ScrapeLogCRUD
from config import DISTRICT_PRICE_RANGES


router = APIRouter(prefix="/analytics", tags=["Analytics"])


@router.get("", response_model=AnalyticsResponse)
async def get_analytics(query: Optional[str] = Query(None)):
    """
    Get analytics, optionally filtered by search query.
    """
    async with get_session() as session:
        # Base query for active listings
        base_query = select(Listing).where(Listing.status == "active")
        
        # Apply search filter if provided
        if query:
            search_filter = (
                Listing.title.ilike(f"%{query}%") | 
                Listing.district.ilike(f"%{query}%") |
                Listing.city.ilike(f"%{query}%")
            )
            base_query = base_query.where(search_filter)

        # 1. Total counts (filtered)
        total_result = await session.execute(
            select(func.count(Listing.id)).where(Listing.status != "deleted")
            .where(search_filter if query else True)
        )
        total_listings = total_result.scalar_one()

        active_result = await session.execute(
            select(func.count(Listing.id)).where(Listing.status == "active")
            .where(search_filter if query else True)
        )
        active_listings = active_result.scalar_one()

        # 2. Platform breakdown (filtered)
        platform_query = (
            select(
                Listing.source_platform,
                func.count(Listing.id).label("count")
            )
            .where(Listing.status != "deleted")
            .where(search_filter if query else True)
            .group_by(Listing.source_platform)
            .order_by(func.count(Listing.id).desc())
        )
        platform_result = await session.execute(platform_query)

        platforms = []
        for row in platform_result:
            percentage = (row.count / total_listings * 100) if total_listings > 0 else 0
            platforms.append(PlatformStats(
                platform=row.source_platform or "unknown",
                count=row.count,
                percentage=round(percentage, 1),
            ))

        # 3. District breakdown (filtered)
        district_query = (
            select(
                Listing.district,
                func.count(Listing.id).label("count"),
                func.avg(Listing.price_number).label("avg_price"),
                func.avg(Listing.price_per_m2).label("avg_price_per_m2"),
            )
            .where(Listing.status == "active")
            .where(Listing.district.isnot(None))
            .where(search_filter if query else True)
            .group_by(Listing.district)
            .order_by(func.count(Listing.id).desc())
            .limit(20)
        )
        district_result = await session.execute(district_query)

        districts = []
        for row in district_result:
            districts.append(DistrictStats(
                district=row.district,
                count=row.count,
                avg_price=int(row.avg_price) if row.avg_price else None,
                avg_price_per_m2=int(row.avg_price_per_m2) if row.avg_price_per_m2 else None,
            ))

        # Scrape stats (global, not filtered by query as it's system stats)
        scrape_stats_dict = await ScrapeLogCRUD.get_stats(session, days=7)
        scrape_stats = ScrapeStats(**scrape_stats_dict)

    return AnalyticsResponse(
        total_listings=total_listings,
        active_listings=active_listings,
        platforms=platforms,
        districts=districts,
        scrape_stats=scrape_stats,
        last_updated=datetime.utcnow(),
    )


@router.get("/price-trends")
async def get_price_trends(
    district: Optional[str] = Query(None),
    property_type: Optional[str] = Query(None),
    days: int = Query(30, ge=7, le=90),
):
    """
    Get price trends over time.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)

    async with get_session() as session:
        query = (
            select(
                func.date(Listing.scraped_at).label("date"),
                func.avg(Listing.price_per_m2).label("avg_price_per_m2"),
                func.count(Listing.id).label("count"),
            )
            .where(Listing.scraped_at >= cutoff)
            .where(Listing.status == "active")
            .where(Listing.price_per_m2.isnot(None))
        )

        if district:
            query = query.where(Listing.district == district)

        if property_type:
            query = query.where(Listing.property_type == property_type)

        query = query.group_by(func.date(Listing.scraped_at))
        query = query.order_by(func.date(Listing.scraped_at))

        result = await session.execute(query)

        trends = []
        for row in result:
            trends.append({
                "date": row.date.isoformat() if row.date else None,
                "avg_price_per_m2": int(row.avg_price_per_m2) if row.avg_price_per_m2 else None,
                "count": row.count,
            })

    return {
        "district": district,
        "property_type": property_type,
        "period_days": days,
        "data": trends,
    }


@router.get("/market-overview")
async def get_market_overview():
    """
    Get market overview by district with expected vs actual prices.
    """
    async with get_session() as session:
        # Get actual averages by district
        result = await session.execute(
            select(
                Listing.district,
                func.count(Listing.id).label("count"),
                func.avg(Listing.price_per_m2).label("actual_avg"),
                func.min(Listing.price_per_m2).label("actual_min"),
                func.max(Listing.price_per_m2).label("actual_max"),
            )
            .where(Listing.status == "active")
            .where(Listing.district.isnot(None))
            .where(Listing.price_per_m2.isnot(None))
            .group_by(Listing.district)
        )

        overview = []
        for row in result:
            district = row.district
            expected = DISTRICT_PRICE_RANGES.get(district)

            overview.append({
                "district": district,
                "count": row.count,
                "actual_avg_per_m2": int(row.actual_avg) if row.actual_avg else None,
                "actual_min_per_m2": int(row.actual_min) if row.actual_min else None,
                "actual_max_per_m2": int(row.actual_max) if row.actual_max else None,
                "expected_min_per_m2": expected[0] * 1_000_000 if expected else None,
                "expected_max_per_m2": expected[1] * 1_000_000 if expected else None,
            })

        # Sort by count descending
        overview.sort(key=lambda x: x["count"], reverse=True)

    return {
        "districts": overview,
        "total_districts": len(overview),
    }


@router.get("/scrape-logs")
async def get_scrape_logs(
    limit: int = Query(20, ge=1, le=100),
    platform: Optional[str] = Query(None),
):
    """
    Get recent scrape logs.
    """
    async with get_session() as session:
        logs = await ScrapeLogCRUD.get_recent(session, limit=limit, platform=platform)

    return {
        "logs": [
            {
                "id": log.id,
                "platform": log.platform,
                "query": log.query,
                "listings_found": log.listings_found,
                "listings_new": log.listings_new,
                "duration_seconds": log.duration_seconds,
                "status": log.status,
                "started_at": log.started_at.isoformat() if log.started_at else None,
                "finished_at": log.finished_at.isoformat() if log.finished_at else None,
                "error_message": log.error_message,
            }
            for log in logs
        ],
        "count": len(logs),
    }


@router.get("/property-types")
async def get_property_type_stats():
    """
    Get statistics by property type.
    """
    async with get_session() as session:
        result = await session.execute(
            select(
                Listing.property_type,
                func.count(Listing.id).label("count"),
                func.avg(Listing.price_number).label("avg_price"),
                func.avg(Listing.area_m2).label("avg_area"),
                func.avg(Listing.price_per_m2).label("avg_price_per_m2"),
            )
            .where(Listing.status == "active")
            .where(Listing.property_type.isnot(None))
            .group_by(Listing.property_type)
            .order_by(func.count(Listing.id).desc())
        )

        stats = []
        for row in result:
            stats.append({
                "property_type": row.property_type,
                "count": row.count,
                "avg_price": int(row.avg_price) if row.avg_price else None,
                "avg_area": round(row.avg_area, 1) if row.avg_area else None,
                "avg_price_per_m2": int(row.avg_price_per_m2) if row.avg_price_per_m2 else None,
            })

    return {"property_types": stats}
