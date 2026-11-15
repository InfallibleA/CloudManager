from collections import defaultdict
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import delete, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.context import Context
from app.core.dependencies import Paginator
from app.core.engines.database import Transaction
from app.core.enums import EUser, EUserRole
from app.core.exceptions import ObjectNotFoundException
from app.core.repositories.soft_base_repository import SoftBaseRepository
from app.core.schemes import PaginatedSchema
from app.core.utils.pget import pget
from app.files.model.file import File
from app.files.schema.files import FileShortSchema
from app.folders.model.folder import Folder
from app.folders.model.folder_file import folder_files
from app.folders.model.folder_video import folder_videos
from app.folders.schema.folders import (
    FolderCreateInternalSchema,
    FolderCreateSchema,
    FolderFilterSchema,
    FolderResponseSchema,
    FolderShortSchema,
    FolderUpdateSchema,
)
from app.videos.model.video import Video
from app.videos.schema.videos import VideoShortSchema


class FoldersRepository(SoftBaseRepository):
    """Папки пользователя: вложенность, файлы внутри и каскадное удаление ветки.

    Папки личные, поэтому владелец (creator_id) вшит в каждую выборку:
    чужую папку репозиторий просто не находит.
    """

    def __init__(self, transaction: Transaction, context: Context):
        super().__init__(model_class=Folder, transaction=transaction, context=context)
        # Область видимости на время выдачи: админ может смотреть папки другого
        # пользователя (creator_id), остальным всегда отдаются только свои.
        self._list_owner: UUID | None = None
        # Админ работает с конкретной папкой без фильтра по владельцу.
        self._all_owners = False

    def _filter_query(self, query, use_deleted: bool = False):
        """Дополняет выборки фильтром по владельцу: только папки текущего пользователя."""
        query = super()._filter_query(query, use_deleted=use_deleted)
        if self._all_owners:
            return query
        return query.where(self._model_class.creator_id == self._owner_id)

    @property
    def _owner_id(self) -> UUID:
        """Владелец папок: область выдачи админа или текущий пользователь запроса."""
        if self._list_owner is not None:
            return self._list_owner
        return pget(self.context, 'user.id') or EUser.ROOT_USER.value

    @property
    def _is_admin(self) -> bool:
        """Роль текущего пользователя: только админу доступен фильтр по creator_id."""
        return pget(self.context, 'user.role') is EUserRole.ADMIN

    @contextmanager
    def _full_access(self):
        """Админ видит и меняет любую папку: фильтр по владельцу отключается."""
        if not self._is_admin:
            yield
            return

        previous = self._all_owners
        self._all_owners = True
        try:
            yield
        finally:
            self._all_owners = previous

    async def create_one(self, *, data: FolderCreateSchema) -> FolderResponseSchema:
        """Создаёт папку от лица текущего пользователя и кладёт в неё файлы и видео."""
        internal = FolderCreateInternalSchema(name=data.name, parent_id=data.parent_id)

        async with self.transaction.atomic():
            folder = await self._create_one(internal, FolderResponseSchema)
            await self._add_files(folder_id=folder.id, file_ids=data.file_ids)
            await self._add_videos(folder_id=folder.id, video_ids=data.video_ids)

        return await self.get_one(pk=folder.id)

    async def create_root(self, *, owner_id: UUID, name: str) -> FolderResponseSchema:
        """Создаёт корневую папку пользователя — вызывается при регистрации.

        Владелец передаётся явно: у запроса регистрации нет текущего пользователя,
        поэтому `creator_id` из контекста здесь не годится (был бы `ROOT_USER`).
        """
        internal = FolderCreateInternalSchema(name=name, is_root=True)
        return await self._create_one(internal, FolderResponseSchema, creator_id=owner_id)

    async def get_root(self, *, owner_id: UUID | None = None) -> FolderResponseSchema | None:
        """Корневая папка пользователя: `None` — у аккаунта её ещё нет.

        `owner_id` передаёт админ, когда работает с папками другого пользователя.
        """
        db_model = self._model_class
        previous = self._list_owner
        if owner_id is not None and self._is_admin:
            self._list_owner = owner_id
        try:
            query = self._filter_query(select(db_model).where(db_model.is_root.is_(True)))
            folders = await self.transaction.scalars(query)
        finally:
            self._list_owner = previous
        if not folders:
            return None
        return FolderResponseSchema.model_validate(folders[0], from_attributes=True)

    async def get_creator_id(self, *, pk: UUID) -> UUID:
        """id владельца папки: по нему админ работает с чужим деревом.

        Неудалённой папки нет — 404, как и при обычной выдаче.
        """
        db_model = self._model_class
        query = select(db_model.creator_id).where(
            db_model.id == pk, db_model.deleted_id.is_(None)
        )
        creator_id = (await self.transaction.execute(query)).scalar_one_or_none()
        if creator_id is None:
            raise ObjectNotFoundException(object_id=pk, object_class=db_model)
        return creator_id

    async def has_folder(self, *, pk: UUID, owner_id: UUID) -> bool:
        """Проверяет, что папка существует, не удалена и принадлежит owner_id."""
        db_model = self._model_class
        query = select(db_model.id).where(
            db_model.id == pk,
            db_model.creator_id == owner_id,
            db_model.deleted_id.is_(None),
        )
        return bool(await self.transaction.scalars(query))

    async def get_one(self, *, pk: UUID) -> FolderResponseSchema:
        """Отдаёт папку вместе с её файлами, видео и подпапками."""
        with self._full_access():
            folder = await self._get_one(pk, FolderResponseSchema, scalars=True)
            files = await self._load_files(folder_ids=[pk])
            videos = await self._load_videos(folder_ids=[pk])
            children = await self._get_children(pk=pk)
        return folder.model_copy(
            update={
                'files': files.get(pk, []),
                'videos': videos.get(pk, []),
                'children': children,
            }
        )

    async def get_list(
        self, *, filters: FolderFilterSchema, paginator: Paginator
    ) -> PaginatedSchema[FolderResponseSchema]:
        """Постраничный список папок с фильтрами по имени, родителю и владельцу.

        `creator_id` меняет область выдачи только у админа: остальным всегда
        отдаются их собственные папки (чужой id даёт пустую страницу).
        """
        db_model = self._model_class
        conditions = []
        if filters.name:
            conditions.append(db_model.name.ilike(f'%{filters.name}%'))
        if filters.parent_id is not None:
            conditions.append(db_model.parent_id == filters.parent_id)
        elif filters.root_only:
            conditions.append(db_model.parent_id.is_(None))

        if filters.creator_id is not None:
            if self._is_admin:
                # область выборки — папки указанного пользователя
                self._list_owner = filters.creator_id
            else:
                # для не-админа фильтр только сужает его собственные папки
                conditions.append(db_model.creator_id == filters.creator_id)

        try:
            page = await self._get_list(
                *conditions,
                schema=FolderResponseSchema,
                scalars=True,
                paginator=paginator,
                transform_query=lambda query: query.order_by(db_model.name, db_model.created_at),
            )
        finally:
            self._list_owner = None

        folders = page.data or []
        files = await self._load_files(folder_ids=[folder.id for folder in folders])
        videos = await self._load_videos(folder_ids=[folder.id for folder in folders])
        return page.model_copy(
            update={
                'data': [
                    folder.model_copy(
                        update={
                            'files': files.get(folder.id, []),
                            'videos': videos.get(folder.id, []),
                        }
                    )
                    for folder in folders
                ]
            }
        )

    async def update_one(self, *, pk: UUID, data: FolderUpdateSchema) -> FolderResponseSchema:
        """Обновляет имя, родителя и полный набор файлов и видео папки."""
        with self._full_access():
            await self.has_one(pk, raise_error=True)
            values = data.model_dump(exclude={'file_ids', 'video_ids'}, exclude_unset=True)

            async with self.transaction.atomic():
                if values:
                    await self._update_one(pk, values, FolderResponseSchema)
                if data.file_ids is not None:
                    await self._replace_files(folder_id=pk, file_ids=data.file_ids)
                if data.video_ids is not None:
                    await self._replace_videos(folder_id=pk, video_ids=data.video_ids)

            return await self.get_one(pk=pk)

    async def delete_one(self, *, pk: UUID) -> None:
        """Мягко удаляет папку вместе со всеми подпапками и их связями с файлами."""
        with self._full_access():
            await self.delete_subtree(folder_ids=await self.get_subtree_ids(pk=pk))

    async def get_subtree_ids(self, *, pk: UUID) -> list[UUID]:
        """id папки и всех её вложенных папок; 404, если папки нет или она чужая."""
        with self._full_access():
            await self.has_one(pk, raise_error=True)

            db_model = self._model_class
            # Рекурсивный обход вниз по parent_id: любой глубины вложенности
            subtree = (
                select(db_model.id.label('folder_id'))
                .where(db_model.id == pk)
                .cte('folder_subtree', recursive=True)
            )
            subtree = subtree.union_all(
                select(db_model.id).where(
                    db_model.parent_id == subtree.c.folder_id, db_model.deleted_id.is_(None)
                )
            )
            return list(await self.transaction.scalars(select(subtree.c.folder_id)))

    async def get_file_ids(self, *, folder_ids: list[UUID]) -> list[UUID]:
        """id неудалённых файлов, лежащих в перечисленных папках."""
        if not folder_ids:
            return []

        query = (
            select(folder_files.c.file_id)
            .join(File, File.id == folder_files.c.file_id)
            .where(folder_files.c.folder_id.in_(folder_ids), File.deleted_id.is_(None))
        )
        return list(await self.transaction.scalars(query))

    async def get_video_ids(self, *, folder_ids: list[UUID]) -> list[UUID]:
        """id неудалённых видео, лежащих в перечисленных папках."""
        if not folder_ids:
            return []

        query = (
            select(folder_videos.c.video_id)
            .join(Video, Video.id == folder_videos.c.video_id)
            .where(folder_videos.c.folder_id.in_(folder_ids), Video.deleted_id.is_(None))
        )
        return list(await self.transaction.scalars(query))

    async def attach_video(self, *, folder_id: UUID, video_id: UUID) -> None:
        """Кладёт видео в папку текущего пользователя (повторная привязка — no-op).

        Папка ищется с фильтром по владельцу, поэтому чужая даёт `404`.
        """
        await self.has_one(folder_id, raise_error=True)

        query = pg_insert(folder_videos).values(
            folder_id=folder_id, video_id=video_id, creator_id=self._owner_id
        )
        await self.transaction.execute(query.on_conflict_do_nothing())

    async def delete_subtree(self, *, folder_ids: list[UUID]) -> None:
        """Убирает связи папок с файлами и видео и мягко удаляет все папки ветки."""
        if not folder_ids:
            return

        async with self.transaction.atomic():
            await self._unlink_files(folder_ids=folder_ids)
            await self._unlink_videos(folder_ids=folder_ids)
            # все папки ветки помечаются одной записью SoftDel — как в других модулях
            await self._delete_many(folder_ids)

    async def _get_children(self, *, pk: UUID) -> list[FolderShortSchema]:
        """Подпапки папки — для выдачи папки целиком."""
        return await self._get_list(
            schema=FolderShortSchema,
            filter_by={'parent_id': pk},
            scalars=True,
            transform_query=lambda query: query.order_by(self._model_class.name),
        )

    async def _add_files(self, *, folder_id: UUID, file_ids: list[UUID]) -> None:
        """Привязывает файлы к папке; creator_id — кто именно это сделал."""
        values = [
            {'folder_id': folder_id, 'file_id': file_id, 'creator_id': self._owner_id}
            for file_id in dict.fromkeys(file_ids)
        ]
        if not values:
            return
        await self.transaction.execute(insert(folder_files).values(values))

    async def _unlink_files(self, *, folder_ids: list[UUID]) -> None:
        """Убирает связи папок с файлами (таблица folder_files)."""
        await self.transaction.execute(
            delete(folder_files).where(folder_files.c.folder_id.in_(folder_ids))
        )

    async def _replace_files(self, *, folder_id: UUID, file_ids: list[UUID]) -> None:
        await self._unlink_files(folder_ids=[folder_id])
        await self._add_files(folder_id=folder_id, file_ids=file_ids)

    async def _add_videos(self, *, folder_id: UUID, video_ids: list[UUID]) -> None:
        """Привязывает видео к папке; creator_id — кто именно это сделал."""
        values = [
            {'folder_id': folder_id, 'video_id': video_id, 'creator_id': self._owner_id}
            for video_id in dict.fromkeys(video_ids)
        ]
        if not values:
            return
        await self.transaction.execute(insert(folder_videos).values(values))

    async def _unlink_videos(self, *, folder_ids: list[UUID]) -> None:
        """Убирает связи папок с видео (таблица folder_videos)."""
        await self.transaction.execute(
            delete(folder_videos).where(folder_videos.c.folder_id.in_(folder_ids))
        )

    async def _replace_videos(self, *, folder_id: UUID, video_ids: list[UUID]) -> None:
        await self._unlink_videos(folder_ids=[folder_id])
        await self._add_videos(folder_id=folder_id, video_ids=video_ids)

    async def _load_videos(self, *, folder_ids: list[UUID]) -> dict[UUID, list[VideoShortSchema]]:
        """Загружает видео папок одним запросом; удалённые видео не отдаются."""
        videos: dict[UUID, list[VideoShortSchema]] = defaultdict(list)
        if not folder_ids:
            return videos

        query = (
            select(folder_videos.c.folder_id, Video)
            .join(Video, Video.id == folder_videos.c.video_id)
            .where(folder_videos.c.folder_id.in_(folder_ids), Video.deleted_id.is_(None))
            .order_by(folder_videos.c.folder_id, Video.name)
        )
        result = await self.transaction.execute(query)
        for folder_id, video in result.all():
            videos[folder_id].append(VideoShortSchema.model_validate(video, from_attributes=True))
        return videos

    async def _load_files(self, *, folder_ids: list[UUID]) -> dict[UUID, list[FileShortSchema]]:
        """Загружает файлы папок одним запросом; удалённые файлы не отдаются."""
        files: dict[UUID, list[FileShortSchema]] = defaultdict(list)
        if not folder_ids:
            return files

        query = (
            select(folder_files.c.folder_id, File)
            .join(File, File.id == folder_files.c.file_id)
            .where(folder_files.c.folder_id.in_(folder_ids), File.deleted_id.is_(None))
            .order_by(folder_files.c.folder_id, File.name)
        )
        result = await self.transaction.execute(query)
        for folder_id, file in result.all():
            files[folder_id].append(FileShortSchema.model_validate(file, from_attributes=True))
        return files
