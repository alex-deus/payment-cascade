from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.authtoken.models import Token as DRFToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.api.base_test import BaseApiTest
from apps.api.user.serializers import UserProfileRetrieveSerializer
from apps.users.models import User


class TestProfileRetrieve(BaseApiTest):
    url_named = "api_v1:user:profile"
    url: str

    def setUp(self) -> None:
        super().setUp()

        self.url = reverse(self.url_named)

    def test_succeed(self) -> None:
        instance: User = G(User, name="name", email="u@e.com")

        self.client.force_authenticate(instance)

        response = self.client.get(self.url)
        self.assertResponseStatus(response, status.HTTP_200_OK)

        self.assertRetrieveInResponse(UserProfileRetrieveSerializer, instance, response, instance)

    def test_un_auth(self) -> None:
        response = self.client.get(self.url)
        self.assertResponseStatus(response, status.HTTP_401_UNAUTHORIZED)

    def test_legacy_drf_token_still_works(self) -> None:
        # Регрессия переходного периода: старые DRF-токены продолжают авторизовывать запросы
        instance: User = G(User)
        token: DRFToken = DRFToken.objects.create(user=instance)

        response = self.client.get(self.url, HTTP_AUTHORIZATION=f"Token {token.key}")
        self.assertResponseStatus(response, status.HTTP_200_OK)

    def test_jwt_access_token_works(self) -> None:
        instance: User = G(User)
        access = RefreshToken.for_user(instance).access_token

        response = self.client.get(self.url, HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertResponseStatus(response, status.HTTP_200_OK)

    def test_jwt_access_token_for_inactive_user_is_rejected(self) -> None:
        instance: User = G(User, is_active=False)
        access = RefreshToken.for_user(instance).access_token

        response = self.client.get(self.url, HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertResponseStatus(response, status.HTTP_401_UNAUTHORIZED)
