"""
API Routes package.
"""

from api.routes.search import router as search_router
from api.routes.listings import router as listings_router
from api.routes.analytics import router as analytics_router

__all__ = ["search_router", "listings_router", "analytics_router"]
