class PythonTaskError(RuntimeError):
    """Base error raised by the Python task runner."""


class PythonTaskTimeoutError(PythonTaskError):
    """Raised when a task exceeds its configured timeout."""


class PythonTaskConfigurationError(PythonTaskError):
    """Raised when the submitted task definition is invalid."""
