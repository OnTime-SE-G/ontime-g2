from behave import given, when, then
from unittest.mock import MagicMock

@given("the Kafka message broker is available")
def step_impl(context):
    # Already configured in environment.py mock default
    pass

@given("the route stop geographical integrity is verified")
def step_impl(context):
    context.mock_validate.return_value = None

@given('the predictor is configured to return prediction "{prediction}" with confidence {confidence:f}')
def step_impl(context, prediction, confidence):
    context.mock_predictor.predict.return_value = {
        "prediction": prediction,
        "confidence": confidence,
        "historical_prediction": "NOT_FULL",
        "live_adjustment": True,
        "live_report_count": 3,
        "source": "hybrid_prediction"
    }

@when('the passenger submits a crowd report for trip "{trip_id}" on route {route_id:d} at stop {stop_id:d} with occupancy score {score:d} using header "{header_name}" value "{header_val}"')
def step_impl(context, trip_id, route_id, stop_id, score, header_name, header_val):
    payload = {
        "trip_id": trip_id,
        "route_id": route_id,
        "direction_id": 0,
        "stop_id": stop_id,
        "stop_sequence": 1,
        "occupancy_score": score,
        "timestamp": "2026-05-18T10:00:00"
    }
    headers = {
        header_name: header_val
    }
    context.response = context.client.post("/api/v1/crowd/report", json=payload, headers=headers)

@when('a user submits a crowd report for trip "{trip_id}" on route {route_id:d} at stop {stop_id:d} with occupancy score {score:d}')
def step_impl(context, trip_id, route_id, stop_id, score):
    payload = {
        "trip_id": trip_id,
        "route_id": route_id,
        "direction_id": 0,
        "stop_id": stop_id,
        "stop_sequence": 1,
        "occupancy_score": score,
        "timestamp": "2026-05-18T10:00:00"
    }
    context.response = context.client.post("/api/v1/crowd/report", json=payload)

@when('a client queries the crowd prediction for route {route_id:d} at stop {stop_id:d}, direction {direction_id:d} for datetime "{dt_str}"')
def step_impl(context, route_id, stop_id, direction_id, dt_str):
    url = f"/api/v1/crowd/predict?route_id={route_id}&stop_id={stop_id}&direction_id={direction_id}&datetime={dt_str}"
    context.response = context.client.get(url)

@then("the response status should be {status_code:d}")
def step_impl(context, status_code):
    assert context.response.status_code == status_code, f"Expected {status_code}, got {context.response.status_code}"

@then('the response body status should be "{expected_status}"')
def step_impl(context, expected_status):
    data = context.response.json()
    assert data.get("status") == expected_status, f"Expected {expected_status}, got {data.get('status')}"

@then('the Kafka message should be sent with passenger ID "{expected_passenger_id}"')
def step_impl(context, expected_passenger_id):
    context.mock_producer.send.assert_called_once()
    args, kwargs = context.mock_producer.send.call_args
    sent_dict = args[1]
    assert sent_dict.get("passenger_id") == expected_passenger_id, f"Expected {expected_passenger_id}, got {sent_dict.get('passenger_id')}"

@then('the response prediction should be "{expected_prediction}"')
def step_impl(context, expected_prediction):
    data = context.response.json()
    assert data.get("prediction") == expected_prediction, f"Expected {expected_prediction}, got {data.get('prediction')}"

@then("the response confidence should be {expected_confidence:f}")
def step_impl(context, expected_confidence):
    data = context.response.json()
    actual_confidence = float(data.get("confidence"))
    assert abs(actual_confidence - expected_confidence) < 1e-5, f"Expected {expected_confidence}, got {actual_confidence}"
