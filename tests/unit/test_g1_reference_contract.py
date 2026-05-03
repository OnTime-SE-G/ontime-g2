from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
G1_ROOT = REPO_ROOT / "g1_temp"
SKETCHES = [
    G1_ROOT / "Full_Implementation" / "GSM+GPS+MQTT",
    G1_ROOT / "Testing_Dummy_Data" / "GSM+MQTT+Dummy",
]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_g1_reference_sketches_publish_to_ingestion_location_topic():
    for sketch in SKETCHES:
        source = read_text(sketch)

        assert 'const char BUS_ID[] = "1";' in source
        assert '"transport/bus/%s/location"' in source
        assert "mqtt.publish(locationTopic, payload, false)" in source


def test_g1_reference_sketches_emit_g2_location_payload_fields():
    required_fields = [
        '"\\"busId\\":\\"%s\\","',
        '"\\"lat\\":%s,"',
        '"\\"lon\\":%s,"',
        '"\\"speed\\":%s,"',
        '"\\"heading\\":%s,"',
        '"\\"timestamp\\":\\"%s\\""',
    ]

    for sketch in SKETCHES:
        source = read_text(sketch)

        for field in required_fields:
            assert field in source


def test_g1_reference_sketches_do_not_emit_legacy_or_trip_fields():
    forbidden_payload_fields = [
        '"\\"tripId\\""',
        '"\\"bus_id\\""',
        '"\\"lng\\""',
        '"\\"speed_kmh\\""',
    ]

    for sketch in SKETCHES:
        source = read_text(sketch)

        for field in forbidden_payload_fields:
            assert field not in source


def test_g1_readme_documents_no_trip_id_and_fleet_id_bus_id():
    readme = read_text(G1_ROOT / "README.md")

    assert "It does **not** publish `tripId`" in readme
    assert "`busId` is the Fleet bus `id`, serialized as a string" in readme
    assert "Live GPS publishes must use retained=false" in readme
