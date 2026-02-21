"""Application composition root.

All concrete dependencies are wired here:
- local persistence (SQLite)
- remote API client (optional)
- offline-first backend facade
- Qt main window
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QDialog, QMessageBox  # pylint: disable=no-name-in-module

from riskapp_client.adapters.local.sqlite_store import LocalStore
from riskapp_client.adapters.remote.api_backend import ApiBackend
from riskapp_client.app.config import AppConfig
from riskapp_client.services.offline_first_backend import OfflineFirstBackend
from riskapp_client.ui.main_window import MainWindow
from riskapp_client.ui.widgets import LoginDialog

logger = logging.getLogger(__name__)


def build_main_window(config: AppConfig) -> MainWindow:
    """Build and return the application's main window."""

    store = LocalStore(str(config.local_db_path))

    remote = None
    base_url = config.base_url
    email = config.email
    password = config.password

    if not email or not password:
        dlg = LoginDialog(default_url=base_url)
        if dlg.exec() != QDialog.Accepted:
            # Allow pure offline start if DB already has data.
            backend = OfflineFirstBackend(store, remote=None)
            return MainWindow(backend)

        base_url, email, password = dlg.values()

    try:
        remote = ApiBackend(
            base_url=base_url,
            email=email,
            password=password,
            auto_create_project=config.auto_create_project,
        )
    except Exception as exc:  # noqa: BLE001 - UX-driven fallback
        logger.warning("Starting offline: %s", exc)
        QMessageBox.warning(
            None,
            "Offline mode",
            f"{exc}\n\nStarting offline (local cache + outbox).",
        )
        remote = None

    backend = OfflineFirstBackend(store, remote=remote)
    return MainWindow(backend)