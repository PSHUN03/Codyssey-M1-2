"""Firestore 클라이언트 초기화 (서비스 계정 키는 환경 변수로만 받는다)."""

import json
import logging
from functools import lru_cache
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, firestore

from .config import settings

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent
DATA_COLLECTION = "data"
CONVERSATIONS_COLLECTION = "conversations"


class FirebaseNotConfigured(RuntimeError):
    pass


@lru_cache
def get_db():
    if not firebase_admin._apps:
        if settings.firebase_service_account_json:
            try:
                info = json.loads(settings.firebase_service_account_json)
            except json.JSONDecodeError as e:
                raise FirebaseNotConfigured("FIREBASE_SERVICE_ACCOUNT_JSON 이 올바른 JSON 이 아닙니다.") from e
            cred = credentials.Certificate(info)
        elif settings.firebase_credentials_path:
            path = Path(settings.firebase_credentials_path)
            if not path.is_absolute():  # 상대 경로는 backend 폴더 기준
                path = BACKEND_DIR / path
            if not path.exists():
                raise FirebaseNotConfigured(f"Firebase 키 파일이 없습니다: {path}")
            cred = credentials.Certificate(str(path))
        else:
            raise FirebaseNotConfigured(
                "Firebase 서비스 계정 키가 없습니다. FIREBASE_SERVICE_ACCOUNT_JSON 또는 "
                "FIREBASE_CREDENTIALS_PATH 환경 변수를 설정하세요."
            )
        firebase_admin.initialize_app(cred)
        logger.info("Firebase 초기화 완료")
    return firestore.client()
