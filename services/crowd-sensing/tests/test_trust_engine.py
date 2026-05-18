import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from app.utils.trust_engine import get_or_create_profile, adjust_trust_scores
from app.database.models import PassengerProfile, CrowdReport

def test_get_or_create_profile_existing():
    db = MagicMock()
    mock_profile = PassengerProfile(passenger_id="user_1", trust_score=0.9)
    db.query.return_value.filter.return_value.first.return_value = mock_profile

    profile = get_or_create_profile(db, "user_1")
    assert profile == mock_profile
    db.add.assert_not_called()

def test_get_or_create_profile_new():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    profile = get_or_create_profile(db, "user_2")
    assert profile.passenger_id == "user_2"
    assert profile.trust_score == 0.8
    assert profile.total_reports == 0
    assert profile.verified_reports == 0
    db.add.assert_called_once()
    db.commit.assert_called_once()
    db.refresh.assert_called_once()

def test_get_or_create_profile_anonymous():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None

    profile = get_or_create_profile(db, "")
    assert profile.passenger_id == "anonymous_passenger"
    db.add.assert_called_once()

def test_adjust_trust_scores_no_passenger():
    db = MagicMock()
    adjust_trust_scores(db, route_id=1, stop_id=10, new_report_score=50, passenger_id="")
    db.query.assert_not_called()

@patch("app.utils.trust_engine.get_or_create_profile")
def test_adjust_trust_scores_insufficient_data(mock_get_profile):
    db = MagicMock()
    mock_profile = PassengerProfile(passenger_id="user_1", trust_score=0.8, total_reports=5, verified_reports=2)
    mock_get_profile.return_value = mock_profile
    
    # Mocking select statement execution returning < 2 other reports (e.g. 1 report)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [45.0]
    db.execute.return_value = mock_result

    adjust_trust_scores(db, route_id=1, stop_id=10, new_report_score=50, passenger_id="user_1")
    
    assert mock_profile.total_reports == 6
    assert mock_profile.verified_reports == 3
    assert mock_profile.trust_score == 0.8
    db.commit.assert_called_once()

@patch("app.utils.trust_engine.get_or_create_profile")
def test_adjust_trust_scores_consensus_match(mock_get_profile):
    db = MagicMock()
    mock_profile = PassengerProfile(passenger_id="user_1", trust_score=0.8, total_reports=5, verified_reports=2)
    mock_get_profile.return_value = mock_profile
    
    # Consensus average of [45, 55] is 50. New report is 60. Diff = 10 (<= 30.0) -> match consensus
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [45.0, 55.0]
    db.execute.return_value = mock_result

    adjust_trust_scores(db, route_id=1, stop_id=10, new_report_score=60, passenger_id="user_1")
    
    assert mock_profile.total_reports == 6
    assert mock_profile.verified_reports == 3
    assert pytest.approx(mock_profile.trust_score) == 0.82
    db.commit.assert_called_once()

@patch("app.utils.trust_engine.get_or_create_profile")
def test_adjust_trust_scores_consensus_outlier(mock_get_profile):
    db = MagicMock()
    mock_profile = PassengerProfile(passenger_id="user_1", trust_score=0.8, total_reports=5, verified_reports=2)
    mock_get_profile.return_value = mock_profile
    
    # Consensus average of [20, 30] is 25. New report is 80. Diff = 55 (> 30.0) -> outlier penalty
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [20.0, 30.0]
    db.execute.return_value = mock_result

    adjust_trust_scores(db, route_id=1, stop_id=10, new_report_score=80, passenger_id="user_1")
    
    assert mock_profile.total_reports == 6
    assert mock_profile.verified_reports == 2 # Remains unchanged since it's an outlier
    assert pytest.approx(mock_profile.trust_score) == 0.75
    db.commit.assert_called_once()
