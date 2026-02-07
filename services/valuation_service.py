"""
AI-Powered Property Valuation Service

Uses LLM to analyze market data and provide intelligent price estimates.
"""

from typing import Dict, List, Optional
import logging
from datetime import datetime, timedelta

from langchain_core.messages import HumanMessage, SystemMessage

from services.llm_service import LLMService
from storage.database import Listing
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

logger = logging.getLogger(__name__)


class AIValuationService:
    """AI-powered property valuation using LLM analysis."""
    
    VALUATION_PROMPT = """Bạn là chuyên gia định giá bất động sản tại Hà Nội với 15 năm kinh nghiệm.

Nhiệm vụ: Phân tích dữ liệu thị trường và đưa ra mức giá hợp lý cho bất động sản.

Dữ liệu thị trường (các tin đăng tương tự):
{market_data}

Tham chiếu từ Mô hình AI Học máy (AutoML): {ml_prediction}

Thông tin bất động sản cần định giá:
- Loại: {property_type}
- Diện tích: {area_m2} m²
- Số phòng ngủ: {bedrooms}
- Quận: {district}
- Hướng: {direction}
- Pháp lý: {legal_status}

Yêu cầu phân tích:
1. So sánh với các tin đăng tương tự trong khu vực
2. Xem xét các yếu tố: vị trí, diện tích, số phòng, hướng nhà
3. Cân nhắc con số tham chiếu từ AI (được huấn luyện từ hàng nghìn tin đăng).
4. Đưa ra khoảng giá hợp lý (min-max) và giá đề xuất
5. Giải thích lý do định giá

Trả về JSON format:
{{
  "price_min": <số tiền tối thiểu (VND)>,
  "price_max": <số tiền tối đa (VND)>,
  "price_suggested": <giá đề xuất (VND)>,
  "price_per_m2": <đơn giá/m² (VND)>,
  "confidence": <độ tin cậy 0-100>,
  "reasoning": "<giải thích ngắn gọn, KÈM THEO nhận xét về dự đoán của AI>",
  "market_comparison": "<so sánh với thị trường>"
}}
"""

    def __init__(self):
        """Initialize valuation service."""
        self.llm_service = LLMService()
        from services.ml_service import MLService
        self.ml_service = MLService()
        
    async def estimate_price(
        self,
        property_type: str,
        area_m2: float,
        district: str,
        bedrooms: Optional[int] = None,
        direction: Optional[str] = None,
        legal_status: Optional[str] = None,
        db: AsyncSession = None
    ) -> Dict:
        """
        Estimate property price using AI analysis.
        """
        try:
            # 1. Get similar listings from database
            market_data = await self._get_market_data(
                property_type=property_type,
                district=district,
                area_m2=area_m2,
                db=db
            )
            
            # 2. Get AI (AutoML) Prediction
            ml_price = self.ml_service.predict_price({
                "property_type": property_type,
                "area_m2": area_m2,
                "district": district,
                "bedrooms": bedrooms or 0,
                "direction": direction,
                "ward": None # Optional, usually specific
            })
            
            ml_prediction_text = f"{ml_price:,.0f} VND" if ml_price else "Chưa có dữ liệu huấn luyện"
            
            if not market_data and not ml_price:
                 return {
                    "error": "Không đủ dữ liệu thị trường để định giá",
                    "suggestion": "Hãy thử tìm kiếm tin đăng tương tự trước"
                }

            # 3. Format market data for prompt
            market_text = self._format_market_data(market_data)
            
            # 4. Build prompt
            prompt = self.VALUATION_PROMPT.format(
                market_data=market_text,
                ml_prediction=ml_prediction_text,
                property_type=property_type,
                area_m2=area_m2,
                bedrooms=bedrooms or "N/A",
                district=district,
                direction=direction or "N/A",
                legal_status=legal_status or "N/A"
            )
            
            # 5. Get AI analysis
            messages = [
                SystemMessage(content="You are a real estate valuation expert. Always respond in valid JSON format."),
                HumanMessage(content=prompt)
            ]
            
            response = await self.llm_service.chat(messages)
            
            # 6. Parse JSON response
            import json
            import re
            
            # Extract JSON from response (handle markdown blocks or conversational padding)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    clean_response = json_match.group(0)
                    result = json.loads(clean_response)
                except json.JSONDecodeError:
                    # Fallback if regex found something that isn't valid JSON
                    result = {"analysis": response}
            else:
                # No JSON found, use the raw response
                result = {"analysis": response}
            
            # 7. Add metadata and ensure fields exist for frontend
            if not isinstance(result, dict):
                result = {"analysis": str(result)}
            
            # Fallback for price fields if missing from LLM response
            if "price_suggested" not in result or not result["price_suggested"]:
                result["price_suggested"] = int(ml_price or 0)
            else:
                result["price_suggested"] = int(result["price_suggested"])
                
            if "price_min" not in result or not result["price_min"]:
                result["price_min"] = int(ml_price * 0.9) if ml_price else 0
            else:
                result["price_min"] = int(result["price_min"])
                
            if "price_max" not in result or not result["price_max"]:
                result["price_max"] = int(ml_price * 1.1) if ml_price else 0
            else:
                result["price_max"] = int(result["price_max"])
                
            if "price_per_m2" not in result or not result["price_per_m2"]:
                if ml_price and area_m2:
                    result["price_per_m2"] = int(ml_price / area_m2)
                else:
                    result["price_per_m2"] = 0
            else:
                result["price_per_m2"] = int(result["price_per_m2"])
            
            if "confidence" not in result:
                result["confidence"] = 70 if ml_price else 30
            else:
                try:
                    result["confidence"] = int(result["confidence"])
                except (ValueError, TypeError):
                    result["confidence"] = 70 if ml_price else 30
                
            result["timestamp"] = datetime.now().isoformat()
            result["market_samples"] = len(market_data)
            result["district"] = district
            result["ml_estimate"] = ml_price
            
            logger.info(f"Valuation completed for {property_type} in {district}")
            return result
            
        except Exception as e:
            logger.error(f"Valuation error: {e}")
            return {
                "error": str(e),
                "fallback_estimate": self._simple_estimate(market_data) if market_data else None
            }
    
    async def _get_market_data(
        self,
        property_type: str,
        district: str,
        area_m2: float,
        db: AsyncSession,
        limit: int = 10
    ) -> List[Dict]:
        """
        Get similar listings from database.
        
        Args:
            property_type: Property type
            district: District name
            area_m2: Target area
            db: Database session
            limit: Max results
            
        Returns:
            List of similar listings
        """
        try:
            # Query similar listings
            area_min = area_m2 * 0.7  # -30%
            area_max = area_m2 * 1.3  # +30%
            
            result = await db.execute(
                select(Listing)
                .where(
                    Listing.property_type == property_type,
                    Listing.district == district,
                    Listing.area_m2.between(area_min, area_max),
                    Listing.price_number.isnot(None),
                    Listing.scraped_at >= datetime.now() - timedelta(days=90)  # Last 3 months
                )
                .order_by(func.abs(Listing.area_m2 - area_m2))
                .limit(limit)
            )
            listings = result.scalars().all()
            
            return [
                {
                    "title": listing.title,
                    "price": listing.price_number,
                    "price_text": listing.price_text,
                    "area_m2": listing.area_m2,
                    "price_per_m2": listing.price_per_m2,
                    "bedrooms": listing.bedrooms,
                    "district": listing.district,
                    "scraped_at": listing.scraped_at.strftime("%Y-%m-%d")
                }
                for listing in listings
            ]
            
        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
            return []
    
    def _format_market_data(self, data: List[Dict]) -> str:
        """Format market data for prompt."""
        if not data:
            return "Không có dữ liệu"
        
        lines = []
        for i, item in enumerate(data, 1):
            lines.append(
                f"{i}. {item['title'][:60]}...\n"
                f"   Giá: {item['price_text']} ({item['price']:,} VND)\n"
                f"   Diện tích: {item['area_m2']} m²\n"
                f"   Đơn giá: {item['price_per_m2']:,} VND/m²\n"
                f"   Ngày: {item['scraped_at']}"
            )
        
        return "\n\n".join(lines)
    
    def _simple_estimate(self, market_data: List[Dict]) -> Dict:
        """Simple fallback estimate using average."""
        if not market_data:
            return None
        
        prices = [d['price'] for d in market_data if d['price']]
        if not prices:
            return None
        
        avg_price = sum(prices) / len(prices)
        min_price = min(prices)
        max_price = max(prices)
        
        return {
            "price_min": int(min_price),
            "price_max": int(max_price),
            "price_suggested": int(avg_price),
            "confidence": 50,
            "reasoning": "Ước tính đơn giản dựa trên trung bình thị trường"
        }
