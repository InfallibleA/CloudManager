from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.exceptions import BaseOrderException

UNAUTHORIZED_CODE = 401


async def order_exception_handler(request: Request, err: BaseOrderException):
    headers = {'WWW-Authenticate': 'Bearer'} if err.code == UNAUTHORIZED_CODE else None
    return JSONResponse(
        status_code=err.code,
        content={'error': err.__class__.__name__, 'detail': err.detail},
        headers=headers,
    )
