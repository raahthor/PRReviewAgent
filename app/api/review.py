from fastapi import APIRouter, Header, HTTPException, Depends
from app.config import settings
from app.services.github import fetch_diff

router = APIRouter()

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != settings.api_secret_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

@router.post("/review")
async def review_pr(repo: str, pr_number: int, _: None = Depends(verify_api_key)):
    diff = await fetch_diff(repo, pr_number)
    return {"diff_preview": diff[:500]}