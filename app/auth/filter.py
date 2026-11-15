from typing import Annotated

from fastapi import Query

from app.core.enums import EUserRole
from app.users.schema.users import UserFilterSchema


def get_user_filters(
    login: Annotated[str | None, Query(max_length=255, description='Поиск по логину')] = None,
    role: Annotated[EUserRole | None, Query(description='Роль пользователя')] = None,
) -> UserFilterSchema:
    """Собирает фильтры списка пользователей из query-параметров запроса."""
    return UserFilterSchema(login=login, role=role)
