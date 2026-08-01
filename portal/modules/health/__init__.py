"""health module: system health, repair dashboard and read-only monitors.

Register with the coexistence registry ONLY after the permission table (A2) and
service tests (A5) pass. Removing the register() call returns these routes to the
legacy adapter with no redeploy (A8).
"""
from portal.modules.health.routes import endpoints

__all__ = ["endpoints"]
