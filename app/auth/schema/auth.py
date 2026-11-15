from app.core.schemes.base import CloudManagerBaseModel


class LoginSchema(CloudManagerBaseModel):
    """Учётные данные для входа."""

    login: str
    password: str


class TokenResponseSchema(CloudManagerBaseModel):
    """Выданный access-токен."""

    access_token: str
    token_type: str = 'Bearer'
    expires_in: int
