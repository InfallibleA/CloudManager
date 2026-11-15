from uuid import UUID

from app.core.dependencies import Paginator
from app.core.exceptions import ValidationException
from app.core.schemes import PaginatedSchema
from app.files.service.files import FilesService
from app.folders.repository.folders import FoldersRepository
from app.folders.schema.folders import (
    FolderCreateSchema,
    FolderFilterSchema,
    FolderResponseSchema,
    FolderUpdateSchema,
)


class FoldersService:
    """Папки пользователя: вложенность, файлы внутри и каскадное удаление ветки."""

    def __init__(
        self, *, folders_repository: FoldersRepository, files_service: FilesService
    ):
        self._folders_repository = folders_repository
        self._files_service = files_service

    async def create(self, *, data: FolderCreateSchema) -> FolderResponseSchema:
        # Без parent_id папка создаётся внутри корневой — от неё строится дерево
        parent_id = data.parent_id or await self._root_id()
        await self._validate_parent(parent_id=parent_id)
        await self._validate_files(file_ids=data.file_ids)
        return await self._folders_repository.create_one(
            data=data.model_copy(update={'parent_id': parent_id})
        )

    async def get_one(self, *, pk: UUID) -> FolderResponseSchema:
        return await self._folders_repository.get_one(pk=pk)

    async def get_list(
        self, *, filters: FolderFilterSchema, paginator: Paginator
    ) -> PaginatedSchema[FolderResponseSchema]:
        return await self._folders_repository.get_list(filters=filters, paginator=paginator)

    async def update(self, *, pk: UUID, data: FolderUpdateSchema) -> FolderResponseSchema:
        folder = await self._folders_repository.get_one(pk=pk)
        # `parent_id: null` — возврат в корневую папку владельца; отсутствие поля — не меняем
        if 'parent_id' in data.model_fields_set:
            if folder.is_root:
                raise ValidationException(detail='Корневую папку нельзя переместить.')
            owner_id = await self._folders_repository.get_creator_id(pk=pk)
            root_id = await self._root_id(owner_id=owner_id)
            parent_id = data.parent_id or root_id
            await self._validate_move(pk=pk, parent_id=parent_id, owner_id=owner_id)
            data = data.model_copy(update={'parent_id': parent_id})
        if data.file_ids is not None:
            await self._validate_files(file_ids=data.file_ids)
        return await self._folders_repository.update_one(pk=pk, data=data)

    async def delete(self, *, pk: UUID) -> None:
        """Удаляет папку со всеми подпапками и файлами внутри.

        Сначала мягко удаляются сами файлы (и их объекты уходят из S3-хранилища),
        затем — папки ветки: файлы не остаются «висячими» в удалённой папке.
        Корневую папку удалить нельзя — иначе у пользователя не останется места,
        куда класть папки и файлы. Админ может удалить чужую папку, но не корневую.
        """
        folder = await self._folders_repository.get_one(pk=pk)
        if folder.is_root:
            raise ValidationException(detail='Корневую папку удалить нельзя.')
        folder_ids = await self._folders_repository.get_subtree_ids(pk=pk)
        file_ids = await self._folders_repository.get_file_ids(folder_ids=folder_ids)
        await self._files_service.delete_many(pks=file_ids)
        await self._folders_repository.delete_subtree(folder_ids=folder_ids)

    async def _root_id(self, *, owner_id: UUID | None = None) -> UUID | None:
        """id корневой папки: `None` — у аккаунта её нет.

        `owner_id` передаёт админ, когда работает с чужим деревом.
        """
        root = await self._folders_repository.get_root(owner_id=owner_id)
        return root.id if root else None

    async def _validate_parent(self, *, parent_id: UUID | None) -> None:
        """Проверяет, что родительская папка существует и принадлежит пользователю."""
        if parent_id is None:
            return
        if not await self._folders_repository.has_one(parent_id):
            raise ValidationException(detail=f'Папка не найдена: {parent_id}.')

    async def _validate_move(
        self, *, pk: UUID, parent_id: UUID | None, owner_id: UUID
    ) -> None:
        """Не даёт переместить папку в саму себя, внутрь подпапки или в чужое дерево."""
        if parent_id is None:
            return
        if parent_id == pk:
            raise ValidationException(detail='Папка не может быть родителем самой себя.')

        subtree_ids = await self._folders_repository.get_subtree_ids(pk=pk)
        if parent_id in subtree_ids:
            raise ValidationException(detail='Нельзя переместить папку внутрь её подпапки.')
        if not await self._folders_repository.has_folder(pk=parent_id, owner_id=owner_id):
            raise ValidationException(detail=f'Папка не найдена: {parent_id}.')

    async def _validate_files(self, *, file_ids: list[UUID]) -> None:
        """Проверяет, что все указанные файлы есть в базе и не удалены."""
        if not file_ids:
            return

        found = await self._files_service.get_many(pks=file_ids)
        missing = set(file_ids) - {file.id for file in found}
        if missing:
            missing_ids = ', '.join(str(file_id) for file_id in sorted(missing))
            raise ValidationException(detail=f'Файлы не найдены: {missing_ids}.')
