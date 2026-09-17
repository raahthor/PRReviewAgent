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

    # skip unsupported file ext
    if p.suffix not in SUPPORTED_EXTENSIONS:
        return False

    # skip files inside ignored dir
    for part in p.parts:
        if part in IGNORED_DIRECTORIES:
            return False
    return True


async def get_repo(db: AsyncSession, repo_url: str) -> Repo | None:
    result = await db.execute(select(Repo).where(Repo.repo_url == repo_url))
    return result.scalar_one_or_none()


async def _index_files(
    db: AsyncSession,
    repo_id: int,
    commit_sha: str,
    files: dict[str, str],
) -> None:

    # 1: extract all symbols from all files
    pending: list[tuple[str, Symbol]] = []
    for file_path, content in files.items():
        for symbol in extract_symbols(file_path=file_path, content=content):
            pending.append((file_path, symbol))

    if not pending:
        return

    # 2: generate embeddings for all symbols concurrently
    # using semaphore to limit how many requests hit the Gemini API at the same time
    sem = asyncio.Semaphore(10)

    async def embed_one(file_path: str, symbol: Symbol) -> list[float]:
        text = (
            f"File: {file_path}\n"
            f"Type: {symbol.symbol_type}\n"
            f"Name: {symbol.name}\n"
            f"Signature: {symbol.signature or ''}"
        )
        async with sem:
            return await generate_embedding(text)

    # asyncio.gather runs all embed_one calls concurrently like Promise.all
    embeddings = await asyncio.gather(
        *[embed_one(file_path, symbol) for file_path, symbol in pending]
    )

    # Step 3: Build and insert DB records.
    # pending[i] and embeddings[i] correspond to the same symbol.
    records = []
    for i, (file_path, symbol) in enumerate(pending):
        records.append(
            RepoTree(
                repo_id=repo_id,
                commit_sha=commit_sha,
                file_path=file_path,
                name=symbol.name,
                symbol_type=symbol.symbol_type,
                signature=symbol.signature,
                embedding=embeddings[i],
            )
        )

    db.add_all(records)


async def initial_sync(db: AsyncSession, repo: Repo, commit_sha: str) -> None:

    # download repo at this commit
    raw_files = await download_repository(repo=repo.repo_url, commit_sha=commit_sha)

    # keeping files we can parse and index
    files = {}
    for path, content in raw_files.items():
        if should_index(path):
            files[path] = content

    # clear any previously indexed symbols for this repo (safe to redo)
    await db.execute(delete(RepoTree).where(RepoTree.repo_id == repo.repo_id))

    await _index_files(db=db, repo_id=repo.repo_id, commit_sha=commit_sha, files=files)


async def incremental_sync(db: AsyncSession, repo: Repo, commit_sha: str) -> None:
    # fetches changed files between two commits and re indexes them

    changed_files = await compare_commits(
        repo=repo.repo_url,
        base_sha=repo.last_indexed_sha,
        head_sha=commit_sha,
    )

    # collect which file paths to delete and which to re fetch
    delete_paths = set()
    fetch_paths = []

    for item in changed_files:
        filename = item.get("filename", "")
        if not should_index(filename):
            continue

        # delete the current path to re index it
        delete_paths.add(filename)

        # if the file was renamed, also delete the old path
        prev_filename = item.get("previous_filename")
        if prev_filename and should_index(prev_filename):
            delete_paths.add(prev_filename)

        # removed files should be deleted but not re fetched
        if item.get("status") != "removed":
            fetch_paths.append(filename)

    # 1: delete stale symbols in one query
    if delete_paths:
        await db.execute(
            delete(RepoTree).where(
                RepoTree.repo_id == repo.repo_id,
                RepoTree.file_path.in_(delete_paths),
            )
        )

    # 2: fetch and re index changed files
    if fetch_paths:
        # fetch all file contents concurrently
        contents = await asyncio.gather(
            *[
                fetch_file_content(repo.repo_url, path, commit_sha)
                for path in fetch_paths
            ]
        )

        # pair each path back with its content, skipping any failed
        files = {}
        for path, content in zip(fetch_paths, contents):
            if content is not None:
                files[path] = content

        await _index_files(
            db=db, repo_id=repo.repo_id, commit_sha=commit_sha, files=files
        )


async def sync_repo(
    db: AsyncSession,
    repo_url: str,
    commit_sha: str,
) -> None:
    repo = await get_repo(db, repo_url)

    # if it doesn't exist yet, create it
    if repo is None:
        repo = Repo(repo_url=repo_url)
        db.add(repo)
        await db.flush()  # assigns repo.repo_id without committing

    # return if upto date
    if repo.last_indexed_sha == commit_sha:
        return

    try:
        if not repo.last_indexed_sha:
            # first time sync
            await initial_sync(db=db, repo=repo, commit_sha=commit_sha)
        else:
            # sync what changed, in existing repo
            await incremental_sync(db=db, repo=repo, commit_sha=commit_sha)

        repo.last_indexed_sha = commit_sha
        await db.commit()
    except Exception:
        await db.rollback()
        raise
