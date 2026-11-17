# API Документация CloudManager

Актуальное описание HTTP API сервиса **CloudManager** (`app/`).

> [!NOTE]
> Этот документ должен обновляться при любом изменении эндпоинтов, схем запросов/ответов, query-фильтров, кодов ответа или правил авторизации.

---

## Общие соглашения

* **Префикс API**: все бизнес-эндпоинты смонтированы под `/api` (`app/routers.py`). Пробы здоровья (`/health`, `/health/ready`) находятся в корне без префикса.
* **Авторизация**: `Authorization: Bearer <access_token>` (JWT). Заблокированные пользователи (`is_blocked: true`) не могут входить и пользоваться API.
* **Пагинация** (для списочных эндпоинтов, возвращающих `PaginatedSchema`):
  * `page` (int, `>= 1`, по умолчанию `1`) — номер страницы.
  * `page_size` (int, `>= 1`, `<= PAGE_LIMIT`, по умолчанию `25`) — размер страницы.

---

## 1. Health (`/health`)

### `GET /health`
Liveness-проба сервиса. Авторизация не требуется.
* **Ответ `200 OK`**: `HealthResponseSchema` (`status`, `version`).

### `GET /health/ready`
Readiness-проба: проверяет доступность сервиса и подключение к PostgreSQL (`SELECT 1`). Авторизация не требуется.
* **Ответ `200 OK`**: `HealthResponseSchema` (`status: ok`, `version`).
* **Ответ `503 Service Unavailable`**: `HealthResponseSchema` (`status: error`, `version`).

---

## 2. Аутентификация и пользователи (`/api/auth`)

### `POST /api/auth/register`
Регистрация нового пользователя. Авторизация не требуется.
* **Тело запроса**: `UserCreateSchema` (`login`: 3–255 символов, `password`: 8–128 символов).
* **Ответ `201 Created`**: `UserResponseSchema` (`id`, `login`, `role`, `is_blocked`, `created_at`).

### `POST /api/auth/login`
Аутентификация по логину и паролю. Авторизация не требуется.
* **Тело запроса**: `LoginSchema` (`login`, `password`).
* **Ответ `200 OK`**: `TokenResponseSchema` (`access_token`, `token_type: "Bearer"`, `expires_in`).

### `GET /api/auth/me`
Информация о текущем авторизованном пользователе.
* **Доступ**: Bearer-токен (любой авторизованный пользователь).
* **Ответ `200 OK`**: `UserResponseSchema`.

### `GET /api/auth/users`
Постраничный список пользователей с фильтрацией.
* **Доступ**: Bearer-токен (только администратор).
* **Query-параметры**:
  * `login` (str, max 255, опционально) — поиск по вхождению подстроки без учёта регистра.
  * `role` (`EUserRole`, опционально) — фильтр по роли.
  * `page`, `page_size` — пагинация.
* **Ответ `200 OK`**: `PaginatedSchema[UserResponseSchema]`.

### `POST /api/auth/users/{user_id}/block`
Блокировка пользователя. Заблокированный пользователь теряет доступ к входу и API.
* **Доступ**: Bearer-токен (только администратор).
* **Path-параметр**: `user_id` (`UUID`).
* **Ответ `200 OK`**: `UserResponseSchema`.

### `POST /api/auth/users/{user_id}/unblock`
Разблокировка пользователя.
* **Доступ**: Bearer-токен (только администратор).
* **Path-параметр**: `user_id` (`UUID`).
* **Ответ `200 OK`**: `UserResponseSchema`.

---

## 3. Файлы (`/api/files`)

### `POST /api/files`
Загрузка файла в S3-хранилище (Garage).
* **Доступ**: Bearer-токен (любой зарегистрированный пользователь).
* **Тип запроса**: `multipart/form-data`
  * `name` (str, Form, 1–255 символов) — отображаемое имя файла.
  * `file` (`UploadFile`, File) — загружаемый файл разрешённого типа.
* **Ответ `201 Created`**: `FileResponseSchema` (`id`, `name`, `object_key`, `type`, `size`, `creator_id`, `creator_login`, `created_at`).

### `GET /api/files`
Список файлов с фильтрацией и пагинацией.
* **Доступ**: Bearer-токен (в endpoint передаётся `UserResponseSchema`; доступ/логика фильтрации определяется сервисом `FilesService`).
* **Query-параметры**:
  * `name` (str, max 255, опционально) — поиск по имени файла.
  * `type` (`list[EFileType]`, опционально, параметр можно повторять) — фильтр по типам файлов.
  * `creator_id` (`UUID`, опционально) — файлы конкретного пользователя.
  * `page`, `page_size` — пагинация.
* **Ответ `200 OK`**: `PaginatedSchema[FileResponseSchema]`.

### `GET /api/files/types`
Справочник разрешённых типов файлов (для UI, атрибута `accept` и фильтра `?type=`). Авторизация не требуется.
* **Ответ `200 OK`**: `list[FileTypeSchema]` (`value`, `content_type`, `is_image`).

### `GET /api/files/{file_id}/download`
Скачивание файла по `id` (`Content-Disposition: attachment`). Авторизация не требуется.
* **Path-параметр**: `file_id` (`UUID`).
* **Ответ `200 OK`**: бинарный поток с MIME-типом файла.

### `GET /api/files/{file_id}/image`
Отдача изображения инлайном (`Content-Disposition: inline`) для вставки в `<img src>`. Поддерживает кэширование (`ETag`, `If-None-Match` -> `304 Not Modified`, `Cache-Control: public, max-age=86400, immutable`, `X-Content-Type-Options: nosniff`). Авторизация не требуется.
* **Path-параметр**: `file_id` (`UUID`).
* **Ответ `200 OK` / `304 Not Modified`**: изображение с соответствующим MIME-типом.

### `PATCH /api/files/{file_id}`
Переименование файла (не затрагивает объект в S3).
* **Доступ**: Bearer-токен (администратор — любой файл, пользователь — только свой).
* **Path-параметр**: `file_id` (`UUID`).
* **Тело запроса**: `FileUpdateSchema` (`name`: str | None, 1–255 символов).
* **Ответ `200 OK`**: `FileResponseSchema`.

### `DELETE /api/files/{file_id}`
Мягкое удаление файла и удаление объекта из хранилища.
* **Доступ**: Bearer-токен (администратор — любой файл, пользователь — только свой).
* **Path-параметр**: `file_id` (`UUID`).
* **Ответ `204 No Content`**.

---

## 4. Папки (`/api/folders`)

Личное пространство пользователя. Все ручки требуют авторизации.

### `POST /api/folders`
Создание папки.
* **Доступ**: Bearer-токен (любой зарегистрированный пользователь).
* **Тело запроса**: `FolderCreateSchema`
  * `name` (str, 1–255 символов).
  * `parent_id` (`UUID | None`, по умолчанию `null` — в корневой папке пользователя).
  * `file_ids` (`list[UUID]`, опционально) — файлы, сразу привязываемые к папке.
  * `video_ids` (`list[UUID]`, опционально) — видео, сразу привязываемые к папке.
  * `audio_ids` (`list[UUID]`, опционально) — аудио, сразу привязываемые к папке.
* **Ответ `201 Created`**: `FolderResponseSchema` (`id`, `name`, `parent_id`, `is_root`, `created_at`, `files: list[FileShortSchema]`, `videos: list[VideoShortSchema]`, `audios: list[AudioShortSchema]`, `children: list[FolderShortSchema]`).

### `GET /api/folders`
Список папок с фильтрацией и пагинацией.
* **Доступ**: Bearer-токен.
* **Query-параметры**:
  * `name` (str, max 255, опционально) — поиск по названию.
  * `parent_id` (`UUID`, опционально) — содержимое конкретной папки.
  * `root_only` (bool, по умолчанию `false`) — только папки верхнего уровня (игнорируется вместе с `parent_id`).
  * `creator_id` (`UUID`, опционально) — папки конкретного пользователя (только для администратора; остальным — только свои).
  * `page`, `page_size` — пагинация.
* **Ответ `200 OK`**: `PaginatedSchema[FolderResponseSchema]`.

### `GET /api/folders/{folder_id}`
Получение папки вместе с её файлами, видео, аудио и подпапками.
* **Доступ**: Bearer-токен.
* **Path-параметр**: `folder_id` (`UUID`).
* **Ответ `200 OK`**: `FolderResponseSchema` — файлы в `files`, видео в `videos`, аудио в `audios`.

### `PATCH /api/folders/{folder_id}`
Изменение папки (переименование, перенос, обновление списков файлов, видео и аудио).
* **Доступ**: Bearer-токен.
* **Path-параметр**: `folder_id` (`UUID`).
* **Тело запроса**: `FolderUpdateSchema`
  * `name` (`str | None`, 1–255 символов).
  * `parent_id` (`UUID | None`, `null` переносит папку в корневую папку, отсутствие поля не меняет родителя).
  * `file_ids` (`list[UUID] | None`, полный новый набор файлов, отсутствие поля не меняет связи).
  * `video_ids` (`list[UUID] | None`, полный новый набор видео, отсутствие поля не меняет связи).
  * `audio_ids` (`list[UUID] | None`, полный новый набор аудио, отсутствие поля не меняет связи).
* **Ответ `200 OK`**: `FolderResponseSchema`.

### `DELETE /api/folders/{folder_id}`
Удаление папки вместе со всеми вложенными подпапками, файлами, видео и аудио внутри.
* **Доступ**: Bearer-токен.
* **Path-параметр**: `folder_id` (`UUID`).
* **Ответ `204 No Content`**.

---

## 5. Видео (`/api/videos`)

### `POST /api/videos`
Загрузка видео в S3-хранилище.
* **Доступ**: Bearer-токен (любой авторизованный пользователь).
* **Тип запроса**: `multipart/form-data`
  * `name` (str, Form, 1–255 символов) — уникальное имя видео.
  * `file` (`UploadFile`, File) — видеофайл разрешённого типа.
  * `folder_id` (`UUID`, Form, опционально) — папка пользователя, в которую сразу кладётся видео.
* **Ответ `201 Created`**: `VideoResponseSchema` (`id`, `name`, `object_key`, `type`, `size`, `created_at`).
* **Ответ `400 Bad Request`**: папка `folder_id` не найдена или принадлежит другому пользователю.

### `GET /api/videos`
Список видео с фильтрацией и пагинацией. Авторизация не требуется.
* **Query-параметры**:
  * `name` (str, max 255, опционально) — поиск по имени видео.
  * `type` (`list[EVideoType]`, опционально, параметр можно повторять) — фильтр по типам видео.
  * `page`, `page_size` — пагинация.
* **Ответ `200 OK`**: `PaginatedSchema[VideoResponseSchema]`.

### `GET /api/videos/types`
Справочник разрешённых типов видео. Авторизация не требуется.
* **Ответ `200 OK`**: `list[VideoTypeSchema]` (`value`, `content_type`).

### `GET /api/videos/by-name`
Поиск видео по точному имени. Авторизация не требуется.
* **Query-параметр**: `name` (str, 1–255 символов, обязательный).
* **Ответ `200 OK`**: `VideoResponseSchema`.

### `GET /api/videos/{video_id}`
Получение метаданных видео по идентификатору. Авторизация не требуется.
* **Path-параметр**: `video_id` (`UUID`).
* **Ответ `200 OK`**: `VideoResponseSchema`.

### `GET /api/videos/{video_id}/playback`
Получение presigned-ссылки на воспроизведение видео. Авторизация не требуется.
* **Path-параметр**: `video_id` (`UUID`).
* **Ответ `200 OK`**: `VideoPlaybackSchema` (`url`, `content_type`, `expires_at`, `expires_in`).

### `DELETE /api/videos/{video_id}`
Удаление видео (запись в БД и объект в хранилище).
* **Доступ**: Bearer-токен (администратор — любое видео, пользователь — только своё).
* **Path-параметр**: `video_id` (`UUID`).
* **Ответ `204 No Content`**.
* **Ответ `403 Forbidden`**: видео загружено другим пользователем.

---

## 6. Аудио (`/api/audios`)

Все эндпоинты аудио доступны **только авторизованным пользователям** (`Authorization: Bearer <access_token>`). Для воспроизведения на клиенте выдаётся presigned GET URL к S3-хранилищу.

### `POST /api/audios`
Загрузка аудио в S3-хранилище.
* **Доступ**: Bearer-токен (любой авторизованный пользователь).
* **Тип запроса**: `multipart/form-data`
  * `name` (str, Form, 1–255 символов) — уникальное имя аудио.
  * `file` (`UploadFile`, File) — аудиофайл разрешённого типа (`mp3`, `wav`, `ogg`, `aac`, `flac`, `m4a`, `opus`, `webm`).
  * `folder_id` (`UUID`, Form, опционально) — папка пользователя, в которую сразу кладётся аудио.
* **Ответ `201 Created`**: `AudioResponseSchema` (`id`, `name`, `object_key`, `type`, `size`, `created_at`).
* **Ответ `400 Bad Request`**: недопустимый тип/размер файла, либо папка `folder_id` не найдена или принадлежит другому пользователю.
* **Ответ `409 Conflict`**: активное аудио с таким именем уже существует.

### `GET /api/audios`
Список аудио с фильтрацией и пагинацией (сначала новые).
* **Доступ**: Bearer-токен (любой авторизованный пользователь).
* **Query-параметры**:
  * `name` (str, max 255, опционально) — поиск по имени аудио.
  * `type` (`list[EAudioType]`, опционально, параметр можно повторять) — фильтр по типам аудио.
  * `page`, `page_size` — пагинация.
* **Ответ `200 OK`**: `PaginatedSchema[AudioResponseSchema]`.

### `GET /api/audios/types`
Справочник разрешённых типов аудио.
* **Доступ**: Bearer-токен (любой авторизованный пользователь).
* **Ответ `200 OK`**: `list[AudioTypeSchema]` (`value`, `content_type`).

### `GET /api/audios/by-name`
Поиск аудио по точному имени (регистрозависимо).
* **Доступ**: Bearer-токен (любой авторизованный пользователь).
* **Query-параметр**: `name` (str, 1–255 символов, обязательный).
* **Ответ `200 OK`**: `AudioResponseSchema`.

### `GET /api/audios/{audio_id}`
Получение метаданных аудио по идентификатору.
* **Доступ**: Bearer-токен (любой авторизованный пользователь).
* **Path-параметр**: `audio_id` (`UUID`).
* **Ответ `200 OK`**: `AudioResponseSchema`.

### `GET /api/audios/{audio_id}/playback`
Получение presigned-ссылки на воспроизведение аудио.
* **Доступ**: Bearer-токен (любой авторизованный пользователь).
* **Path-параметр**: `audio_id` (`UUID`).
* **Ответ `200 OK`**: `AudioPlaybackSchema` (`url`, `content_type`, `expires_at`, `expires_in`).

### `PATCH /api/audios/{audio_id}`
Переименование аудио (не затрагивает объект в S3).
* **Доступ**: Bearer-токен (администратор — любое аудио, пользователь — только своё).
* **Path-параметр**: `audio_id` (`UUID`).
* **Тело запроса**: `AudioUpdateSchema` (`name`: str | None, 1–255 символов).
* **Ответ `200 OK`**: `AudioResponseSchema`.
* **Ответ `403 Forbidden`**: аудио загружено другим пользователем.
* **Ответ `409 Conflict`**: активное аудио с таким именем уже существует.

### `DELETE /api/audios/{audio_id}`
Удаление аудио (мягкое удаление записи в БД, очистка связей с папками и удаление объекта из хранилища).
* **Доступ**: Bearer-токен (администратор — любое аудио, пользователь — только своё).
* **Path-параметр**: `audio_id` (`UUID`).
* **Ответ `204 No Content`**.
* **Ответ `403 Forbidden`**: аудио загружено другим пользователем.

---

## 7. Новости (`/api/news`)

### `POST /api/news`
Создание новости.
* **Доступ**: Bearer-токен (только администратор).
* **Тело запроса**: `NewsCreateSchema` (`name`: 1–255 символов, `description`: str, `media_id`: `UUID | None`).
* **Ответ `201 Created`**: `NewsResponseSchema` (`id`, `name`, `description`, `weight`, `media_id`).

### `GET /api/news`
Список новостей с фильтрацией и пагинацией (сортировка по весу). Авторизация не требуется.
* **Query-параметры**:
  * `name` (str, max 255, опционально) — поиск по названию.
  * `weight_from` (int, `>= 0`, опционально) — вес от (включительно).
  * `weight_to` (int, `>= 0`, опционально) — вес до (включительно).
  * `page`, `page_size` — пагинация.
* **Ответ `200 OK`**: `PaginatedSchema[NewsResponseSchema]`.

### `GET /api/news/{news_id}`
Получение новости по идентификатору. Авторизация не требуется.
* **Path-параметр**: `news_id` (`UUID`).
* **Ответ `200 OK`**: `NewsResponseSchema`.

### `PATCH /api/news/{news_id}`
Обновление новости.
* **Доступ**: Bearer-токен (только администратор).
* **Path-параметр**: `news_id` (`UUID`).
* **Тело запроса**: `NewsUpdateSchema` (`name`, `description`, `weight`, `media_id` — все поля опциональны).
* **Ответ `200 OK`**: `NewsResponseSchema`.

### `DELETE /api/news/{news_id}`
Удаление новости.
* **Доступ**: Bearer-токен (только администратор).
* **Path-параметр**: `news_id` (`UUID`).
* **Ответ `204 No Content`**.
