"""
Pydantic models for API request/response schemas.
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# Base Models
# ============================================================================

class LocationSchema(BaseModel):
    """Location information."""
    address: Optional[str] = None
    ward: Optional[str] = None
    district: Optional[str] = None
    city: str = "Hà Nội"
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ContactSchema(BaseModel):
    """Contact information."""
    name: Optional[str] = None
    phone: Optional[str] = None
    phone_clean: Optional[str] = None


# ============================================================================
# Listing Models
# ============================================================================

class ListingBase(BaseModel):
    """Base listing schema."""
    title: str
    description: Optional[str] = None
    price_text: Optional[str] = None
    price_number: Optional[int] = None
    area_m2: Optional[float] = None
    property_type: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    direction: Optional[str] = None
    legal_status: Optional[str] = None


class ListingCreate(ListingBase):
    """Schema for creating a listing."""
    source_url: str
    source_platform: str = "manual"
    location: Optional[LocationSchema] = None
    contact: Optional[ContactSchema] = None
    images: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)


class ListingUpdate(BaseModel):
    """Schema for updating a listing."""
    title: Optional[str] = None
    description: Optional[str] = None
    price_text: Optional[str] = None
    price_number: Optional[int] = None
    area_m2: Optional[float] = None
    property_type: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    status: Optional[str] = None
    is_verified: Optional[bool] = None


class ListingResponse(ListingBase):
    """Schema for listing response."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    price_per_m2: Optional[int] = None
    location: Optional[LocationSchema] = None
    contact: Optional[ContactSchema] = None
    images: list[str] = Field(default_factory=list)
    thumbnail: Optional[str] = None
    source_url: str
    source_platform: str
    posted_at: Optional[datetime] = None
    scraped_at: Optional[datetime] = None
    status: str = "active"
    is_verified: bool = False
    features: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class ListingListResponse(BaseModel):
    """Schema for listing list response."""
    listings: list[ListingResponse]
    total: int
    page: int = 1
    page_size: int = 20
    has_more: bool = False


# ============================================================================
# Search Models
# ============================================================================

class SearchFilters(BaseModel):
    """Search filters."""
    property_type: Optional[str] = None
    district: Optional[str] = None
    city: Optional[str] = None
    min_price: Optional[int] = None
    max_price: Optional[int] = None
    min_area: Optional[float] = None
    max_area: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    source_platform: Optional[str] = None


class SearchRequest(BaseModel):
    """Search request schema."""
    query: str = Field(..., min_length=2, max_length=500)
    filters: Optional[SearchFilters] = None
    max_results: int = Field(default=20, ge=1, le=100)
    search_realtime: bool = Field(default=False, description="Force real-time search")
    platforms: Optional[list[str]] = None


class SearchResultItem(BaseModel):
    """Single search result item."""
    id: str
    title: str
    price_text: Optional[str] = None
    price_number: Optional[int] = None
    area_m2: Optional[float] = None
    location: Optional[LocationSchema] = None
    contact: Optional[ContactSchema] = None
    thumbnail: Optional[str] = None
    source_url: str
    source_platform: str
    property_type: Optional[str] = None
    bedrooms: Optional[int] = None
    similarity_score: Optional[float] = None


class SearchResponse(BaseModel):
    """Search response schema."""
    results: list[SearchResultItem]
    total: int
    from_cache: bool = True
    sources: list[str] = Field(default_factory=list)
    execution_time_ms: int = 0
    synthesis: Optional[str] = None
    errors: list[str] = Field(default_factory=list)
    applied_filters: Optional[dict] = None # New field to return actual filters used


# ============================================================================
# User Models
# ============================================================================

class UserBase(BaseModel):
    """Base user schema."""
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None


class UserCreate(UserBase):
    """Schema for creating a user."""
    telegram_id: Optional[str] = None


class UserResponse(UserBase):
    """Schema for user response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: Optional[str] = None
    role: str = "user"
    notification_enabled: bool = True
    created_at: datetime
    is_active: bool = True


# ============================================================================
# Saved Search Models
# ============================================================================

class SavedSearchCreate(BaseModel):
    """Schema for creating a saved search."""
    name: Optional[str] = None
    query: str
    filters: Optional[dict] = None
    notify_enabled: bool = True
    notify_frequency: str = "realtime"


class SavedSearchResponse(BaseModel):
    """Schema for saved search response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: Optional[str] = None
    query: str
    filters: Optional[dict] = None
    notify_enabled: bool
    notify_frequency: str
    match_count: int = 0
    last_match_at: Optional[datetime] = None
    created_at: datetime
    is_active: bool = True


# ============================================================================
# Analytics Models
# ============================================================================

class ScrapeStats(BaseModel):
    """Scraping statistics."""
    total_scrapes: int
    successful_scrapes: int
    total_listings_found: int
    total_new_listings: int
    avg_duration_seconds: float
    period_days: int


class PlatformStats(BaseModel):
    """Stats per platform."""
    platform: str
    count: int
    percentage: float


class DistrictStats(BaseModel):
    """Stats per district."""
    district: str
    count: int
    avg_price: Optional[int] = None
    avg_price_per_m2: Optional[int] = None


class AnalyticsResponse(BaseModel):
    """Analytics response schema."""
    total_listings: int
    active_listings: int
    platforms: list[PlatformStats]
    districts: list[DistrictStats]
    scrape_stats: Optional[ScrapeStats] = None
    last_updated: datetime


# ============================================================================
# Job Models
# ============================================================================

class JobStatus(BaseModel):
    """Job status schema."""
    id: str
    name: str
    next_run: Optional[str] = None
    trigger: str


class JobTriggerRequest(BaseModel):
    """Request to trigger a job."""
    job_id: str


class JobTriggerResponse(BaseModel):
    """Response from triggering a job."""
    success: bool
    message: str


# ============================================================================
# WebSocket Models
# ============================================================================

class WSProgressMessage(BaseModel):
    """WebSocket progress message."""
    type: str = "progress"
    message: str
    percent: int
    timestamp: str


class WSResultMessage(BaseModel):
    """WebSocket result message."""
    type: str = "result"
    data: dict


class WSErrorMessage(BaseModel):
    """WebSocket error message."""
    type: str = "error"
    error: str


# ============================================================================
# Generic Response Models
# ============================================================================

class SuccessResponse(BaseModel):
    """Generic success response."""
    success: bool = True
    message: str = "OK"


class ErrorResponse(BaseModel):
    """Generic error response."""
    success: bool = False
    error: str
    detail: Optional[str] = None
