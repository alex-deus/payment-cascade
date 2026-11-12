from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status

from apps.api.base_test import BaseApiTest
from apps.users.models import User


class TestProfileDestroy(BaseApiTest):
    url_named = "api_v1:user:profile"
    url: str

    def setUp(self) -> None:
        super().setUp()

        self.url = reverse(self.url_named)

    def test_succeed(self) -> None:
        instance: User = G(User)

        self.client.force_authenticate(instance)

        response = self.client.delete(self.url)
        self.assertResponseStatus(response, status.HTTP_204_NO_CONTENT)

        is_exists: bool = User.objects.filter(pk=instance.pk).exists()
        self.assertFalse(is_exists)

    def test_un_auth(self) -> None:
        response = self.client.delete(self.url)
        self.assertResponseStatus(response, status.HTTP_401_UNAUTHORIZED)
