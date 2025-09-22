"""Web monitoring utilities for the multi-agent crypto system."""

from __future__ import annotations

from typing import Any

__all__ = ["create_app", "MonitoringStateManager"]


def __getattr__(name: str) -> Any:
    if name == "create_app":
        from .app import create_app

        return create_app
    if name == "MonitoringStateManager":
        from .state_manager import MonitoringStateManager

        return MonitoringStateManager
    raise AttributeError(f"module 'multi_agent_crypto.monitoring' has no attribute {name!r}")
