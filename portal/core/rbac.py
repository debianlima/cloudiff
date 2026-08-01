"""Minimal permission contract for Portal v2 modules."""
from collections.abc import Callable

PermissionCheck = Callable[[str], bool]
