"""
Version management for DevOps Agentic Framework agents.
"""
import os
from pathlib import Path


def get_version() -> str:
    """
    Get the current version from environment variable or VERSION file.

    Priority:
    1. AGENT_VERSION environment variable (set per-agent in ECS)
    2. VERSION file at project root
    3. Default fallback

    Returns:
        str: Version string in semantic versioning format (e.g., "1.0.4")
    """
    # First check environment variable (set per-agent in ECS task definition)
    agent_version = os.getenv('AGENT_VERSION')
    if agent_version:
        return agent_version.strip()

    try:
        # Fallback to VERSION file
        version_file = Path(__file__).parent.parent.parent.parent / "VERSION"
        if version_file.exists():
            return version_file.read_text().strip()
        return "1.0.0"  # Default fallback
    except Exception:
        return "1.0.0"  # Default fallback


__version__ = get_version()
