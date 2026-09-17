from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.api.review import verify_api_key
from app.core.exceptions import SyncError
from app.services.sync import sync_repo
from app.services.github import get_main_sha

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("")
async def manual_sync(
    repo: str,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_api_key),
):
    try:
        main_sha = await get_main_sha(repo)
        await sync_repo(
            db=db,
            repo_url=repo,
            commit_sha=main_sha,
        )
        return {
            "status": "success",
            "message": f"Successfully synced {repo} at commit {main_sha}",
            "repo": repo,
            "commit_sha": main_sha,
        }
    except Exception as exc:
        raise SyncError(message="Sync failed", status_code=502) from exc
