from fastapi import APIRouter, Depends, Header, HTTPException
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.core.config import settings
from app.services.github import fetch_review_context, get_branch_sha
from app.services.ai import review_code
from app.services.sync import sync_repo
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


@router.post("")
async def review_pr(
    repo: str,
    pr_number: int,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    try:
        async with asyncio.timeout(settings.review_timeout):

            context = await fetch_review_context(repo, pr_number)
            head_sha = context["pr"]["head_sha"]  # PR branch, for reviewing the diff
            base_branch = context["pr"]["base_branch"]  # main
            main_sha = await get_branch_sha(repo, base_branch)

            # 1: sync repo before AI review
            await sync_repo(
                db=db,
                repo_url=repo,
                commit_sha=main_sha,
            )

            # 2: run AI review
            return await review_code(
                context=context,
                repo=repo,
                head_sha=head_sha,
                db=db,
            )

    except TimeoutError as exc:
        raise ReviewError(message="Review timed out", status_code=502) from exc
