
import asyncio
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from loguru import logger
from agents.search_agent import RealEstateSearchAgent
from storage.database import init_db, close_db, get_session, ListingCRUD, ScrapeLogCRUD
from storage.vector_db import index_listings
from services.validator import get_validator

# Comprehensive list of queries to cover Hanoi market
QUERIES = [
    # Cầu Giấy
    "chung cư Cầu Giấy 2-4 tỷ",
    "nhà riêng Cầu Giấy 5-10 tỷ",
    "văn phòng cho thuê Cầu Giấy",
    
    # Đống Đa
    "nhà ngõ Đống Đa 3-6 tỷ",
    "chung cư Đống Đa dưới 3 tỷ",
    "nhà mặt phố Đống Đa kinh doanh",

    # Thanh Xuân
    "chung cư Thanh Xuân 3 phòng ngủ",
    "nhà riêng Thanh Xuân 4-7 tỷ",
    "chung cư mini Thanh Xuân cho thuê",

    # Tây Hồ
    "biệt thự Tây Hồ view hồ",
    "căn hộ dịch vụ Tây Hồ cho thuê",
    "nhà riêng Tây Hồ 5-10 tỷ",

    # Long Biên
    "đất nền Long Biên 30-50m2",
    "liền kề Vinhomes Riverside Long Biên",
    "nhà riêng Long Biên dưới 3 tỷ",

    # Nam Từ Liêm
    "chung cư Mỹ Đình 2-3 tỷ",
    "nhà đất Nam Từ Liêm 3-5 tỷ",
    "biệt thự Nam Từ Liêm",

    # Hà Đông
    "chung cư Hà Đông dưới 2 tỷ",
    "nhà liền kề Hà Đông 5-8 tỷ",
    "đất dịch vụ Hà Đông",

    # Hoàng Mai
    "chung cư Hoàng Mai giá rẻ",
    "nhà riêng Hoàng Mai 2-4 tỷ",
    
    # Hai Bà Trưng
    "nhà mặt phố Hai Bà Trưng",
    "chung cư cao cấp Hai Bà Trưng",
]

async def main():
    logger.info("🚀 Starting BULK SCRAPE for Data Population...")
    
    # Init DB
    await init_db()
    
    # Init Agent
    agent = RealEstateSearchAgent(headless=True)
    validator = get_validator()

    total_listings = 0
    total_new = 0

    try:
        for idx, query in enumerate(QUERIES):
            logger.info(f"🔍 [{idx+1}/{len(QUERIES)}] Scraping: {query}")
            
            try:
                # 1. Search
                result = await agent.search(
                    query,
                    max_results=20, # Get up to 20 per query
                    platforms=["chotot", "batdongsan"],
                )

                if result.listings:
                    # 2. Validate
                    valid_listings, _ = validator.validate_listings(result.listings)
                    
                    # 3. Save to DB
                    new_count = 0
                    async with get_session() as session:
                        for listing in valid_listings:
                            # Generate ID if missing (MD5 of URL)
                            listing_id = listing.get("id")
                            if not listing_id and listing.get("source_url"):
                                import hashlib
                                listing_id = hashlib.md5(listing.get("source_url").encode("utf-8")).hexdigest()

                            _, is_new = await ListingCRUD.upsert(session, {
                                "id": listing_id,
                                "title": listing.get("title"),
                                "description": listing.get("description"),
                                "price_text": listing.get("price_text"),
                                "price_number": listing.get("price_number"),
                                "price_per_m2": listing.get("price_per_m2"),
                                "property_type": listing.get("property_type"),
                                "area_m2": listing.get("area_m2"),
                                "bedrooms": listing.get("bedrooms"),
                                "bathrooms": listing.get("bathrooms"),
                                "address": listing.get("location", {}).get("address"),
                                "ward": listing.get("location", {}).get("ward"),
                                "district": listing.get("location", {}).get("district"),
                                "city": listing.get("location", {}).get("city", "Hà Nội"),
                                "contact_name": listing.get("contact", {}).get("name"),
                                "contact_phone": listing.get("contact", {}).get("phone"),
                                "contact_phone_clean": listing.get("contact", {}).get("phone_clean"),
                                "images": listing.get("images", []),
                                "source_url": listing.get("source_url"),
                                "source_platform": listing.get("source_platform"),
                            })
                            if is_new:
                                new_count += 1
                                
                    # 4. Index Vector DB
                    if valid_listings:
                         await index_listings(valid_listings)

                    total_listings += len(valid_listings)
                    total_new += new_count
                    logger.info(f"   ✅ Saved {len(valid_listings)} listings ({new_count} new)")
                else:
                    logger.warning("   ⚠️ No listings found")

                # Cooldown
                logger.info("⏳ Cooling down 5s...")
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"❌ Error scraping '{query}': {e}")
                await asyncio.sleep(5)

    finally:
        await close_db()
        await agent.close()
        logger.info(f"\n🎉 Bulk Scrape Completed!")
        logger.info(f"Total Processed: {total_listings}")
        logger.info(f"Total New Configured: {total_new}")

if __name__ == "__main__":
    # Fix for Windows: Force ProactorEventLoop for Playwright subprocess support
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        asyncio.run(main())
    else:
        asyncio.run(main())
