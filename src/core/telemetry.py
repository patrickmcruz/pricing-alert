from __future__ import annotations

import logging
import time
from typing import Optional
from contextlib import contextmanager

from src.core.config import settings

logger = logging.getLogger(__name__)

# Global flag to track initialized state
_TELEMETRY_INITIALIZED = False

# Meter and instrument holders
_meter = None
_scraper_execution_duration = None
_sku_processing_duration = None
_ecommerce_http_latency = None
_selector_failures = None
_sku_observations_saved = None
_alert_evaluations = None
_alert_dispatches = None
_alert_dispatch_duration = None


def init_telemetry(port: Optional[int] = None) -> bool:
    """
    Initializes OpenTelemetry MeterProvider with Prometheus exporter
    and starts the HTTP metrics endpoint on the specified port.
    Returns True if successfully initialized, False otherwise.
    """
    global _TELEMETRY_INITIALIZED
    global _meter, _scraper_execution_duration, _sku_processing_duration
    global _ecommerce_http_latency, _selector_failures, _sku_observations_saved
    global _alert_evaluations, _alert_dispatches, _alert_dispatch_duration

    if _TELEMETRY_INITIALIZED:
        return True

    if not settings.telemetry_enabled:
        logger.info("OpenTelemetry metrics disabled in settings.")
        return False

    metrics_port = port or settings.metrics_port

    try:
        from prometheus_client import start_http_server
        from opentelemetry import metrics
        from opentelemetry.exporter.prometheus import PrometheusMetricReader
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": settings.telemetry_service_name})
        reader = PrometheusMetricReader()
        provider = MeterProvider(resource=resource, metric_readers=[reader])
        metrics.set_meter_provider(provider)

        _meter = metrics.get_meter("pricing-alert-telemetry")

        # 1. Scraper overall run duration
        _scraper_execution_duration = _meter.create_histogram(
            name="scraper_execution_duration_seconds",
            description="Overall duration of a store scraper run in seconds",
            unit="s",
        )

        # 2. Per-SKU processing duration
        _sku_processing_duration = _meter.create_histogram(
            name="sku_processing_duration_seconds",
            description="Processing time per individual SKU in seconds",
            unit="s",
        )

        # 3. E-commerce HTTP / Browser fetch latency
        _ecommerce_http_latency = _meter.create_histogram(
            name="ecommerce_http_latency_seconds",
            description="Network I/O fetch duration per e-commerce page in seconds",
            unit="s",
        )

        # 4. DOM selector failures
        _selector_failures = _meter.create_counter(
            name="selector_failures_total",
            description="Total count of CSS DOM selector failures (outdated/missing elements)",
            unit="1",
        )

        # 5. Successfully saved SKU price observations
        _sku_observations_saved = _meter.create_counter(
            name="sku_observations_saved_total",
            description="Total count of price observations successfully parsed and saved",
            unit="1",
        )

        # 6. Alert evaluations
        _alert_evaluations = _meter.create_counter(
            name="alert_evaluations_total",
            description="Total count of price alert evaluations performed",
            unit="1",
        )

        # 7. Alert dispatches
        _alert_dispatches = _meter.create_counter(
            name="alert_dispatches_total",
            description="Total count of alerts dispatched to channels",
            unit="1",
        )

        # 8. Alert dispatch duration
        _alert_dispatch_duration = _meter.create_histogram(
            name="alert_dispatch_latency_seconds",
            description="Latency of alert delivery to notification channels in seconds",
            unit="s",
        )

        start_http_server(port=metrics_port)
        _TELEMETRY_INITIALIZED = True
        logger.info(
            "OpenTelemetry metrics server initialized and listening on port %d",
            metrics_port,
        )
        return True
    except Exception as e:
        logger.warning(
            "Failed to initialize OpenTelemetry Prometheus metrics exporter: %s", e
        )
        return False


def record_scraper_run(
    store_name: str, duration_seconds: float, status: str = "success"
) -> None:
    """Records the duration of a store scraper run."""
    if _scraper_execution_duration:
        _scraper_execution_duration.record(
            duration_seconds, {"store_name": store_name, "status": status}
        )


def record_sku_processing(
    store_name: str, gpu_model: str, duration_seconds: float, status: str = "success"
) -> None:
    """Records the processing time for an individual SKU."""
    if _sku_processing_duration:
        _sku_processing_duration.record(
            duration_seconds,
            {"store_name": store_name, "gpu_model": gpu_model, "status": status},
        )


def record_http_latency(
    store_name: str,
    transport_type: str,
    duration_seconds: float,
    http_status: str = "200",
) -> None:
    """Records network I/O fetch duration."""
    if _ecommerce_http_latency:
        _ecommerce_http_latency.record(
            duration_seconds,
            {
                "store_name": store_name,
                "transport_type": transport_type,
                "http_status": str(http_status),
            },
        )


def record_selector_failure(
    store_name: str, selector_key: str, error_type: str = "SelectorOutdatedException"
) -> None:
    """Records a CSS DOM selector failure."""
    if _selector_failures:
        _selector_failures.add(
            1,
            {
                "store_name": store_name,
                "selector_key": selector_key,
                "error_type": error_type,
            },
        )


def record_observation_saved(store_name: str, gpu_model: str, in_stock: bool) -> None:
    """Records a successfully saved price observation."""
    if _sku_observations_saved:
        _sku_observations_saved.add(
            1,
            {
                "store_name": store_name,
                "gpu_model": gpu_model,
                "in_stock": "true" if in_stock else "false",
            },
        )


def record_alert_evaluation(rule_type: str, triggered: bool) -> None:
    """Records an alert evaluation event."""
    if _alert_evaluations:
        _alert_evaluations.add(
            1,
            {
                "rule_type": rule_type,
                "triggered": "true" if triggered else "false",
            },
        )


def record_alert_dispatch(
    channel: str, duration_seconds: float, status: str = "success"
) -> None:
    """Records alert dispatch latency and status."""
    if _alert_dispatches:
        _alert_dispatches.add(1, {"channel": channel, "status": status})
    if _alert_dispatch_duration:
        _alert_dispatch_duration.record(
            duration_seconds, {"channel": channel, "status": status}
        )


@contextmanager
def measure_time():
    """Simple context manager helper to measure elapsed time in seconds."""
    start = time.perf_counter()

    def elapsed() -> float:
        return time.perf_counter() - start

    try:
        yield elapsed
    finally:
        pass
