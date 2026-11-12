from django.urls import reverse

from apps.api.base_test import BaseApiTest


class DocsTest(BaseApiTest):
    url_named = "api_v1:docs:schema-redoc"
    url: str

    def setUp(self) -> None:
        super().setUp()

        self.url = reverse(self.url_named)

    def test_success(self) -> None:
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
