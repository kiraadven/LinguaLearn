from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8080

    funasr_ws_url: str = "ws://127.0.0.1:10095"
    asr_final_timeout_seconds: float = 30.0
    cosyvoice_http_url: str = "http://127.0.0.1:9880"
    cosyvoice_connect_timeout_seconds: float = 10.0
    cosyvoice_read_timeout_seconds: float = 180.0
    cosyvoice_write_timeout_seconds: float = 60.0
    cosyvoice_pool_timeout_seconds: float = 60.0

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-haiku-latest"
    llm_api_base_url: str = "https://api.chatanywhere.tech"
    llm_chat_path: str = "/v1/chat/completions"
    llm_timeout_seconds: float = 120.0

    default_voice_id: str = "sarah_en"
    default_language: str = "en"

    profile_db_path: Path = Field(default=Path("data/learner_profiles.db"))
    lesson_plan_dir: Path = Field(default=Path("data/lesson_plans"))
    filler_dir: Path = Field(default=Path("data/fillers"))

    # AI Tutor extended paths
    ai_tutor_db_path: Path = Field(default=Path("data/ai_tutor.db"))
    lingualearn_data_dir: Path = Field(
        default=Path("/Users/yangyangqinqin/Desktop/automation/data/output")
    )
    lingualearn_db_path: Path = Field(
        default=Path("/Users/yangyangqinqin/Desktop/lingualearn_plus_ai_tutor/data/lingualearn.db")
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
