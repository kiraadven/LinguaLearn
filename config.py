"""
Compatibility config shim.

Imports are kept compatible (`import config`) after moving backend
implementation into `backend/config.py`.
"""

from backend.config import *  # noqa: F401,F403

