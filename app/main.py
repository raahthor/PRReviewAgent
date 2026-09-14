from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import review
from app.core.exceptions import GitHubError, AIError

app = FastAPI(title="PR Review Agent")


@app.exception_handler(GitHubError)
async def github_error_handler(
    _request: Request,
    exc: GitHubError,
):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "github_error",
            "message": exc.message,
        },
    )


@app.exception_handler(AIError)
async def ai_error_handler(
    _request: Request,
    exc: AIError,
):
    return JSONResponse(
        status_code=502,
        content={
            "error": "ai_error",
            "message": exc.message,
        },
    )

app.include_router(review.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
