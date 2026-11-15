from uuid import UUID

from app.core.models.base import Base


class BaseOrderException(Exception):
    default_code = 400
    default_detail = 'Неизвестная ошибка'

    def __init__(self, *, detail=None, code: int = None):
        super().__init__()
        self.code = code or self.default_code
        self.detail = detail or self.default_detail


class UniqueConstraintException(BaseOrderException):
    default_detail = 'Нарушение условий уникальности объекта.'

    def __init__(self, *, fields: list = None, detail=None, code: int = None):
        detail = (
            detail if detail or not fields else f'Поле {", ".join(fields)} должны быть уникальны.'
        )
        super().__init__(detail=detail, code=code)
        self.fields = fields


class ObjectNotFoundException(BaseOrderException):
    default_code = 404
    default_detail = 'Объект не существует.'

    def __init__(
        self,
        *,
        object_id: UUID | str = None,
        detail=None,
        code: int = None,
        object_class: type[Base] = None,
    ):
        object_data = f' {object_class.__name__}' if object_class else ''
        detail = (
            detail
            if detail or not object_id
            else f'Объект{object_data} с id {object_id} не существует.'
        )

        super().__init__(detail=detail, code=code)
        self.object_id = object_id
        self.object_class = object_class


class ValidationException(BaseOrderException):
    default_code = 400
    default_detail = {'_all_': ['Ошибка валидации']}

    def __init__(self, *, detail=None, code: int = None, object_class: type[Base] = None):
        object_data = f' {object_class.__name__}' if object_class else ''
        detail = detail if detail else f'Объект{object_data} не прошёл валидацию.'

        super().__init__(detail=detail, code=code)
        self.object_class = object_class


class ForbiddenException(BaseOrderException):
    default_code = 403
    default_detail = 'Доступ запрещён'

    def __init__(
        self,
        *,
        object_id: UUID | str = None,
        detail=None,
        code: int = None,
        object_class: type[Base] = None,
    ):
        object_data = f' {object_class.__name__}' if object_class else ''
        detail = detail if detail else f'Доступ к объекту{object_data} с id {object_id} запрещён.'

        super().__init__(detail=detail, code=code)
        self.object_class = object_class


class InternalServerException(BaseOrderException):
    default_code = 500
    default_detail = 'Внутренняя ошибка сервера'

    def __init__(
        self,
        *,
        object_id: UUID | str = None,
        detail=None,
        code: int = None,
        object_class: type[Base] = None,
    ):
        object_data = f' {object_class.__name__}' if object_class else ''
        detail = detail if detail else f'Неизвестная ошибка в объекте{object_data}'

        super().__init__(detail=detail, code=code)
        self.object_class = object_class


class UnauthorizedException(BaseOrderException):
    default_code = 401
    default_detail = 'Требуется авторизация.'
