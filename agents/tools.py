"""
Custom tools for the Real Estate Search Agent.
Provides utilities for data validation, parsing, and storage.
"""
import hashlib
import re
from datetime import datetime
from typing import Any, Optional
import phonenumbers
from loguru import logger

from config import settings, DISTRICT_PRICE_RANGES, PHONE_PATTERNS, PROPERTY_TYPES


def generate_listing_id(url: str, phone: str, title: str) -> str:
    """
    Generate unique ID for a listing using MD5 hash.

    Args:
        url: Source URL of the listing
        phone: Contact phone number
        title: Listing title

    Returns:
        MD5 hash string
    """
    # Normalize inputs
    url = url.strip().lower() if url else ""
    phone = clean_phone_number(phone) if phone else ""
    title = title.strip().lower() if title else ""

    # Create hash
    content = f"{url}|{phone}|{title}"
    return hashlib.md5(content.encode('utf-8')).hexdigest()


def clean_phone_number(phone: str) -> str:
    """
    Clean and normalize Vietnamese phone number.

    Args:
        phone: Raw phone number string

    Returns:
        Cleaned phone number (digits only, starting with 0)
    """
    if not phone:
        return ""

    # Remove all non-digit characters
    digits = re.sub(r'\D', '', phone)

    # Handle +84 prefix
    if digits.startswith('84') and len(digits) >= 11:
        digits = '0' + digits[2:]

    # Ensure starts with 0
    if not digits.startswith('0') and len(digits) == 9:
        digits = '0' + digits

    return digits


def validate_phone(phone: str) -> tuple[bool, str]:
    """
    Validate Vietnamese phone number.

    Args:
        phone: Phone number to validate

    Returns:
        Tuple of (is_valid, cleaned_phone_or_error_message)
    """
    if not phone:
        return False, "Số điện thoại trống"

    cleaned = clean_phone_number(phone)

    # Check length (10-11 digits for Vietnam)
    if len(cleaned) < 10 or len(cleaned) > 11:
        return False, f"Số điện thoại không hợp lệ: {len(cleaned)} số"

    # Check starts with valid prefix
    valid_prefixes = ['03', '05', '07', '08', '09', '01']  # Vietnamese mobile prefixes
    if not any(cleaned.startswith(p) for p in valid_prefixes):
        return False, f"Đầu số không hợp lệ: {cleaned[:2]}"

    # Try to parse with phonenumbers library for extra validation
    try:
        parsed = phonenumbers.parse(cleaned, "VN")
        if not phonenumbers.is_valid_number(parsed):
            return False, "Số điện thoại không hợp lệ theo chuẩn VN"
        return True, cleaned
    except Exception:
        # Fallback to regex validation
        if re.match(r'^0[0-9]{9,10}$', cleaned):
            return True, cleaned
        return False, "Không thể xác thực số điện thoại"


def parse_price(text: str) -> dict[str, Any]:
    """
    Parse Vietnamese price text to structured data.

    Examples:
        "3 tỷ 500 triệu" -> {"number": 3500000000, "text": "3 tỷ 500 triệu"}
        "2.5 tỷ" -> {"number": 2500000000, "text": "2.5 tỷ"}
        "850 triệu" -> {"number": 850000000, "text": "850 triệu"}

    Args:
        text: Price text in Vietnamese

    Returns:
        Dict with 'number' and 'text' keys
    """
    if not text:
        return {"number": None, "text": None}

    text = text.strip().lower()
    original_text = text

    # Remove common prefixes/suffixes
    text = re.sub(r'(giá|vnd|đồng|vnđ|₫)', '', text)
    text = text.strip()

    total = 0

    # Pattern: X tỷ Y triệu
    pattern_full = r'(\d+(?:[.,]\d+)?)\s*tỷ\s*(\d+(?:[.,]\d+)?)\s*triệu'
    match = re.search(pattern_full, text)
    if match:
        ty = float(match.group(1).replace(',', '.'))
        trieu = float(match.group(2).replace(',', '.'))
        total = int(ty * 1_000_000_000 + trieu * 1_000_000)
        return {"number": total, "text": original_text}

    # Pattern: X tỷ
    pattern_ty = r'(\d+(?:[.,]\d+)?)\s*tỷ'
    match = re.search(pattern_ty, text)
    if match:
        ty = float(match.group(1).replace(',', '.'))
        total = int(ty * 1_000_000_000)

        # Check for remaining triệu after tỷ
        remaining = text[match.end():]
        pattern_remaining = r'(\d+(?:[.,]\d+)?)\s*triệu'
        match_remaining = re.search(pattern_remaining, remaining)
        if match_remaining:
            trieu = float(match_remaining.group(1).replace(',', '.'))
            total += int(trieu * 1_000_000)

        return {"number": total, "text": original_text}

    # Pattern: X triệu
    pattern_trieu = r'(\d+(?:[.,]\d+)?)\s*triệu'
    match = re.search(pattern_trieu, text)
    if match:
        trieu = float(match.group(1).replace(',', '.'))
        total = int(trieu * 1_000_000)
        return {"number": total, "text": original_text}

    # Pattern: Raw number (assume VND if > 1M, else triệu)
    pattern_number = r'(\d+(?:[.,]\d+)?)'
    match = re.search(pattern_number, text)
    if match:
        num = float(match.group(1).replace(',', '.'))
        if num > 1_000_000:
            # Likely already in VND
            total = int(num)
        else:
            # Likely in triệu
            total = int(num * 1_000_000)
        return {"number": total, "text": original_text}

    return {"number": None, "text": original_text}


def parse_area(text: str) -> Optional[float]:
    """
    Parse area text to square meters.

    Examples:
        "85.5 m2" -> 85.5
        "100m²" -> 100.0
        "50 mét vuông" -> 50.0

    Args:
        text: Area text

    Returns:
        Area in square meters or None
    """
    if not text:
        return None

    text = text.strip().lower()

    # Pattern: X m2, X m², X mét vuông
    patterns = [
        r'(\d+(?:[.,]\d+)?)\s*(?:m2|m²|mét\s*vuông|met\s*vuong)',
        r'(\d+(?:[.,]\d+)?)\s*(?:m|met)(?:\s|$)',
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1).replace(',', '.'))

    return None


def validate_price_range(
    price: int,
    area: Optional[float],
    district: Optional[str] = None
) -> tuple[bool, str]:
    """
    Validate if price is reasonable for the location.

    Args:
        price: Price in VND
        area: Area in m²
        district: District name

    Returns:
        Tuple of (is_valid, message)
    """
    if not price or price <= 0:
        return False, "Giá không hợp lệ"

    # If no area, just check absolute bounds
    if not area or area <= 0:
        # Price should be between 100 triệu and 500 tỷ for Hanoi
        if price < 100_000_000:
            return False, "Giá quá thấp (< 100 triệu)"
        if price > 500_000_000_000:
            return False, "Giá quá cao (> 500 tỷ)"
        return True, "OK (không có diện tích để tính /m²)"

    # Calculate price per m²
    price_per_m2 = price / area

    # Get district bounds
    if district:
        district_clean = district.strip()
        bounds = DISTRICT_PRICE_RANGES.get(district_clean)
        if bounds:
            min_price, max_price = bounds
            min_per_m2 = min_price * 1_000_000  # Convert from triệu to VND
            max_per_m2 = max_price * 1_000_000

            if price_per_m2 < min_per_m2 * 0.5:  # Allow 50% below min
                return False, f"Giá quá thấp cho {district}: {price_per_m2/1_000_000:.0f}tr/m² (kỳ vọng {min_price}-{max_price}tr/m²)"
            if price_per_m2 > max_per_m2 * 1.5:  # Allow 50% above max
                return False, f"Giá quá cao cho {district}: {price_per_m2/1_000_000:.0f}tr/m² (kỳ vọng {min_price}-{max_price}tr/m²)"

            return True, f"Giá hợp lý: {price_per_m2/1_000_000:.0f}tr/m²"

    # Fallback to global bounds
    if price_per_m2 < settings.price_min_per_m2 * 0.5:
        return False, f"Giá quá thấp: {price_per_m2/1_000_000:.0f}tr/m²"
    if price_per_m2 > settings.price_max_per_m2 * 1.5:
        return False, f"Giá quá cao: {price_per_m2/1_000_000:.0f}tr/m²"

    return True, f"Giá hợp lý: {price_per_m2/1_000_000:.0f}tr/m²"


def normalize_property_type(text: str) -> Optional[str]:
    """
    Normalize property type text to standard categories.

    Args:
        text: Raw property type text

    Returns:
        Standardized property type or None
    """
    if not text:
        return None

    text = text.strip().lower()

    for standard_type, variations in PROPERTY_TYPES.items():
        for variation in variations:
            if variation in text:
                return standard_type

    return None


def extract_district(location_text: str) -> Optional[str]:
    """
    Extract district name from location text.

    Args:
        location_text: Full location string

    Returns:
        District name or None
    """
    if not location_text:
        return None

    text = location_text.strip()

    # Check for known districts
    for district in DISTRICT_PRICE_RANGES.keys():
        if district.lower() in text.lower():
            return district

    # Pattern matching for common formats
    patterns = [
        r'(?:quận|q\.?)\s*([^,]+)',  # Quận X
        r'(?:huyện|h\.?)\s*([^,]+)',  # Huyện X
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            district_name = match.group(1).strip()
            # Clean up
            district_name = re.sub(r'[,\.].*$', '', district_name)
            return district_name.strip()

    return None


def validate_listing(listing: dict) -> tuple[bool, list[str], list[str]]:
    """
    Comprehensive validation of a listing.

    Args:
        listing: Listing data dict

    Returns:
        Tuple of (is_valid, errors, warnings)
    """
    errors = []
    warnings = []

    # Required fields
    required_fields = ['source_url', 'title']
    for field in required_fields:
        if not listing.get(field):
            errors.append(f"Thiếu trường bắt buộc: {field}")

    # Validate phone
    phone = listing.get('contact', {}).get('phone')
    if phone:
        is_valid, msg = validate_phone(phone)
        if not is_valid:
            warnings.append(f"SĐT: {msg}")
    else:
        warnings.append("Không có số điện thoại")

    # Validate price
    price = listing.get('price_number')
    area = listing.get('area_m2')
    district = listing.get('location', {}).get('district')

    if price:
        is_valid, msg = validate_price_range(price, area, district)
        if not is_valid:
            warnings.append(f"Giá: {msg}")
    else:
        warnings.append("Không có giá")

    # Validate source_url format
    source_url = listing.get('source_url', '')
    if source_url and not source_url.startswith(('http://', 'https://')):
        errors.append(f"URL không hợp lệ: {source_url}")

    # Check for spam patterns
    title = listing.get('title', '')
    description = listing.get('description', '')
    content = f"{title} {description}".lower()

    spam_keywords = ['môi giới', 'ký gửi', 'hotline', 'liên hệ ngay']
    spam_count = sum(1 for kw in spam_keywords if kw in content)
    if spam_count >= 2:
        warnings.append("Có thể là tin môi giới")

    is_valid = len(errors) == 0
    return is_valid, errors, warnings


def create_listing_schema(
    title: str,
    price_text: Optional[str] = None,
    price_number: Optional[int] = None,
    area_m2: Optional[float] = None,
    address: Optional[str] = None,
    ward: Optional[str] = None,
    district: Optional[str] = None,
    city: str = "Hà Nội",
    contact_name: Optional[str] = None,
    contact_phone: Optional[str] = None,
    images: Optional[list[str]] = None,
    source_url: str = "",
    source_platform: str = "",
    property_type: Optional[str] = None,
    bedrooms: Optional[int] = None,
    bathrooms: Optional[int] = None,
    description: Optional[str] = None,
    legal_status: Optional[str] = None,
    direction: Optional[str] = None,
    posted_at: Optional[datetime] = None,
) -> dict:
    """
    Create a standardized listing schema.

    Returns:
        Dict with all listing fields properly structured
    """
    # Clean phone
    phone_clean = clean_phone_number(contact_phone) if contact_phone else None

    # Generate ID
    listing_id = generate_listing_id(source_url, phone_clean or "", title)

    # Normalize property type
    property_type_normalized = normalize_property_type(property_type) if property_type else None

    # Extract district if not provided
    if not district and address:
        district = extract_district(address)

    return {
        "id": listing_id,
        "title": title,
        "price_text": price_text,
        "price_number": price_number,
        "area_m2": area_m2,
        "location": {
            "address": address,
            "ward": ward,
            "district": district,
            "city": city,
        },
        "contact": {
            "name": contact_name,
            "phone": contact_phone,
            "phone_clean": phone_clean,
        },
        "images": images or [],
        "source_url": source_url,
        "source_platform": source_platform,
        "scraped_at": datetime.utcnow().isoformat(),
        "posted_at": posted_at.isoformat() if posted_at else None,
        "property_type": property_type_normalized,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "description": description,
        "legal_status": legal_status,
        "direction": direction,
    }


def deduplicate_listings(listings: list[dict]) -> list[dict]:
    """
    Remove duplicate listings based on ID hash.

    Args:
        listings: List of listing dicts

    Returns:
        Deduplicated list
    """
    seen_ids = set()
    unique_listings = []

    for listing in listings:
        listing_id = listing.get('id')
        if not listing_id:
            # Generate ID if not present
            listing_id = generate_listing_id(
                listing.get('source_url', ''),
                listing.get('contact', {}).get('phone', ''),
                listing.get('title', '')
            )
            listing['id'] = listing_id

        if listing_id not in seen_ids:
            seen_ids.add(listing_id)
            unique_listings.append(listing)
        else:
            logger.debug(f"Duplicate listing removed: {listing_id}")

    logger.info(f"Deduplicated: {len(listings)} -> {len(unique_listings)} listings")
    return unique_listings
