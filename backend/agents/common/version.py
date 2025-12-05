"""
Version management for DevOps Agentic Framework agents.
"""
import os
from pathlib import Path


def get_version() -> str:
    """
    Get the current version from the VERSION file at the project root.

    Returns:
        str: Version string in semantic versioning format (e.g., "1.0.0")
    """
    try:
        # Navigate up from common module to project root
        version_file = Path(__file__).parent.parent.parent.parent / "VERSION"
        if version_file.exists():
            return version_file.read_text().strip()
        return "1.0.0"  # Default fallback
    except Exception:
        return "1.0.0"  # Default fallback


__version__ = get_version()
