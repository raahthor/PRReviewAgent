from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pathlib import PurePosixPath
import asyncio

from app.db.models import Repo, RepoTree
from app.services.github import (
    download_repository,
    compare_commits,
    fetch_file_content,
)
from app.services.parser import extract_symbols, Symbol, LANGUAGES
from app.services.embeddings import generate_embedding

SUPPORTED_EXTENSIONS = set(LANGUAGES.keys())

IGNORED_DIRECTORIES = {
    ".git",
    "node_modules",
    "dist",
    "build",
    ".next",
    "coverage",
    "__pycache__",
}


def should_index(path: str) -> bool:
    p = PurePosixPath(path)
    return p.suffix in SUPPORTED_EXTENSIONS and not any(
        d in IGNORED_DIRECTORIES for d in p.parts
    )


async def get_repo(db: AsyncSession, repo_url: str) -> Repo | None:
    result = await db.execute(select(Repo).where(Repo.repo_url == repo_url))
    return result.scalar_one_or_none()


async def _index_files(
    db: AsyncSession,
    repo_id: int,
    commit_sha: str,
    files: dict[str, str],
) -> None:
    """Extracts symbols, generates embeddings concurrently, and adds records to session."""
    pending: list[tuple[str, Symbol]] = [
        (file_path, symbol)
        for file_path, content in files.items()
        for symbol in extract_symbols(file_path=file_path, content=content)
    ]

    if not pending:
        return

    sem = asyncio.Semaphore(10)

    async def embed_with_limit(file_path: str, symbol: Symbol) -> list[float]:
        text = (
            f"File: {file_path}\n"
            f"Type: {symbol.symbol_type}\n"
            f"Name: {symbol.name}\n"
            f"Signature: {symbol.signature or ''}"
        )
        async with sem:
            return await generate_embedding(text)

    embeddings = await asyncio.gather(
        *(embed_with_limit(file_path, symbol) for file_path, symbol in pending)
    )

    db.add_all(
        [
            RepoTree(
                repo_id=repo_id,
                commit_sha=commit_sha,
                file_path=file_path,
                name=symbol.name,
                symbol_type=symbol.symbol_type,
                signature=symbol.signature,
                embedding=embedding,
            )
            for (file_path, symbol), embedding in zip(pending, embeddings)
        ]
    )


async def initial_sync(db: AsyncSession, repo: Repo, commit_sha: str) -> None:
    raw_files = await download_repository(repo=repo.repo_url, commit_sha=commit_sha)
    files = {path: content for path, content in raw_files.items() if should_index(path)}
    print("here")
    await db.execute(delete(RepoTree).where(RepoTree.repo_id == repo.repo_id))
    await _index_files(db=db, repo_id=repo.repo_id, commit_sha=commit_sha, files=files)


async def incremental_sync(db: AsyncSession, repo: Repo, commit_sha: str) -> None:
    changed_files = await compare_commits(
        repo=repo.repo_url,
        base_sha=repo.last_indexed_sha,
        head_sha=commit_sha,
    )

    delete_paths = set()
    fetch_paths = []

    for item in changed_files:
        filename = item.get("filename", "")
        if not should_index(filename):
            continue

        delete_paths.add(filename)

        prev_filename = item.get("previous_filename")
        if prev_filename and should_index(prev_filename):
            delete_paths.add(prev_filename)

        if item.get("status") != "removed":
            fetch_paths.append(filename)

    # 1. Single batch delete for all touched paths
    if delete_paths:
        await db.execute(
            delete(RepoTree).where(
                RepoTree.repo_id == repo.repo_id,
                RepoTree.file_path.in_(delete_paths),
            )
        )

    # 2. Fetch and index updated contents for active files
    if fetch_paths:
        contents = await asyncio.gather(
            *(
                fetch_file_content(repo.repo_url, path, commit_sha)
                for path in fetch_paths
            )
        )
        files = {
            path: content
            for path, content in zip(fetch_paths, contents)
            if content is not None
        }
        await _index_files(
            db=db, repo_id=repo.repo_id, commit_sha=commit_sha, files=files
        )


async def sync_repo(
    db: AsyncSession,
    repo_url: str,
    commit_sha: str,
) -> None:
    repo = await get_repo(db, repo_url)

    if repo is None:
        repo = Repo(repo_url=repo_url)
        db.add(repo)
        await db.flush()

    if repo.last_indexed_sha == commit_sha:
        return

    try:
        if not repo.last_indexed_sha:
            await initial_sync(db=db, repo=repo, commit_sha=commit_sha)
        else:
            await incremental_sync(db=db, repo=repo, commit_sha=commit_sha)

        repo.last_indexed_sha = commit_sha
        await db.commit()
    except Exception:
        await db.rollback()
        raise
