"""환경 변수 로딩. 키/비밀 값은 코드에 두지 않고 .env(로컬) 또는 Render 환경 변수로만 주입한다."""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _split(value: str) -> list[str]:
    return [v.strip().rstrip("/") for v in value.split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    # 과금 방지: 답변 1회 최대 토큰, 도구 호출 반복 횟수, 대화 히스토리 길이 제한
    openai_max_tokens: int = int(os.getenv("OPENAI_MAX_TOKENS", "900"))
    max_tool_rounds: int = int(os.getenv("MAX_TOOL_ROUNDS", "3"))
    history_limit: int = int(os.getenv("CHAT_HISTORY_LIMIT", "10"))

    # firestore(기본) | memory(Firebase 키 없이 로컬에서 기능만 확인할 때, 재시작하면 사라짐)
    storage_backend: str = os.getenv("STORAGE_BACKEND", "firestore").lower()
    # 둘 중 하나: JSON 문자열(배포용) 또는 키 파일 경로(로컬용)
    firebase_service_account_json: str = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "")
    firebase_credentials_path: str = os.getenv("FIREBASE_CREDENTIALS_PATH", "")

    allowed_origins: list[str] = field(
        default_factory=lambda: _split(
            os.getenv("ALLOWED_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500,http://localhost:3000")
        )
    )


settings = Settings()
