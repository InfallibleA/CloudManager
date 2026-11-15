from typing import Annotated
from uuid import UUID

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, status

from app.auth.dependencies import bearer_scheme
from app.auth.filter import get_user_filters
from app.auth.schema.auth import LoginSchema, TokenResponseSchema
from app.auth.service.auth import AuthService
from app.core.dependencies import PaginatorDep
from app.core.schemes import PaginatedSchema
from app.users.schema.users import (
    AdminUserSchema,
    UserCreateSchema,
    UserFilterSchema,
    UserResponseSchema,
)
from app.users.service.users import UsersService

router = APIRouter(prefix='/auth', tags=['auth'])


@router.post(
    '/register',
    status_code=status.HTTP_201_CREATED,
    summary='Регистрация пользователя (без авторизации)',
)
@inject
async def register(
    data: UserCreateSchema, auth_service: FromDishka[AuthService]
) -> UserResponseSchema:
    return await auth_service.register(data=data)


@router.post('/login', summary='Получение JWT по логину и паролю')
@inject
async def login(
    data: LoginSchema, auth_service: FromDishka[AuthService]
) -> TokenResponseSchema:
    return await auth_service.login(data=data)


@router.get('/me', summary='Текущий пользователь', dependencies=[Depends(bearer_scheme)])
@inject
async def me(user: FromDishka[UserResponseSchema]) -> UserResponseSchema:
    return user


@router.get(
    '/users',
    summary='Список пользователей: пагинация, фильтры по логину и роли (только админ)',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def get_users_list(
    users_service: FromDishka[UsersService],
    admin: FromDishka[AdminUserSchema],
    filters: Annotated[UserFilterSchema, Depends(get_user_filters)],
    paginator: PaginatorDep,
) -> PaginatedSchema[UserResponseSchema]:
    return await users_service.get_list(filters=filters, paginator=paginator)


@router.post(
    '/users/{user_id}/block',
    summary='Блокировка пользователя (только админ)',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def block_user(
    user_id: UUID,
    users_service: FromDishka[UsersService],
    admin: FromDishka[AdminUserSchema],
) -> UserResponseSchema:
    """Заблокированный пользователь не может войти и пользоваться API."""
    return await users_service.block(pk=user_id)


@router.post(
    '/users/{user_id}/unblock',
    summary='Разблокировка пользователя (только админ)',
    dependencies=[Depends(bearer_scheme)],
)
@inject
async def unblock_user(
    user_id: UUID,
    users_service: FromDishka[UsersService],
    admin: FromDishka[AdminUserSchema],
) -> UserResponseSchema:
    return await users_service.unblock(pk=user_id)
