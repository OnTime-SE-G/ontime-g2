from unittest.mock import MagicMock, patch

import pytest

import services.ingestion.app.main as main_module
from services.ingestion.app.metrics import MetricsCollector


@pytest.fixture(autouse=True)
def isolated_main_state(monkeypatch):
    monkeypatch.setattr(main_module, "producer", None)
    monkeypatch.setattr(main_module, "subscriber", None)
    monkeypatch.setattr(main_module, "health_thread", None)
    collector = MetricsCollector()
    monkeypatch.setattr(main_module, "metrics", collector)
    return collector


def test_main_starts_producer_subscriber_and_health_server(isolated_main_state, monkeypatch):
    mock_producer = MagicMock()
    mock_subscriber = MagicMock()
    mock_health_thread = MagicMock()

    producer_factory = MagicMock(return_value=mock_producer)
    subscriber_factory = MagicMock(return_value=mock_subscriber)
    thread_factory = MagicMock(return_value=mock_health_thread)

    monkeypatch.setattr(main_module.signal, "signal", MagicMock())
    monkeypatch.setattr(main_module, "TelemetryProducer", producer_factory)
    monkeypatch.setattr(main_module, "MQTTSubscriber", subscriber_factory)
    monkeypatch.setattr(main_module.threading, "Thread", thread_factory)

    with patch("builtins.print"):
        main_module.main()

    producer_factory.assert_called_once_with()
    subscriber_factory.assert_called_once_with(mock_producer)
    mock_subscriber.connect.assert_called_once_with()
    thread_factory.assert_called_once_with(target=main_module.start_health_server, daemon=True)
    mock_health_thread.start.assert_called_once_with()
    mock_subscriber.start.assert_called_once_with()
    assert isolated_main_state.kafka_broker_up is True


def test_main_runs_in_degraded_mode_when_producer_fails(isolated_main_state, monkeypatch):
    wait_guard = RuntimeError("stop waiting")
    mock_health_thread = MagicMock()
    mock_event = MagicMock()
    mock_event.wait.side_effect = wait_guard

    monkeypatch.setattr(main_module.signal, "signal", MagicMock())
    monkeypatch.setattr(
        main_module,
        "TelemetryProducer",
        MagicMock(side_effect=RuntimeError("kafka unavailable")),
    )
    mqtt_subscriber_factory = MagicMock()
    monkeypatch.setattr(main_module, "MQTTSubscriber", mqtt_subscriber_factory)
    monkeypatch.setattr(main_module.threading, "Thread", MagicMock(return_value=mock_health_thread))
    monkeypatch.setattr(main_module.threading, "Event", MagicMock(return_value=mock_event))

    with patch("builtins.print"):
        with pytest.raises(RuntimeError, match="stop waiting"):
            main_module.main()

    mqtt_subscriber_factory.assert_not_called()
    mock_health_thread.start.assert_called_once_with()
    mock_event.wait.assert_called_once_with()
    assert isolated_main_state.kafka_broker_up is False
    assert isolated_main_state.mqtt_broker_up is False


def test_main_runs_in_degraded_mode_when_mqtt_startup_fails(isolated_main_state, monkeypatch):
    mock_producer = MagicMock()
    mock_health_thread = MagicMock()
    mock_event = MagicMock()
    mock_event.wait.side_effect = RuntimeError("stop waiting")

    monkeypatch.setattr(main_module.signal, "signal", MagicMock())
    monkeypatch.setattr(main_module, "TelemetryProducer", MagicMock(return_value=mock_producer))
    monkeypatch.setattr(
        main_module,
        "MQTTSubscriber",
        MagicMock(side_effect=RuntimeError("mqtt unavailable")),
    )
    monkeypatch.setattr(main_module.threading, "Thread", MagicMock(return_value=mock_health_thread))
    monkeypatch.setattr(main_module.threading, "Event", MagicMock(return_value=mock_event))

    with patch("builtins.print"):
        with pytest.raises(RuntimeError, match="stop waiting"):
            main_module.main()

    mock_health_thread.start.assert_called_once_with()
    assert isolated_main_state.kafka_broker_up is True
    assert isolated_main_state.mqtt_broker_up is False


def test_handle_shutdown_stops_subscriber_and_producer(monkeypatch):
    mock_producer = MagicMock()
    mock_subscriber = MagicMock()

    monkeypatch.setattr(main_module, "producer", mock_producer)
    monkeypatch.setattr(main_module, "subscriber", mock_subscriber)

    with patch("builtins.print"):
        with patch.object(main_module.sys, "exit", side_effect=SystemExit(0)):
            with pytest.raises(SystemExit):
                main_module.handle_shutdown(None, None)

    mock_subscriber.stop.assert_called_once_with()
    mock_producer.close.assert_called_once_with()
