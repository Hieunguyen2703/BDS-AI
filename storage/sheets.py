"""
Google Sheets Integration for backup and viewing listings.
Uses gspread library with service account authentication.
"""

import asyncio
from datetime import datetime
from typing import Any, Optional
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials
from loguru import logger

from config import settings


# Google Sheets API scopes
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Sheet column headers
LISTING_HEADERS = [
    "ID",
    "Title",
    "Property Type",
    "Price Text",
    "Price (VND)",
    "Area (m²)",
    "Bedrooms",
    "Address",
    "District",
    "City",
    "Contact Name",
    "Contact Phone",
    "Source Platform",
    "Source URL",
    "Scraped At",
    "Status",
]


class GoogleSheetsClient:
    """
    Google Sheets client for backing up and viewing listings.
    """

    def __init__(
        self,
        credentials_file: Optional[str] = None,
        spreadsheet_id: Optional[str] = None,
        worksheet_name: Optional[str] = None,
    ):
        """
        Initialize Google Sheets client.

        Args:
            credentials_file: Path to service account JSON credentials
            spreadsheet_id: ID of the Google Spreadsheet
            worksheet_name: Name of the worksheet to use
        """
        self.credentials_file = credentials_file or settings.google_sheets_credentials_file
        self.spreadsheet_id = spreadsheet_id or settings.google_sheets_spreadsheet_id
        self.worksheet_name = worksheet_name or settings.google_sheets_worksheet_name

        self._client: Optional[gspread.Client] = None
        self._spreadsheet: Optional[gspread.Spreadsheet] = None
        self._worksheet: Optional[gspread.Worksheet] = None

        self._initialized = False

    def _check_credentials(self) -> bool:
        """Check if credentials file exists."""
        if not self.credentials_file:
            logger.warning("Google Sheets credentials file not configured")
            return False

        creds_path = Path(self.credentials_file)
        if not creds_path.exists():
            logger.warning(f"Credentials file not found: {self.credentials_file}")
            return False

        return True

    async def initialize(self) -> bool:
        """
        Initialize connection to Google Sheets.

        Returns:
            True if successful, False otherwise
        """
        if self._initialized:
            return True

        if not self._check_credentials():
            return False

        try:
            # Load credentials
            credentials = Credentials.from_service_account_file(
                self.credentials_file,
                scopes=SCOPES,
            )

            # Create client
            self._client = gspread.authorize(credentials)

            # Open spreadsheet
            if self.spreadsheet_id:
                self._spreadsheet = self._client.open_by_key(self.spreadsheet_id)
            else:
                # Create new spreadsheet if not specified
                self._spreadsheet = self._client.create("BDS Agent Listings")
                self.spreadsheet_id = self._spreadsheet.id
                logger.info(f"Created new spreadsheet: {self.spreadsheet_id}")

            # Get or create worksheet
            try:
                self._worksheet = self._spreadsheet.worksheet(self.worksheet_name)
            except gspread.WorksheetNotFound:
                self._worksheet = self._spreadsheet.add_worksheet(
                    title=self.worksheet_name,
                    rows=1000,
                    cols=len(LISTING_HEADERS),
                )
                # Add headers
                self._worksheet.update("A1", [LISTING_HEADERS])
                logger.info(f"Created worksheet: {self.worksheet_name}")

            self._initialized = True
            logger.info(f"Google Sheets initialized: {self._spreadsheet.title}")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets: {e}")
            return False

    def _listing_to_row(self, listing: dict) -> list:
        """Convert listing dict to spreadsheet row."""
        location = listing.get("location", {})
        if isinstance(location, dict):
            address = location.get("address", "")
            district = location.get("district", "")
            city = location.get("city", "Hà Nội")
        else:
            address = str(location)
            district = ""
            city = "Hà Nội"

        contact = listing.get("contact", {})
        if isinstance(contact, dict):
            contact_name = contact.get("name", "")
            contact_phone = contact.get("phone_clean") or contact.get("phone", "")
        else:
            contact_name = ""
            contact_phone = ""

        scraped_at = listing.get("scraped_at", "")
        if isinstance(scraped_at, datetime):
            scraped_at = scraped_at.strftime("%Y-%m-%d %H:%M:%S")

        return [
            listing.get("id", ""),
            listing.get("title", "")[:200],  # Truncate long titles
            listing.get("property_type", ""),
            listing.get("price_text", ""),
            listing.get("price_number", ""),
            listing.get("area_m2", ""),
            listing.get("bedrooms", ""),
            address[:200],
            district,
            city,
            contact_name,
            contact_phone,
            listing.get("source_platform", ""),
            listing.get("source_url", "")[:500],
            scraped_at,
            listing.get("status", "active"),
        ]

    async def append_listing(self, listing: dict) -> bool:
        """
        Append a single listing to the spreadsheet.

        Args:
            listing: Listing dict

        Returns:
            True if successful
        """
        if not await self.initialize():
            return False

        try:
            row = self._listing_to_row(listing)
            self._worksheet.append_row(row, value_input_option="USER_ENTERED")
            logger.debug(f"Appended listing to sheets: {listing.get('id')}")
            return True
        except Exception as e:
            logger.error(f"Failed to append listing: {e}")
            return False

    async def append_listings(self, listings: list[dict]) -> int:
        """
        Append multiple listings to the spreadsheet.

        Args:
            listings: List of listing dicts

        Returns:
            Number of successfully appended listings
        """
        if not listings:
            return 0

        if not await self.initialize():
            return 0

        try:
            rows = [self._listing_to_row(listing) for listing in listings]

            # Batch append
            self._worksheet.append_rows(rows, value_input_option="USER_ENTERED")

            logger.info(f"Appended {len(rows)} listings to Google Sheets")
            return len(rows)

        except Exception as e:
            logger.error(f"Failed to append listings: {e}")
            return 0

    async def get_all_listings(self) -> list[dict]:
        """
        Get all listings from the spreadsheet.

        Returns:
            List of listing dicts
        """
        if not await self.initialize():
            return []

        try:
            # Get all records as dicts
            records = self._worksheet.get_all_records()

            listings = []
            for record in records:
                listing = {
                    "id": record.get("ID", ""),
                    "title": record.get("Title", ""),
                    "property_type": record.get("Property Type", ""),
                    "price_text": record.get("Price Text", ""),
                    "price_number": record.get("Price (VND)", None),
                    "area_m2": record.get("Area (m²)", None),
                    "bedrooms": record.get("Bedrooms", None),
                    "location": {
                        "address": record.get("Address", ""),
                        "district": record.get("District", ""),
                        "city": record.get("City", "Hà Nội"),
                    },
                    "contact": {
                        "name": record.get("Contact Name", ""),
                        "phone": record.get("Contact Phone", ""),
                    },
                    "source_platform": record.get("Source Platform", ""),
                    "source_url": record.get("Source URL", ""),
                    "scraped_at": record.get("Scraped At", ""),
                    "status": record.get("Status", "active"),
                }
                listings.append(listing)

            logger.info(f"Retrieved {len(listings)} listings from Google Sheets")
            return listings

        except Exception as e:
            logger.error(f"Failed to get listings: {e}")
            return []

    async def find_by_id(self, listing_id: str) -> Optional[dict]:
        """
        Find a listing by ID in the spreadsheet.

        Args:
            listing_id: Listing ID to find

        Returns:
            Listing dict or None
        """
        if not await self.initialize():
            return None

        try:
            cell = self._worksheet.find(listing_id, in_column=1)
            if cell:
                row = self._worksheet.row_values(cell.row)
                if len(row) >= len(LISTING_HEADERS):
                    return {
                        "id": row[0],
                        "title": row[1],
                        "property_type": row[2],
                        "price_text": row[3],
                        "price_number": int(row[4]) if row[4] else None,
                        "area_m2": float(row[5]) if row[5] else None,
                        "source_url": row[13],
                    }
            return None
        except Exception as e:
            logger.error(f"Failed to find listing: {e}")
            return None

    async def update_status(self, listing_id: str, status: str) -> bool:
        """
        Update listing status in spreadsheet.

        Args:
            listing_id: Listing ID
            status: New status

        Returns:
            True if successful
        """
        if not await self.initialize():
            return False

        try:
            cell = self._worksheet.find(listing_id, in_column=1)
            if cell:
                # Status is in column 16 (index 15 + 1 = 16)
                self._worksheet.update_cell(cell.row, 16, status)
                logger.debug(f"Updated listing status: {listing_id} -> {status}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to update status: {e}")
            return False

    async def delete_listing(self, listing_id: str) -> bool:
        """
        Delete a listing row from spreadsheet.

        Args:
            listing_id: Listing ID to delete

        Returns:
            True if successful
        """
        if not await self.initialize():
            return False

        try:
            cell = self._worksheet.find(listing_id, in_column=1)
            if cell:
                self._worksheet.delete_rows(cell.row)
                logger.debug(f"Deleted listing from sheets: {listing_id}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete listing: {e}")
            return False

    async def clear_all(self) -> bool:
        """
        Clear all data except headers.

        Returns:
            True if successful
        """
        if not await self.initialize():
            return False

        try:
            # Get row count
            row_count = self._worksheet.row_count

            if row_count > 1:
                # Delete all rows except header
                self._worksheet.delete_rows(2, row_count)

            logger.warning("Cleared all data from Google Sheets")
            return True

        except Exception as e:
            logger.error(f"Failed to clear sheets: {e}")
            return False

    async def get_stats(self) -> dict:
        """Get spreadsheet statistics."""
        if not await self.initialize():
            return {"error": "Not initialized"}

        try:
            row_count = self._worksheet.row_count - 1  # Exclude header

            return {
                "spreadsheet_id": self.spreadsheet_id,
                "spreadsheet_title": self._spreadsheet.title,
                "worksheet_name": self.worksheet_name,
                "total_listings": max(0, row_count),
                "url": f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}",
            }
        except Exception as e:
            return {"error": str(e)}

    def get_spreadsheet_url(self) -> str:
        """Get URL to the spreadsheet."""
        if self.spreadsheet_id:
            return f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}"
        return ""


# Singleton instance
_sheets_client: Optional[GoogleSheetsClient] = None


def get_sheets_client() -> GoogleSheetsClient:
    """Get or create Google Sheets client."""
    global _sheets_client
    if _sheets_client is None:
        _sheets_client = GoogleSheetsClient()
    return _sheets_client


async def backup_listing(listing: dict) -> bool:
    """Convenience function to backup a listing."""
    client = get_sheets_client()
    return await client.append_listing(listing)


async def backup_listings(listings: list[dict]) -> int:
    """Convenience function to backup multiple listings."""
    client = get_sheets_client()
    return await client.append_listings(listings)


async def sync_to_sheets(listings: list[dict]) -> dict:
    """
    Sync listings to Google Sheets.
    Checks for duplicates before appending.

    Args:
        listings: Listings to sync

    Returns:
        Stats dict with success/skip counts
    """
    client = get_sheets_client()

    if not await client.initialize():
        return {"error": "Failed to initialize", "success": 0, "skipped": 0}

    # Get existing IDs
    existing = await client.get_all_listings()
    existing_ids = {l["id"] for l in existing}

    # Filter new listings
    new_listings = [l for l in listings if l.get("id") not in existing_ids]
    skipped = len(listings) - len(new_listings)

    # Append new ones
    success = await client.append_listings(new_listings)

    return {
        "success": success,
        "skipped": skipped,
        "total": len(listings),
    }
