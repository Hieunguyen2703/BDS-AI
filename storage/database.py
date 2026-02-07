"""
SQLAlchemy Database Models and CRUD Operations.
Defines all database tables and provides async database operations.
"""

import enum
from datetime import datetime
from typing import Any, Optional
from contextlib import asynccontextmanager

from sqlalchemy import (
    Column,
    String,
    Integer,
    BigInteger,
    Float,
    Boolean,
    Text,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
    UniqueConstraint,
    func,
    select,
    update,
    delete,
)
from sqlalchemy import case
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)
from loguru import logger

from config import settings


# ============================================================================
# Base Configuration
# ============================================================================

class Base(DeclarativeBase):
    """Base class for all models."""
    pass


# Async engine and session factory
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@asynccontextmanager
async def get_session() -> AsyncSession:
    """Get async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_db():
    """Get async database session (generator for Depends)."""
    async with async_session_factory() as session:
        yield session

async def init_db():
    """Initialize database - create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")


async def close_db():
    """Close database connections."""
    await engine.dispose()
    logger.info("Database connections closed")


async def drop_db():
    """Drop all tables - use with caution!"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.warning("Database tables dropped")


# ============================================================================
# Enums
# ============================================================================

class PropertyType(str, enum.Enum):
    """Property type enum."""
    CHUNG_CU = "chung_cu"
    NHA_RIENG = "nha_rieng"
    BIET_THU = "biet_thu"
    DAT_NEN = "dat_nen"
    NHA_MAT_PHO = "nha_mat_pho"
    OTHER = "other"


class ListingStatus(str, enum.Enum):
    """Listing status enum."""
    ACTIVE = "active"
    SOLD = "sold"
    EXPIRED = "expired"
    DELETED = "deleted"


class SourcePlatform(str, enum.Enum):
    """Source platform enum."""
    CHOTOT = "chotot"
    BATDONGSAN = "batdongsan"
    MOGI = "mogi"
    ALONHADAT = "alonhadat"
    FACEBOOK = "facebook"
    GOOGLE = "google"
    MANUAL = "manual"


class UserRole(str, enum.Enum):
    """User role enum."""
    USER = "user"
    ADMIN = "admin"
    AGENT = "agent"


# ============================================================================
# Models
# ============================================================================

class Listing(Base):
    """Real estate listing model."""

    __tablename__ = "listings"

    # Primary key
    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # MD5 hash

    # Basic info
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)

    # Price
    price_text: Mapped[Optional[str]] = mapped_column(String(100))
    price_number: Mapped[Optional[int]] = mapped_column(BigInteger)  # VND
    price_per_m2: Mapped[Optional[int]] = mapped_column(BigInteger)  # VND/m²

    # Property details
    property_type: Mapped[Optional[str]] = mapped_column(String(50))
    area_m2: Mapped[Optional[float]] = mapped_column(Float)
    bedrooms: Mapped[Optional[int]] = mapped_column(Integer)
    bathrooms: Mapped[Optional[int]] = mapped_column(Integer)
    floors: Mapped[Optional[int]] = mapped_column(Integer)
    direction: Mapped[Optional[str]] = mapped_column(String(50))
    legal_status: Mapped[Optional[str]] = mapped_column(String(100))

    # Location
    address: Mapped[Optional[str]] = mapped_column(String(500))
    ward: Mapped[Optional[str]] = mapped_column(String(100))
    district: Mapped[Optional[str]] = mapped_column(String(100))
    city: Mapped[str] = mapped_column(String(100), default="Hà Nội")
    latitude: Mapped[Optional[float]] = mapped_column(Float)
    longitude: Mapped[Optional[float]] = mapped_column(Float)

    # Contact
    contact_name: Mapped[Optional[str]] = mapped_column(String(200))
    contact_phone: Mapped[Optional[str]] = mapped_column(String(20))
    contact_phone_clean: Mapped[Optional[str]] = mapped_column(String(15))

    # Images
    images: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    thumbnail: Mapped[Optional[str]] = mapped_column(String(500))

    # Source & tracking
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    source_platform: Mapped[str] = mapped_column(String(50), nullable=False)
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    scraped_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Status & validation
    status: Mapped[str] = mapped_column(
        String(20),
        default=ListingStatus.ACTIVE.value
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    validation_errors: Mapped[Optional[list]] = mapped_column(JSON)
    validation_warnings: Mapped[Optional[list]] = mapped_column(JSON)

    # Features & tags
    features: Mapped[Optional[list]] = mapped_column(JSON, default=list)
    tags: Mapped[Optional[list]] = mapped_column(JSON, default=list)

    # Extra data
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON)

    # Relationships
    saved_by = relationship("SavedListing", back_populates="listing")

    # Indexes
    __table_args__ = (
        Index("idx_listing_district", "district"),
        Index("idx_listing_price", "price_number"),
        Index("idx_listing_type", "property_type"),
        Index("idx_listing_status", "status"),
        Index("idx_listing_source", "source_platform"),
        Index("idx_listing_scraped", "scraped_at"),
        Index("idx_listing_phone", "contact_phone_clean"),
        UniqueConstraint("source_url", name="uq_listing_url"),
    )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "price_text": self.price_text,
            "price_number": self.price_number,
            "price_per_m2": self.price_per_m2,
            "area_m2": self.area_m2,
            "location": {
                "address": self.address,
                "ward": self.ward,
                "district": self.district,
                "city": self.city,
                "latitude": self.latitude,
                "longitude": self.longitude,
            },
            "contact": {
                "name": self.contact_name,
                "phone": self.contact_phone,
                "phone_clean": self.contact_phone_clean,
            },
            "images": self.images or [],
            "thumbnail": self.thumbnail,
            "source_url": self.source_url,
            "source_platform": self.source_platform,
            "property_type": self.property_type,
            "bedrooms": self.bedrooms,
            "bathrooms": self.bathrooms,
            "floors": self.floors,
            "direction": self.direction,
            "legal_status": self.legal_status,
            "features": self.features or [],
            "tags": self.tags or [],
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
            "status": self.status,
            "is_verified": self.is_verified,
        }


class User(Base):
    """User model."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Auth
    telegram_id: Mapped[Optional[str]] = mapped_column(String(50), unique=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255))

    # Profile
    name: Mapped[Optional[str]] = mapped_column(String(200))
    phone: Mapped[Optional[str]] = mapped_column(String(20))
    role: Mapped[str] = mapped_column(String(20), default=UserRole.USER.value)

    # Preferences
    preferences: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    notification_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    saved_searches = relationship("SavedSearch", back_populates="user")
    saved_listings = relationship("SavedListing", back_populates="user")

    __table_args__ = (
        Index("idx_user_telegram", "telegram_id"),
        Index("idx_user_email", "email"),
    )


class ChatHistory(Base):
    """Chat history for AI assistant conversations."""

    __tablename__ = "chat_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Session info
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    session_id: Mapped[str] = mapped_column(String(50), nullable=False)

    # Message
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # 'user' or 'assistant'
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        Index("idx_chat_session", "session_id"),
        Index("idx_chat_user", "user_id"),
        Index("idx_chat_created", "created_at"),
    )



class SavedSearch(Base):
    """Saved search for alerts."""

    __tablename__ = "saved_searches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))

    # Search criteria
    name: Mapped[Optional[str]] = mapped_column(String(200))
    query: Mapped[str] = mapped_column(Text, nullable=False)
    filters: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)

    # Notification settings
    notify_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    notify_frequency: Mapped[str] = mapped_column(String(20), default="realtime")
    last_notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Stats
    match_count: Mapped[int] = mapped_column(Integer, default=0)
    last_match_at: Mapped[Optional[datetime]] = mapped_column(DateTime)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    user = relationship("User", back_populates="saved_searches")

    __table_args__ = (
        Index("idx_saved_search_user", "user_id"),
        Index("idx_saved_search_active", "is_active"),
    )


class SavedListing(Base):
    """User's saved/favorited listings."""

    __tablename__ = "saved_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    listing_id: Mapped[str] = mapped_column(String(32), ForeignKey("listings.id"))

    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text)

    # Timestamps
    saved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="saved_listings")
    listing = relationship("Listing", back_populates="saved_by")

    __table_args__ = (
        UniqueConstraint("user_id", "listing_id", name="uq_user_listing"),
        Index("idx_saved_listing_user", "user_id"),
    )


class ScrapeLog(Base):
    """Log of scraping operations."""

    __tablename__ = "scrape_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Operation details
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    query: Mapped[Optional[str]] = mapped_column(Text)
    url: Mapped[Optional[str]] = mapped_column(String(1000))

    # Results
    listings_found: Mapped[int] = mapped_column(Integer, default=0)
    listings_new: Mapped[int] = mapped_column(Integer, default=0)
    listings_updated: Mapped[int] = mapped_column(Integer, default=0)
    listings_failed: Mapped[int] = mapped_column(Integer, default=0)

    # Timing
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    duration_seconds: Mapped[Optional[float]] = mapped_column(Float)

    # Status
    status: Mapped[str] = mapped_column(String(20), default="running")
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Extra
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON)

    __table_args__ = (
        Index("idx_scrape_log_platform", "platform"),
        Index("idx_scrape_log_started", "started_at"),
        Index("idx_scrape_log_status", "status"),
    )


class SearchHistory(Base):
    """Log of user search queries."""

    __tablename__ = "search_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    query: Mapped[str] = mapped_column(Text, nullable=False)
    filters: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    results_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_search_history_user", "user_id"),
        Index("idx_search_history_created", "created_at"),
    )


class ValuationHistory(Base):
    """Log of user property valuation requests."""

    __tablename__ = "valuation_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    
    # Property info
    property_type: Mapped[str] = mapped_column(String(50), nullable=False)
    area_m2: Mapped[float] = mapped_column(Float, nullable=False)
    district: Mapped[str] = mapped_column(String(100), nullable=False)
    bedrooms: Mapped[Optional[int]] = mapped_column(Integer)
    direction: Mapped[Optional[str]] = mapped_column(String(50))
    legal_status: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Result info
    price_suggested: Mapped[Optional[BigInteger]] = mapped_column(BigInteger)
    price_min: Mapped[Optional[BigInteger]] = mapped_column(BigInteger)
    price_max: Mapped[Optional[BigInteger]] = mapped_column(BigInteger)
    confidence: Mapped[Optional[int]] = mapped_column(Integer)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_valuation_history_user", "user_id"),
        Index("idx_valuation_history_created", "created_at"),
    )


# ============================================================================
# CRUD Operations
# ============================================================================

class SearchHistoryCRUD:
    """CRUD operations for SearchHistory model."""

    @staticmethod
    async def create(session: AsyncSession, data: dict) -> SearchHistory:
        """Create a search history entry."""
        entry = SearchHistory(**data)
        session.add(entry)
        await session.flush()
        return entry

    @staticmethod
    async def list_by_user(
        session: AsyncSession,
        user_id: Optional[int] = None,
        limit: int = 20
    ) -> list[SearchHistory]:
        """List search history entries."""
        query = select(SearchHistory).order_by(SearchHistory.created_at.desc()).limit(limit)
        if user_id:
            query = query.where(SearchHistory.user_id == user_id)
        
        result = await session.execute(query)
        return list(result.scalars().all())


class ValuationHistoryCRUD:
    """CRUD operations for ValuationHistory model."""

    @staticmethod
    async def create(session: AsyncSession, data: dict) -> ValuationHistory:
        """Create a valuation history entry."""
        entry = ValuationHistory(**data)
        session.add(entry)
        await session.flush()
        return entry

    @staticmethod
    async def list_by_user(
        session: AsyncSession,
        user_id: Optional[int] = None,
        limit: int = 20
    ) -> list[ValuationHistory]:
        """List valuation history entries."""
        query = select(ValuationHistory).order_by(ValuationHistory.created_at.desc()).limit(limit)
        if user_id:
            query = query.where(ValuationHistory.user_id == user_id)
        
        result = await session.execute(query)
        return list(result.scalars().all())

class ListingCRUD:
    """CRUD operations for Listing model."""

    @staticmethod
    async def create(session: AsyncSession, data: dict) -> Listing:
        """Create a new listing."""
        listing = Listing(**data)
        session.add(listing)
        await session.flush()
        logger.debug(f"Created listing: {listing.id}")
        return listing

    @staticmethod
    async def create_many(session: AsyncSession, data_list: list[dict]) -> list[Listing]:
        """Create multiple listings."""
        listings = [Listing(**data) for data in data_list]
        session.add_all(listings)
        await session.flush()
        logger.info(f"Created {len(listings)} listings")
        return listings

    @staticmethod
    async def get_by_id(session: AsyncSession, listing_id: str) -> Optional[Listing]:
        """Get listing by ID."""
        result = await session.execute(
            select(Listing).where(Listing.id == listing_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_url(session: AsyncSession, url: str) -> Optional[Listing]:
        """Get listing by source URL."""
        result = await session.execute(
            select(Listing).where(Listing.source_url == url)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def exists(session: AsyncSession, listing_id: str) -> bool:
        """Check if listing exists."""
        result = await session.execute(
            select(Listing.id).where(Listing.id == listing_id)
        )
        return result.scalar_one_or_none() is not None

    @staticmethod
    async def update(
        session: AsyncSession,
        listing_id: str,
        data: dict
    ) -> Optional[Listing]:
        """Update listing."""
        await session.execute(
            update(Listing)
            .where(Listing.id == listing_id)
            .values(**data)
        )
        return await ListingCRUD.get_by_id(session, listing_id)

    @staticmethod
    async def delete(session: AsyncSession, listing_id: str) -> bool:
        """Soft delete listing."""
        result = await session.execute(
            update(Listing)
            .where(Listing.id == listing_id)
            .values(status=ListingStatus.DELETED.value)
        )
        return result.rowcount > 0

    @staticmethod
    async def hard_delete(session: AsyncSession, listing_id: str) -> bool:
        """Hard delete listing."""
        result = await session.execute(
            delete(Listing).where(Listing.id == listing_id)
        )
        return result.rowcount > 0

    @staticmethod
    async def list_all(
        session: AsyncSession,
        skip: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
        district: Optional[str] = None,
        property_type: Optional[str] = None,
        price_min: Optional[int] = None,
        price_max: Optional[int] = None,
        platform: Optional[str] = None,
    ) -> list[Listing]:
        """List listings with filters."""
        query = select(Listing)

        # Apply filters
        if status:
            query = query.where(Listing.status == status)
        else:
            query = query.where(Listing.status != ListingStatus.DELETED.value)

        if district:
            query = query.where(Listing.district == district)

        if property_type:
            query = query.where(Listing.property_type == property_type)

        if price_min:
            query = query.where(Listing.price_number >= price_min)

        if price_max:
            query = query.where(Listing.price_number <= price_max)

        if platform:
            query = query.where(Listing.source_platform == platform)

        # Order and paginate
        query = query.order_by(Listing.scraped_at.desc())
        query = query.offset(skip).limit(limit)

        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def count(
        session: AsyncSession,
        status: Optional[str] = None,
        district: Optional[str] = None,
    ) -> int:
        """Count listings."""
        query = select(func.count(Listing.id))

        if status:
            query = query.where(Listing.status == status)
        else:
            query = query.where(Listing.status != ListingStatus.DELETED.value)

        if district:
            query = query.where(Listing.district == district)

        result = await session.execute(query)
        return result.scalar_one()

    @staticmethod
    async def get_by_url(session: AsyncSession, url: str) -> Optional[Listing]:
        """Get listing by source URL."""
        if not url:
            return None
        result = await session.execute(
            select(Listing).where(Listing.source_url == url)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def upsert(session: AsyncSession, data: dict) -> tuple[Listing, bool]:
        """
        Insert or update listing.

        Returns:
            Tuple of (listing, is_new)
        """
        listing_id = data.get("id")
        existing = await ListingCRUD.get_by_id(session, listing_id)
        
        # Check by URL if not found by ID to prevent duplicates
        if not existing and data.get("source_url"):
            existing = await ListingCRUD.get_by_url(session, data["source_url"])

        if existing:
            # Update
            for key, value in data.items():
                if hasattr(existing, key) and key != "id":
                    setattr(existing, key, value)
            existing.updated_at = datetime.utcnow()
            await session.flush()
            return existing, False
        else:
            # Create
            try:
                listing = await ListingCRUD.create(session, data)
                return listing, True
            except Exception as e:
                # Double check race condition
                if "duplicate key" in str(e).lower() and data.get("source_url"):
                     existing = await ListingCRUD.get_by_url(session, data["source_url"])
                     if existing:
                         # Retry update
                         for key, value in data.items():
                            if hasattr(existing, key) and key != "id":
                                setattr(existing, key, value)
                         existing.updated_at = datetime.utcnow()
                         await session.flush()
                         return existing, False
                raise e

    @staticmethod
    async def get_by_phone(
        session: AsyncSession,
        phone: str,
        limit: int = 50
    ) -> list[Listing]:
        """Get listings by phone number."""
        result = await session.execute(
            select(Listing)
            .where(Listing.contact_phone_clean == phone)
            .order_by(Listing.scraped_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    @staticmethod
    async def cleanup_old(
        session: AsyncSession,
        days: int = 30
    ) -> int:
        """Mark old listings as expired."""
        from datetime import timedelta

        threshold = datetime.utcnow() - timedelta(days=days)

        result = await session.execute(
            update(Listing)
            .where(Listing.scraped_at < threshold)
            .where(Listing.status == ListingStatus.ACTIVE.value)
            .values(status=ListingStatus.EXPIRED.value)
        )

        count = result.rowcount
        logger.info(f"Marked {count} old listings as expired")
        return count


class UserCRUD:
    """CRUD operations for User model."""

    @staticmethod
    async def create(session: AsyncSession, data: dict) -> User:
        """Create a new user."""
        user = User(**data)
        session.add(user)
        await session.flush()
        return user

    @staticmethod
    async def get_by_id(session: AsyncSession, user_id: int) -> Optional[User]:
        """Get user by ID."""
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_telegram(session: AsyncSession, telegram_id: str) -> Optional[User]:
        """Get user by Telegram ID."""
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_or_create_telegram(
        session: AsyncSession,
        telegram_id: str,
        name: Optional[str] = None
    ) -> tuple[User, bool]:
        """Get or create user by Telegram ID."""
        user = await UserCRUD.get_by_telegram(session, telegram_id)
        if user:
            return user, False

        user = await UserCRUD.create(session, {
            "telegram_id": telegram_id,
            "name": name,
        })
        return user, True


class SavedSearchCRUD:
    """CRUD operations for SavedSearch model."""

    @staticmethod
    async def create(session: AsyncSession, data: dict) -> SavedSearch:
        """Create a saved search."""
        saved_search = SavedSearch(**data)
        session.add(saved_search)
        await session.flush()
        return saved_search

    @staticmethod
    async def get_by_user(
        session: AsyncSession,
        user_id: int,
        active_only: bool = True
    ) -> list[SavedSearch]:
        """Get saved searches for a user."""
        query = select(SavedSearch).where(SavedSearch.user_id == user_id)

        if active_only:
            query = query.where(SavedSearch.is_active == True)

        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_all_active(session: AsyncSession) -> list[SavedSearch]:
        """Get all active saved searches for notification."""
        result = await session.execute(
            select(SavedSearch)
            .where(SavedSearch.is_active == True)
            .where(SavedSearch.notify_enabled == True)
        )
        return list(result.scalars().all())


class ScrapeLogCRUD:
    """CRUD operations for ScrapeLog model."""

    @staticmethod
    async def create(session: AsyncSession, data: dict) -> ScrapeLog:
        """Create a scrape log entry."""
        log = ScrapeLog(**data)
        session.add(log)
        await session.flush()
        return log

    @staticmethod
    async def finish(
        session: AsyncSession,
        log_id: int,
        listings_found: int = 0,
        listings_new: int = 0,
        listings_updated: int = 0,
        listings_failed: int = 0,
        status: str = "completed",
        error_message: Optional[str] = None,
    ) -> Optional[ScrapeLog]:
        """Mark scrape log as finished."""
        now = datetime.utcnow()

        # Get the log to calculate duration
        result = await session.execute(
            select(ScrapeLog).where(ScrapeLog.id == log_id)
        )
        log = result.scalar_one_or_none()

        if log:
            duration = (now - log.started_at).total_seconds()

            await session.execute(
                update(ScrapeLog)
                .where(ScrapeLog.id == log_id)
                .values(
                    finished_at=now,
                    duration_seconds=duration,
                    listings_found=listings_found,
                    listings_new=listings_new,
                    listings_updated=listings_updated,
                    listings_failed=listings_failed,
                    status=status,
                    error_message=error_message,
                )
            )

            await session.refresh(log)

        return log

    @staticmethod
    async def get_recent(
        session: AsyncSession,
        limit: int = 20,
        platform: Optional[str] = None,
    ) -> list[ScrapeLog]:
        """Get recent scrape logs."""
        query = select(ScrapeLog).order_by(ScrapeLog.started_at.desc())

        if platform:
            query = query.where(ScrapeLog.platform == platform)

        query = query.limit(limit)

        result = await session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_stats(
        session: AsyncSession,
        days: int = 7,
    ) -> dict:
        """Get scraping statistics."""
        from datetime import timedelta

        threshold = datetime.utcnow() - timedelta(days=days)

        result = await session.execute(
            select(
                func.count(ScrapeLog.id).label("total_scrapes"),
                func.sum(case((ScrapeLog.status == "completed", 1), else_=0)).label("successful_scrapes"),
                func.sum(ScrapeLog.listings_found).label("total_listings_found"),
                func.sum(ScrapeLog.listings_new).label("total_new_listings"),
                func.avg(ScrapeLog.duration_seconds).label("avg_duration_seconds"),
            )
            .where(ScrapeLog.started_at >= threshold)
        )

        row = result.one()

        return {
            "total_scrapes": row.total_scrapes or 0,
            "successful_scrapes": row.successful_scrapes or 0,
            "total_listings_found": row.total_listings_found or 0,
            "total_new_listings": row.total_new_listings or 0,
            "avg_duration_seconds": round(row.avg_duration_seconds or 0, 2),
            "period_days": days,
        }
