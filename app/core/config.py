from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    github_token: str = ""
    gemini_api_key: str = ""
    api_secret_key: str
    database_url:str

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
