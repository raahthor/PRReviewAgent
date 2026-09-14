import httpx

from app.core.config import settings
from app.core.exceptions import GitHubError

GITHUB_API = "https://api.github.com"
GITHUB_TIMEOUT = 10.0


def get_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "PR-Review-Agent",
    }

    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    return headers


async def fetch_pr(repo: str, pr_number: int) -> dict:
    url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}"

    async with httpx.AsyncClient(timeout=GITHUB_TIMEOUT) as client:
        response = await client.get(
            url,
            headers=get_headers(),
        )
        response.raise_for_status()
        return response.json()


async def fetch_changed_files(repo: str, pr_number: int) -> list[dict]:
    url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/files"

    async with httpx.AsyncClient(timeout=GITHUB_TIMEOUT) as client:
        response = await client.get(
            url,
            headers=get_headers(),
        )
        response.raise_for_status()
        return response.json()


async def fetch_file_content(
    repo: str,
    path: str,
    ref: str,
) -> str:
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"

    headers = get_headers()
    headers["Accept"] = "application/vnd.github.raw+json"

    try:
        async with httpx.AsyncClient(timeout=GITHUB_TIMEOUT) as client:
            response = await client.get(
                url,
                headers=headers,
                params={"ref": ref},
            )
            response.raise_for_status()
            return response.text

    except httpx.HTTPStatusError as exc:
        raise GitHubError(
            status_code=exc.response.status_code,
            message=f"GitHub request failed: {exc.response.reason_phrase}",
        ) from exc

    except httpx.RequestError as exc:
        raise GitHubError(
            status_code=502,
            message="Failed to connect to GitHub",
        ) from exc


async def fetch_review_context(repo: str, pr_number: int) -> dict:
    try:
        pr = await fetch_pr(repo, pr_number)
        changed_files = await fetch_changed_files(repo, pr_number)

        return {
            "pr": {
                "number": pr["number"],
                "title": pr["title"],
                "description": pr["body"],
                "head_sha": pr["head"]["sha"],
                "base_sha": pr["base"]["sha"],
                "base_branch": pr["base"]["ref"],
            },
            "files": [
                {
                    "path": file["filename"],
                    "status": file["status"],
                    "additions": file["additions"],
                    "deletions": file["deletions"],
                    "patch": file.get("patch"),
                }
                for file in changed_files
            ],
        }

    except httpx.HTTPStatusError as exc:
        raise GitHubError(
            status_code=exc.response.status_code,
            message=f"GitHub request failed: {exc.response.reason_phrase}",
        ) from exc

    except httpx.RequestError as exc:
        raise GitHubError(
            status_code=502,
            message="Failed to connect to GitHub",
        ) from exc
