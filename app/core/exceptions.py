class AppError(Exception):
    """Base exception for application errors."""


class GitHubError(AppError):
    """Raised when a GitHub operation fails."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(message)


class AIError(AppError):
    """Raised when an AI operation fails."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)