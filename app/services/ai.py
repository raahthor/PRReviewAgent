from google import genai
from google.genai import types, errors

from app.core.config import settings
from app.schemas.review import CodeReview
from app.tools.github import create_github_tools
from app.core.exceptions import AIError

client = genai.Client(api_key=settings.gemini_api_key)

GEMINI_MODEL = "gemini-3.1-flash-lite"

SYSTEM_INSTRUCTION = """
You are a senior software engineer performing code reviews on GitHub pull requests.

Your job is to identify real, actionable problems introduced by the pull request.

Review the changes for:

- Bugs and incorrect behavior
- Security vulnerabilities
- Performance problems
- Maintainability problems

Focus primarily on issues introduced by the PR.

Do not report:
- Personal style preferences
- Minor formatting issues
- Issues that existed before the PR
- Speculative problems without reasonable evidence
- Suggestions that do not provide meaningful value

Only report an issue when you have sufficient evidence from the provided
pull request context.

For every issue:
- Identify the affected file.
- Give the most relevant line number when possible.
- Explain why it is a problem.
- Provide a concrete suggestion for fixing it.
- Assign an appropriate severity.

Severity definitions:

critical:
A severe vulnerability, data loss, system compromise, or issue that can
cause major production impact.

high:
A serious bug or security issue that is likely to cause significant
incorrect behavior or impact.

medium:
A meaningful bug, performance issue, or maintainability problem that should
be addressed but is unlikely to cause severe damage.

low:
A minor but actionable issue with limited impact.

If there are no meaningful issues, return an empty issues array.

Do not invent repository behavior or assumptions that are not supported by
the provided context.
"""


async def review_code(context: dict, repo: str, head_sha: str) -> CodeReview:

    tools = [*create_github_tools(repo=repo, head_sha=head_sha)]

    try:
        chat = client.aio.chats.create(
            model=GEMINI_MODEL,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
                response_schema=CodeReview,
                tools=tools,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(
                    maximum_remote_calls=settings.max_tool_calls
                ),
            ),
        )

        response = await chat.send_message(str(context))

        return CodeReview.model_validate_json(response.text)
    except errors.APIError as exc:
        raise AIError(
            message=f"AI request failed: {exc.message}",
            status_code=502
        ) from exc

    except Exception as exc:
        raise AIError(
            message="AI review failed",
            status_code=502
        ) from exc
