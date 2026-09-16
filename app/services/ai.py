from google import genai
from google.genai import types, errors
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.schemas.review import CodeReview
from app.tools.github import create_github_tools
from app.tools.rag import create_rag_tools
from app.core.exceptions import AIError

client = genai.Client(api_key=settings.gemini_api_key)

GEMINI_MODEL = "gemini-3.1-flash-lite"

SYSTEM_INSTRUCTION = """
You are a senior engineer reviewing a GitHub pull request. Report only
real, actionable problems introduced by this PR: bugs, security issues,
performance problems, and maintainability issues.

Skip style preferences, formatting nitpicks, pre-existing issues, and
speculative concerns without clear evidence in the provided context.

Tools:
- get_file_content: full content of a file when the diff lacks context
- search_codebase: semantic search to find related functions/classes
  elsewhere in the repo; follow up with get_file_content if you need
  the full implementation

For each issue, give: file, line (if known), why it's a problem, a
concrete fix, and a severity.

Severity: critical (data loss/security/major prod impact), high (serious
bug likely to cause real incorrect behavior), medium (meaningful but
limited-impact issue), low (minor, actionable).

Return an empty issues array if there's nothing meaningful to report.
Don't invent behavior not supported by the given context.
"""


def _build_tools(repo: str, head_sha: str, db: AsyncSession) -> list:
    return [
        *create_github_tools(repo=repo, head_sha=head_sha),
        *create_rag_tools(repo=repo, db=db),
    ]


async def review_code(
    context: dict,
    repo: str,
    head_sha: str,
    db: AsyncSession,
) -> CodeReview:
    try:
        chat = client.aio.chats.create(
            model=GEMINI_MODEL,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=CodeReview,
                tools=_build_tools(repo, head_sha, db),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    maximum_remote_calls=settings.max_tool_calls
                ),
            ),
        )

        response = await chat.send_message(str(context))
        return CodeReview.model_validate_json(response.text)

    except errors.APIError as exc:
        raise AIError(
            message=f"AI request failed: {exc.message}", status_code=502
        ) from exc
    except Exception as exc:
        raise AIError(message="AI review failed", status_code=502) from exc
