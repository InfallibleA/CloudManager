class Context:
    """Контекст выполнения запроса.

    Пользователь берётся из ``request.state.user``: его устанавливает
    провайдер аутентификации при успешной проверке JWT.
    """

    def __init__(self, request=None, **extra):
        self.request = request
        for key, value in extra.items():
            setattr(self, key, value)

    def init(self, request, *, context: dict | None = None) -> 'Context':
        self.request = request
        if context:
            for key, value in context.items():
                setattr(self, key, value)
        return self

    @property
    def user(self):
        return getattr(self.request.state, 'user', None) if self.request is not None else None

    @user.setter
    def user(self, value) -> None:
        if self.request is not None:
            self.request.state.user = value
