"""Application composition root.

All concrete dependencies are wired here:
- local persistence (SQLite)
- remote API client (optional)
- offline-first backend facade
- Qt main window
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtWidgets import QDialog, QMessageBox  # pylint: disable=no-name-in-module

from riskapp_client.adapters.local_storage.sqlite_data_store import LocalStore
from riskapp_client.adapters.remote_api.rest_api_client import ApiBackend
from riskapp_client.app.environment_config import AppConfig
from riskapp_client.services.offline_first_facade import OfflineFirstBackend
from riskapp_client.ui_v2.components.custom_gui_widgets import LoginDialog
from riskapp_client.ui_v2.main_application_window import MainWindow
from riskapp_client.utils.url_validation_helpers import UrlPolicy

logger = logging.getLogger(__name__)


def build_main_window(config: AppConfig) -> MainWindow:
    """Build and return the application's main window."""
    try:
        Path(config.local_db_path).expanduser().parent.mkdir(
            parents=True, exist_ok=True
        )
    except OSError as exc:
        QMessageBox.critical(
            None,
            "Local storage error",
            f"Cannot create local DB directory for:\n{config.local_db_path}\n\n{exc}",
        )
        raise
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
            url_policy=UrlPolicy(allow_http_anywhere=config.allow_http_anywhere),
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
