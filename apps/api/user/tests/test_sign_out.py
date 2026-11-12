from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.test import APIRequestFactory

from apps.api.base_test import BaseApiTest
from apps.api.user.views import TokenRefreshView
from apps.users.models import User


class TestSignOutCreate(BaseApiTest):
    url_named = "api_v1:user:sign-out"
    url: str

    def setUp(self) -> None:
        super().setUp()

        self.url = reverse(self.url_named)

    def test_succeed(self) -> None:
        user: User = G(User)

        self.client.force_authenticate(user)

        response = self.client.post(self.url)
        self.assertResponseStatus(response, status.HTTP_202_ACCEPTED)

    def test_un_auth(self) -> None:
        response = self.client.post(self.url)
        self.assertResponseStatus(response, status.HTTP_401_UNAUTHORIZED)

    def test_sign_out_with_refresh_revokes_it(self) -> None:
        user: User = G(User)
        refresh = RefreshToken.for_user(user)

        self.client.force_authenticate(user)

        response = self.client.post(self.url, data={"refresh": str(refresh)})
        self.assertResponseStatus(response, status.HTTP_202_ACCEPTED)

        request = APIRequestFactory().post("/token-refresh/", {"refresh": str(refresh)}, format="json")
        refresh_response = TokenRefreshView.as_view()(request)
        self.assertResponseStatus(refresh_response, status.HTTP_401_UNAUTHORIZED)

    def test_sign_out_without_refresh(self) -> None:
        user: User = G(User)

        self.client.force_authenticate(user)

        response = self.client.post(self.url, data={})
        self.assertResponseStatus(response, status.HTTP_202_ACCEPTED)

    def test_sign_out_twice_with_same_refresh_is_idempotent(self) -> None:
        user: User = G(User)
        refresh = RefreshToken.for_user(user)

        self.client.force_authenticate(user)

        first_response = self.client.post(self.url, data={"refresh": str(refresh)})
        self.assertResponseStatus(first_response, status.HTTP_202_ACCEPTED)

        second_response = self.client.post(self.url, data={"refresh": str(refresh)})
        self.assertResponseStatus(second_response, status.HTTP_202_ACCEPTED)
