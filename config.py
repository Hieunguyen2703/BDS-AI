"""
Configuration settings using Pydantic Settings.
Loads from .env file and environment variables.
"""
from pathlib import Path
from typing import Optional
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application
    app_name: str = "BDS Agent"
    app_env: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/bds_agent"
    database_sync_url: str = "postgresql://postgres:postgres@localhost:5432/bds_agent"

    # Redis
    redis_url: Optional[str] = None

    # LLM Configuration
    llm_mode: str = "ollama"  # groq, gemini, or ollama
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Google Gemini (FREE - 15 RPM, 1500 RPD)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # Ollama Fallback
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:1.5b"

    # ChromaDB
    chroma_persist_dir: str = "./data/chroma"
    chroma_collection_name: str = "bds_listings"

    # Google Sheets
    google_sheets_credentials_file: Optional[str] = None
    google_sheets_spreadsheet_id: Optional[str] = None
    google_sheets_worksheet_name: str = "Listings"

    # Telegram
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_admin_chat_id: Optional[str] = None

    # Scraping
    scrape_delay_min: int = 2
    scrape_delay_max: int = 5
    scrape_max_pages: int = 10
    headless_mode: bool = True
    browser_use_vision: bool = False

    # Google-First Search Settings
    google_search_enabled: bool = False # Disabled to prevent hallucinations (Amazon)
    max_urls_per_search: int = 8
    max_steps_google_search: int = 6
    max_steps_per_url: int = 4
    delay_between_urls: int = 20  # seconds - Groq rate limit safe
    rate_limit_per_minute: int = 25  # Groq limit is 30, use 25 for buffer

    # Validation - Price per m2 in VND
    price_min_per_m2: int = 20_000_000  # 20 triệu/m2
    price_max_per_m2: int = 300_000_000  # 300 triệu/m2
    default_city: str = "Hà Nội"

    # Scheduler
    scheduler_enabled: bool = True
    auto_scrape_interval_hours: int = 4
    cleanup_days_threshold: int = 30

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list = ["http://localhost:3000", "http://127.0.0.1:3000"]
    api_reload: bool = True

    # Frontend
    frontend_url: str = "http://localhost:3000"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def chroma_path(self) -> Path:
        path = Path(self.chroma_persist_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    # Uppercase aliases for API compatibility
    @property
    def DEBUG(self) -> bool:
        return self.debug

    @property
    def CORS_ORIGINS(self) -> list:
        return self.cors_origins

    @property
    def API_HOST(self) -> str:
        return self.api_host

    @property
    def API_PORT(self) -> int:
        return self.api_port

    @property
    def TELEGRAM_BOT_TOKEN(self) -> str:
        return self.telegram_bot_token

    @property
    def TELEGRAM_CHAT_ID(self) -> str:
        return self.telegram_chat_id

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v = v.upper()
        if v not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v


# Hanoi district price ranges (triệu VND/m2)
DISTRICT_PRICE_RANGES = {
    # Inner districts - expensive
    "Ba Đình": (80, 250),
    "Hoàn Kiếm": (100, 300),
    "Đống Đa": (70, 200),
    "Hai Bà Trưng": (60, 180),
    "Tây Hồ": (80, 250),
    "Cầu Giấy": (60, 180),
    "Thanh Xuân": (50, 150),

    # Middle districts
    "Hoàng Mai": (40, 120),
    "Long Biên": (40, 130),
    "Nam Từ Liêm": (50, 150),
    "Bắc Từ Liêm": (40, 120),
    "Hà Đông": (35, 100),

    # Outer districts - cheaper
    "Gia Lâm": (30, 80),
    "Đông Anh": (25, 70),
    "Thanh Trì": (30, 80),
    "Hoài Đức": (25, 70),
    "Đan Phượng": (20, 60),
    "Mê Linh": (15, 50),
    "Sóc Sơn": (10, 40),
    "Thạch Thất": (15, 50),
    "Quốc Oai": (15, 45),
    "Chương Mỹ": (15, 45),
    "Thanh Oai": (15, 45),
    "Thường Tín": (15, 45),
    "Phú Xuyên": (10, 35),
    "Ứng Hòa": (10, 35),
    "Mỹ Đức": (10, 30),
    "Ba Vì": (8, 25),
    "Sơn Tây": (15, 50),
    "Phúc Thọ": (15, 50),
}

# Property type mappings
PROPERTY_TYPES = {
    "chung cư": ["chung cư", "căn hộ", "apartment", "cc", "chung cu"],
    "nhà riêng": ["nhà riêng", "nhà phố", "nhà mặt tiền", "nha rieng", "townhouse"],
    "biệt thự": ["biệt thự", "villa", "biet thu"],
    "đất nền": ["đất nền", "đất thổ cư", "dat nen", "đất", "land"],
    "nhà mặt phố": ["mặt phố", "mặt đường", "mat pho", "shophouse"],
}

# Vietnamese phone regex patterns
PHONE_PATTERNS = [
    r"0[0-9]{9,10}",  # 10-11 digits starting with 0
    r"\+84[0-9]{9,10}",  # +84 prefix
    r"84[0-9]{9,10}",  # 84 prefix without +
]

# Common spam patterns to filter
SPAM_PATTERNS = [
    r"môi giới|mô giới|moigioi",
    r"ký gửi|kí gửi|ky gui",
    r"(mua|bán).*(mua|bán)",  # "mua bán" together
]

# Target platforms for scraping
SCRAPING_PLATFORMS = {
    "chotot": {
        "name": "Chợ Tốt",
        "base_url": "https://nha.chotot.com",
        "search_url": "https://nha.chotot.com/ha-noi/mua-ban-bat-dong-san",
        "priority": 1,
    },
    "batdongsan": {
        "name": "Batdongsan.com.vn",
        "base_url": "https://batdongsan.com.vn",
        "search_url": "https://batdongsan.com.vn/ban-bat-dong-san-ha-noi",
        "priority": 2,
    },
    "mogi": {
        "name": "Mogi.vn",
        "base_url": "https://mogi.vn",
        "search_url": "https://mogi.vn/ha-noi/mua-ban-bat-dong-san",
        "priority": 3,
    },
    "alonhadat": {
        "name": "Alonhadat.com.vn",
        "base_url": "https://alonhadat.com.vn",
        "search_url": "https://alonhadat.com.vn/nha-dat/can-ban/ha-noi.html",
        "priority": 4,
    },
    "facebook": {
        "name": "Facebook Groups",
        "base_url": "https://www.facebook.com",
        "priority": 5,
    },
    "google": {
        "name": "Google Search",
        "base_url": "https://www.google.com",
        "priority": 6,
    },
}


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Singleton instance
settings = get_settings()
