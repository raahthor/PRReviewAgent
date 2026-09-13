from typing import Literal
from pydantic import BaseModel


class ReviewIssue(BaseModel):
    severity: Literal["critical", "high", "medium", "low"]
    file: str
    line: int | None
    category: Literal[
        "bug",
        "security",
        "performance",
        "maintainability",
    ]
    title: str
    explanation: str
    suggestion: str


class CodeReview(BaseModel):
    summary: str
    issues: list[ReviewIssue]
