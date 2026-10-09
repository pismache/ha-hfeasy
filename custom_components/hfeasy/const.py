"""Constantes de l'intégration HFeasy."""

from datetime import timedelta

DOMAIN = "hfeasy"
MANUFACTURER = "HFeasy"

DEFAULT_PORT = 8080
CONF_SCAN_INTERVAL = "scan_interval"
DEFAULT_SCAN_INTERVAL = 30  # secondes
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 3600

REQUEST_TIMEOUT = 5  # secondes : une prise sur le réseau local répond vite ou pas du tout


def scan_interval(seconds: int) -> timedelta:
    return timedelta(seconds=max(MIN_SCAN_INTERVAL, min(MAX_SCAN_INTERVAL, int(seconds))))
