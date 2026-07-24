from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "RepoFlow"
    gemini_api_key: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

