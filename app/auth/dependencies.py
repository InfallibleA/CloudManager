from fastapi import Request
from fastapi.security import HTTPBearer

from app.core.exceptions import UnauthorizedException

BEARER_PREFIX = 'bearer '

# auto_error=False: ответ формирует провайдер аутентификации, в едином формате ошибок
bearer_scheme = HTTPBearer(auto_error=False)


def extract_bearer_token(request: Request) -> str:
    """Достаёт access-токен из заголовка Authorization."""
    authorization = request.headers.get('Authorization', '')
    if not authorization.lower().startswith(BEARER_PREFIX):
        raise UnauthorizedException()

    token = authorization[len(BEARER_PREFIX) :].strip()
    if not token:
        raise UnauthorizedException()

    return token
