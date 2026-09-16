from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Repo, RepoTree
from app.services.embeddings import generate_embedding


def create_rag_tools(repo: str, db: AsyncSession):
    async def search_codebase(query: str) -> str:
        """
        Search the repository codebase using semantic vector search to find
        functions, classes, or types relevant to a given query — returns names,
        signatures, and file locations only, not full file content.

        If you need to see the full implementation of a matched symbol, call
        fetch_file_content with the file_path returned here.

        Args:
            query: What symbol, pattern, or logic to find (e.g. "user authentication middleware").
        """
        try:
            query_embedding = await generate_embedding(query)

            stmt = (
                select(RepoTree)
                .join(Repo, Repo.repo_id == RepoTree.repo_id)
                .where(Repo.repo_url == repo)
                .order_by(RepoTree.embedding.cosine_distance(query_embedding))
                .limit(5)
            )
            result = await db.execute(stmt)
            matches = result.scalars().all()

            if not matches:
                return f"No relevant symbols found for query: '{query}'"

            output = [f"### Codebase search results for '{query}':\n"]
            for m in matches:
                sig = f" — `{m.signature}`" if m.signature else ""
                output.append(f"- `{m.name}` ({m.symbol_type}) in `{m.file_path}`{sig}")

            output.append(
                "\nUse fetch_file_content on a file_path above if you need the full implementation."
            )
            return "\n".join(output)

        except Exception as exc:
            return f"Failed to perform codebase search: {exc}"

    return [search_codebase]
