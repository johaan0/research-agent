"""
Central configuration. Loads from environment variables / .env file.
Every other module should import `settings` from here rather than
calling os.environ directly — keeps config in one place.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    groq_api_key: str
    tavily_api_key: str
    database_url: str

    groq_model: str = "openai/gpt-oss-120b"
    max_subquestions: int = 5
    results_per_subquestion: int = 3
    max_revision_cycles: int = 2      # hard cap so a bad draft can't loop forever
    issue_tolerance: int = 0          # 0 = any flagged issue triggers a revision

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
