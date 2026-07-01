"""Portable, strictly-validated Pydantic models for device definitions.

Self-contained: depends only on ``pydantic>=2.5`` and the standard library, so it
can be vendored in this repository or extracted into its own shared package/repo
without change.
"""

from .models import *  # noqa: F401,F403
from .models import __all__  # noqa: F401

__version__ = "0.1.0"
