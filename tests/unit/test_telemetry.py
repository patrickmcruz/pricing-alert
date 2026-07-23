from unittest.mock import patch, MagicMock

from src.core.telemetry import (
    init_telemetry,
    record_scraper_run,
    record_sku_processing,
    record_http_latency,
    record_selector_failure,
    record_observation_saved,
    record_alert_evaluation,
    record_alert_dispatch,
    measure_time,
)


def test_telemetry_disabled_by_settings():
    with (
        patch("src.core.telemetry._TELEMETRY_INITIALIZED", False),
        patch("src.core.telemetry.settings.telemetry_enabled", False),
    ):
        res = init_telemetry(port=9999)
        assert res is False


def test_telemetry_init_already_initialized():
    with patch("src.core.telemetry._TELEMETRY_INITIALIZED", True):
        res = init_telemetry(port=9999)
        assert res is True


def test_telemetry_init_success():
    with (
        patch("src.core.telemetry._TELEMETRY_INITIALIZED", False),
        patch("src.core.telemetry.settings.telemetry_enabled", True),
        patch("prometheus_client.start_http_server") as mock_start_http,
    ):
        res = init_telemetry(port=9102)
        assert res is True
        mock_start_http.assert_called_once_with(port=9102)


def test_telemetry_init_exception_handled():
    with (
        patch("src.core.telemetry._TELEMETRY_INITIALIZED", False),
        patch("src.core.telemetry.settings.telemetry_enabled", True),
        patch(
            "prometheus_client.start_http_server",
            side_effect=RuntimeError("Port bound"),
        ),
    ):
        res = init_telemetry(port=9102)
        assert res is False


def test_record_functions_safe_when_uninitialized():
    record_scraper_run("kabum", 1.5, "success")
    record_sku_processing("pichau", "rtx 5070", 0.5, "success")
    record_http_latency("terabyte", "browser", 2.1, "200")
    record_selector_failure("kabum", "price_cash", "SelectorOutdatedException")
    record_observation_saved("amazon", "rtx 5070 ti", True)
    record_alert_evaluation("PRICE_BELOW", True)
    record_alert_dispatch("TelegramChannel", 0.3, "success")


def test_telemetry_recording_invokes_instruments():
    mock_duration = MagicMock()
    mock_sku_duration = MagicMock()
    mock_http_latency = MagicMock()
    mock_failures = MagicMock()
    mock_saved = MagicMock()
    mock_alert_eval = MagicMock()
    mock_alert_dispatch = MagicMock()

    with (
        patch("src.core.telemetry._scraper_execution_duration", mock_duration),
        patch("src.core.telemetry._sku_processing_duration", mock_sku_duration),
        patch("src.core.telemetry._ecommerce_http_latency", mock_http_latency),
        patch("src.core.telemetry._selector_failures", mock_failures),
        patch("src.core.telemetry._sku_observations_saved", mock_saved),
        patch("src.core.telemetry._alert_evaluations", mock_alert_eval),
        patch("src.core.telemetry._alert_dispatches", mock_alert_dispatch),
    ):

        record_scraper_run("kabum", 5.2, "success")
        mock_duration.record.assert_called_once_with(
            5.2, {"store_name": "kabum", "status": "success"}
        )

        record_sku_processing("pichau", "rtx 5070", 1.2, "success")
        mock_sku_duration.record.assert_called_once_with(
            1.2, {"store_name": "pichau", "gpu_model": "rtx 5070", "status": "success"}
        )

        record_http_latency("terabyte", "browser", 3.0, "200")
        mock_http_latency.record.assert_called_once_with(
            3.0,
            {
                "store_name": "terabyte",
                "transport_type": "browser",
                "http_status": "200",
            },
        )

        record_selector_failure("kabum", "price_cash", "SelectorOutdatedException")
        mock_failures.add.assert_called_once_with(
            1,
            {
                "store_name": "kabum",
                "selector_key": "price_cash",
                "error_type": "SelectorOutdatedException",
            },
        )

        record_observation_saved("amazon", "rtx 5070 ti", True)
        mock_saved.add.assert_called_once_with(
            1, {"store_name": "amazon", "gpu_model": "rtx 5070 ti", "in_stock": "true"}
        )

        record_alert_evaluation("PRICE_BELOW", True)
        mock_alert_eval.add.assert_called_once_with(
            1, {"rule_type": "PRICE_BELOW", "triggered": "true"}
        )

        record_alert_dispatch("TelegramChannel", 0.4, "success")
        mock_alert_dispatch.add.assert_called_once_with(
            1, {"channel": "TelegramChannel", "status": "success"}
        )


def test_measure_time_context_manager():
    with measure_time() as elapsed:
        pass
    assert elapsed() >= 0.0
