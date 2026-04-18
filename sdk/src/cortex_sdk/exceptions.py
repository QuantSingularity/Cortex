class CortexError(Exception):
    """Base exception for all Cortex SDK errors."""

    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class CortexNotFoundError(CortexError):
    """Resource not found (HTTP 404)."""


class CortexConflictError(CortexError):
    """Resource already exists (HTTP 409)."""


class CortexServiceError(CortexError):
    """Upstream service error (HTTP 5xx)."""


def _raise_for_status(response) -> None:
    if response.status_code == 404:
        raise CortexNotFoundError(response.text, status_code=404)
    if response.status_code == 409:
        raise CortexConflictError(response.text, status_code=409)
    if response.status_code >= 500:
        raise CortexServiceError(response.text, status_code=response.status_code)
    if response.status_code >= 400:
        raise CortexError(response.text, status_code=response.status_code)
