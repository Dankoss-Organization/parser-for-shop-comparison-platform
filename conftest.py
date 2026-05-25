"""
conftest.py — Pytest configuration and shared fixtures.

Mocks all external third-party modules (cloudinary, cloudscraper, etc.)
before any imports happen, so tests run without needing real credentials
or network access.
"""

import sys
import os
import types
from unittest.mock import MagicMock

# --- Set env vars before any project import ---
os.environ.setdefault("DATABASE_URL", "postgresql://fake:fake@localhost/fake")

# --- cloudinary: must be a proper package-like mock so submodule access works ---
_cloudinary_pkg = types.ModuleType("cloudinary")
_cloudinary_pkg.uploader = MagicMock()
_cloudinary_pkg.api = MagicMock()
_cloudinary_pkg.config = MagicMock()
_cloudinary_exceptions = types.ModuleType("cloudinary.exceptions")
_cloudinary_exceptions.NotFound = Exception
_cloudinary_pkg.exceptions = _cloudinary_exceptions
sys.modules["cloudinary"] = _cloudinary_pkg
sys.modules["cloudinary.uploader"] = _cloudinary_pkg.uploader
sys.modules["cloudinary.api"] = _cloudinary_pkg.api
sys.modules["cloudinary.exceptions"] = _cloudinary_exceptions

# --- All other external mocks ---
for _mod in [
    "cloudscraper",
    "requests",
    "dotenv",
    "sentence_transformers",
    "sklearn",
    "sklearn.metrics",
    "sklearn.metrics.pairwise",
    "torch",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# python-dotenv: make load_dotenv a no-op
sys.modules["dotenv"].load_dotenv = lambda *a, **k: None
