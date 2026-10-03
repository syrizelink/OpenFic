# -*- coding: utf-8 -*-
"""
Models Services - 模型业务逻辑层。
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.services.model_provider_service import ModelProviderService
    from app.models.services.model_service import ModelService

__all__ = ["ModelProviderService", "ModelService"]


def __getattr__(name: str) -> object:
    if name == "ModelProviderService":
        from app.models.services.model_provider_service import ModelProviderService

        return ModelProviderService
    if name == "ModelService":
        from app.models.services.model_service import ModelService

        return ModelService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
