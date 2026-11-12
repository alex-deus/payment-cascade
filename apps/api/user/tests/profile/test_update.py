from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status

from apps.api.base_test import BaseApiTest
from apps.api.user.serializers import UserProfileRetrieveSerializer
from apps.users.models import User


class TestProfileUpdate(BaseApiTest):
    url_named = "api_v1:user:profile"
    url: str
    patch_data = {"name": "n"}

    def setUp(self) -> None:
        super().setUp()

        self.url = reverse(self.url_named)

    def test_succeed(self) -> None:
        instance: User = G(User)

        self.client.force_authenticate(instance)

        response = self.client.patch(self.url, self.patch_data)
        self.assertResponseStatus(response, status.HTTP_202_ACCEPTED)

        instance.refresh_from_db()
        self.assertEqual(instance.name, self.patch_data["name"])
        self.assertRetrieveInResponse(UserProfileRetrieveSerializer, instance, response, instance)

    def test_un_auth(self) -> None:
        response = self.client.patch(self.url, self.patch_data)
        self.assertResponseStatus(response, status.HTTP_401_UNAUTHORIZED)
