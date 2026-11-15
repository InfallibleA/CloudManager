from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.core.dependencies import Paginator
from app.core.enums import EFileType, EVideoType
from app.core.exceptions import ObjectNotFoundException, UniqueConstraintException
from app.core.schemes import PaginatedSchema
from app.files.model.file import File
from app.files.repository.files import FilesRepository
from app.files.schema.files import (
    FileCreateSchema,
    FileFilterSchema,
    FileResponseSchema,
    FileShortSchema,
    FileUpdateSchema,
)
from app.files.storage import FileStorage
from app.folders.model.folder import Folder
from app.folders.repository.folders import FoldersRepository
from app.folders.schema.folders import (
    FolderCreateSchema,
    FolderFilterSchema,
    FolderResponseSchema,
    FolderShortSchema,
    FolderUpdateSchema,
)
from app.news.repository.news import NewsRepository
from app.news.schema.news import (
    NewsCreateSchema,
    NewsFilterSchema,
    NewsResponseSchema,
    NewsUpdateSchema,
)
from app.users.repository.users import UsersRepository
from app.users.schema.users import (
    UserCreateInternalSchema,
    UserCredentialsSchema,
    UserFilterSchema,
    UserResponseSchema,
)
from app.videos.model.video import Video
from app.videos.repository.videos import VideosRepository
from app.videos.schema.videos import (
    VideoCreateSchema,
    VideoFilterSchema,
    VideoResponseSchema,
    VideoShortSchema,
)


class FakeUsersRepository(UsersRepository):
    """Пользователи в памяти: саморегистрация и логин без обращений к БД."""

    def __init__(self) -> None:
        self.items: dict[UUID, UserResponseSchema] = {}
        self.credentials: dict[str, UserCredentialsSchema] = {}

    async def create_one(
        self, *, data: UserCreateInternalSchema, creator_id: UUID | None = None
    ) -> UserResponseSchema:
        if await self.has_login(login=data.login):
            raise UniqueConstraintException(fields=['login'])
        user = UserResponseSchema(
            id=uuid4(),
            login=data.login,
            role=data.role,
            created_at=datetime.now(timezone.utc),
        )
        self.items[user.id] = user
        self.credentials[data.login] = UserCredentialsSchema(
            id=user.id, login=data.login, password_hash=data.password_hash
        )
        return user

    async def get_one(self, *, pk: UUID) -> UserResponseSchema:
        user = self.items.get(pk)
        if user is None:
            raise ObjectNotFoundException(object_id=pk)
        return user

    async def set_blocked(self, *, pk: UUID, blocked: bool) -> UserResponseSchema:
        user = await self.get_one(pk=pk)
        user = user.model_copy(update={'is_blocked': blocked})
        self.items[pk] = user
        credentials = self.credentials.get(user.login)
        if credentials is not None:
            self.credentials[user.login] = credentials.model_copy(
                update={'is_blocked': blocked}
            )
        return user

    async def get_list(
        self, *, filters: UserFilterSchema, paginator: Paginator
    ) -> PaginatedSchema[UserResponseSchema]:
        users = sorted(self.items.values(), key=lambda user: user.login)
        if filters.login:
            search = filters.login.lower()
            users = [user for user in users if search in user.login.lower()]
        if filters.role is not None:
            users = [user for user in users if user.role is filters.role]

        offset = paginator.page_size * (paginator.page - 1)
        return PaginatedSchema(
            count=len(users),
            offset=offset,
            page=paginator.page,
            page_size=paginator.page_size,
            data=users[offset : offset + paginator.page_size],
        )

    async def get_by_login(self, *, login: str) -> UserCredentialsSchema | None:
        return self.credentials.get(login)

    async def has_login(self, *, login: str) -> bool:
        return login in self.credentials


class FakeFileStorage(FileStorage):
    """S3-хранилище в памяти: тесты не требуют поднятого сервиса и сети."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def check_bucket(self) -> None:
        return None

    async def upload(self, *, object_id: str, data: bytes, content_type: str) -> None:
        self.objects[object_id] = data

    async def upload_stream(
        self, *, object_id: str, stream, length: int, content_type: str
    ) -> None:
        self.objects[object_id] = stream.read()

    async def download(self, *, object_id: str) -> bytes:
        if object_id not in self.objects:
            raise ObjectNotFoundException(object_id=object_id)
        return self.objects[object_id]

    async def remove(self, *, object_id: str) -> None:
        self.objects.pop(object_id, None)

    def presign_get(self, *, object_id: str, expires_seconds: int) -> str:
        """Ссылка в том же виде, что строит minio: путь содержит ключ объекта."""
        return f'https://storage.test/cloudmanager-files/{object_id}?X-Amz-Expires={expires_seconds}'


class FakeFolderFileLinks:
    """Таблица связей «папка — файл» в памяти, общая для фейковых репозиториев.

    Реальный репозиторий файлов чистит связи при удалении файла, а репозиторий
    папок — при удалении папки; здесь это повторяет одна общая таблица.
    creator_id хранится рядом: по нему видно, кто положил файл в папку.
    """

    def __init__(self) -> None:
        self.links: dict[UUID, set[UUID]] = {}
        # Кто положил файл в папку: ключ — пара (папка, файл)
        self.creators: dict[tuple[UUID, UUID], UUID | None] = {}

    def link(self, *, folder_id: UUID, file_ids: set[UUID], creator_id: UUID | None) -> None:
        self.unlink_folder(folder_ids=[folder_id])
        self.links[folder_id] = set(file_ids)
        for file_id in file_ids:
            self.creators[(folder_id, file_id)] = creator_id

    def unlink_file(self, *, file_id: UUID) -> None:
        """Убирает файл из связей всех папок (как _unlink_folders)."""
        for folder_id, file_ids in self.links.items():
            file_ids.discard(file_id)
            self.creators.pop((folder_id, file_id), None)

    def unlink_folder(self, *, folder_ids: list[UUID]) -> None:
        """Убирает связи папок (как _unlink_files)."""
        for folder_id in folder_ids:
            self.links.pop(folder_id, None)
            for key in [key for key in self.creators if key[0] == folder_id]:
                del self.creators[key]


class FakeFolderVideoLinks:
    """Таблица связей «папка — видео» в памяти, общая для фейковых репозиториев.

    Реальный репозиторий видео чистит связи при удалении видео, а репозиторий
    папок — при удалении папки; здесь это повторяет одна общая таблица.
    creator_id хранится рядом: по нему видно, кто положил видео в папку.
    """

    def __init__(self) -> None:
        self.links: dict[UUID, set[UUID]] = {}
        # Кто положил видео в папку: ключ — пара (папка, видео)
        self.creators: dict[tuple[UUID, UUID], UUID | None] = {}

    def link(self, *, folder_id: UUID, video_ids: set[UUID], creator_id: UUID | None) -> None:
        self.unlink_folder(folder_ids=[folder_id])
        self.links[folder_id] = set(video_ids)
        for video_id in video_ids:
            self.creators[(folder_id, video_id)] = creator_id

    def unlink_video(self, *, video_id: UUID) -> None:
        """Убирает видео из связей всех папок (как _unlink_folders)."""
        for folder_id, video_ids in self.links.items():
            video_ids.discard(video_id)
            self.creators.pop((folder_id, video_id), None)

    def unlink_folder(self, *, folder_ids: list[UUID]) -> None:
        """Убирает связи папок (как _unlink_videos)."""
        for folder_id in folder_ids:
            self.links.pop(folder_id, None)
            for key in [key for key in self.creators if key[0] == folder_id]:
                del self.creators[key]


class FakeFilesRepository(FilesRepository):
    """Репозиторий файлов в памяти: заменяет запросы к БД в тестах."""

    def __init__(
        self,
        *,
        folder_links: FakeFolderFileLinks | None = None,
    ) -> None:
        self.items: dict[UUID, FileResponseSchema] = {}
        self.creators: dict[UUID, UUID | None] = {}
        self.folder_links = folder_links or FakeFolderFileLinks()
        # в реальном репозитории creator_id берётся из контекста запроса
        self._owner: UUID | None = None
        self._owner_login: str | None = None

    def use_owner(self, *, owner_id: UUID | None, login: str | None = None) -> None:
        """Кто считается создателем новых файлов — как creator_id из контекста."""
        self._owner = owner_id
        self._owner_login = login

    async def create_one(self, *, data: FileCreateSchema) -> FileResponseSchema:
        file = FileResponseSchema(
            id=uuid4(),
            name=data.name,
            object_key=data.object_key,
            type=data.type,
            size=data.size,
            creator_id=self._owner,
            creator_login=self._owner_login,
            created_at=datetime.now(timezone.utc),
        )
        self.items[file.id] = file
        self.creators[file.id] = self._owner
        return file

    async def get_one(self, *, pk: UUID) -> FileResponseSchema:
        file = self.items.get(pk)
        if file is None:
            raise ObjectNotFoundException(object_id=pk)
        return file

    async def get_many(self, *, pks: list[UUID]) -> list[FileResponseSchema]:
        return [self.items[pk] for pk in pks if pk in self.items]

    async def get_creator_id(self, *, pk: UUID) -> UUID:
        """id создателя файла — как creator_id в таблице files."""
        if pk not in self.items:
            raise ObjectNotFoundException(object_id=pk, object_class=File)
        return self.creators.get(pk)

    async def update_one(self, *, pk: UUID, data: FileUpdateSchema) -> FileResponseSchema:
        file = await self.get_one(pk=pk)
        if data.name is None:
            return file
        updated = file.model_copy(update={'name': data.name})
        self.items[pk] = updated
        return updated

    async def get_list(
        self, *, filters: FileFilterSchema, paginator: Paginator
    ) -> PaginatedSchema[FileResponseSchema]:
        items = [
            item.model_copy(update={'creator_id': self.creators.get(item.id)})
            for item in self.items.values()
        ]
        if filters.name:
            items = [item for item in items if filters.name.lower() in item.name.lower()]
        if filters.types:
            items = [item for item in items if item.type in filters.types]
        if filters.creator_id is not None:
            items = [
                item for item in items if self.creators.get(item.id) == filters.creator_id
            ]
        items.sort(key=lambda item: item.created_at, reverse=True)

        offset = paginator.page_size * (paginator.page - 1)
        return PaginatedSchema(
            count=len(items),
            offset=offset,
            page=paginator.page,
            page_size=paginator.page_size,
            data=items[offset : offset + paginator.page_size],
        )

    async def delete_one(self, *, pk: UUID) -> FileResponseSchema:
        files = await self.delete_many(pks=[pk])
        return files[0]

    async def delete_many(self, *, pks: list[UUID]) -> list[FileResponseSchema]:
        files = await self.get_many(pks=pks)
        found_ids = {file.id for file in files}
        for pk in pks:
            if pk not in found_ids:
                raise ObjectNotFoundException(object_id=pk, object_class=File)

        for pk in found_ids:
            del self.items[pk]
            self.creators.pop(pk, None)
            self.folder_links.unlink_file(file_id=pk)
        return files


async def seed_file(
    repository: FakeFilesRepository,
    storage: FakeFileStorage,
    *,
    name: str = 'Файл',
    file_type: EFileType = EFileType.PDF,
    data: bytes = b'file-data',
    creator_id: UUID | None = None,
) -> FileResponseSchema:
    """Кладёт файл в подменённые хранилище и БД — как будто его загрузил админ."""
    object_key = f'{uuid4().hex}.{file_type.value}'
    storage.objects[object_key] = data
    file = await repository.create_one(
        data=FileCreateSchema(name=name, object_key=object_key, type=file_type, size=len(data))
    )
    if creator_id is not None:
        repository.creators[file.id] = creator_id
        file = file.model_copy(update={'creator_id': creator_id})
        repository.items[file.id] = file
    return file


class FakeVideosRepository(VideosRepository):
    """Репозиторий видео в памяти: заменяет запросы к БД в тестах."""

    def __init__(self) -> None:
        self.items: dict[UUID, VideoResponseSchema] = {}
        self.creators: dict[UUID, UUID | None] = {}
        # таблица folder_videos в памяти: общая с фейком папок
        self.folder_links = FakeFolderVideoLinks()
        # в реальном репозитории creator_id берётся из контекста запроса
        self._owner: UUID | None = None
        # Имитация гонки: имя свободно при проверке, но занято при вставке
        self.conflict_on_create = False

    def use_owner(self, *, owner_id: UUID | None) -> None:
        """Кто считается создателем новых видео — как creator_id из контекста."""
        self._owner = owner_id

    async def create_one(self, *, data: VideoCreateSchema) -> VideoResponseSchema:
        if self.conflict_on_create:
            raise UniqueConstraintException(code=409)
        video = VideoResponseSchema(
            id=uuid4(),
            name=data.name,
            object_key=data.object_key,
            type=data.type,
            size=data.size,
            created_at=datetime.now(timezone.utc),
        )
        self.items[video.id] = video
        self.creators[video.id] = self._owner
        return video

    async def get_one(self, *, pk: UUID) -> VideoResponseSchema:
        video = self.items.get(pk)
        if video is None:
            raise ObjectNotFoundException(object_id=pk, object_class=Video)
        return video

    async def get_one_by_name(self, *, name: str) -> VideoResponseSchema:
        for video in self.items.values():
            if video.name == name:
                return video
        raise ObjectNotFoundException(detail=f'Видео с именем «{name}» не найдено.')

    async def exists_by_name(self, *, name: str) -> bool:
        return any(video.name == name for video in self.items.values())

    async def has_one(self, pk: UUID, raise_error: bool = False) -> bool:
        exists = pk in self.items
        if raise_error and not exists:
            raise ObjectNotFoundException(object_id=pk, object_class=Video)
        return exists

    async def get_list(
        self, *, filters: VideoFilterSchema, paginator: Paginator
    ) -> PaginatedSchema[VideoResponseSchema]:
        items = list(self.items.values())
        if filters.name:
            items = [item for item in items if filters.name.lower() in item.name.lower()]
        if filters.types:
            items = [item for item in items if item.type in filters.types]
        items.sort(key=lambda item: item.created_at, reverse=True)

        offset = paginator.page_size * (paginator.page - 1)
        return PaginatedSchema(
            count=len(items),
            offset=offset,
            page=paginator.page,
            page_size=paginator.page_size,
            data=items[offset : offset + paginator.page_size],
        )

    async def get_creator_id(self, *, pk: UUID) -> UUID:
        """id создателя видео — как creator_id в таблице videos."""
        if pk not in self.items:
            raise ObjectNotFoundException(object_id=pk, object_class=Video)
        return self.creators.get(pk)

    async def get_many(self, *, pks: list[UUID]) -> list[VideoResponseSchema]:
        return [self.items[pk] for pk in pks if pk in self.items]

    async def delete_one(self, *, pk: UUID) -> VideoResponseSchema:
        videos = await self.delete_many(pks=[pk])
        return videos[0]

    async def delete_many(self, *, pks: list[UUID]) -> list[VideoResponseSchema]:
        videos = await self.get_many(pks=pks)
        found_ids = {video.id for video in videos}
        for pk in pks:
            if pk not in found_ids:
                raise ObjectNotFoundException(object_id=pk, object_class=Video)

        for pk in found_ids:
            del self.items[pk]
            self.creators.pop(pk, None)
            self.folder_links.unlink_video(video_id=pk)
        return videos


async def seed_video(
    repository: FakeVideosRepository,
    storage: FakeFileStorage,
    *,
    name: str = 'Видео',
    video_type: EVideoType = EVideoType.MP4,
    data: bytes = b'video-data',
    creator_id: UUID | None = None,
) -> VideoResponseSchema:
    """Кладёт видео в подменённые хранилище и БД — как будто его загрузил админ."""
    object_key = f'videos/{uuid4().hex}.{video_type.value}'
    storage.objects[object_key] = data
    video = await repository.create_one(
        data=VideoCreateSchema(name=name, object_key=object_key, type=video_type, size=len(data))
    )
    if creator_id is not None:
        repository.creators[video.id] = creator_id
    return video


class FakeNewsRepository(NewsRepository):
    """Репозиторий новостей в памяти: заменяет запросы к БД в тестах."""

    def __init__(self, *, files_repository: FakeFilesRepository) -> None:
        self.items: dict[UUID, NewsResponseSchema] = {}
        self._files_repository = files_repository

    def _with_media(self, news: NewsResponseSchema) -> NewsResponseSchema:
        """Как _detach_media в репозитории файлов: удалённый файл не остаётся media_id."""
        if news.media_id is not None and news.media_id not in self._files_repository.items:
            return news.model_copy(update={'media_id': None})
        return news

    async def create_one(self, *, data: NewsCreateSchema) -> NewsResponseSchema:
        weight = await self.get_max_weight() + 1
        news = NewsResponseSchema(
            id=uuid4(),
            name=data.name,
            description=data.description,
            weight=weight,
            media_id=data.media_id,
        )
        self.items[news.id] = news
        return self._with_media(news)

    async def get_one(self, *, pk: UUID) -> NewsResponseSchema:
        news = self.items.get(pk)
        if news is None:
            raise ObjectNotFoundException(object_id=pk)
        return self._with_media(news)

    async def get_max_weight(self) -> int:
        return max((item.weight for item in self.items.values()), default=-1)

    async def has_one(self, pk: UUID, raise_error: bool = False) -> bool:
        exists = pk in self.items
        if raise_error and not exists:
            raise ObjectNotFoundException(object_id=pk)
        return exists

    async def get_list(
        self, *, filters: NewsFilterSchema, paginator: Paginator
    ) -> PaginatedSchema[NewsResponseSchema]:
        news_items = sorted(self.items.values(), key=lambda item: item.weight)
        if filters.name:
            news_items = [
                item for item in news_items if filters.name.lower() in item.name.lower()
            ]
        if filters.weight_from is not None:
            news_items = [item for item in news_items if item.weight >= filters.weight_from]
        if filters.weight_to is not None:
            news_items = [item for item in news_items if item.weight <= filters.weight_to]

        offset = paginator.page_size * (paginator.page - 1)
        page = news_items[offset : offset + paginator.page_size]
        return PaginatedSchema(
            count=len(news_items),
            offset=offset,
            page=paginator.page,
            page_size=paginator.page_size,
            data=[self._with_media(item) for item in page],
        )

    async def update_one(self, *, pk: UUID, data: NewsUpdateSchema) -> NewsResponseSchema:
        news = await self.get_one(pk=pk)
        values = data.model_dump(exclude={'weight'}, exclude_unset=True)
        updated = news.model_copy(update=values)

        if data.weight is not None and data.weight != news.weight:
            # как в репозитории: сначала закрываем пропуск на старом месте, потом освобождаем новое
            for news_id, item in list(self.items.items()):
                if news_id != pk and item.weight > news.weight:
                    self.items[news_id] = item.model_copy(update={'weight': item.weight - 1})
            for news_id, item in list(self.items.items()):
                if news_id != pk and item.weight >= data.weight:
                    self.items[news_id] = item.model_copy(update={'weight': item.weight + 1})
            updated = updated.model_copy(update={'weight': data.weight})

        self.items[pk] = updated
        return self._with_media(updated)

    async def delete_one(self, *, pk: UUID) -> None:
        await self.delete_many(pks=[pk])

    async def delete_many(self, *, pks: list[UUID]) -> None:
        for pk in pks:
            await self.get_one(pk=pk)

        for pk in pks:
            del self.items[pk]

        self._recount_weights()

    def _recount_weights(self) -> None:
        """Смыкает веса в 0..N-1 в прежнем порядке — как _recount_weights в репозитории."""
        ordered = sorted(self.items.values(), key=lambda item: item.weight)
        for weight, news in enumerate(ordered):
            if news.weight != weight:
                self.items[news.id] = news.model_copy(update={'weight': weight})


class FakeFoldersRepository(FoldersRepository):
    """Репозиторий папок в памяти: вложенность, файлы и владелец записи.

    Владелец (creator_id) выставляется под текущего пользователя запроса — поэтому
    «чужие» папки здесь так же не видны, как в реальных выборках с фильтром.
    """

    def __init__(
        self,
        *,
        files_repository: FakeFilesRepository,
        videos_repository: FakeVideosRepository,
        owner_id: UUID | None = None,
    ) -> None:
        self.items: dict[UUID, FolderResponseSchema] = {}
        self.creators: dict[UUID, UUID | None] = {}
        self._links = files_repository.folder_links
        self._files_repository = files_repository
        self._video_links = videos_repository.folder_links
        self._videos_repository = videos_repository
        # в реальном репозитории владелец берётся из контекста запроса
        self._owner = owner_id
        self._admin = False

    def use_owner(self, *, owner_id: UUID | None) -> None:
        """Считает владельцем папок текущего пользователя — как репозиторий с контекстом."""
        self._owner = owner_id

    def use_admin(self, *, is_admin: bool) -> None:
        """Роль текущего пользователя: админу доступен фильтр по creator_id."""
        self._admin = is_admin

    @property
    def _is_admin(self) -> bool:
        return self._admin

    @property
    def links(self) -> dict[UUID, set[UUID]]:
        """Связи папок с файлами — та же таблица, что чистит репозиторий файлов."""
        return self._links.links

    @property
    def file_creators(self) -> dict[tuple[UUID, UUID], UUID | None]:
        """Кто привязал файл к папке — как creator_id в таблице folder_files."""
        return self._links.creators

    @property
    def video_links(self) -> dict[UUID, set[UUID]]:
        """Связи папок с видео — та же таблица, что чистит репозиторий видео."""
        return self._video_links.links

    @property
    def video_creators(self) -> dict[tuple[UUID, UUID], UUID | None]:
        """Кто привязал видео к папке — как creator_id в таблице folder_videos."""
        return self._video_links.creators

    async def create_one(self, *, data: FolderCreateSchema) -> FolderResponseSchema:
        folder = FolderResponseSchema(
            id=uuid4(),
            name=data.name,
            parent_id=data.parent_id,
            created_at=datetime.now(timezone.utc),
        )
        self.items[folder.id] = folder
        self.creators[folder.id] = self._owner
        self._links.link(
            folder_id=folder.id, file_ids=set(data.file_ids), creator_id=self._owner
        )
        self._video_links.link(
            folder_id=folder.id, video_ids=set(data.video_ids), creator_id=self._owner
        )
        return self._with_videos(self._with_files(folder))

    async def create_root(self, *, owner_id: UUID, name: str) -> FolderResponseSchema:
        """Корневая папка регистрации: владелец задаётся явно, без текущего пользователя."""
        folder = FolderResponseSchema(
            id=uuid4(), name=name, is_root=True, created_at=datetime.now(timezone.utc)
        )
        self.items[folder.id] = folder
        self.creators[folder.id] = owner_id
        return folder

    async def get_root(self, *, owner_id: UUID | None = None) -> FolderResponseSchema | None:
        """Корневая папка пользователя: `owner_id` передаёт админ для чужого дерева."""
        owner = owner_id if owner_id is not None else self._owner
        return next(
            (
                folder
                for folder in self.items.values()
                if self.creators.get(folder.id) == owner and folder.is_root
            ),
            None,
        )

    async def get_creator_id(self, *, pk: UUID) -> UUID:
        if pk not in self.items:
            raise ObjectNotFoundException(object_id=pk, object_class=Folder)
        creator_id = self.creators.get(pk)
        if creator_id is None:
            raise ObjectNotFoundException(object_id=pk, object_class=Folder)
        return creator_id

    async def has_folder(self, *, pk: UUID, owner_id: UUID) -> bool:
        return pk in self.items and self.creators.get(pk) == owner_id

    async def get_one(self, *, pk: UUID) -> FolderResponseSchema:
        folder = await self._mine(pk)
        return self._with_videos(self._with_files(folder)).model_copy(
            update={'children': self._children(pk=pk)}
        )

    async def get_list(
        self, *, filters: FolderFilterSchema, paginator: Paginator
    ) -> PaginatedSchema[FolderResponseSchema]:
        folders = sorted(self._visible(creator_id=filters.creator_id), key=lambda item: item.name)
        if filters.name:
            folders = [item for item in folders if filters.name.lower() in item.name.lower()]
        if filters.parent_id is not None:
            folders = [item for item in folders if item.parent_id == filters.parent_id]
        elif filters.root_only:
            folders = [item for item in folders if item.parent_id is None]

        offset = paginator.page_size * (paginator.page - 1)
        page = folders[offset : offset + paginator.page_size]
        return PaginatedSchema(
            count=len(folders),
            offset=offset,
            page=paginator.page,
            page_size=paginator.page_size,
            data=[self._with_videos(self._with_files(item)) for item in page],
        )

    async def update_one(self, *, pk: UUID, data: FolderUpdateSchema) -> FolderResponseSchema:
        folder = await self._mine(pk)
        values = data.model_dump(exclude={'file_ids', 'video_ids'}, exclude_unset=True)
        self.items[pk] = folder.model_copy(update=values)
        if data.file_ids is not None:
            self._links.link(
                folder_id=pk, file_ids=set(data.file_ids), creator_id=self._owner
            )
        if data.video_ids is not None:
            self._video_links.link(
                folder_id=pk, video_ids=set(data.video_ids), creator_id=self._owner
            )
        return await self.get_one(pk=pk)

    async def has_one(self, pk: UUID, raise_error: bool = False) -> bool:
        exists = self.creators.get(pk) == self._owner
        if raise_error and not exists:
            raise ObjectNotFoundException(object_id=pk, object_class=Folder)
        return exists

    async def get_subtree_ids(self, *, pk: UUID) -> list[UUID]:
        await self._mine(pk=pk)

        candidates = list(self.items.values()) if self._is_admin else self._owned()
        subtree_ids = [pk]
        index = 0
        while index < len(subtree_ids):
            current_id = subtree_ids[index]
            index += 1
            subtree_ids.extend(
                folder.id
                for folder in candidates
                if folder.parent_id == current_id and folder.id not in subtree_ids
            )
        return subtree_ids

    async def get_file_ids(self, *, folder_ids: list[UUID]) -> list[UUID]:
        file_ids: list[UUID] = []
        for folder_id in folder_ids:
            for file_id in sorted(self.links.get(folder_id, set()), key=str):
                if file_id in self._files_repository.items and file_id not in file_ids:
                    file_ids.append(file_id)
        return file_ids

    async def get_video_ids(self, *, folder_ids: list[UUID]) -> list[UUID]:
        video_ids: list[UUID] = []
        for folder_id in folder_ids:
            for video_id in sorted(self.video_links.get(folder_id, set()), key=str):
                if video_id in self._videos_repository.items and video_id not in video_ids:
                    video_ids.append(video_id)
        return video_ids

    async def attach_video(self, *, folder_id: UUID, video_id: UUID) -> None:
        await self.has_one(folder_id, raise_error=True)
        video_ids = set(self.video_links.get(folder_id, set())) | {video_id}
        self._video_links.link(
            folder_id=folder_id, video_ids=video_ids, creator_id=self._owner
        )

    async def delete_subtree(self, *, folder_ids: list[UUID]) -> None:
        self._links.unlink_folder(folder_ids=folder_ids)
        self._video_links.unlink_folder(folder_ids=folder_ids)
        for folder_id in folder_ids:
            self.items.pop(folder_id, None)
            self.creators.pop(folder_id, None)

    async def delete_one(self, *, pk: UUID) -> None:
        await self.delete_subtree(folder_ids=await self.get_subtree_ids(pk=pk))

    async def _mine(self, pk: UUID) -> FolderResponseSchema:
        folder = self.items.get(pk)
        if folder is None or (not self._is_admin and self.creators.get(pk) != self._owner):
            raise ObjectNotFoundException(object_id=pk, object_class=Folder)
        return folder

    def _owned(self) -> list[FolderResponseSchema]:
        """Папки текущего пользователя: чужие записи в выборку не попадают."""
        return [
            folder
            for folder in self.items.values()
            if self.creators.get(folder.id) == self._owner
        ]

    def _visible(self, *, creator_id: UUID | None) -> list[FolderResponseSchema]:
        """Область выдачи: свои папки, либо (для админа) папки указанного пользователя."""
        if creator_id is None:
            return self._owned()
        if self._is_admin:
            return [
                folder
                for folder in self.items.values()
                if self.creators.get(folder.id) == creator_id
            ]
        return [folder for folder in self._owned() if self.creators.get(folder.id) == creator_id]

    def _children(self, *, pk: UUID) -> list[FolderShortSchema]:
        candidates = list(self.items.values()) if self._is_admin else self._owned()
        return [
            FolderShortSchema(
                id=folder.id,
                name=folder.name,
                parent_id=folder.parent_id,
                created_at=folder.created_at,
            )
            for folder in sorted(candidates, key=lambda item: item.name)
            if folder.parent_id == pk
        ]

    def _with_files(self, folder: FolderResponseSchema) -> FolderResponseSchema:
        files = [
            FileShortSchema.model_validate(file, from_attributes=True)
            for file_id in sorted(self.links.get(folder.id, set()), key=str)
            if (file := self._files_repository.items.get(file_id)) is not None
        ]
        return folder.model_copy(update={'files': files})

    def _with_videos(self, folder: FolderResponseSchema) -> FolderResponseSchema:
        videos = [
            VideoShortSchema.model_validate(video, from_attributes=True)
            for video_id in sorted(self.video_links.get(folder.id, set()), key=str)
            if (video := self._videos_repository.items.get(video_id)) is not None
        ]
        return folder.model_copy(update={'videos': videos})


async def seed_folder(
    repository: FakeFoldersRepository,
    *,
    name: str = 'Папка',
    parent_id: UUID | None = None,
    file_ids: list[UUID] | None = None,
    video_ids: list[UUID] | None = None,
    creator_id: UUID | None = None,
) -> FolderResponseSchema:
    """Кладёт папку в подменённую БД; `creator_id` — от чьего лица она создана."""
    folder = await repository.create_one(
        data=FolderCreateSchema(
            name=name,
            parent_id=parent_id,
            file_ids=file_ids or [],
            video_ids=video_ids or [],
        )
    )
    if creator_id is not None:
        repository.creators[folder.id] = creator_id
    return folder
