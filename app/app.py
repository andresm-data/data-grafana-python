import os
import time
import logging
import random
import json

from prometheus_client import Counter, Gauge, Histogram, start_http_server
import logging_loki

# Prometheus custom metrics
REQUEST_COUNTER = Counter(
    "app_requests_total",
    "Total requests processed by the demo app",
    ["status"],
)
TEMPERATURE_GAUGE = Gauge(
    "app_temperature_celsius",
    "Fake temperature gauge exposed by the demo app",
)
REQUEST_LATENCY_SECONDS = Histogram(
    "app_request_latency_seconds",
    "Synthetic request latency in seconds",
    buckets=(0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0),
)
ERROR_COUNTER = Counter(
    "app_errors_total",
    "Total synthetic processing errors",
    ["type"],
)


def configure_logging():
    """Configure Python logging to push logs to Loki using python-logging-loki."""
    loki_url = os.getenv("LOKI_URL", "http://loki:3100/loki/api/v1/push")

    handler = logging_loki.LokiHandler(
        url=loki_url,
        tags={"app": "python-demo"},
        version="1",
    )

    logger = logging.getLogger("demo-app")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)

    # Also log to stdout so `docker logs` still works
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


def log_structured(logger, level, event, **fields):
    payload = {"event": event, **fields}
    tags = {
        "app": "python-demo",
        "component": fields.get("component", "worker"),
        "level": level,
    }

    message = json.dumps(payload, separators=(",", ":"))
    if level == "error":
        logger.error(message, extra={"tags": tags})
    elif level == "warning":
        logger.warning(message, extra={"tags": tags})
    else:
        logger.info(message, extra={"tags": tags})


def main():
    logger = configure_logging()

    metrics_port = int(os.getenv("METRICS_PORT", "8000"))
    log_structured(
        logger,
        "info",
        "metrics_server_starting",
        component="bootstrap",
        port=metrics_port,
    )
    start_http_server(metrics_port)

    i = 0
    while True:
        start = time.perf_counter()
        synthetic_latency = random.uniform(0.05, 1.2)
        time.sleep(synthetic_latency)

        status = "success"
        if i % 15 == 0 and i != 0:
            status = "error"
            ERROR_COUNTER.labels(type="synthetic_exception").inc()

        REQUEST_COUNTER.labels(status=status).inc()
        REQUEST_LATENCY_SECONDS.observe(synthetic_latency)
        TEMPERATURE_GAUGE.set(20 + (i % 10) + random.uniform(-0.4, 0.4))

        elapsed = time.perf_counter() - start
        log_structured(
            logger,
            "error" if status == "error" else "info",
            "request_processed",
            iteration=i,
            status=status,
            synthetic_latency_seconds=round(synthetic_latency, 3),
            processing_seconds=round(elapsed, 3),
            component="worker",
        )

        time.sleep(5)
        i += 1


if __name__ == "__main__":
    main()
