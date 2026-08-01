"""Portal-scoped startup hook.

Loaded only when the portal service sets PYTHONPATH=/srv/cloudif/lib. Other
Python processes on the host are not modified.
"""
try:
    import cloudif_portal_v2_coexist  # noqa: F401
except Exception:
    # Auto-recovery: the legacy portal remains available if coexistence fails.
    pass
