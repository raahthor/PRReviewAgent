from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    github_token: str = ""
    gemini_api_key: str = ""
    api_secret_key: str
    database_url: str

    max_tool_calls: int = 10
    max_file_size: int = 100_000
    review_timeout: float = 120.0

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
