from fastapi import APIRouter, Depends, Header, HTTPException

from app.config import settings
from app.services.github import fetch_review_context
from app.services.ai import review_code

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
    _: None = Depends(verify_api_key),
):
    context = await fetch_review_context(repo, pr_number)
    review = await review_code(context, repo=repo, head_sha=context["pr"]["head_sha"])
    return review
