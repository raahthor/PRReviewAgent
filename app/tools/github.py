from app.services.github import fetch_file_content


def create_github_tools(repo: str, head_sha: str):
    async def get_file_content(path: str) -> str:
        """
        Get the complete contents of a file from the pull request's
        current revision.

        Use this when the diff does not provide enough context
        to confidently understand a change.
        """
        return await fetch_file_content(
            repo=repo,
            path=path,
            ref=head_sha,
        )

    return [get_file_content]
