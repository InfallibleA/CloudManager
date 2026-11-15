from uuid import UUID

from app.core.schemes import BaseSchema


class EnumDBMixinSchema(BaseSchema):
    id: UUID
    name: str
    code: str
