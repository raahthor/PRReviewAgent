from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import review
from app.core.exceptions import AppError

app = FastAPI(title="PR Review Agent")


@app.exception_handler(AppError)
async def app_error_handler(
    _request: Request,
    exc: AppError,
):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
        },
    )


app.include_router(review.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
