from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "RepoFlow"
    groq_api_key: str = ""
    redis_url: str = "redis://localhost:6379"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
