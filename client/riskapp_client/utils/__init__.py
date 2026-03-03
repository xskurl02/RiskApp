"""Shared client utilities.

This package is intentionally small and dependency-free so it can be reused
across UI, offline storage, and API client layers.

Import style:
    Prefer importing concrete helpers from their modules, e.g.::

        from riskapp_client.utils.role_permission_evaluator import role_at_least

We intentionally avoid re-exporting symbols from this package to keep imports
explicit and prevent circular-import surprises.
"""
