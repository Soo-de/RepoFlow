from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "RepoFlow"
    llm_provider: str = "auto"  # "auto", "gemini", or "groq"
    gemini_api_key: str = ""
    groq_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    groq_model: str = "llama-3.3-70b-versatile"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
