import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.database.models import PassengerProfile, CrowdReport

logger = logging.getLogger(__name__)

def get_or_create_profile(db: Session, passenger_id: str) -> PassengerProfile:
    """
    Get an existing passenger trust profile, or create a new one with a default score of 0.8.
    """
    if not passenger_id:
        # Fallback profile for anonymous reports
        passenger_id = "anonymous_passenger"
        
    profile = db.query(PassengerProfile).filter(PassengerProfile.passenger_id == passenger_id).first()
    if not profile:
        profile = PassengerProfile(passenger_id=passenger_id, trust_score=0.8, total_reports=0, verified_reports=0)
        db.add(profile)
        db.commit()
        db.refresh(profile)
        logger.info(f"Created new trust profile for passenger: {passenger_id}")
    return profile

def adjust_trust_scores(db: Session, route_id: int, stop_id: int, new_report_score: int, passenger_id: str):
    """
    Dynamically reward or penalize user trust scores based on consensus with other recent reports.
    """
    if not passenger_id:
        return
        
    logger.info(f"Evaluating trust score consensus for passenger {passenger_id} at stop {stop_id}")
    profile = get_or_create_profile(db, passenger_id)
    profile.total_reports += 1
    
    # Query other reports at the same stop within the last 20 minutes (excluding this user)
    window_start = datetime.utcnow() - timedelta(minutes=20)
    stmt = select(CrowdReport.occupancy_score).where(
        CrowdReport.route_id == route_id,
        CrowdReport.stop_id == stop_id,
        CrowdReport.passenger_id != passenger_id,
        CrowdReport.timestamp >= window_start
    )
    other_scores = list(db.execute(stmt).scalars().all())
    
    if len(other_scores) >= 2:
        # Calculate consensus average of other passengers
        consensus_avg = sum(other_scores) / len(other_scores)
        diff = abs(new_report_score - consensus_avg)
        
        if diff <= 30.0:
            # consensus match: reward!
            profile.trust_score = min(1.0, profile.trust_score + 0.02)
            profile.verified_reports += 1
            logger.info(f"User {passenger_id} matched consensus. Trust score increased to {profile.trust_score:.2f}")
        else:
            # consensus outlier: penalize!
            profile.trust_score = max(0.0, profile.trust_score - 0.05)
            logger.warning(f"User {passenger_id} is an outlier. Trust score decreased to {profile.trust_score:.2f}")
    else:
        # Insufficient other data to evaluate consensus, trust score remains unchanged
        # but count towards participation verification
        profile.verified_reports += 1
        
    db.commit()
