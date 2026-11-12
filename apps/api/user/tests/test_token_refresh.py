from django_dynamic_fixture import G
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.test import APIRequestFactory

from apps.api.base_test import BaseApiTest
from apps.api.user.views import TokenRefreshView
from apps.users.models import User


class TestTokenRefreshCreate(BaseApiTest):
    def post(self, data: dict):
        request = APIRequestFactory().post("/token-refresh/", data, format="json")
        return TokenRefreshView.as_view()(request)

    def test_valid_refresh_returns_new_pair(self) -> None:
        user: User = G(User)
        refresh = RefreshToken.for_user(user)

        response = self.post({"refresh": str(refresh)})
        self.assertResponseStatus(response, status.HTTP_200_OK)

        data: dict = response.data
        self.assertIn("access", data)
        self.assertIn("refresh", data)
        # Ротация включена: новый refresh отличается от исходного
        self.assertNotEqual(data["refresh"], str(refresh))

    def test_rotated_refresh_is_rejected(self) -> None:
        user: User = G(User)
        refresh = RefreshToken.for_user(user)

        first_response = self.post({"refresh": str(refresh)})
        self.assertResponseStatus(first_response, status.HTTP_200_OK)

        second_response = self.post({"refresh": str(refresh)})
        self.assertResponseStatus(second_response, status.HTTP_401_UNAUTHORIZED)

    def test_garbage_refresh_is_rejected(self) -> None:
        response = self.post({"refresh": "garbage.token.value"})
        self.assertResponseStatus(response, status.HTTP_401_UNAUTHORIZED)
