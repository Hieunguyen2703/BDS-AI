"""
Core Real Estate Search Agent using browser-use with Groq API.
Implements Google-First search strategy with multi-platform scraping.
Supports Groq API (fast) with Ollama fallback (local).
"""
import asyncio
import json
import re
import sys
import platform
import time
from collections import deque
from datetime import datetime, timedelta
from typing import Any, Optional, List, Dict
from dataclasses import dataclass, field

from browser_use import Agent, Browser
from loguru import logger
from bs4 import BeautifulSoup
import re

# Fix for Windows asyncio subprocess NotImplementedError
# if platform.system() == 'Windows':
#     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from config import settings
from agents.tools import extract_district


# Platform priorities for scraping
PLATFORM_PRIORITY = {
    'batdongsan': 1,
    'chotot': 1,
    'mogi': 2,
    'alonhadat': 2,
    'nhadat247': 2,
    'muaban': 3,
    'facebook': 3,
    'other': 4
}


@dataclass
class SearchIntent:
    """Parsed search intent from user query."""
    property_type: Optional[str] = None
    city: str = "Hà Nội"
    district: Optional[str] = None
    ward: Optional[str] = None
    street: Optional[str] = None
    price_min: Optional[int] = None
    price_max: Optional[int] = None
    price_text: Optional[str] = None
    area_min: Optional[float] = None
    area_max: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    features: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    requirements: list[str] = field(default_factory=list) # New: Detailed requirements (e.g., "ngõ ô tô", "nở hậu")
    intent: str = "mua"  # mua or thuê

    @classmethod
    def from_dict(cls, data: dict) -> "SearchIntent":
        """Create SearchIntent from parsed dict."""
        location = data.get("location", {})
        price = data.get("price", {})
        area = data.get("area", {})

        # Sanitize city if LLM returns "Hà Nội | Hồ Chí Minh"
        # Always force Hà Nội
        raw_city = "Hà Nội"

        return cls(
            property_type=data.get("property_type"),
            city=raw_city,
            district=location.get("district"),
            ward=location.get("ward"),
            street=location.get("street"),
            price_min=price.get("min"),
            price_max=price.get("max"),
            price_text=price.get("text"),
            area_min=area.get("min"),
            area_max=area.get("max"),
            bedrooms=data.get("bedrooms"),
            bathrooms=data.get("bathrooms"),
            features=data.get("features", []),
            keywords=data.get("keywords", []),
            requirements=data.get("requirements", []),
            intent=data.get("intent", "mua"),
        )

    def to_search_query(self) -> str:
        """Convert intent to natural language search query."""
        parts = []

        if self.intent == "thuê":
            parts.append("cho thuê")
        else:
            parts.append("mua bán")

        if self.property_type:
            parts.append(self.property_type)

        if self.bedrooms:
            parts.append(f"{self.bedrooms} phòng ngủ")

        if self.district:
            parts.append(self.district)

        if self.city and self.city != "Hà Nội":
            parts.append(self.city)

        if self.price_text:
            parts.append(self.price_text)
        elif self.price_min and self.price_max:
            min_text = f"{self.price_min / 1_000_000_000:.1f} tỷ"
            max_text = f"{self.price_max / 1_000_000_000:.1f} tỷ"
            parts.append(f"{min_text} - {max_text}")

        return " ".join(parts)


@dataclass
class SearchResult:
    """Result from a search operation."""
    listings: list[dict] = field(default_factory=list)
    total_found: int = 0
    sources_searched: list[str] = field(default_factory=list)
    from_cache: bool = False
    execution_time_ms: int = 0
    errors: list[str] = field(default_factory=list)
    synthesis: Optional[str] = None


class RealEstateSearchAgent:
    """
    AI Agent for searching and scraping real estate listings.
    Uses Google-first strategy to discover URLs, then scrapes multiple platforms.
    Supports Groq API (fast, free) with Ollama fallback (local).
    """

    def __init__(self, headless: bool = None, vision_mode: bool = None):
        """Initialize the search agent with LLM and rate limiter."""
        if headless is not None:
            settings.headless_mode = headless
        if vision_mode is not None:
            settings.browser_use_vision = vision_mode
            
        self.llm = None # Initialize LLM later
        self.agent = None
        self.browser_session = None
        self.headless = settings.headless_mode
        self.vision_mode = settings.browser_use_vision
        
        # Re-enable Google-first search (with stealth mode to avoid CAPTCHA)
        self.google_first = settings.google_search_enabled
        
        # Rate limiter for Groq API
        self.request_times = deque(maxlen=30)
        self.rate_limit_per_minute = 15 # Set explicit rate limit

        # Initialize LLM after setting up basic attributes
        self.llm = self._init_llm()
        self.llm_type = "groq" if "Groq" in type(self.llm).__name__ else "ollama"

        logger.info(f"✅ Agent initialized with LLM: {type(self.llm).__name__}")
        logger.info(f"✅ Browser headless: {self.headless}")
        logger.info(f"✅ Vision mode: {self.vision_mode}")
        logger.info(f"✅ Google-first search: {self.google_first} (forced)")

    def _init_llm(self):
        """Initialize LLM with Priority: Ollama -> Gemini -> Groq."""
        
        # 1. Priority: Ollama (Local, Unrestricted)
        try:
            from browser_use.llm.ollama.chat import ChatOllama as BrowserUseOllama
            # logger.info(f"🔄 Attempting to use Ollama ({settings.ollama_model})...")
            
            # Check if Ollama is reachable? 
            # BrowserUseOllama is lazy, but we want it as primary.
            
            llm = BrowserUseOllama(
                model=settings.ollama_model,
                host=settings.ollama_base_url,
                timeout=120, # Increase timeout for local inference
            )
            logger.info(f"✅ Selected Primary LLM: Ollama ({settings.ollama_model})")
            return llm
        except Exception as e:
            logger.warning(f"⚠️ Ollama initialization failed: {e}")

        # 2. Priority: Gemini (Fast, but Rate Limited)
        if settings.gemini_api_key:
            try:
                logger.info("🔄 Falling back to Gemini...")
                from langchain_google_genai import ChatGoogleGenerativeAI
                
                # Wrapper to satisfy browser-use 'provider' check safely
                class BrowserUseGemini(ChatGoogleGenerativeAI):
                    provider: str = "google"

                llm = BrowserUseGemini(
                    model=settings.gemini_model,
                    google_api_key=settings.gemini_api_key,
                    temperature=0.1,
                    max_retries=2,
                    timeout=60,
                )
                logger.info(f"✅ Selected Fallback LLM: Gemini")
                return llm
            except Exception as e:
                logger.warning(f"⚠️ Gemini initialization failed: {e}")

        # 3. Priority: Groq (Fastest, High Limits but 500k/day)
        if settings.groq_api_key:
            try:
                logger.info("🔄 Falling back to Groq...")
                from browser_use.llm.groq.chat import ChatGroq as BrowserUseGroq

                llm = BrowserUseGroq(
                    model=settings.groq_model,
                    api_key=settings.groq_api_key,
                    temperature=0.1,
                    timeout=30,
                    max_retries=2
                )
                logger.info(f"✅ Selected Fallback LLM: Groq")
                return llm
            except Exception as e:
                logger.warning(f"⚠️ Groq initialization failed: {e}")

        logger.error("❌ Failed to initialize ALL LLMs (Ollama, Gemini, Groq)")
        raise RuntimeError("No LLM available. Please check your API keys or Ollama.")

    async def parse_query(self, query: str) -> SearchIntent:
        """Parse natural language query into structured search intent."""
        logger.info(f"Parsing query: {query}")

        prompt = f"""Phân tích query tìm kiếm bất động sản và trả về JSON:

Query: {query}

Trả về CHÍNH XÁC JSON format (không có text khác):
{{
    "property_type": "chung cư (hoặc nhà riêng, đất nền... CHỌN 1 LOẠI DUY NHẤT)",
    "location": {{
        "city": "Hà Nội (mặc định)",
        "district": "tên quận/huyện hoặc null"
    }},
    "price": {{
        "min": số_tiền_VND_hoặc_null,
        "max": số_tiền_VND_hoặc_null,
        "text": "text giá như 2-3 tỷ"
    }},
    "bedrooms": số_hoặc_null,
    "intent": "mua | thuê",
    "requirements": ["keyword1", "keyword2"]
}}

Lưu ý quan trọng:
- 1 tỷ = 1000000000, 1 triệu = 1000000
- CHỈ TÌM KIẾM TẠI HÀ NỘI. Bỏ qua các địa danh TP.HCM.
- Quận/Huyện Hà Nội: Cầu Giấy, Đống Đa, Ba Đình, Hoàn Kiếm, Thanh Xuân, Hai Bà Trưng, Long Biên, Tây Hồ, Nam Từ Liêm, Bắc Từ Liêm, Hà Đông, Hoàng Mai, Gia Lâm, Đông Anh, Thanh Trì, Hoài Đức, Đan Phượng, Mê Linh, Sóc Sơn, Thạch Thất, Quốc Oai, v.v.
- NẾU query có tên quận/huyện, PHẢI điền vào "district"
- KHÔN NGOAN: Map địa danh về Quận tương ứng TẠI HÀ NỘI. Ví dụ:
  - "gần hồ Tây", "view hồ Tây" -> district: "Tây Hồ"
  - "gần bờ hồ", "phố cổ" -> district: "Hoàn Kiếm"
  - "gần Mỹ Đình" -> district: "Nam Từ Liêm"
  - "gần Royal City" -> district: "Thanh Xuân"
  - "gần Times City" -> district: "Hai Bà Trưng"
- "requirements" là các yêu cầu chi tiết khác ngoài giá/khu vực. Ví dụ:
  - "ngõ ô tô" -> ["ngõ ô tô", "ô tô đỗ"]
  - "kinh doanh tốt" -> ["kinh doanh"]
  - "gần hồ" -> ["gần hồ", "view hồ"]
  - "nở hậu" -> ["nở hậu"]
  - "mặt tiền" -> ["mặt tiền", "mặt phố"]
"""

        try:
            # Different message format for different LLMs
            # Different message format for different LLMs
            if "Gemini" in type(self.llm).__name__ or "Google" in type(self.llm).__name__:
                from langchain_core.messages import HumanMessage
                # Safe call for Gemini wrapper
                try:
                    response = await self.llm.ainvoke([HumanMessage(content=prompt)])
                except AttributeError:
                    # Fallback if ainvoke is missing (should stick to standard langchain interface)
                    response = self.llm.invoke([HumanMessage(content=prompt)])
                
                content = response.content if hasattr(response, 'content') else str(response)
            else:
                from browser_use.llm import UserMessage
                response = await self.llm.ainvoke([UserMessage(content=prompt)])
                content = response.completion if hasattr(response, 'completion') else str(response)

            # Extract JSON safely
            parsed = self._safe_parse_json(content)
            if parsed:
                intent = SearchIntent.from_dict(parsed)
                
                # Validation: If critical fields are missing, force fallback
                if not intent.district and not intent.price_max and not intent.price_min:
                    logger.warning("⚠️ Parsed intent is empty, triggering fallback...")
                    raise ValueError("Empty intent from LLM")

                logger.info(f"Parsed intent: property_type={intent.property_type}, "
                           f"district={intent.district}, price={intent.price_text}, reqs={intent.requirements}")
                           
                # HYBRID FIX: If LLM missed district, check fallback rules (Regex/Landmark)
                if not intent.district:
                     logger.debug("⚠️ LLM returned None for district, checking fallback rules...")
                     fallback = self._fallback_parse_query(query)
                     if fallback.district:
                         intent.district = fallback.district
                         logger.info(f"✅ Backfilled district from regex/landmark: {intent.district}")
                         
                return intent

        except Exception as e:
            logger.warning(f"Query parsing error (Primary LLM): {e}")
            
            # Semantic Fallback: Try Ollama if Gemini failed
            if "Gemini" in type(self.llm).__name__ or "Google" in type(self.llm).__name__:
                 logger.info("🔄 Switching to Ollama for fallback parsing...")
                 try:
                     from browser_use.llm.ollama.chat import ChatOllama as BrowserUseOllama
                     from browser_use.llm import UserMessage
                     from config import settings 
                     
                     ollama_llm = BrowserUseOllama(
                        model=settings.ollama_model,
                        host=settings.ollama_base_url,
                     )
                     
                     response = await ollama_llm.ainvoke([UserMessage(content=prompt)])
                     content = response.completion if hasattr(response, 'completion') else str(response)
                     
                     parsed = self._safe_parse_json(content)
                     if parsed:
                         intent = SearchIntent.from_dict(parsed)
                         logger.info(f"✅ Parsed intent via Ollama: {intent}")
                         return intent
                         
                 except Exception as ollama_e:
                     logger.warning(f"❌ Ollama fallback also failed: {ollama_e}")

        # Fallback: basic regex parsing
        return self._fallback_parse_query(query)

    def _safe_parse_json(self, text: str) -> Optional[dict]:
        """Safely extract and parse JSON from text."""
        if not text:
            return None

        try:
            # Try direct parse
            return json.loads(text.strip())
        except:
            pass

        # Try to find JSON in text
        patterns = [
            r'```json\s*(.*?)\s*```',  # Markdown code block
            r'```\s*(.*?)\s*```',       # Generic code block
            r'\{[^{}]*\}',              # Simple JSON object
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    json_str = match.group(1) if '```' in pattern else match.group(0)
                    return json.loads(json_str.strip())
                except:
                    continue

        return None

    def _fallback_parse_query(self, query: str) -> SearchIntent:
        """Fallback query parsing using regex."""
        intent = SearchIntent()
        query_lower = query.lower()

        # Property type (Accented + Unaccented)
        ptype_map = {
            "chung cu": "chung cư", "chung cư": "chung cư", "can ho": "chung cư", "căn hộ": "chung cư",
            "nha rieng": "nhà riêng", "nhà riêng": "nhà riêng", "nha dat": "nhà riêng",
            "biet thu": "biệt thự", "biệt thự": "biệt thự", "villa": "biệt thự",
            "dat nen": "đất nền", "đất nền": "đất nền", "dat tho cu": "đất nền",
            "nha mat pho": "nhà mặt phố", "nhà mặt phố": "nhà mặt phố", "shophouse": "nhà mặt phố"
        }
        
        sorted_ptypes = sorted(ptype_map.keys(), key=len, reverse=True)
        
        for ptype in sorted_ptypes:
            if ptype in query_lower:
                intent.property_type = ptype_map[ptype]
                logger.info(f"✅ Regex Fallback: Found property type '{ptype}' -> '{intent.property_type}'")
                break

        # District detection
        # 1. Check specific landmarks first
        landmark_map = {
            "hồ tây": "Tây Hồ",
            "ho tay": "Tây Hồ",
            "phố cổ": "Hoàn Kiếm",
            "hồ gươm": "Hoàn Kiếm",
            "bờ hồ": "Hoàn Kiếm",
            "royal city": "Thanh Xuân",
            "times city": "Hai Bà Trưng",
            "ecopark": "Văn Giang",
            "ocean park": "Gia Lâm",
            "smart city": "Nam Từ Liêm"
        }
        
        for landmark, district_name in landmark_map.items():
            if landmark in query_lower:
                intent.district = district_name
                break
                
        # 2. If no landmark, check standard district names
        # 2. If no landmark, check standard district names (Accented + Unaccented)
        if not intent.district:
            # Map variations to standard display name
            district_map = {
                "ba dinh": "Ba Đình", "ba đình": "Ba Đình",
                "hoan kiem": "Hoàn Kiếm", "hoàn kiếm": "Hoàn Kiếm",
                "tay ho": "Tây Hồ", "tây hồ": "Tây Hồ",
                "cau giay": "Cầu Giấy", "cầu giấy": "Cầu Giấy",
                "dong da": "Đống Đa", "đống đa": "Đống Đa",
                "hai ba trung": "Hai Bà Trưng", "hai bà trưng": "Hai Bà Trưng",
                "hoang mai": "Hoàng Mai", "hoàng mai": "Hoàng Mai",
                "thanh xuan": "Thanh Xuân", "thanh xuân": "Thanh Xuân",
                "long bien": "Long Biên", "long biên": "Long Biên",
                "nam tu liem": "Nam Từ Liêm", "nam từ liêm": "Nam Từ Liêm",
                "bac tu liem": "Bắc Từ Liêm", "bắc từ liêm": "Bắc Từ Liêm",
                "ha dong": "Hà Đông", "hà đông": "Hà Đông",
                "son tay": "Sơn Tây", "sơn tây": "Sơn Tây",
                "phuc tho": "Phúc Thọ", "phúc thọ": "Phúc Thọ",
                "dong anh": "Đông Anh", "đông anh": "Đông Anh",
                "gia lam": "Gia Lâm", "gia lâm": "Gia Lâm",
                "soc son": "Sóc Sơn", "sóc sơn": "Sóc Sơn",
                "thanh tri": "Thanh Trì", "thanh trì": "Thanh Trì",
                "hoai duc": "Hoài Đức", "hoài đức": "Hoài Đức",
                "thach that": "Thạch Thất", "thạch thất": "Thạch Thất",
                "quoc oai": "Quốc Oai", "quốc oai": "Quốc Oai",
                "thanh oai": "Thanh Oai", "thanh oai": "Thanh Oai",
                "thuong tin": "Thường Tín", "thường tín": "Thường Tín",
                "me linh": "Mê Linh", "mê linh": "Mê Linh",
                "chuong my": "Chương Mỹ", "chương mỹ": "Chương Mỹ",
                "ba vi": "Ba Vì", "ba vì": "Ba Vì",
                "dan phuong": "Đan Phượng", "đan phượng": "Đan Phượng",
                "ung hoa": "Ứng Hòa", "ứng hòa": "Ứng Hòa",
                "my duc": "Mỹ Đức", "mỹ đức": "Mỹ Đức",
                "phu xuyen": "Phú Xuyên", "phú xuyên": "Phú Xuyên"
            }
            
            # Sort keys by length desc to match longest first (e.g. "Nam Tu Liem" vs "Nam Tu")
            sorted_keys = sorted(district_map.keys(), key=len, reverse=True)
            
            for key in sorted_keys:
                if key in query_lower:
                    intent.district = district_map[key]
                    logger.info(f"✅ Regex Fallback: Found district '{key}' -> '{intent.district}'")
                    break

        # Bedrooms
        bedroom_match = re.search(r'(\d+)\s*(pn|phòng ngủ|phong ngu|pn)', query_lower)
        if bedroom_match:
            intent.bedrooms = int(bedroom_match.group(1))

        # Price
        price_match = re.search(r'(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*tỷ', query_lower)
        if price_match:
            intent.price_min = int(float(price_match.group(1)) * 1_000_000_000)
            intent.price_max = int(float(price_match.group(2)) * 1_000_000_000)
            intent.price_text = f"{price_match.group(1)}-{price_match.group(2)} tỷ"
        else:
            # Check for "dưới X tỷ" or "under X billion"
            under_match = re.search(r'dưới\s*(\d+(?:\.\d+)?)\s*tỷ', query_lower)
            if under_match:
                intent.price_max = int(float(under_match.group(1)) * 1_000_000_000)
                intent.price_text = f"dưới {under_match.group(1)} tỷ"

        # City
        # City - STRICTLY FORCE HANOI as per user request
        intent.city = "Hà Nội"
        if "hồ chí minh" in query_lower or "sài gòn" in query_lower or "hcm" in query_lower:
            logger.warning("Ignoring request for HCM, enforcing Hanoi as per policy.")

        # Intent (buy/rent)
        if "thuê" in query_lower or "cho thuê" in query_lower:
            intent.intent = "thuê"

        intent.keywords = [query]
        return intent

    async def search(self, query: str, max_results: int = 10, platforms: list = None, intent: SearchIntent = None) -> SearchResult:
        """
        Perform a comprehensive search using DIRECT SCRAPING (Optimized).
        Google Search has been removed to prevent hallucinations with local LLM.
        
        Args:
            query: Natural language query
            max_results: Maximum number of results to return
            platforms: List of platforms to scrape (chotot, batdongsan, etc)
            intent: Optional pre-parsed intent to avoid re-parsing
        """
        start_time = datetime.now()
        
        # 1. Parse Query Intent
        if not intent:
            intent = await self.parse_query(query)
        else:
            logger.info(f"Using provided intent: {intent}")
        
        result = SearchResult()

        print(f"\n{'='*60}")
        print(f"🏠 REAL ESTATE SEARCH (Direct Mode): {query}")
        print(f"{'='*60}")

        try:
            all_listings = []

            # DIRECT SCRAPE STRATEGY (Deterministic & Fast)
            print("\n📍 STEP 1: Direct Scraping (Batdongsan & Chotot)")
            all_listings = await self._fallback_direct_scrape(intent, result, platforms)

            # STEP 2: Deduplicate
            print(f"\n📍 STEP 2: Deduplication")
            
            # Safety check: ensure all_listings is a list
            if all_listings is None:
                logger.warning("all_listings is None, initializing to empty list")
                all_listings = []
            
            print(f"   [DEBUG_SEARCH] Pre-dedup count: {len(all_listings)}")
            result.listings = self._deduplicate_listings(all_listings)[:max_results]
            result.total_found = len(result.listings)

            print(f"\n{'='*60}")
            print(f"✅ TOTAL: {result.total_found} unique listings")
            print(f"   (from {len(all_listings)} raw results)")
            print(f"   Sources: {', '.join(set(result.sources_searched)) if result.sources_searched else 'None'}")
            print(f"{'='*60}")

        except Exception as e:
            logger.error(f"Search error: {e}")
            result.errors.append(str(e))
            import traceback
            traceback.print_exc()

        result.execution_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        logger.info(f"Search completed: {result.total_found} results in {result.execution_time_ms}ms")

        return result

    def _parse_google_results(self, result: Any) -> List[Dict]:
        """Parse Google search agent results into URL list."""
        try:
            content = None

            # Handle AgentHistoryList
            if hasattr(result, 'final_result'):
                content = result.final_result()
            elif hasattr(result, 'last_result'):
                content = result.last_result()
            else:
                content = str(result)

            # Already a list
            if isinstance(content, list):
                return self._validate_urls(content)

            # Parse string
            if isinstance(content, str):
                parsed = self._safe_parse_json(content)
                if isinstance(parsed, list):
                    return self._validate_urls(parsed)

                # Try to find JSON array in text
                match = re.search(r'\[.*\]', content, re.DOTALL)
                if match:
                    try:
                        urls = json.loads(match.group(0))
                        return self._validate_urls(urls)
                    except:
                        pass

            # Dict format
            if isinstance(content, dict):
                for key in ['urls', 'results', 'data']:
                    if key in content and isinstance(content[key], list):
                        return self._validate_urls(content[key])

        except Exception as e:
            logger.warning(f"Parse Google results error: {e}")

        return []

    def _validate_urls(self, urls: List[Dict]) -> List[Dict]:
        """Validate and clean URL list."""
        valid_urls = []
        seen = set()

        for item in urls:
            if not isinstance(item, dict):
                continue

            url = item.get('url', '')
            if not url or not url.startswith('http'):
                continue

            # Skip duplicates
            if url in seen:
                continue
            seen.add(url)

            # Auto-detect platform if not provided
            if not item.get('platform'):
                item['platform'] = self._detect_platform(url)

            # Skip unwanted platforms
            if item['platform'] in ['news', 'forum', 'video']:
                continue

            # Strict blacklist check
            blacklist = ['amazon', 'ebay', 'shopee', 'lazada', 'tiki', 'walmart', 'bestbuy', 'alibaba', 'taobao', '1688']
            if any(b in url.lower() for b in blacklist):
                continue

            valid_urls.append(item)

        return valid_urls

    async def _scrape_single_url(self, url_data: Dict) -> List[Dict]:
        """
        Scrape listings từ 1 URL cụ thể.

        Args:
            url_data: {url, platform, title}

        Returns:
            List of listings
        """
        url = url_data.get('url', '')
        platform = url_data.get('platform', 'other')

        print(f"   🌐 Scraping [{platform}]: {url[:70]}...")

        # Build platform-specific task
        task = self._build_scrape_task(url, platform)

        try:
            agent = Agent(
                task=task,
                llm=self.llm,
                use_vision=settings.browser_use_vision,
                max_actions_per_step=3,
            )

            result = await agent.run(max_steps=settings.max_steps_per_url)
            listings = self._parse_agent_result(result)

            # Add source info to each listing
            for listing in listings:
                listing['source_platform'] = platform
                listing['source_url'] = url

            if listings:
                print(f"      ✅ Extracted {len(listings)} listings")
            else:
                print(f"      ⚠️ No listings found")

            return listings

        except Exception as e:
            logger.error(f"Scrape error for {url}: {e}")
            print(f"      ❌ Scrape error: {e}")
            return []

    def _build_scrape_task(self, url: str, platform: str) -> str:
        """Build scraping task based on platform."""

        if platform == 'facebook':
            return f"""
NHIỆM VỤ: Extract BĐS posts từ Facebook

1. Navigate to: {url}
2. Wait for page to load
3. Scroll để load thêm content nếu cần
4. Extract posts/listings với:
   - title: tiêu đề hoặc dòng đầu post
   - price_text: giá (VD: "3.5 tỷ", "3500 triệu")
   - area_text: diện tích (VD: "85m2")
   - location: địa chỉ/khu vực
   - url: link post nếu có
   - contact: số điện thoại/zalo

5. Return JSON array (max 10 listings):
[{{"title": "...", "price_text": "...", "area_text": "...", "location": "...", "url": "...", "contact": "..."}}]

CHỈ return JSON array, không có text khác.
"""
        else:
            return f"""
NHIỆM VỤ: Extract BĐS listings từ {platform}

1. Navigate to: {url}
2. Wait for page to load completely
3. Xác định page type:
   - Nếu là SINGLE listing page: extract 1 listing đầy đủ
   - Nếu là LIST page: extract tất cả listings visible (max 10)

4. Với mỗi listing extract:
   - title: tiêu đề BĐS
   - price_text: giá hiển thị (VD: "3,5 tỷ", "35 triệu/tháng")
   - area_text: diện tích (VD: "85 m²")
   - location: địa chỉ đầy đủ hoặc quận/huyện
   - url: link chi tiết listing
   - bedrooms: số phòng ngủ (nếu có)
   - contact: số điện thoại (nếu hiển thị)

5. Return JSON array:
[{{"title": "...", "price_text": "...", "area_text": "...", "location": "...", "url": "...", "bedrooms": null, "contact": null}}]

CHỈ return JSON array với data THẬT từ page, không fake.
"""

    async def _fallback_direct_scrape(self, intent: SearchIntent, result: SearchResult, platforms_to_scrape: List[str] = None) -> List[Dict]:
        """Fallback: scrape trực tiếp bằng Playwright (không dùng AI Agent để tránh lỗi timeout)."""
        print("\n📍 Fallback: Direct platform scrape (Deterministic)")

        all_listings = []
        platforms = platforms_to_scrape or ["batdongsan", "chotot"]
        
        # Use simpler Playwright logic directly
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            # Launch browser
            # Launch browser with stealth args
            browser = await p.chromium.launch(
                headless=settings.headless_mode,
                args=[
                    "--disable-blink-features=AutomationControlled",  # Hide automation
                    "--disable-gpu", 
                    "--no-sandbox", 
                    "--disable-dev-shm-usage",
                    "--disable-web-security",  # For CORS
                    "--disable-features=IsolateOrigins,site-per-process"
                ]
            )
            
            # Stealth context with realistic user agent
            import random
            user_agents = [
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            ]
            
            context = await browser.new_context(
                viewport={"width": random.randint(1366, 1920), "height": random.randint(768, 1080)},
                user_agent=random.choice(user_agents),
                locale="vi-VN",
                timezone_id="Asia/Ho_Chi_Minh",
                extra_http_headers={
                    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
                }
            )
            
            # Add stealth scripts to hide WebDriver
            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                window.chrome = {
                    runtime: {},
                };
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
            """)
            
            try:
                for platform in platforms:
                    logger.info(f"Searching platform: {platform}")
                    result.sources_searched.append(platform)

                    try:
                        await self._rate_limit_wait()
                        
                        # Open new page for each platform
                        page = await context.new_page()
                        
                        listings = []
                        if platform == "chotot":
                            listings = await self._scrape_chotot_direct(page, intent)
                        elif platform == "batdongsan":
                            listings = await self._scrape_batdongsan_direct(page, intent)
                            
                        if listings:
                            print(f"[DEBUG_FALLBACK] Got {len(listings)} from {platform}")
                            all_listings.extend(listings)
                            logger.info(f"Platform {platform}: found {len(listings)} listings")
                        else:
                            print(f"[DEBUG_FALLBACK] Got 0 from {platform}")
                            logger.warning(f"Platform {platform}: found 0 listings")
                            
                        await page.close()
                        
                    except Exception as e:
                        logger.error(f"Platform {platform} error: {e}")
                        result.errors.append(f"{platform}: {str(e)}")

                    # Delay between platforms
                    if platform != platforms[-1]:
                        logger.info(f"⏳ Waiting 5s for rate limit cooldown...")
                        await asyncio.sleep(5)
                        
            finally:
                await browser.close()
        
        # Return all collected listings
        return all_listings


    def _filter_listings_by_intent(self, listings: List[Dict], intent: SearchIntent) -> List[Dict]:
        """Filter listings based on search intent (Price, District, City)."""
        filtered = []
        print(f"   [FILTER] Checking {len(listings)} listings against intent: Price < {intent.price_max}, Dist: {intent.district}, City: {intent.city}")
        
        for listing in listings:
            # 1. Price Check
            price = listing.get("price_number")
            if price:
                # Max price check (with 10% buffer)
                if intent.price_max and price > (intent.price_max * 1.1):
                    print(f"   [REJECT] Price {listing.get('price_text')} ({price}) > max {intent.price_max}")
                    continue
                # Min price check (with 10% buffer)
                if intent.price_min and price < (intent.price_min * 0.9):
                    print(f"   [REJECT] Price {listing.get('price_text')} ({price}) < min {intent.price_min}")
                    continue

            # 2. Strict Location Check
            l_loc = listing.get("location", {})
            l_city = l_loc.get("city", "")
            l_dist = l_loc.get("district", "")
            
            # City Mismatch (Crucial: Hanoi vs HCM)
            if intent.city and l_city:
                # 1. Exact match (case-insensitive) - FAST PATH
                if intent.city.lower() == l_city.lower():
                     pass # Match!
                else:
                    # Normalize key cities
                    c1 = intent.city.lower()
                    c2 = l_city.lower()
                    
                    # Check mapping for HN/HCM variants
                    hn_variants = ["hà nội", "ha noi", "hn"]
                    hcm_variants = ["hồ chí minh", "ho chi minh", "hcm", "sài gòn", "sai gon", "tp.hcm"]
                    
                    is_hn_1 = any(v in c1 for v in hn_variants)
                    is_hn_2 = any(v in c2 for v in hn_variants)
                    is_hcm_1 = any(v in c1 for v in hcm_variants)
                    is_hcm_2 = any(v in c2 for v in hcm_variants)
                    
                    # Log logic for debugging
                    # print(f"DEBUG: City check '{c1}' vs '{c2}' -> HN1:{is_hn_1}, HN2:{is_hn_2}, HCM1:{is_hcm_1}, HCM2:{is_hcm_2}")

                    if (is_hn_1 and is_hcm_2) or (is_hcm_1 and is_hn_2):
                        print(f"   [REJECT] City mismatch: Intent '{intent.city}' vs Listing '{l_city}'")
                        continue
                    
                    # If intent is specific (e.g. "Hà Nội") and listing is just "Toàn Quốc" or different, we might keep it 
                    # if the district matches, but here we cover the hard mismatch case.

            # District Mismatch
            if intent.district and l_dist:
                d1 = intent.district.lower().replace("quận", "").replace("huyện", "").strip()
                d2 = l_dist.lower().replace("quận", "").replace("huyện", "").strip()
                
                # If scraping found a district, it MUST match intent if intent has district
                # (Allow partial match e.g., "Thanh Xuan" in "Thanh Xuan Trung")
                if d1 not in d2 and d2 not in d1:
                     print(f"   [REJECT] District mismatch: Intent '{intent.district}' vs Listing '{l_dist}'")
                     continue
            
            # Backfill REMOVED - User requested Strict Mode ("Quality over Quantity")
            # If listing has no district/city but intent requires it, we must REJECT it
            # instead of assuming it matches.
            
            # Strict District Check for Missing Data
            if intent.district and not l_dist:
                 print(f"   [REJECT] Missing District info (Intent requires '{intent.district}')")
                 continue
                 
            # Strict Bedroom Check for Missing Data
            if intent.bedrooms:
                l_bedrooms = listing.get("bedrooms")
                if l_bedrooms is None:
                     print(f"   [REJECT] Missing Bedroom info (Intent requires {intent.bedrooms})")
                     continue
                try:
                    if int(l_bedrooms) != intent.bedrooms:
                         print(f"   [REJECT] Bedroom mismatch: Intent {intent.bedrooms} vs Listing {l_bedrooms}")
                         continue
                except:
                     pass

            # 5. Strict Property Type Check (New)
            # If intent is "chung cư", reject "nhà đất", "biệt thự", "liền kề" if title is clear.
            if intent.property_type:
                pt_lower = intent.property_type.lower()
                title_lower = listing.get("title", "").lower()

                # Define keywords for common types
                # Map intent type -> [must_have_one_of] OR [must_not_have]
                # For now, strict inclusion for "chung cư"
                if "chung cư" in pt_lower or "căn hộ" in pt_lower:
                    valid_keywords = ["chung cư", "căn hộ", "tập thể", "apartment", "condo"]
                    if not any(k in title_lower for k in valid_keywords):
                        print(f"   [REJECT] Property Type mismatch: Intent '{intent.property_type}' vs Title '{listing.get('title')}'")
                        continue
                
                elif "đất" in pt_lower:
                    if not any(k in title_lower for k in ["đất", "thổ cư", "lô"]):
                         print(f"   [REJECT] Property Type mismatch: Intent '{intent.property_type}' vs Title '{listing.get('title')}'")
                         continue

            filtered.append(listing)
        
        print(f"   [FILTER] Kept {len(filtered)}/{len(listings)} listings")
        return filtered

    async def _scrape_chotot_direct(self, page, intent) -> List[Dict]:
        """Scrape Chợ Tốt using robust BeautifulSoup parsing."""
        # Clean up property type for better search
        prop_type = intent.property_type
        if prop_type and "|" in prop_type:
            prop_type = prop_type.split("|")[0].strip()
            
        # Simplified Query Construction for ChoTot: [Loại BĐS] + [Quận]
        # Example: "chung cư Ba Đình", "nhà đất Cầu Giấy"
        district_name = intent.district or ""
        # Remove prefixes like "Quận", "Huyện" for cleaner search
        import re
        district_clean = re.sub(r'^(Quận|Huyện)\s+', '', district_name, flags=re.IGNORECASE)
        
        query = f"{prop_type or 'bất động sản'} {district_clean} {intent.city or ''}"
        
        # Optimize Region Slug
        region_slug = "toan-quoc"
        if intent.city:
            if "hà nội" in intent.city.lower():
                region_slug = "ha-noi"
            elif "hồ chí minh" in intent.city.lower():
                region_slug = "tp-ho-chi-minh"
            elif "đà nẵng" in intent.city.lower():
                region_slug = "da-nang"
        
        # Optimize District Slug Mapping
        district_slug = ""
        if intent.district:
            d_lower = intent.district.lower()
            slug_map = {
                "ba đình": "/quan-ba-dinh",
                "hoàn kiếm": "/quan-hoan-kiem",
                "tây hồ": "/quan-tay-ho",
                "long biên": "/quan-long-bien",
                "cầu giấy": "/quan-cau-giay",
                "đống đa": "/quan-dong-da",
                "hai bà trưng": "/quan-hai-ba-trung",
                "hoàng mai": "/quan-hoang-mai",
                "thanh xuân": "/quan-thanh-xuan",
                "sóc sơn": "/huyen-soc-son",
                "đông anh": "/huyen-dong-anh",
                "gia lâm": "/huyen-gia-lam",
                "nam từ liêm": "/quan-nam-tu-liem",
                "thanh trì": "/huyen-thanh-tri",
                "bắc từ liêm": "/quan-bac-tu-liem",
                "mê linh": "/huyen-me-linh",
                "hà đông": "/quan-ha-dong",
                "sơn tây": "/thi-xa-son-tay",
                "ba vì": "/huyen-ba-vi",
                "phúc thọ": "/huyen-phuc-tho",
                "đan phượng": "/huyen-dan-phuong",
                "hoài đức": "/huyen-hoai-duc",
                "quốc oai": "/huyen-quoc-oai",
                "thạch thất": "/huyen-thach-that",
                "chương mỹ": "/huyen-chuong-my",
                "thanh oai": "/huyen-thanh-oai",
                "thường tín": "/huyen-thuong-tin",
                "phú xuyên": "/huyen-phu-xuyen",
                "ứng hòa": "/huyen-ung-hoa",
                "mỹ đức": "/huyen-my-duc"
            }
            # Find best match
            for k, v in slug_map.items():
                if k in d_lower:
                    district_slug = v
                    break
        
        encoded_query = query.strip().replace(" ", "+")
        
        # Priority: URL Structure > Query Param
        # If district known, go to /ha-noi/quan-ba-dinh/mua-ban-bat-dong-san
        if district_slug:
             url = f"https://nha.chotot.com/{region_slug}{district_slug}/mua-ban-bat-dong-san?q={encoded_query}"
        else:
             url = f"https://nha.chotot.com/{region_slug}/mua-ban-bat-dong-san?q={encoded_query}"
        
        print(f"   🌐 Navigating to: {url}")
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000) # Wait for hydration
            
            html = await page.content()
            soup = BeautifulSoup(html, 'lxml')
            listings = []
            
            # CSS Selector Update for Chotot (2025 Layout)
            # Listings are usually in <li> inside <ul>
            # Searching for standard list items
            candidates = soup.find_all('li')
            print(f"   Structure scan: Found {len(candidates)} list items")
            
            seen_urls = set()
            
            price_pattern = re.compile(r"(\d+(?:[.,]\d+)?)\s*(tỷ|triệu)", re.IGNORECASE)
            
            for item in candidates:
                try:
                    # HEURISTIC: A valid listing LI usually contains an <a> tag and Price text
                    link_tag = item.find('a')
                    text_content = item.get_text(" ", strip=True)
                    
                    if not link_tag: continue
                    
                    # Must look like a real estate listing
                    href = link_tag.get('href', '')
                    if not href or href in seen_urls: continue
                    
                    # Filter out non-listing links (e.g. footer links, nav)
                    if not any(x in href for x in ['.htm', 'mua-ban-bat-dong-san']):
                         continue
                         
                    # Price check is mandatory for a valid listing
                    price_match = price_pattern.search(text_content)
                    if not price_match: continue

                    if href.startswith('/'):
                        href = f"https://nha.chotot.com{href}"
                    seen_urls.add(href)
                    
                    # Extraction
                    title = link_tag.get_text(" ", strip=True)
                    
                    # Extract Price
                    price = price_match.group(0)
                    price_number = self._parse_price_to_number(price)
                    
                    # Extract Area
                    import re
                    area_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(m²|m2)", text_content, re.IGNORECASE)
                    area_val = area_match.group(1) if area_match else None
                    area = self._normalize_vietnamese_number(area_val) if area_val else None
                    
                    # Location Heuristic
                    # Chotot listing usually has district in text if we are lucky, OR we inherit from Intent
                    # Inherit from Intent if we are on a district-specific page
                    address = "N/A"
                    listing_district = None
                    if district_slug and intent.district:
                         listing_district = intent.district # Inherit HIGH confidence
                         address = f"{intent.district}, {intent.city}"
                    
                    # If not inherited, try to parse
                    if not listing_district:
                        listing_district = extract_district(text_content)
                    
                    location = {
                        "address": address,
                        "district": listing_district or intent.district, # Fallback to intent
                        "city": intent.city or "Hà Nội"
                    }

                    listings.append({
                        "title": title,
                        "price_text": price,
                        "price_number": price_number,
                        "area_m2": area,
                        "bedrooms": None, # Chotot list view hard to get bedrooms reliably without detail page
                        "location": location,
                        "contact": {"phone_clean": "Liên hệ"}, 
                        "source_url": href,
                        "source_platform": "chotot"
                    })
                    
                    if len(listings) >= 12: break # Limit 
                    
                except Exception as e:
                    continue

            print(f"   Extracted {len(listings)} listings from Chotot")
            return self._filter_listings_by_intent(listings, intent)
            
        except Exception as e:
            logger.error(f"Chotot scrape error: {e}")
            return []

    async def _scrape_batdongsan_direct(self, page, intent) -> List[Dict]:
        """Scrape Batdongsan using robust BeautifulSoup parsing with district targeting."""
        
        # Map common districts to slugs
        district_slugs = {
            "cầu giấy": "cau-giay",
            "đống đa": "dong-da",
            "ba đình": "ba-dinh",
            "hoàn kiếm": "hoan-kiem",
            "thanh xuân": "thanh-xuan",
            "hai bà trưng": "hai-ba-trung",
            "long biên": "long-bien",
            "tây hồ": "tay-ho",
            "nam từ liêm": "nam-tu-liem",
            "bắc từ liêm": "bac-tu-liem",
            "hà đông": "ha-dong",
            "hoàng mai": "hoang-mai",
            "thanh trì": "thanh-tri",
            "gia lâm": "gia-lam",
            "đông anh": "dong-anh",
            "sóc sơn": "soc-son",
            "hoài đức": "hoai-duc",
            "thạch thất": "thach-that",
            "quốc oai": "quoc-oai",
            "thanh oai": "thanh-oai",
            "thường tín": "thuong-tin",
            "mê linh": "me-linh",
            "chương mỹ": "chuong-my",
            "sơn tây": "son-tay",
            "ba vì": "ba-vi",
            "phúc thọ": "phuc-tho",
            "đan phượng": "dan-phuong",
            "ứng hòa": "ung-hoa",
            "mỹ đức": "my-duc",
            "phú xuyên": "phu-xuyen"
        }

        # Construct optimized URL
        # Batdongsan structure: /ban-nha-dat-[quan] or /ban-chung-cu-[quan]
        
        base_action = "ban-nha-dat"
        if intent.property_type:
            pt_lower = intent.property_type.lower()
            if "chung cư" in pt_lower or "căn hộ" in pt_lower:
                base_action = "ban-can-ho-chung-cu"
            elif "nhà riêng" in pt_lower:
                base_action = "ban-nha-rieng"
            elif "biệt thự" in pt_lower or "liền kề" in pt_lower:
                 base_action = "ban-biet-thu-lien-ke"
            elif "nhà mặt phố" in pt_lower:
                base_action = "ban-nha-mat-pho"
            elif "shophouse" in pt_lower or "nhà phố thương mại" in pt_lower:
                base_action = "ban-shophouse-nha-pho-thuong-mai"
            elif "đất nền" in pt_lower:
                base_action = "ban-dat-nen-du-an"
            elif "đất" in pt_lower:
                base_action = "ban-dat"
            elif "trang trại" in pt_lower or "nghỉ dưỡng" in pt_lower:
                base_action = "ban-trang-trai-khu-nghi-duong"
            elif "condotel" in pt_lower:
                base_action = "ban-condotel"
            elif "kho" in pt_lower or "xưởng" in pt_lower:
                base_action = "ban-kho-nha-xuong"
                
        base_url = f"https://batdongsan.com.vn/{base_action}"
        city_slug = "ha-noi"
        
        if intent.city and "hồ chí minh" in intent.city.lower():
            city_slug = "ho-chi-minh"
        
        target_path = f"{base_url}-{city_slug}"

        # If specific district found, use its slug instead of city
        # Batdongsan URL format: /ban-nha-dat-[district-slug] (implicitly specific to that district)
        # Note: Usually just /ban-nha-dat-tay-ho (no "ha-noi" suffix if district is known unique, or maybe /ban-nha-dat-tay-ho-ha-noi?)
        # Standard Batdongsan: /ban-...-[district]-[city]
        
        district_slug_part = ""
        if intent.district:
            d_lower = intent.district.lower().replace("quận", "").replace("huyện", "").strip()
            if d_lower in district_slugs:
                d_slug = district_slugs[d_lower]
                # Batdongsan usually appends city after district: tay-ho-ha-noi
                target_path = f"{base_url}-{d_slug}-{city_slug}"
                district_slug_part = d_slug
            elif city_slug == "ha-noi":
                 naive_slug = d_lower.replace(" ", "-")
                 target_path = f"{base_url}-{naive_slug}-{city_slug}"

        url = target_path
        print(f"   🌐 Navigating to: {url}")
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)
            
            html = await page.content()
            soup = BeautifulSoup(html, 'lxml')
            listings = []
            
            # IMPROVED SELECTOR: Focus on .js__card (Official class for listings)
            candidates = soup.select(".js__card")
            if not candidates:
                 # Backup selectors if site updated
                 candidates = soup.select("div[class*='product-item'], .re__card-full")
            
            print(f"   Structure scan: Found {len(candidates)} listings via class")
            
            if len(candidates) == 0:
                 # Fallback to broad scan but filter heavily
                 print("   Structure unclear, using broad div scan...")
                 candidates = soup.find_all('div', class_=True)

            price_pattern = re.compile(r"(\d+(?:[.,]\d+)?)\s*(tỷ|triệu|nghìn/m2|nghìn/m²)", re.IGNORECASE)
            area_pattern = re.compile(r"(\d+(?:[.,]\d+)?)\s*(m²|m2)", re.IGNORECASE)
            bedroom_pattern = re.compile(r"(\d+)\s*(pn|phòng ngủ|ngủ)", re.IGNORECASE)
            
            seen_urls = set()

            for item in candidates:
                try:
                    text = item.get_text(" ", strip=True)
                    link_tag = item.find('a')
                    
                    if not link_tag: continue
                    if not price_pattern.search(text): continue
                    
                    full_url = link_tag.get('href', '')
                    if not full_url or full_url in seen_urls: continue
                    
                    if full_url.startswith('/'):
                        full_url = f"https://batdongsan.com.vn{full_url}"
                    
                    # Skip project intro or news links
                    if "/du-an/" in full_url or "/tin-tuc/" in full_url: continue
                    
                    seen_urls.add(full_url)
                    
                    # Check if it's a real listing (has price and area usually)
                    price_match = price_pattern.search(text)
                    area_match = area_pattern.search(text)
                    
                    # Ignore if "Liên hệ" is the price? No, we might want those. But user asked for prices.
                    # Price processing
                    price_txt = price_match.group(0) if price_match else "Liên hệ"
                    
                    # Normalize area
                    area_val = area_match.group(1) if area_match else None
                    area_normalized = self._normalize_vietnamese_number(area_val) if area_val else None

                    # Extract Phone
                    phone_pattern = re.compile(r"(0\d{3}[\s.]?\d{3}[\s.]?\d{3}|0\d{2}[\s.]?\d{3}[\s.]?\d{3})")
                    phone_match = phone_pattern.search(text)
                    phone = phone_match.group(0) if phone_match else "Liên hệ"
                    
                    # Location Logic
                    # If we are on a targeted URL (e.g. /ba-dinh), we trust the intent district logic more
                    # But verifying text is good
                    listing_district = None
                    address_text = "N/A"
                    
                    # Batdongsan cards often have a location span
                    # Try to find location element
                    loc_elem = item.select_one(".re__card-location, span[class*='location']")
                    if loc_elem:
                        address_text = loc_elem.get_text(strip=True)
                    elif "Hà Nội" in text:
                         address_text = "Hà Nội"
                    
                    # Extract district from address_text
                    # Extract district from address_text
                    if address_text != "N/A":
                         listing_district = extract_district(address_text)
                         # Debug location extraction
                         # print(f"   [LOC] '{address_text}' -> '{listing_district}'")
                    
                    # FALLBACK REMOVED: Do not force intent.district if extraction failed. 
                    # This caused "Suggested" items (e.g. Nam Tu Liem) to be labeled as "Dong Da".
                    
                    address_full = address_text
                    if listing_district and intent.district and listing_district.lower() != intent.district.lower():
                         # If we found a district and it doesn't match intent (while on a valid URL),
                         # it might be a "Suggested" item.
                         pass

                    location = {
                        "address": address_text,
                        "district": listing_district, # STRICT: Only use extracted district
                        "city": intent.city or "Hà Nội"
                    }
                    
                    # Bedrooms
                    bedrooms = None
                    bd_match = bedroom_pattern.search(text)
                    if bd_match:
                         try: bedrooms = int(bd_match.group(1))
                         except: pass

                    # Parse price
                    price_number = self._parse_price_to_number(price_txt)
                    
                    # Title
                    title = link_tag.get_text(" ", strip=True)
                    if not title or len(title) < 10:
                        # Try finding title in h3 or span
                        h3 = item.find('h3')
                        if h3: title = h3.get_text(strip=True)
                    
                    listings.append({
                        "title": title,
                        "price_text": price_txt,
                        "price_number": price_number,
                        "area_m2": area_normalized,
                        "bedrooms": bedrooms,
                        "location": location,
                        "contact": {"phone_clean": phone},
                        "source_url": full_url,
                        "source_platform": "batdongsan"
                    })
                    
                    if len(listings) >= 12: break
                    
                except Exception as e:
                    continue
                    
            print(f"   Extracted {len(listings)} listings from Batdongsan")
            return self._filter_listings_by_intent(listings, intent)
            
        except Exception as e:
            logger.error(f"Batdongsan scrape error: {e}")
            return []

    @staticmethod
    def _parse_price_to_number(price_text: str) -> Optional[float]:
        """
        Parse Vietnamese price text to number in VND.
        Examples:
            "29,88 tỷ" → 29880000000
            "3.5 tỷ" → 3500000000
            "500 triệu" → 500000000
            "Thỏa thuận" → None
        """
        if not price_text or not isinstance(price_text, str):
            return None
        
        # Skip if contains negotiation keywords
        negotiation_keywords = ['thỏa thuận', 'liên hệ', 'thoả thuận', 'lien he']
        if any(kw in price_text.lower() for kw in negotiation_keywords):
            return None
        
        # Use the normalize function which already handles tỷ/triệu
        val = RealEstateSearchAgent._normalize_vietnamese_number(price_text)
        return int(val) if val is not None else None

    async def _rate_limit_wait(self):
        """Wait if approaching Groq rate limit."""
        now = time.time()
        self.request_times.append(now)

        # Check requests in last 60s
        one_minute_ago = now - 60
        recent_requests = [t for t in self.request_times if t > one_minute_ago]

        if len(recent_requests) >= self.rate_limit_per_minute:
            oldest = min(recent_requests)
            wait_time = 60 - (now - oldest) + 1  # Reduced buffer from 3s to 1s

            if wait_time > 0:
                print(f"   ⏸️ Rate limit: waiting {wait_time:.0f}s...")
                await asyncio.sleep(wait_time)

    @staticmethod
    def _normalize_vietnamese_number(value: str) -> Optional[float]:
        """Convert Vietnamese number format to float.
        Examples: '67,5' -> 67.5, '1.200' -> 1200, '2,5 tỷ' -> 2500000000
        """
        if not value or not isinstance(value, str):
            return None
        
        try:
            # Remove whitespace and convert to lowercase
            value = value.strip().lower()
            
            # Handle billion/million suffixes
            multiplier = 1
            if 'tỷ' in value or 'ty' in value:
                multiplier = 1_000_000_000
                value = value.replace('tỷ', '').replace('ty', '').strip()
            elif 'triệu' in value or 'tr' in value:
                multiplier = 1_000_000
                value = value.replace('triệu', '').replace('tr', '').strip()
            
            # Remove any non-numeric characters except comma and dot
            value = re.sub(r'[^0-9,.]', '', value)
            
            # Determine if comma is decimal separator or thousands separator
            # If there's both comma and dot, assume European format (1.234,56)
            if ',' in value and '.' in value:
                # European: 1.234,56 -> remove dots, replace comma with dot
                value = value.replace('.', '').replace(',', '.')
            elif ',' in value:
                # Vietnamese decimal: 67,5 -> 67.5
                # But also handle thousands: 1,200 -> 1200
                parts = value.split(',')
                if len(parts) == 2 and len(parts[1]) <= 2:
                    # Likely decimal: 67,5
                    value = value.replace(',', '.')
                else:
                    # Likely thousands: 1,200
                    value = value.replace(',', '')
            
            result = float(value) * multiplier
            return result if result > 0 else None
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _detect_platform(url: str) -> str:
        """Detect platform from URL."""
        url_lower = url.lower()

        if 'chotot.com' in url_lower or 'nhatot.com' in url_lower:
            return 'chotot'
        elif 'batdongsan.com' in url_lower:
            return 'batdongsan'
        elif 'facebook.com' in url_lower:
            return 'facebook'
        elif 'mogi.vn' in url_lower:
            return 'mogi'
        elif 'alonhadat.com' in url_lower:
            return 'alonhadat'
        elif 'nhadat247.com' in url_lower:
            return 'nhadat247'
        elif 'muaban.net' in url_lower:
            return 'muaban'
        elif any(x in url_lower for x in ['vnexpress', 'dantri', 'cafef', 'vietnamnet']):
            return 'news'
        elif any(x in url_lower for x in ['youtube', 'tiktok']):
            return 'video'
        elif any(x in url_lower for x in ['webtretho', 'otofun']):
            return 'forum'
        else:
            return 'other'

    async def _search_platform(self, platform: str, intent: SearchIntent) -> List[Dict]:
        """Search a specific platform."""
        if platform == "chotot":
            return await self._search_chotot(intent)
        elif platform == "batdongsan":
            return await self._search_batdongsan(intent)
        else:
            logger.warning(f"Platform {platform} not implemented")
            return []

    async def _search_chotot(self, intent: SearchIntent) -> List[Dict]:
        """Search Chợ Tốt for listings."""

        task = f"""
Tìm kiếm bất động sản trên Chợ Tốt:
- Loại: {intent.property_type or 'tất cả'}
- Khu vực: {intent.district or intent.city}
- Giá: {intent.price_text or 'không giới hạn'}
- Phòng ngủ: {intent.bedrooms or 'không giới hạn'}

Các bước:
1. Truy cập https://nha.chotot.com/ha-noi/mua-ban-bat-dong-san
2. Thu thập 5 listing đầu tiên
3. Cho mỗi listing, lấy: tiêu đề, giá, diện tích, địa chỉ, URL

Trả về JSON array:
[{{"title": "...", "price_text": "...", "area_text": "...", "location": "...", "url": "..."}}]
"""

        try:
            agent = Agent(
                task=task,
                llm=self.llm,
                use_vision=settings.browser_use_vision,
                max_actions_per_step=3,
            )

            result = await agent.run(max_steps=5)
            return self._parse_agent_result(result)

        except Exception as e:
            logger.error(f"Chợ Tốt search error: {e}")
            return []

    async def _search_batdongsan(self, intent: SearchIntent) -> List[Dict]:
        """Search Batdongsan.com.vn using direct scraping logic."""
        logger.info(f"🔍 Direct scraping Batdongsan for: {intent.city} - {intent.district}")
        
        # Initialize browser agent just for the context (or reuse existing if architecture allows)
        # But here we need to run the _scrape_batdongsan_direct method which takes (page, intent)
        # We'll use a temporary Browser-Use agent to get the browser context
        
        try:
            task = "Scrape batdongsan" # Dummy task
            agent = Agent(
                task=task,
                llm=self.llm,
                use_vision=False
            )
            
            # Custom action to run our direct scraper
            async def perform_scrape(browser_context):
                page = await browser_context.get_current_page()
                return await self._scrape_batdongsan_direct(page, intent)
            
            # We can't easily inject this into agent.run(), so we might need to manually handle browser
            # Or simpler: The SearchAgent class should probably manage the browser itself if we are doing direct scraping.
            # However, looking at _scrape_chotot_direct usage (it's not used yet? or mixed?)
            # Let's see how _search_chotot is implemented. it uses self._search_chotot(intent) which calls agent.run()
            
            # Wait, `_scrape_batdongsan_direct` expects a playwright `page` object.
            # To get a page object, we can use the Agent's browser.
            
            # Hack: Use a minimal Agent run to get access, OR rewrite to just launch a playwright browser.
            # Since RealEstateSearchAgent seems to be designed around "Browser Use" library, we should stick to it if possible,
            # but for direct scraping we want control.
            
            # If we utilize the existing 'agent' infrastructure:
            # The 'search' method (main entry) calls _search_platform.
            
            # Let's instantiate a browser explicitly for direct control, it's faster and more reliable for this specific task.
            from playwright.async_api import async_playwright
            
            listings = []
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=settings.headless_mode)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = await context.new_page()
                listings = await self._scrape_batdongsan_direct(page, intent)
                await browser.close()
                
            return listings

        except Exception as e:
            logger.error(f"Batdongsan direct search error: {e}")
            return []

    def _parse_agent_result(self, result: Any) -> List[Dict]:
        """Parse agent result into list of dicts."""
        try:
            # Handle AgentHistoryList
            if hasattr(result, 'final_result'):
                content = result.final_result()
            elif hasattr(result, 'last_result'):
                content = result.last_result()
            else:
                content = str(result)

            # Already a list
            if isinstance(content, list):
                return content

            # Parse string
            if isinstance(content, str):
                parsed = self._safe_parse_json(content)
                if isinstance(parsed, list):
                    return parsed

                # Try to find JSON array
                match = re.search(r'\[.*\]', content, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group(0))
                    except:
                        pass

            # Dict with results
            if isinstance(content, dict):
                for key in ['results', 'listings', 'data']:
                    if key in content and isinstance(content[key], list):
                        return content[key]

        except Exception as e:
            logger.warning(f"Parse agent result error: {e}")

        return []

    def _deduplicate_listings(self, listings: List[Dict]) -> List[Dict]:
        """Remove duplicate listings based on URL, title, or phone."""
        print(f"   [DEDUP] Processing {len(listings)} listings...")
        seen_urls = set()
        seen_titles = set()
        unique = []

        for listing in listings:
            # Get identifiers
            url = listing.get('url') or listing.get('source_url', '')
            title = listing.get('title', '').lower().strip()[:50]  # First 50 chars
            phone = listing.get('contact', '')

            # Create multiple keys for dedup
            url_key = url if url else None
            title_key = title if title else None
            
            # Check if duplicate
            is_dup = False
            if url_key and url_key in seen_urls:
                is_dup = True
                print(f"   [DEDUP] Duplicate URL: {url_key}")
            if title_key and title_key in seen_titles:
                is_dup = True
                print(f"   [DEDUP] Duplicate Title: {title_key}")

            if not is_dup:
                if url_key:
                    seen_urls.add(url_key)
                if title_key:
                    seen_titles.add(title_key)
                unique.append(listing)
            else:
                 print(f"   [DEDUP] Dropped listing: {title}")

        logger.info(f"Deduplicated: {len(listings)} -> {len(unique)} listings")
        print(f"   [DEDUP] Final count: {len(unique)}")
        return unique

    async def close(self):
        """Close any active resources."""
        pass

    async def search_with_progress(self, query: str, progress_callback=None, max_results: int = 20, platforms: List[str] = None) -> SearchResult:
        """Search with simulated progress updates."""
        if progress_callback:
            await progress_callback({"percent": 10, "message": "Đang phân tích yêu cầu..."})
        
        # Call standard search
        result = await self.search(query, max_results)
        
        if progress_callback:
            await progress_callback({"percent": 100, "message": "Tìm kiếm hoàn tất!"})
            
        return result

    async def health_check(self) -> Dict:
        """Check LLM health and connection."""
        try:
            start = time.time()

            # Different message format for different LLMs
            if "Gemini" in type(self.llm).__name__ or "Google" in type(self.llm).__name__:
                # Langchain format for Gemini
                from langchain_core.messages import HumanMessage
                response = await self.llm.ainvoke([HumanMessage(content="ping")])
                content = response.content if hasattr(response, 'content') else str(response)
            else:
                # browser-use format for Groq/Ollama
                from browser_use.llm import UserMessage
                response = await self.llm.ainvoke([UserMessage(content="ping")])
                content = response.completion if hasattr(response, 'completion') else str(response)

            elapsed = int((time.time() - start) * 1000)

            return {
                "status": "healthy",
                "llm_type": self.llm_type,
                "llm_class": type(self.llm).__name__,
                "response_time_ms": elapsed,
                "headless": settings.headless_mode,
                "vision_enabled": settings.browser_use_vision,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "llm_type": self.llm_type,
            }

    def get_stats(self) -> Dict:
        """Get current configuration stats."""
        return {
            "llm_mode": settings.llm_mode,
            "llm_type": self.llm_type,
            "model": settings.groq_model if settings.llm_mode == "groq" else settings.ollama_model,
            "headless": settings.headless_mode,
            "vision_enabled": settings.browser_use_vision,
        }


async def quick_search(query: str, max_results: int = 20) -> SearchResult:
    """Helper function for quick one-off searches."""
    agent = RealEstateSearchAgent()
    try:
        return await agent.search(query, max_results)
    finally:
        await agent.close()
