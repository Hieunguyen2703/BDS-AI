
import os
import pandas as pd
import logging
from typing import Dict, Optional, List
from datetime import datetime
from autogluon.tabular import TabularPredictor
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from storage.database import Listing, ListingStatus

logger = logging.getLogger(__name__)

MODEL_PATH = "data/autogluon_valuation"

class MLService:
    """
    Machine Learning Service using AutoGluon for Property Valuation.
    """

    def __init__(self):
        self.predictor = None
        self._load_model()

    def _load_model(self):
        """Load the trained AutoGluon predictor if it exists."""
        if os.path.exists(MODEL_PATH) and os.path.exists(os.path.join(MODEL_PATH, "predictor.pkl")):
            try:
                self.predictor = TabularPredictor.load(MODEL_PATH)
                logger.info("✅ AutoGluon model loaded successfully.")
            except Exception as e:
                logger.warning(f"⚠️ Could not load AutoGluon model: {e}")
        else:
            logger.info("ℹ️ No trained model found at start.")

    async def train_model(self, db: AsyncSession) -> Dict:
        """
        Train a new AutoGluon model using data from the database.
        """
        logger.info("🚀 Starting model training...")
        
        # 1. Fetch Data
        try:
            result = await db.execute(
                select(Listing).where(
                    Listing.status == ListingStatus.ACTIVE.value,
                    Listing.price_number.isnot(None),
                    Listing.area_m2.isnot(None),
                    Listing.area_m2 > 10,  # Filter tiny erroneous areas
                    Listing.price_number > 100_000_000 # Filter suspiciously low prices
                )
            )
            listings = result.scalars().all()
            
            if len(listings) < 10:
                logger.warning("Not enough data to train model.")
                return {"status": "failed", "reason": "Not enough data (<10 samples)"}

            # 2. Prepare DataFrame
            data = []
            for l in listings:
                data.append({
                    "price_number": l.price_number,
                    "area_m2": l.area_m2,
                    "district": l.district,
                    "ward": l.ward,
                    "property_type": l.property_type,
                    "bedrooms": l.bedrooms if l.bedrooms else 0,
                    "bathrooms": l.bathrooms if l.bathrooms else 0,
                    "direction": l.direction,
                    # "legal_status": l.legal_status, # Often missing or unstructured
                })
            
            df = pd.DataFrame(data)
            
            # 3. Train AutoGluon
            # 'best_quality' might be too slow for a demo/quick feedback loop. 
            # 'medium_quality' or 'high_quality' is better for production speed/accuracy balance.
            # Using 'medium_quality' for reasonable training time (<1 min for small data).
            predictor = TabularPredictor(
                label='price_number', 
                path=MODEL_PATH,
                eval_metric='mean_absolute_error'
            ).fit(
                train_data=df,
                presets='medium_quality', 
                time_limit=300 # Max 5 mins training
            )

            self.predictor = predictor
            
            leaderboard = predictor.leaderboard(silent=True)
            best_model = leaderboard.iloc[0]
            
            logger.info(f"✅ Training completed. Best model: {best_model['model']} (Score: {best_model['score_val']})")

            return {
                "status": "success", 
                "samples": len(df),
                "best_model": best_model['model'],
                "score_val": best_model['score_val']
            }

        except Exception as e:
            logger.error(f"Training failed: {e}")
            return {"status": "error", "message": str(e)}

    def predict_price(self, features: Dict) -> Optional[float]:
        """
        Predict price for a given property.
        """
        if not self.predictor:
            logger.warning("Predict called but no model loaded.")
            return None

        try:
            # Construct DataFrame from single input
            # AutoGluon handles missing columns automatically (if they were in training)
            input_df = pd.DataFrame([features])
            
            # Predict
            prediction = self.predictor.predict(input_df)
            return float(prediction.iloc[0])
            
        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return None
