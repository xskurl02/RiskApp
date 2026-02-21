"""Client-side services."""

from .export_csv import export_opportunities, export_risks

# Offline-first backend facade (Qt client uses this as its Backend implementation)
from .offline_first_backend import OfflineFirstBackend  # noqa: F401