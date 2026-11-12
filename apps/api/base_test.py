from typing import Optional

from django.contrib.auth.models import AnonymousUser
from django.db.models import QuerySet
from django.test import RequestFactory
from rest_framework.test import APITestCase

from apps.common.base_test import BaseTest
from apps.users.models import User


__all__ = ["BaseApiTest"]


class BaseApiTest(APITestCase, BaseTest):
    def assertResponseStatus(self, response, status_code: int) -> None:
        if response.status_code != status_code:
            message = f"Status code is not {status_code}. It's {response.status_code}"
            if response.status_code == 400:
                try:
                    message += f" JSON={response.json()}"
                except ValueError:
                    ...

            self.fail(message)

    def assertListInResponse(
        self, serializer_class, queryset: QuerySet, response, context_user: Optional[User] = None
    ) -> None:
        self.assertIn("results", response.data)

        context = self._get_request_context(context_user)
        serializer = serializer_class(many=True, instance=queryset, context=context)
        self.assertEqual(len(serializer.data), len(response.data["results"]))
        self.assertListEqual(list(serializer.data), response.data["results"])

    def assertRetrieveInResponse(
        self, serializer_class, instance, response, context_user: Optional[User] = None
    ) -> None:
        context = self._get_request_context(context_user)
        serializer = serializer_class(instance=instance, context=context)
        self.assertDictEqual(serializer.data, response.data)

    def assertRetrieveDataInResponse(
        self, serializer_class, data: dict, response, context_user: Optional[User] = None
    ) -> None:
        context: dict = self._get_request_context(context_user)
        serializer = serializer_class(data=data, context=context)

        is_valid: bool = serializer.is_valid()
        if not is_valid:
            self.assertTrue(is_valid, f"Errors: {serializer.errors}")

        self.assertDictEqual(serializer.data, response.data)

    @staticmethod
    def _get_request_context(user: Optional[User] = None, **kwargs) -> dict:
        context = {}

        request = RequestFactory()
        request.user = user if user else AnonymousUser()
        context["request"] = request

        context.update(kwargs)

        return context
