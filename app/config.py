from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    github_pat: str = ""
    api_secret_key: str

    class Config:
        env_file = ".env"


settings = Settings()
