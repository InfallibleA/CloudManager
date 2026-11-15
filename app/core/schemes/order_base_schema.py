import inspect
from collections import defaultdict
from typing import Callable
from uuid import UUID

from pydantic import BaseModel

from app.core.exceptions import BaseOrderException, ValidationException


def async_model_validator(func: Callable):
    setattr(func, 'async_model_validator', True)
    return func


def async_field_validator(field_name: str):
    def _outer_wrapper(func: Callable):
        async def _inner_wrapper(self, *args, **kwargs):
            value = getattr(self, field_name)
            new_value = await func(self=self, value=value, *args, **kwargs)
            setattr(self, field_name, new_value)

        setattr(_inner_wrapper, 'async_field_validator', True)
        setattr(_inner_wrapper, 'field_name', field_name)
        return _inner_wrapper

    return _outer_wrapper


class BaseSchema(BaseModel):
    @staticmethod
    def _is_validated():
        return False

    @staticmethod
    async def _async_validate(session, validator_methods: list, object_id: UUID | None = None):
        exceptions_data = defaultdict(list)
        for method in validator_methods:
            try:
                await method(session=session, object_id=object_id)
            except BaseOrderException as e:
                if hasattr(method, 'field_name'):
                    exceptions_data[method.field_name].append(f'{e.detail}')
                else:
                    exceptions_data['__all__'].append(f'{e.detail}')
        return exceptions_data

    async def async_validate(self, session, object_id: UUID | None = None):
        if self._is_validated():
            return

        field_validator_methods = [
            m[1] for m in inspect.getmembers(self) if hasattr(m[1], 'async_field_validator')
        ]
        model_validator_methods = [
            m[1] for m in inspect.getmembers(self) if hasattr(m[1], 'async_model_validator')
        ]

        exceptions_data = await self._async_validate(
            session=session, validator_methods=field_validator_methods, object_id=object_id
        )

        if exceptions_data:
            raise ValidationException(detail=exceptions_data)

        exceptions_data = await self._async_validate(
            session=session, validator_methods=model_validator_methods, object_id=object_id
        )

        if exceptions_data:
            raise ValidationException(detail=exceptions_data)

        setattr(self, '_is_validated', lambda: True)
