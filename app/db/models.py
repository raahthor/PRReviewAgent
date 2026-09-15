from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Text, ForeignKey, DateTime, func
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    pass


class Repo(Base):
    __tablename__ = "repos"
    repo_id: Mapped[int] = mapped_column(primary_key=True)
    repo_url: Mapped[str] = mapped_column(String, unique=True)
    last_indexed_sha: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())


class RepoTree(Base):
    __tablename__ = "repo_tree"
    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int] = mapped_column(
        ForeignKey("repos.repo_id", ondelete="CASCADE")
    )
    commit_sha: Mapped[str] = mapped_column(String(40))
    file_path: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    symbol_type: Mapped[str] = mapped_column(String(50))
    signature: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
