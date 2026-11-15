from dishka import Provider, Scope, provide
from fastapi import Request

from app.auth.dependencies import extract_bearer_token
from app.auth.service.auth import AuthService
from app.users.schema.users import AdminUserSchema, UserResponseSchema


class AuthProvider(Provider):
    """Провайдер текущего пользователя: ``FromDishka[UserResponseSchema]``."""

    scope = Scope.REQUEST

    @provide
    async def get_current_user(
        self, request: Request, auth_service: AuthService
    ) -> UserResponseSchema:
        user = await auth_service.authenticate(token=extract_bearer_token(request))
        # доступно зависимостям запроса через Context
        request.state.user = user
        return user

    @provide
    def get_admin_user(self, user: UserResponseSchema) -> AdminUserSchema:
        """Текущий пользователь с ролью администратора: ``FromDishka[AdminUserSchema]``."""
        return AdminUserSchema.from_user(user)
