"""Module quản lý tài nguyên (Resource Management) cho Chatbox 2.0."""

from src.resource.manager import (
    EmbeddingModelManager,
    HardwareTelemetry,
    IndexAccessCoordinator,
    ResourceManager,
    ResourceState,
    get_resource_manager,
)

__all__ = [
    "ResourceState",
    "IndexAccessCoordinator",
    "EmbeddingModelManager",
    "HardwareTelemetry",
    "ResourceManager",
    "get_resource_manager",
]
