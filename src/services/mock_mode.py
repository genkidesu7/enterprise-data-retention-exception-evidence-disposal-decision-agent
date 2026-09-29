"""AgentCore Platform v1.0"""

# Shared mock-mode resolution helper.
# `deploy-stg` sets STG_MOCK_MODE=true as a CI-script-only variable; it is
# never exported to the uvicorn process. USE_MOCK is the canonical flag tests
# set. Every service must resolve mock mode through this single helper so a
# future rename only needs one edit — never re-derive this per service.

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values

_env: dict[str, str | None] = dotenv_values(Path(__file__).parent.parent.parent / ".env")


def _get_flag(key: str) -> str:
    """OS env takes precedence over .env file."""
    return os.environ.get(key) or _env.get(key) or ""


def mock_mode_enabled() -> bool:
    """True if either USE_MOCK or STG_MOCK_MODE is set to a truthy value."""
    truthy = ("1", "true", "yes")
    return _get_flag("USE_MOCK").lower() in truthy or _get_flag("STG_MOCK_MODE").lower() in truthy
