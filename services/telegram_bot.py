"""
Telegram Bot Service.
Gửi thông báo tin mới về Telegram.
"""

import asyncio
from datetime import datetime
from typing import List, Optional

import httpx
from loguru import logger

from config import settings
from storage.database import Listing



class TelegramBot:
    """
    Telegram Bot để gửi notifications.
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
    ):
        self.bot_token = bot_token or settings.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or settings.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self._enabled = bool(self.bot_token and self.chat_id)

        if not self._enabled:
            logger.warning("Telegram bot not configured - notifications disabled")

    @property
    def enabled(self) -> bool:
        """Check if bot is enabled."""
        return self._enabled

    async def send_message(
        self,
        text: str,
        parse_mode: str = "HTML",
        disable_preview: bool = True,
        chat_id: Optional[str] = None,
    ) -> bool:
        """
        Gửi tin nhắn đến Telegram.

        Args:
            text: Nội dung tin nhắn (HTML format)
            parse_mode: HTML hoặc Markdown
            disable_preview: Tắt link preview

        Returns:
            True nếu gửi thành công
        """
        if not self._enabled:
            logger.debug("Telegram not enabled, skipping message")
            return False

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.base_url}/sendMessage",
                    json={
                        "chat_id": chat_id or self.chat_id,
                        "text": text,
                        "parse_mode": parse_mode,
                        "disable_web_page_preview": disable_preview,
                    },
                )

                if response.status_code == 200:
                    logger.info("Telegram message sent successfully")
                    return True
                else:
                    logger.error(f"Telegram send failed: status={response.status_code}, response={response.text}")
                    return False

        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False

    def format_listing_message(self, listing: Listing) -> str:
        """
        Format listing thành HTML message.

        Args:
            listing: Listing object

        Returns:
            HTML formatted message
        """
        # Price formatting
        if listing.price_number:
            if listing.price_number >= 1_000_000_000:
                price_display = f"{listing.price_number / 1_000_000_000:.1f} tỷ"
            else:
                price_display = f"{listing.price_number / 1_000_000:.0f} triệu"
        else:
            price_display = listing.price_display or "Thỏa thuận"

        # Build message
        lines = [
            f"🏠 <b>{listing.title or 'Tin mới'}</b>",
            "",
        ]

        # Price
        lines.append(f"💰 <b>Giá:</b> {price_display}")

        # Area
        if listing.area_m2:
            lines.append(f"📐 <b>Diện tích:</b> {listing.area_m2:.0f}m²")

        # Price per m2
        if listing.price_per_m2:
            ppm2 = listing.price_per_m2 / 1_000_000
            lines.append(f"📊 <b>Giá/m²:</b> {ppm2:.1f} triệu/m²")

        # Location
        if listing.address:
            lines.append(f"📍 <b>Địa chỉ:</b> {listing.address}")
        elif listing.district:
            lines.append(f"📍 <b>Quận:</b> {listing.district}")

        # Property type
        if listing.property_type:
            lines.append(f"🏢 <b>Loại:</b> {listing.property_type}")

        # Bedrooms/Bathrooms
        if listing.bedrooms or listing.bathrooms:
            rooms = []
            if listing.bedrooms:
                rooms.append(f"{listing.bedrooms} PN")
            if listing.bathrooms:
                rooms.append(f"{listing.bathrooms} WC")
            lines.append(f"🛏️ <b>Phòng:</b> {', '.join(rooms)}")

        # Contact
        if listing.contact_phone:
            lines.append(f"📞 <b>Liên hệ:</b> {listing.contact_phone}")

        # Platform
        lines.append(f"🌐 <b>Nguồn:</b> {listing.source_platform or 'Unknown'}")

        # Link
        if listing.source_url:
            lines.append(f"\n🔗 <a href='{listing.source_url}'>Xem chi tiết</a>")

        return "\n".join(lines)

    async def notify_new_listing(self, listing: Listing) -> bool:
        """
        Gửi thông báo tin mới.

        Args:
            listing: Listing mới

        Returns:
            True nếu thành công
        """
        message = self.format_listing_message(listing)
        return await self.send_message(message)

    async def notify_new_listings(
        self,
        listings: List[Listing],
        batch_size: int = 5,
        delay_seconds: float = 1.0,
    ) -> int:
        """
        Gửi thông báo nhiều tin mới.

        Args:
            listings: Danh sách listings
            batch_size: Số tin gửi mỗi batch
            delay_seconds: Delay giữa các messages

        Returns:
            Số tin đã gửi thành công
        """
        if not listings:
            return 0

        # Summary message first
        summary = (
            f"🔔 <b>CÓ {len(listings)} TIN MỚI!</b>\n\n"
            f"📊 Đang gửi chi tiết..."
        )
        await self.send_message(summary)
        await asyncio.sleep(0.5)

        sent = 0
        for i, listing in enumerate(listings[:batch_size]):
            success = await self.notify_new_listing(listing)
            if success:
                sent += 1

            # Rate limiting
            if i < len(listings) - 1:
                await asyncio.sleep(delay_seconds)

        # If more listings, show remaining count
        if len(listings) > batch_size:
            remaining = len(listings) - batch_size
            await self.send_message(
                f"➕ Còn <b>{remaining}</b> tin khác. "
                f"Truy cập web để xem đầy đủ."
            )

        return sent

    async def notify_summary(
        self,
        total_new: int,
        by_district: dict,
        by_platform: dict,
    ) -> bool:
        """
        Gửi thông báo tổng hợp.

        Args:
            total_new: Tổng số tin mới
            by_district: Thống kê theo quận
            by_platform: Thống kê theo platform

        Returns:
            True nếu thành công
        """
        lines = [
            f"📊 <b>TỔNG HỢP TIN MỚI</b>",
            f"",
            f"🆕 Tổng cộng: <b>{total_new}</b> tin mới",
            "",
        ]

        # By district
        if by_district:
            lines.append("📍 <b>Theo quận:</b>")
            for district, count in sorted(
                by_district.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:5]:
                lines.append(f"  • {district}: {count} tin")
            lines.append("")

        # By platform
        if by_platform:
            lines.append("🌐 <b>Theo nguồn:</b>")
            for platform, count in sorted(
                by_platform.items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                lines.append(f"  • {platform}: {count} tin")

        lines.append(f"\n⏰ Cập nhật lúc: {datetime.now().strftime('%H:%M %d/%m/%Y')}")

        return await self.send_message("\n".join(lines))

    async def notify_error(self, error_message: str) -> bool:
        """
        Gửi thông báo lỗi.

        Args:
            error_message: Mô tả lỗi

        Returns:
            True nếu thành công
        """
        message = (
            f"⚠️ <b>CẢNH BÁO HỆ THỐNG</b>\n\n"
            f"{error_message}\n\n"
            f"⏰ {datetime.now().strftime('%H:%M %d/%m/%Y')}"
        )
        return await self.send_message(message)

    async def test_connection(self) -> dict:
        """
        Test kết nối Telegram.

        Returns:
            Bot info hoặc error
        """
        if not self._enabled:
            return {"success": False, "error": "Bot not configured"}

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(f"{self.base_url}/getMe")

                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "bot": data.get("result", {}),
                    }
                else:
                    return {
                        "success": False,
                        "error": f"API error: {response.status_code}",
                    }

        except Exception as e:
            return {"success": False, "error": str(e)}


# Singleton instance
_telegram_bot: Optional[TelegramBot] = None


def get_telegram_bot() -> TelegramBot:
    """Get or create Telegram bot instance."""
    global _telegram_bot
    if _telegram_bot is None:
        _telegram_bot = TelegramBot()
    return _telegram_bot


# Convenience functions
async def send_notification(text: str) -> bool:
    """Quick send notification."""
    bot = get_telegram_bot()
    return await bot.send_message(text)


async def notify_new_listings(listings: List[Listing]) -> int:
    """Quick notify new listings."""
    bot = get_telegram_bot()
    return await bot.notify_new_listings(listings)


async def send_search_alert(
    user_id: int,
    search_name: str,
    listings: List[dict],
) -> bool:
    """
    Send search alert to specific user.
    Note: Requires user_id to be mapped to telegram_chat_id in database.
    For now, we just log it as we don't have direct mapping yet.
    """
    # In a real app, we would look up User.telegram_id from user_id
    # from storage.database import UserCRUD, get_session
    # async with get_session() as session:
    #     user = await UserCRUD.get_by_id(session, user_id)
    #     chat_id = user.telegram_id if user else None
    
    # For now, send to default admin chat with user info
    bot = get_telegram_bot()
    
    message = (
        f"🔔 <b>ALERT FOR USER {user_id}</b>\n"
        f"🔍 Search: {search_name}\n"
        f"📊 Found {len(listings)} new listings\n\n"
    )
    
    for i, l in enumerate(listings[:5]):
        # Handle dict or Listing object
        title = l.get('title') if isinstance(l, dict) else l.title
        price = l.get('price_text') if isinstance(l, dict) else l.price_text
        message += f"{i+1}. {title} ({price})\n"
        
    return await bot.send_message(message)
