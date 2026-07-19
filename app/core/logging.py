"""structlog configuration: JSON lines in prod, pretty console in dev."""
import logging
import sys

import structlog


def configure_logging(level: str = "INFO", env: str = "dev") -> None:
    logging.basicConfig(stream=sys.stdout, level=level.upper(), format="%(message)s")

    shared: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    renderer = (
        structlog.dev.ConsoleRenderer()
        if env == "dev"
        else structlog.processors.JSONRenderer()
    )
    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[level.upper()]
        ),
        cache_logger_on_first_use=True,
    )
