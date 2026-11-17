"""Standalone role-B generator. The repository adapter is intentionally separate."""

from .errors import ConfigurationError, GenerationError, InputError
from .generator import generate
from .model import ChatModel, Settings

__all__ = ["generate", "ChatModel", "Settings", "InputError", "GenerationError", "ConfigurationError"]
