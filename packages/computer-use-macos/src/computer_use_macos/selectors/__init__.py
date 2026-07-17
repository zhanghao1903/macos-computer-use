"""Internal Accessibility selector profile support.

This package is intentionally not re-exported from ``computer_use_macos`` while
the selector engine is in its internal MVP phase.
"""

from .models import AccessibilitySelectorProfile
from .profile import parse_selector_profile
from .collections import CollectionExtractor
from .resolver import SelectorResolver
from .validation import SelectorProfileValidationError, validate_selector_profile

__all__ = [
    "AccessibilitySelectorProfile",
    "CollectionExtractor",
    "SelectorResolver",
    "SelectorProfileValidationError",
    "parse_selector_profile",
    "validate_selector_profile",
]
