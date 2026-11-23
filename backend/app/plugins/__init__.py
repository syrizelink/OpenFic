"""OpenFic extension host, API version 1. Public SDK imports remain lazy."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.plugins.sdk import PluginContext as PluginContext

__all__ = ["PluginContext"]


def __getattr__(name):
    if name == "PluginContext":
        from app.plugins.sdk import PluginContext

        return PluginContext
    raise AttributeError(name)
