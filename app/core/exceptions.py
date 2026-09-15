class AppError(Exception):
    """Base exception for expected application errors."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class GitHubError(AppError):
    """Raised when a GitHub operation fails."""


class AIError(AppError):
    """Raised when an AI operation fails."""


class ReviewError(AppError):
    """Raised when a review operation fails."""
