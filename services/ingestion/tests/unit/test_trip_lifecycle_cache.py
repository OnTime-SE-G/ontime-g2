import services.ingestion.app.trip_lifecycle_cache as cache_module
from services.ingestion.app.trip_lifecycle_cache import (
    ActiveTripCache,
    TripLifecycleConsumer,
    decode_trip_lifecycle_event,
)


def trip_started_payload(bus_id: str = "1", trip_id: str = "TRIP-001") -> dict:
    return {
        "event": "TRIP_STARTED",
        "busId": bus_id,
        "tripId": trip_id,
        "routeId": "202",
        "timestamp": "2026-05-02T10:00:00Z",
    }


def trip_ended_payload(bus_id: str = "1", trip_id: str = "TRIP-001") -> dict:
    return {
        "event": "TRIP_ENDED",
        "busId": bus_id,
        "tripId": trip_id,
        "routeId": "202",
        "timestamp": "2026-05-02T11:00:00Z",
    }


def test_trip_started_adds_active_trip():
    cache = ActiveTripCache()
    cache.apply_event(decode_trip_lifecycle_event(trip_started_payload()))

    active_trip = cache.get_active_trip("1")

    assert active_trip is not None
    assert active_trip.bus_id == "1"
    assert active_trip.trip_id == "TRIP-001"
    assert active_trip.route_id == "202"
    assert cache.snapshot()["active_trip_count"] == 1


def test_trip_ended_removes_matching_active_trip():
    cache = ActiveTripCache()
    cache.apply_event(decode_trip_lifecycle_event(trip_started_payload()))
    cache.apply_event(decode_trip_lifecycle_event(trip_ended_payload()))

    assert cache.get_active_trip("1") is None
    assert cache.snapshot()["active_trip_count"] == 0


def test_trip_ended_does_not_remove_different_active_trip():
    cache = ActiveTripCache()
    cache.apply_event(decode_trip_lifecycle_event(trip_started_payload()))
    cache.apply_event(decode_trip_lifecycle_event(trip_ended_payload(trip_id="TRIP-OTHER")))

    assert cache.get_active_trip("1") is not None
    assert cache.snapshot()["active_trip_count"] == 1


def test_new_trip_started_replaces_previous_active_trip_for_bus():
    cache = ActiveTripCache()
    cache.apply_event(decode_trip_lifecycle_event(trip_started_payload(trip_id="TRIP-001")))
    cache.apply_event(decode_trip_lifecycle_event(trip_started_payload(trip_id="TRIP-002")))

    active_trip = cache.get_active_trip("1")

    assert active_trip is not None
    assert active_trip.trip_id == "TRIP-002"
    assert cache.snapshot()["active_trip_count"] == 1


def test_cache_status_transitions():
    cache = ActiveTripCache(initial_status="rebuilding")
    assert cache.status == "rebuilding"
    assert cache.is_rebuilding is True

    cache.mark_ready()

    assert cache.status == "ready"
    assert cache.is_ready is True

    cache.mark_degraded()
    assert cache.status == "degraded"


def test_consumer_rebuild_preparation_rewinds_all_topic_partitions():
    class FakeKafkaConsumer:
        def __init__(self):
            self.assigned_partitions = None
            self.seeked_partitions = None

        def partitions_for_topic(self, topic):
            assert topic == "trip.lifecycle"
            return {1, 0}

        def assign(self, partitions):
            self.assigned_partitions = partitions

        def seek_to_beginning(self, *partitions):
            self.seeked_partitions = partitions

    fake_consumer = FakeKafkaConsumer()
    consumer = TripLifecycleConsumer(ActiveTripCache(), topic="trip.lifecycle")
    consumer._consumer = fake_consumer

    consumer._prepare_rebuild_offsets()

    expected_partitions = [
        cache_module.TopicPartition("trip.lifecycle", 0),
        cache_module.TopicPartition("trip.lifecycle", 1),
    ]
    assert fake_consumer.assigned_partitions == expected_partitions
    assert fake_consumer.seeked_partitions == tuple(expected_partitions)


def test_consumer_rebuild_preparation_subscribes_when_topic_metadata_is_missing():
    class FakeKafkaConsumer:
        def __init__(self):
            self.subscribed_topics = None

        def partitions_for_topic(self, topic):
            assert topic == "trip.lifecycle"
            return None

        def subscribe(self, topics):
            self.subscribed_topics = topics

    fake_consumer = FakeKafkaConsumer()
    consumer = TripLifecycleConsumer(ActiveTripCache(), topic="trip.lifecycle")
    consumer._consumer = fake_consumer

    consumer._prepare_rebuild_offsets()

    assert fake_consumer.subscribed_topics == ["trip.lifecycle"]
