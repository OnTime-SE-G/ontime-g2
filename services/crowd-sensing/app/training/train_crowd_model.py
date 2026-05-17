import os
import argparse
import logging
import pandas as pd
from sqlalchemy import create_engine
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, f1_score
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fetch_data(db_url: str):
    engine = create_engine(db_url)
    
    # Check counts of real vs synthetic data
    count_query = """
    SELECT 
        SUM(CASE WHEN passenger_id = 'synthetic' THEN 1 ELSE 0 END) as synthetic_count,
        SUM(CASE WHEN passenger_id != 'synthetic' OR passenger_id IS NULL THEN 1 ELSE 0 END) as real_count
    FROM crowd_reports
    """
    try:
        counts = pd.read_sql(count_query, engine).iloc[0]
        synthetic_count = int(counts['synthetic_count'] or 0)
        real_count = int(counts['real_count'] or 0)
        logger.info(f"Database contains {real_count} real reports and {synthetic_count} synthetic reports.")
    except Exception as e:
        logger.warning(f"Could not fetch data counts: {e}. Defaulting to all records.")
        real_count = 0
        synthetic_count = 0

    # Smart filtering: If we have at least 100 real user reports, train EXCLUSIVELY on real data!
    if real_count >= 100:
        logger.info("Transitioning to 100% Real User Data! Excluding synthetic reports from training.")
        query = """
        SELECT 
            route_id, direction_id, stop_id, stop_sequence,
            occupancy_score, timestamp, passenger_id
        FROM crowd_reports
        WHERE passenger_id != 'synthetic' OR passenger_id IS NULL
        """
    else:
        logger.info("Training on hybrid dataset (synthetic + real) to ensure sufficient cold-start coverage.")
        query = """
        SELECT 
            route_id, direction_id, stop_id, stop_sequence,
            occupancy_score, timestamp, passenger_id
        FROM crowd_reports
        """
    df = pd.read_sql(query, engine)
    
    # Feature Engineering
    df['hour_of_day'] = df['timestamp'].dt.hour
    df['day_of_week'] = df['timestamp'].dt.dayofweek
    df['is_weekend'] = (df['day_of_week'] >= 5).astype(int)
    
    # Fill NA direction with 0
    df['direction_id'] = df['direction_id'].fillna(0).astype(int)
    
    # Create target classes based on mapping
    # 0-39: NOT_FULL (0)
    # 40-74: SEMI_FULL (1)
    # 75-100: FULL (2)
    def to_class(score):
        if score < 40: return 0
        elif score < 75: return 1
        else: return 2
        
    df['target'] = df['occupancy_score'].apply(to_class)
    return df

def train_and_log(df: pd.DataFrame):
    import mlflow
    import mlflow.xgboost

    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", settings.mlflow_tracking_uri)
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("crowd_occupancy_prediction")

    features = ['route_id', 'direction_id', 'stop_id', 'stop_sequence', 'hour_of_day', 'day_of_week', 'is_weekend']
    X = df[features]
    y = df['target']

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    with mlflow.start_run():
        params = {
            "objective": "multi:softmax",
            "num_class": 3,
            "max_depth": 6,
            "learning_rate": 0.1,
            "n_estimators": 100,
            "random_state": 42
        }
        mlflow.log_params(params)

        model = xgb.XGBClassifier(**params)
        model.fit(X_train, y_train)

        preds = model.predict(X_test)
        acc = accuracy_score(y_test, preds)
        f1 = f1_score(y_test, preds, average='weighted')

        mlflow.log_metric("accuracy", acc)
        mlflow.log_metric("f1_score", f1)
        logger.info(f"Test Accuracy: {acc:.4f}, F1: {f1:.4f}")

        mlflow.xgboost.log_model(
            xgb_model=model,
            artifact_path="model",
            registered_model_name="CrowdOccupancyModel"
        )
        logger.info("Successfully trained and registered CrowdOccupancyModel to MLflow.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-url", default=settings.database_url)
    args = parser.parse_args()

    try:
        df = fetch_data(args.db_url)
        if len(df) < 50:
            logger.warning("Not enough data to train. Need at least 50 reports.")
        else:
            train_and_log(df)
    except Exception as e:
        logger.error(f"Training failed: {e}")
