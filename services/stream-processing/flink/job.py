"""Minimal PyFlink job template (scaffold).

This job demonstrates the high-level steps described in CR1:
- consume `transport-telemetry-raw`
- maintain a startup cache (one-time REST calls to route/fleet services)
- consume `trip.lifecycle` updates to keep cache fresh
- perform physics checks and classification
- emit `transport-telemetry-cleaned` and `telemetry-invalid`

This file is intentionally small and illustrative. Adapt for your cluster,
serialization, and checkpointing strategy.
"""
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.common import Types

def enrich_and_classify(event: dict, cache: dict) -> list:
    """Placeholder enrichment: attach 'on_route' flag and return a single
    cleaned event or an 'invalid' event depending on simple physics checks.
    """
    # Minimal physics check: require lat/lon and reasonable speed
    lat = event.get("lat")
    lon = event.get("lon")
    speed = event.get("speed") or 0.0
    if lat is None or lon is None:
        event["_invalid_reason"] = "MISSING_COORDINATES"
        return [("invalid", event)]

    if speed is not None and speed > 120.0:
        event["_invalid_reason"] = "UNREALISTIC_SPEED"
        return [("invalid", event)]

    # Classification placeholder: everything that passes physics is forwarded
    # with an `on_route` flag (True by default in this scaffold)
    event["on_route"] = True
    return [("cleaned", event)]


def main():
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)

    # NOTE: Kafka connectors and serializers must be configured for a real job.
    # Here we demonstrate the transform logic in a map function.

    # pseudo-code: source = env.add_source(KafkaSource(...))
    # source.map(lambda e: enrich_and_classify(e, cache)).add_sink(...)

    print("This is a scaffold PyFlink job. Implement connector configuration and deployment specifics before running.")


if __name__ == "__main__":
    main()
