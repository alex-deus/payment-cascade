from unittest import skip

from django.urls import reverse
from django_dynamic_fixture import G
from rest_framework import status
from rest_framework.authtoken.models import Token as DRFToken

from apps.api.base_test import BaseApiTest
from apps.users.models import User


class TestSignUpCreate(BaseApiTest):
    def test_new_user(self) -> None:
        response = self.client.post(reverse("api_v1:user:sign-up"), data={"name": "name"})

        self.assertResponseStatus(response, status.HTTP_201_CREATED)
        data = response.json()
        token = DRFToken.objects.get(key=data["token"])
        self.assertEqual(token.user.name, "name")
        self.assertEqual(token.user.role, User.ROLE.USER)
        self.assertIn("access", data)
        self.assertIn("refresh", data)
        profile = self.client.get(reverse("api_v1:user:profile"), HTTP_AUTHORIZATION=f"Bearer {data['access']}")
        self.assertResponseStatus(profile, status.HTTP_200_OK)

    @skip("Sign-up no longer accepts a user ID or implements existing-user lookup")
    def test_exists_user(self) -> None:
        user = G(User, name="existing")

        response = self.client.post(reverse("api_v1:user:sign-up"), data={"id": str(user.id), "name": "new"})

        self.assertResponseStatus(response, status.HTTP_202_ACCEPTED)
        user.refresh_from_db()
        self.assertEqual(user.name, "existing")
