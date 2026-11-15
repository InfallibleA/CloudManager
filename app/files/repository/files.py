from uuid import UUID

from sqlalchemy import delete, select, update

from app.core.context import Context
from app.core.dependencies import Paginator
from app.core.engines.database import Transaction
from app.core.exceptions import ObjectNotFoundException
from app.core.repositories.soft_base_repository import SoftBaseRepository
from app.core.schemes import PaginatedSchema
from app.core.utils.pget import pget
from app.files.model.file import File
from app.files.schema.files import (
    FileCreateSchema,
    FileFilterSchema,
    FileResponseSchema,
    FileUpdateSchema,
)
from app.folders.model.folder_file import folder_files
from app.news.model.news import News
from app.users.model.user import User


class FilesRepository(SoftBaseRepository):
    def __init__(self, transaction: Transaction, context: Context):
        super().__init__(model_class=File, transaction=transaction, context=context)

    def _creator_columns(self) -> tuple:
        """Колонки файла + логин владельца: один запрос вместо N+1."""
        return (*self._model_class.__table__.c, User.login.label('creator_login'))

    def _with_creator(self, query):
        """Джойнит владельца файла; логин нужен клиенту для колонки «Пользователь»."""
        return query.join(User, User.id == self._model_class.creator_id, isouter=True)

    async def create_one(self, *, data: FileCreateSchema) -> FileResponseSchema:
        """Сохраняет запись о файле, уже загруженном в хранилище."""
        file = await self._create_one(data, FileResponseSchema)
        return file.model_copy(update={'creator_login': pget(self.context, 'user.login')})

    async def get_one(self, *, pk: UUID) -> FileResponseSchema:
        files = await self._get_list(
            self._model_class.id == pk,
            schema=FileResponseSchema,
            columns=self._creator_columns(),
            asdict=True,
            transform_query=self._with_creator,
        )
        if not files:
            raise ObjectNotFoundException(object_id=pk, object_class=self._model_class)
        return files[0]

    async def get_many(self, *, pks: list[UUID]) -> list[FileResponseSchema]:
        """Возвращает неудалённые файлы по списку id."""
        if not pks:
            return []

        return await self._get_list(
            self._model_class.id.in_(pks),
            schema=FileResponseSchema,
            columns=self._creator_columns(),
            asdict=True,
            transform_query=self._with_creator,
        )

    async def get_list(
        self, *, filters: FileFilterSchema, paginator: Paginator
    ) -> PaginatedSchema[FileResponseSchema]:
        """Постраничный список неудалённых файлов с фильтрами по имени, типу и владельцу."""
        db_model = self._model_class
        conditions = []
        if filters.name:
            conditions.append(db_model.name.ilike(f'%{filters.name}%'))
        if filters.types:
            conditions.append(db_model.type.in_(filters.types))
        if filters.creator_id is not None:
            conditions.append(db_model.creator_id == filters.creator_id)

        return await self._get_list(
            *conditions,
            schema=FileResponseSchema,
            columns=self._creator_columns(),
            asdict=True,
            paginator=paginator,
            transform_query=lambda query: self._with_creator(query).order_by(
                db_model.created_at.desc()
            ),
        )

    async def get_creator_id(self, *, pk: UUID) -> UUID:
        """id создателя файла: по нему проверяется право на удаление.

        Неудалённого файла нет — 404, как и при удалении.
        """
        db_model = self._model_class
        query = select(db_model.creator_id).where(db_model.id == pk, db_model.deleted_id.is_(None))
        creator_id = (await self.transaction.execute(query)).scalar_one_or_none()
        if creator_id is None:
            raise ObjectNotFoundException(object_id=pk, object_class=db_model)
        return creator_id

    async def update_one(self, *, pk: UUID, data: FileUpdateSchema) -> FileResponseSchema:
        """Меняет имя файла; пустой патч просто возвращает текущую запись.

        Ключ объекта, тип и размер не меняются: файл в хранилище остаётся тем же.
        """
        if data.name is None:
            return await self.get_one(pk=pk)
        await self._update_one(pk, data)
        return await self.get_one(pk=pk)

    async def delete_one(self, *, pk: UUID) -> FileResponseSchema:
        """Мягко удаляет файл и возвращает его данные для удаления объекта из хранилища."""
        files = await self.delete_many(pks=[pk])
        return files[0]

    async def delete_many(self, *, pks: list[UUID]) -> list[FileResponseSchema]:
        """Мягко удаляет файлы, убирает их связи с папками и возвращает записи.

        Удалённый файл нельзя удалить из таблицы связей каскадом БД, поэтому связи
        с папками убираются явно — иначе в `folder_files` останутся «висячие» записи.
        Возвращённые записи нужны сервису, чтобы почистить объекты в S3-хранилище.
        """
        if not pks:
            return []

        files = await self.get_many(pks=pks)
        found_ids = {file.id for file in files}
        for pk in pks:
            if pk not in found_ids:
                raise ObjectNotFoundException(object_id=pk, object_class=self._model_class)

        async with self.transaction.atomic():
            await self._unlink_folders(pks=list(found_ids))
            await self._detach_media(pks=list(found_ids))
            await self._delete_many(list(found_ids))

        return files

    async def _unlink_folders(self, *, pks: list[UUID]) -> None:
        """Убирает файлы из папок (таблица folder_files)."""
        await self.transaction.execute(
            delete(folder_files).where(folder_files.c.file_id.in_(pks))
        )

    async def _detach_media(self, *, pks: list[UUID]) -> None:
        """Обнуляет media_id новостей, у которых главным изображением был удаляемый файл.

        Ссылка на удалённый файл осталась бы «висячей»: запись отдавала бы media_id,
        который уже нельзя ни скачать, ни показать.
        """
        await self.transaction.execute(
            update(News).where(News.media_id.in_(pks)).values(media_id=None)
        )
