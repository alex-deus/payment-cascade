from django_dynamic_fixture import G
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.test import APIRequestFactory

from apps.api.base_test import BaseApiTest
from apps.api.user.views import TokenVerifyView
from apps.users.models import User


class TestTokenVerifyCreate(BaseApiTest):
    def post(self, data: dict):
        request = APIRequestFactory().post("/token-verify/", data, format="json")
        return TokenVerifyView.as_view()(request)

    def test_valid_access_token(self) -> None:
        user: User = G(User)
        access = RefreshToken.for_user(user).access_token

        response = self.post({"token": str(access)})
        self.assertResponseStatus(response, status.HTTP_200_OK)

    def test_garbage_token(self) -> None:
        response = self.post({"token": "garbage.token.value"})
        self.assertResponseStatus(response, status.HTTP_401_UNAUTHORIZED)
