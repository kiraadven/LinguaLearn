from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AI_TUTOR_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = AI_TUTOR_DIR.parent


def _project_path(path_value: Path) -> Path:
    p = path_value.expanduser()
    if p.is_absolute():
        return p
    return (PROJECT_ROOT / p).resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", AI_TUTOR_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=(),
    )

    host: str = "0.0.0.0"
    port: int = 8080

    funasr_ws_url: str = "ws://127.0.0.1:10095"
    funasr_device: str = "cpu"
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

    # Auto-start local model services (FunASR/CosyVoice) with the main backend.
    auto_start_model_services: bool = True
    model_service_python_bin: str = ""
    model_service_startup_timeout_seconds: float = 120.0

    # AI Tutor extended paths
    ai_tutor_db_path: Path = Field(default=Path("data/ai_tutor.db"))
    lingualearn_data_dir: Path = Field(default=Path("data/output"))
    lingualearn_db_path: Path = Field(default=Path("data/lingualearn.db"))

    @model_validator(mode="after")
    def _normalize_paths(self) -> Settings:
        self.profile_db_path = _project_path(self.profile_db_path)
        self.lesson_plan_dir = _project_path(self.lesson_plan_dir)
        self.filler_dir = _project_path(self.filler_dir)
        self.ai_tutor_db_path = _project_path(self.ai_tutor_db_path)
        self.lingualearn_data_dir = _project_path(self.lingualearn_data_dir)
        self.lingualearn_db_path = _project_path(self.lingualearn_db_path)
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
