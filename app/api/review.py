from fastapi import APIRouter, Depends, Header, HTTPException
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.core.config import settings
from app.services.github import fetch_review_context
from app.services.ai import review_code
from app.core.exceptions import ReviewError

router = APIRouter(prefix="/reviews", tags=["reviews"])


def verify_api_key(
    x_api_key: str = Header(...),
) -> None:
    if x_api_key != settings.api_secret_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
        )


@router.post("/")
async def review_pr(
    repo: str,
    pr_number: int,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    try:
        async with asyncio.timeout(settings.review_timeout):
            context = await fetch_review_context(repo, pr_number)

            return await review_code(
                context=context,
                repo=repo,
                head_sha=context["pr"]["head_sha"],
            )

    except TimeoutError as exc:
        raise ReviewError(message="Review timed out", status_code=502) from exc
