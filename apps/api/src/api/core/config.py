from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    OPENAI_API_KEY: str
    GROQ_API_KEY: str
    GOOGLE_API_KEY: str
    POLICIES_DIR: str = "/app/data/policies"

    model_config = SettingsConfigDict(env_file=".env")

config = Config()
