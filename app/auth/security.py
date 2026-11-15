from datetime import datetime, timedelta, timezone
from functools import lru_cache
from uuid import UUID

import bcrypt
import jwt

from app.config import Settings
from app.core.exceptions import UnauthorizedException

# Ограничение алгоритма bcrypt: всё, что длиннее, обрезается
BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    """Возвращает bcrypt-хеш пароля."""
    return bcrypt.hashpw(_as_bytes(password), bcrypt.gensalt()).decode()


def verify_password(*, password: str, password_hash: str) -> bool:
    """Проверяет пароль по bcrypt-хешу."""
    try:
        return bcrypt.checkpw(_as_bytes(password), password_hash.encode())
    except ValueError:
        return False


@lru_cache
def get_dummy_password_hash() -> str:
    """Хеш-заглушка для выравнивания времени ответа, когда логин не найден."""
    return hash_password('dummy-password')


def create_access_token(*, user_id: UUID, config: Settings) -> tuple[str, int]:
    """Создаёт JWT access-токен. Возвращает токен и время жизни в секундах."""
    expires_in = config.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
    now = datetime.now(timezone.utc)
    payload = {
        'sub': str(user_id),
        'iat': now,
        'exp': now + timedelta(seconds=expires_in),
    }
    token = jwt.encode(payload, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)
    return token, expires_in


def decode_access_token(*, token: str, config: Settings) -> dict:
    """Декодирует access-токен, бросая UnauthorizedException при любой ошибке."""
    try:
        return jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
    except jwt.InvalidTokenError as err:
        raise UnauthorizedException(detail='Некорректный или истёкший токен.') from err


def _as_bytes(password: str) -> bytes:
    return password.encode()[:BCRYPT_MAX_BYTES]
