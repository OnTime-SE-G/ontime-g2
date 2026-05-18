import random
from datetime import datetime, timedelta
import pandas as pd
from sqlalchemy import create_engine
from app.config import settings

def generate_synthetic_data(num_records=500):
    records = []
    base_time = datetime.now() - timedelta(days=30)
    
    # 5 different routes
    routes = [101, 102, 138, 177, 255]
    
    for i in range(num_records):
        route_id = random.choice(routes)
        direction_id = random.choice([0, 1])
        # 10 stops per route
        stop_sequence = random.randint(1, 10)
        stop_id = (route_id * 10) + stop_sequence
        
        # Shift timestamps over the last 30 days
        timestamp = base_time + timedelta(
            days=random.randint(0, 29),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59)
        )
        
        # Synthesize realistic occupancy scores:
        # Rush hours: 7-9 AM, 5-7 PM (higher score)
        # Weekends: slightly lower
        # Later stop sequences: higher occupancy
        hour = timestamp.hour
        is_rush_hour = (7 <= hour <= 9) or (17 <= hour <= 19)
        is_weekend = timestamp.weekday() >= 5
        
        base_score = 25
        if is_rush_hour:
            base_score += 45
        if not is_weekend:
            base_score += 15
        base_score += stop_sequence * 2  # Bus fills up along route
        
        # Add random noise
        score = min(100, max(0, int(base_score + random.normalvariate(0, 8))))
        
        records.append({
            "trip_id": f"T{1000 + i}",
            "route_id": route_id,
            "direction_id": direction_id,
            "stop_id": stop_id,
            "stop_sequence": stop_sequence,
            "occupancy_score": score,
            "occupancy_label": "FULL" if score >= 75 else ("SEMI_FULL" if score >= 40 else "NOT_FULL"),
            "passenger_id": "synthetic",
            "timestamp": timestamp
        })
        
    df = pd.DataFrame(records)
    return df

def seed_db(df: pd.DataFrame, db_url: str):
    from app.database.connection import init_db
    init_db()
    engine = create_engine(db_url)
    df.to_sql("crowd_reports", engine, if_exists="append", index=False)
    print(f"Successfully seeded database with {len(df)} synthetic crowd reports.")

if __name__ == "__main__":
    df = generate_synthetic_data()
    seed_db(df, settings.database_url)
