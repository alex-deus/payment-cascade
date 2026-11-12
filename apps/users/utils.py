import logging

from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import User


__all__ = ["blacklist_refresh_token", "issue_token_pair"]

logger = logging.getLogger("django.request")


def issue_token_pair(user: User) -> dict[str, str]:
    """Выпускает пару JWT-токенов (access, refresh) для пользователя."""

    refresh = RefreshToken.for_user(user)

    return {"access": str(refresh.access_token), "refresh": str(refresh)}


def blacklist_refresh_token(value: str) -> bool:
    """Отзывает refresh-токен. Идемпотентна: мусорный/уже отозванный токен не вызывает ошибку."""

    try:
        token = RefreshToken(value)
        token.blacklist()
    except TokenError:
        return False

    return True
