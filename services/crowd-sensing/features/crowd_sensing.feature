Feature: Crowd Sensing Service Occupancy Reports and Predictions
  As a passenger or client of the OnTime system
  I want to submit crowd reports and query predictions
  So that we can monitor bus occupancy in real-time

  Scenario: Passenger successfully submits a crowd report via API Gateway header
    Given the Kafka message broker is available
    When the passenger submits a crowd report for trip "TRIP_100" on route 2 at stop 10 with occupancy score 65 using header "X-Passenger-Id" value "passenger_abc"
    Then the response status should be 202
    And the response body status should be "accepted"
    And the Kafka message should be sent with passenger ID "passenger_abc"

  Scenario: Submission fails when the occupancy score is out of bounds
    When a user submits a crowd report for trip "TRIP_101" on route 2 at stop 10 with occupancy score 150
    Then the response status should be 422

  Scenario: Requesting crowd occupancy prediction successfully
    Given the route stop geographical integrity is verified
    And the predictor is configured to return prediction "SEMI_FULL" with confidence 0.85
    When a client queries the crowd prediction for route 1 at stop 5, direction 0 for datetime "2026-05-17T20:00:00Z"
    Then the response status should be 200
    And the response prediction should be "SEMI_FULL"
    And the response confidence should be 0.85
