class AppError(Exception):
    """Base exception for application errors."""


class GitHubError(AppError):
    """Raised when a GitHub operation fails."""


class AIError(AppError):
    """Raised when an AI operation fails."""