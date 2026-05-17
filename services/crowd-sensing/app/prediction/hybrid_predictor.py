import os
import logging
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.config import settings
from app.database.connection import SessionLocal
from app.database.models import CrowdReport
from app.utils.occupancy import score_to_label, label_to_score

logger = logging.getLogger(__name__)

class HybridPredictor:
    def __init__(self):
        self.model = None
        self.features = None
        self._load_model()

    def _load_model(self):
        try:
            import mlflow.xgboost
            mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
            model_uri = "models:/CrowdOccupancyModel/latest"
            logger.info(f"Loading ML model from {model_uri}")
            self.model = mlflow.xgboost.load_model(model_uri)
            # Default feature columns for XGBoost
            self.features = ['route_id', 'direction_id', 'stop_id', 'stop_sequence', 'hour_of_day', 'day_of_week', 'is_weekend']
            logger.info("Successfully loaded ML model")
        except Exception as e:
            logger.warning(f"Failed to load MLflow model: {e}. Will use heuristics.")
            self.model = None

    def _predict_historical(self, route_id: int, direction_id: int, stop_id: int, dt: datetime) -> int:
        if not self.model:
            # Cold start fallback
            hour = dt.hour
            is_rush_hour = (7 <= hour <= 9) or (17 <= hour <= 19)
            return label_to_score("SEMI_FULL") if is_rush_hour else label_to_score("NOT_FULL")
        
        # Prepare feature vector
        data = {
            'route_id': [route_id],
            'direction_id': [direction_id or 0],
            'stop_id': [stop_id],
            'stop_sequence': [1], # Fallback if unknown
            'hour_of_day': [dt.hour],
            'day_of_week': [dt.weekday()],
            'is_weekend': [1 if dt.weekday() >= 5 else 0]
        }
        df = pd.DataFrame(data)[self.features]
        try:
            pred_class = int(self.model.predict(df)[0])
            # Convert class back to a default score for hybrid blending
            class_to_score = {0: 20, 1: 55, 2: 90}
            return class_to_score.get(pred_class, 55)
        except Exception as e:
            logger.error(f"Inference error: {e}")
            return label_to_score("SEMI_FULL")

    def _get_live_reports(self, route_id: int, stop_id: int, dt: datetime) -> list[int]:
        window_start = dt - timedelta(minutes=20)
        with SessionLocal() as db:
            stmt = select(CrowdReport.occupancy_score).where(
                CrowdReport.route_id == route_id,
                CrowdReport.stop_id == stop_id,
                CrowdReport.timestamp >= window_start,
                CrowdReport.timestamp <= dt
            )
            results = db.execute(stmt).scalars().all()
            return list(results)

    def predict(self, route_id: int, direction_id: int, stop_id: int, dt: datetime):
        hist_score = self._predict_historical(route_id, direction_id, stop_id, dt)
        hist_label = score_to_label(hist_score)

        live_scores = self._get_live_reports(route_id, stop_id, dt)
        report_count = len(live_scores)
        
        # Hybrid logic
        if report_count >= 5:
            avg_live_score = sum(live_scores) / report_count
            final_score = (0.7 * avg_live_score) + (0.3 * hist_score)
            live_adj = True
            confidence = min(0.95, 0.70 + (report_count * 0.05))
        else:
            final_score = hist_score
            live_adj = False
            confidence = 0.75 # Baseline confidence

        final_label = score_to_label(final_score)
        
        return {
            "prediction": final_label,
            "confidence": round(confidence, 2),
            "historical_prediction": hist_label,
            "live_adjustment": live_adj,
            "live_report_count": report_count,
            "source": "hybrid_prediction"
        }

predictor = HybridPredictor()
