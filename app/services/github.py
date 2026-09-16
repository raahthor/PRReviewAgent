import contextlib
import io
import zipfile
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

@contextlib.asynccontextmanager
async def _github_client(timeout: float = GITHUB_TIMEOUT, follow_redirects: bool = True):
    """Reusable async client context that maps httpx errors to GitHubError."""
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=follow_redirects) as client:
            yield client
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


async def download_repository(
    repo: str,
    commit_sha: str,
) -> dict[str, str]:
    url = f"{GITHUB_API}/repos/{repo}/zipball/{commit_sha}"

    # Use a 60s timeout for downloading repository archives
    async with _github_client(timeout=60.0) as client:
        response = await client.get(url, headers=get_headers())
        response.raise_for_status()

    files = {}
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            path = "/".join(info.filename.split("/")[1:])
            if not path:
                continue
            files[path] = archive.read(info).decode("utf-8", errors="ignore")

    return files


async def fetch_pr(repo: str, pr_number: int) -> dict:
    url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}"

    async with _github_client() as client:
        response = await client.get(url, headers=get_headers())
        response.raise_for_status()
        return response.json()


async def fetch_changed_files(repo: str, pr_number: int) -> list[dict]:
    url = f"{GITHUB_API}/repos/{repo}/pulls/{pr_number}/files"

    async with _github_client() as client:
        response = await client.get(url, headers=get_headers())
        response.raise_for_status()
        return response.json()


async def compare_commits(
    repo: str,
    base_sha: str,
    head_sha: str,
) -> list[dict]:
    url = f"{GITHUB_API}/repos/{repo}/compare/{base_sha}...{head_sha}"

    async with _github_client() as client:
        response = await client.get(url, headers=get_headers())
        response.raise_for_status()
        return response.json().get("files", [])


async def fetch_file_content(
    repo: str,
    path: str,
    ref: str,
) -> str:
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"

    headers = {
        **get_headers(),
        "Accept": "application/vnd.github.raw+json",
    }

    async with _github_client() as client:
        response = await client.get(url, headers=headers, params={"ref": ref})
        response.raise_for_status()
        content = response.text
        if len(content) > settings.max_file_size:
            raise GitHubError(
                status_code=413,
                message=f"File is too large to retrieve: {path}",
            )
        return content


async def fetch_review_context(repo: str, pr_number: int) -> dict:
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
