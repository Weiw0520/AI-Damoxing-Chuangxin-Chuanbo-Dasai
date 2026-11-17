class InputError(ValueError):
    """Invalid caller input; map to an HTTP 4xx in the repository adapter."""


class GenerationError(RuntimeError):
    """Upstream model or schema error; never silently return mock content."""


class ConfigurationError(GenerationError):
    """Missing or invalid model configuration."""
