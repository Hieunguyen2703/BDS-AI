"""
Data Validation Service.
Validates and cleans real estate listing data.
"""

import hashlib
import re
from datetime import datetime, timedelta
from typing import Any, Optional
from dataclasses import dataclass, field

import phonenumbers
from loguru import logger

from config import settings, DISTRICT_PRICE_RANGES, PHONE_PATTERNS, SPAM_PATTERNS


@dataclass
class ValidationResult:
    """Result of validation."""
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    cleaned_data: Optional[dict] = None

    def add_error(self, error: str):
        """Add an error."""
        self.errors.append(error)
        self.is_valid = False

    def add_warning(self, warning: str):
        """Add a warning."""
        self.warnings.append(warning)


class RealDataValidator:
    """
    Comprehensive validator for real estate listing data.
    Ensures all data is real, not fake or spam.
    """

    # Valid phone prefixes in Vietnam
    VALID_PHONE_PREFIXES = [
        "032", "033", "034", "035", "036", "037", "038", "039",  # Viettel
        "070", "076", "077", "078", "079",  # Mobifone
        "081", "082", "083", "084", "085",  # Vinaphone
        "056", "058",  # Vietnamobile
        "059",  # Gmobile
        "086", "096", "097", "098", "099",  # Old Viettel
        "090", "093",  # Old Mobifone
        "091", "094",  # Old Vinaphone
        "092",  # Old Vietnamobile
        "024",  # Hanoi landline
        "028",  # HCMC landline
    ]

    # Spam keywords
    SPAM_KEYWORDS = [
        "môi giới", "mô giới", "moi gioi",
        "ký gửi", "kí gửi", "ky gui",
        "hotline", "liên hệ ngay",
        "đăng tin miễn phí",
        "nhận đăng tin",
        "cần bán gấp",  # Often spam
        "siêu hot", "siêu rẻ",
        "giá sốc", "giá shock",
    ]

    # Required fields
    REQUIRED_FIELDS = ["source_url", "title"]

    def __init__(
        self,
        strict_mode: bool = False,
        max_posts_per_phone_per_day: int = 50,
    ):
        """
        Initialize validator.

        Args:
            strict_mode: If True, warnings become errors
            max_posts_per_phone_per_day: Max listings allowed per phone per day
        """
        self.strict_mode = strict_mode
        self.max_posts_per_phone = max_posts_per_phone_per_day

        # Phone frequency tracking (for spam detection)
        self._phone_counts: dict[str, list[datetime]] = {}

    def validate_listing(self, listing: dict) -> ValidationResult:
        """
        Validate a single listing.

        Args:
            listing: Listing dict to validate

        Returns:
            ValidationResult with is_valid, errors, warnings
        """
        result = ValidationResult(is_valid=True, cleaned_data=listing.copy())

        # 1. Check required fields
        self._validate_required_fields(listing, result)

        # 2. Validate source URL
        self._validate_source_url(listing, result)

        # 3. Validate phone
        self._validate_phone(listing, result)

        # 4. Validate price
        self._validate_price(listing, result)

        # 5. Validate area
        self._validate_area(listing, result)

        # 6. Check spam patterns
        self._check_spam(listing, result)

        # 7. Validate location
        self._validate_location(listing, result)

        # In strict mode, warnings become errors
        if self.strict_mode and result.warnings:
            result.errors.extend(result.warnings)
            result.warnings = []
            result.is_valid = len(result.errors) == 0

        return result

    def _validate_required_fields(self, listing: dict, result: ValidationResult):
        """Check required fields are present."""
        for field in self.REQUIRED_FIELDS:
            value = listing.get(field)
            if not value or (isinstance(value, str) and not value.strip()):
                result.add_error(f"Thiếu trường bắt buộc: {field}")

    def _validate_source_url(self, listing: dict, result: ValidationResult):
        """Validate source URL."""
        url = listing.get("source_url", "")

        if not url:
            result.add_error("Thiếu source_url - không thể verify nguồn")
            return

        # Check URL format
        url_pattern = r'^https?://[^\s<>"{}|\\^`\[\]]+$'
        if not re.match(url_pattern, url):
            result.add_error(f"URL không hợp lệ: {url[:100]}")
            return

        # Check for known platforms
        known_domains = [
            "chotot.com", "batdongsan.com.vn", "mogi.vn",
            "alonhadat.com.vn", "facebook.com", "nha.chotot.com",
            "muaban.net", "homedy.com", "cafeland.vn",
        ]

        is_known = any(domain in url.lower() for domain in known_domains)
        if not is_known:
            result.add_warning(f"URL từ nguồn không phổ biến: {url[:50]}")

    def _validate_phone(self, listing: dict, result: ValidationResult):
        """Validate phone number."""
        contact = listing.get("contact", {})
        if isinstance(contact, dict):
            phone = contact.get("phone") or contact.get("phone_clean")
        else:
            phone = None

        if not phone:
            result.add_warning("Không có số điện thoại liên hệ")
            return

        # Clean phone number
        cleaned = self._clean_phone(phone)

        if not cleaned:
            result.add_warning(f"Không thể làm sạch SĐT: {phone}")
            return

        # Update cleaned data
        if result.cleaned_data:
            if "contact" not in result.cleaned_data:
                result.cleaned_data["contact"] = {}
            result.cleaned_data["contact"]["phone_clean"] = cleaned

        # Check length
        if len(cleaned) < 10 or len(cleaned) > 11:
            result.add_error(f"SĐT không hợp lệ (độ dài): {cleaned}")
            return

        # Check prefix
        prefix = cleaned[:3]
        prefix_2 = cleaned[:2]

        valid_prefix = (
            any(cleaned.startswith(p) for p in self.VALID_PHONE_PREFIXES) or
            prefix_2 in ["09", "08", "07", "05", "03"]
        )

        if not valid_prefix:
            result.add_error(f"Đầu số không hợp lệ: {prefix}")
            return

        # Check phone frequency (spam detection)
        self._check_phone_frequency(cleaned, result)

        # Try phonenumbers library
        try:
            parsed = phonenumbers.parse(cleaned, "VN")
            if not phonenumbers.is_valid_number(parsed):
                result.add_warning("SĐT có thể không hợp lệ theo chuẩn quốc tế")
        except Exception:
            pass  # Fallback already validated above

    def _clean_phone(self, phone: str) -> str:
        """Clean and normalize phone number."""
        if not phone:
            return ""

        # Remove all non-digit characters
        digits = re.sub(r'\D', '', str(phone))

        # Handle +84 prefix
        if digits.startswith('84') and len(digits) >= 11:
            digits = '0' + digits[2:]

        # Ensure starts with 0
        if not digits.startswith('0') and len(digits) == 9:
            digits = '0' + digits

        return digits

    def _check_phone_frequency(self, phone: str, result: ValidationResult):
        """Check if phone appears too frequently (spam indicator)."""
        now = datetime.utcnow()
        cutoff = now - timedelta(days=1)

        # Clean old entries
        if phone in self._phone_counts:
            self._phone_counts[phone] = [
                dt for dt in self._phone_counts[phone] if dt > cutoff
            ]
        else:
            self._phone_counts[phone] = []

        # Check count
        count = len(self._phone_counts[phone])
        if count >= self.max_posts_per_phone:
            result.add_warning(
                f"SĐT này có {count} tin trong 24h - có thể là môi giới"
            )

        # Add current
        self._phone_counts[phone].append(now)

    def _validate_price(self, listing: dict, result: ValidationResult):
        """Validate price is reasonable."""
        price = listing.get("price_number")
        area = listing.get("area_m2")

        location = listing.get("location", {})
        if isinstance(location, dict):
            district = location.get("district")
        else:
            district = None

        if not price:
            result.add_warning("Không có giá")
            return

        # Basic bounds check
        if price < 100_000_000:  # < 100 triệu
            result.add_warning("Giá quá thấp (< 100 triệu)")

        if price > 500_000_000_000:  # > 500 tỷ
            result.add_error("Giá quá cao (> 500 tỷ) - có thể sai dữ liệu")

        # Price per m² check
        if area and area > 0:
            price_per_m2 = price / area

            # Get district bounds
            if district and district in DISTRICT_PRICE_RANGES:
                min_price, max_price = DISTRICT_PRICE_RANGES[district]
                min_per_m2 = min_price * 1_000_000
                max_per_m2 = max_price * 1_000_000

                if price_per_m2 < min_per_m2 * 0.3:
                    result.add_warning(
                        f"Giá/m² thấp bất thường cho {district}: "
                        f"{price_per_m2/1_000_000:.0f}tr/m² "
                        f"(kỳ vọng {min_price}-{max_price}tr/m²)"
                    )

                if price_per_m2 > max_per_m2 * 2:
                    result.add_warning(
                        f"Giá/m² cao bất thường cho {district}: "
                        f"{price_per_m2/1_000_000:.0f}tr/m² "
                        f"(kỳ vọng {min_price}-{max_price}tr/m²)"
                    )
            else:
                # General bounds
                if price_per_m2 < settings.price_min_per_m2 * 0.3:
                    result.add_warning(f"Giá/m² quá thấp: {price_per_m2/1_000_000:.0f}tr")

                if price_per_m2 > settings.price_max_per_m2 * 2:
                    result.add_warning(f"Giá/m² quá cao: {price_per_m2/1_000_000:.0f}tr")

            # Update cleaned data with price_per_m2
            if result.cleaned_data:
                result.cleaned_data["price_per_m2"] = int(price_per_m2)

    def _validate_area(self, listing: dict, result: ValidationResult):
        """Validate area is reasonable."""
        area = listing.get("area_m2")

        if not area:
            result.add_warning("Không có diện tích")
            return

        if area <= 0:
            result.add_error("Diện tích không hợp lệ (<= 0)")

        if area > 10000:  # > 1 hectare
            result.add_warning("Diện tích rất lớn (> 10,000 m²)")

        if area < 10:  # < 10m²
            result.add_warning("Diện tích rất nhỏ (< 10 m²)")

    def _check_spam(self, listing: dict, result: ValidationResult):
        """Check for spam patterns."""
        title = listing.get("title", "").lower()
        description = listing.get("description", "").lower()
        content = f"{title} {description}"

        # Check spam keywords
        spam_count = 0
        found_keywords = []

        for keyword in self.SPAM_KEYWORDS:
            if keyword in content:
                spam_count += 1
                found_keywords.append(keyword)

        if spam_count >= 3:
            result.add_warning(f"Nhiều dấu hiệu spam: {', '.join(found_keywords[:3])}")
        elif spam_count >= 1:
            result.add_warning(f"Có thể là tin môi giới: '{found_keywords[0]}'")

        # Check for repeated characters (spam pattern)
        if re.search(r'(.)\1{5,}', content):
            result.add_warning("Có ký tự lặp lại bất thường")

        # Check for too many phone numbers in content
        phone_matches = re.findall(r'0\d{9,10}', content)
        if len(phone_matches) > 3:
            result.add_warning("Có nhiều SĐT trong nội dung (>3)")

        # Check for ALL CAPS
        if title.isupper() and len(title) > 20:
            result.add_warning("Tiêu đề viết hoa toàn bộ")

    def _validate_location(self, listing: dict, result: ValidationResult):
        """Validate location data."""
        location = listing.get("location", {})

        if not location:
            result.add_warning("Không có thông tin vị trí")
            return

        if isinstance(location, dict):
            district = location.get("district")
            city = location.get("city")

            if not district:
                result.add_warning("Không có thông tin quận/huyện")
            elif district not in DISTRICT_PRICE_RANGES:
                result.add_warning(f"Quận/huyện không nhận dạng được: {district}")

            if city and city not in ["Hà Nội", "Hồ Chí Minh", "Đà Nẵng"]:
                result.add_warning(f"Thành phố chưa hỗ trợ: {city}")

    def validate_listings(self, listings: list[dict]) -> tuple[list[dict], list[dict]]:
        """
        Validate multiple listings.

        Args:
            listings: List of listings to validate

        Returns:
            Tuple of (valid_listings, invalid_listings)
        """
        valid = []
        invalid = []

        for listing in listings:
            result = self.validate_listing(listing)

            if result.is_valid:
                # Attach validation info to listing
                validated = result.cleaned_data or listing.copy()
                validated["_validation_warnings"] = result.warnings
                valid.append(validated)
            else:
                listing["_validation_errors"] = result.errors
                listing["_validation_warnings"] = result.warnings
                invalid.append(listing)

        logger.info(f"Validation: {len(valid)} valid, {len(invalid)} invalid")
        return valid, invalid

    def generate_listing_id(
        self,
        url: str,
        phone: Optional[str] = None,
        title: Optional[str] = None
    ) -> str:
        """
        Generate unique listing ID.

        Args:
            url: Source URL
            phone: Contact phone
            title: Listing title

        Returns:
            MD5 hash ID
        """
        url = url.strip().lower() if url else ""
        phone = self._clean_phone(phone) if phone else ""
        title = title.strip().lower() if title else ""

        content = f"{url}|{phone}|{title}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()

    def deduplicate(
        self,
        listings: list[dict],
        existing_ids: Optional[set[str]] = None,
    ) -> list[dict]:
        """
        Remove duplicate listings.

        Args:
            listings: List of listings
            existing_ids: Set of existing IDs to check against

        Returns:
            Deduplicated list
        """
        seen_ids = set(existing_ids or [])
        unique = []

        for listing in listings:
            # Generate ID if not present
            if not listing.get("id"):
                contact = listing.get("contact", {})
                phone = contact.get("phone") if isinstance(contact, dict) else None

                listing["id"] = self.generate_listing_id(
                    listing.get("source_url", ""),
                    phone,
                    listing.get("title", ""),
                )

            listing_id = listing["id"]

            if listing_id not in seen_ids:
                seen_ids.add(listing_id)
                unique.append(listing)
            else:
                logger.debug(f"Duplicate removed: {listing_id}")

        removed = len(listings) - len(unique)
        if removed > 0:
            logger.info(f"Deduplication: {len(listings)} -> {len(unique)} ({removed} removed)")

        return unique

    def clean_listing(self, listing: dict) -> dict:
        """
        Clean and normalize listing data.

        Args:
            listing: Raw listing dict

        Returns:
            Cleaned listing dict
        """
        cleaned = listing.copy()

        # Clean title
        if cleaned.get("title"):
            cleaned["title"] = cleaned["title"].strip()
            # Remove excessive whitespace
            cleaned["title"] = re.sub(r'\s+', ' ', cleaned["title"])

        # Clean phone
        contact = cleaned.get("contact", {})
        if isinstance(contact, dict) and contact.get("phone"):
            contact["phone_clean"] = self._clean_phone(contact["phone"])
            cleaned["contact"] = contact

        # Ensure scraped_at
        if not cleaned.get("scraped_at"):
            cleaned["scraped_at"] = datetime.utcnow().isoformat()

        # Generate ID
        if not cleaned.get("id"):
            phone = contact.get("phone") if isinstance(contact, dict) else None
            cleaned["id"] = self.generate_listing_id(
                cleaned.get("source_url", ""),
                phone,
                cleaned.get("title", ""),
            )

        # Calculate price per m²
        price = cleaned.get("price_number")
        area = cleaned.get("area_m2")
        if price and area and area > 0:
            cleaned["price_per_m2"] = int(price / area)

        return cleaned


# Singleton instance
_validator: Optional[RealDataValidator] = None


def get_validator() -> RealDataValidator:
    """Get or create validator instance."""
    global _validator
    if _validator is None:
        _validator = RealDataValidator()
    return _validator


def validate_listing(listing: dict) -> ValidationResult:
    """Convenience function to validate a listing."""
    return get_validator().validate_listing(listing)


def validate_and_filter(listings: list[dict]) -> list[dict]:
    """Convenience function to validate and filter listings."""
    validator = get_validator()
    valid, _ = validator.validate_listings(listings)
    return valid


def deduplicate_listings(
    listings: list[dict],
    existing_ids: Optional[set[str]] = None
) -> list[dict]:
    """Convenience function to deduplicate listings."""
    return get_validator().deduplicate(listings, existing_ids)
