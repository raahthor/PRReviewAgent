import httpx
from app.config import settings

GITHUB_API = "https://api.github.com"

async def fetch_diff(repo: str, pr_number: int) -> str:
    url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}"
    headers = {"Accept": "application/vnd.github.v3.diff"}
    if settings.github_pat:
        headers["Authorization"] = f"Bearer {settings.github_pat}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response.text