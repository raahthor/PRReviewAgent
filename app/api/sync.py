from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.api.review import verify_api_key
from app.services.sync import sync_repo

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("")
async def manual_sync(
    repo: str,
    commit_sha: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    await sync_repo(
        db=db,
        repo_url=repo,
        commit_sha=commit_sha,
    )
    return {
        "status": "success",
        "message": f"Successfully synced {repo} at commit {commit_sha}",
        "repo": repo,
        "commit_sha": commit_sha,
    }
