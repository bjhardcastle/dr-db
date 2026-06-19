from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

import requests

from scripts.fetch_aind_subjects import fetch_service_resource


class FakeResponse:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> object:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} Client Error")


class FetchServiceResourceTests(TestCase):
    def setUp(self) -> None:
        self.args = SimpleNamespace(
            host="http://aind-metadata-service/",
            api_prefix="api/v2",
            timeout=30.0,
        )

    def test_returns_resource_json_even_when_service_responds_400(self) -> None:
        payload = {
            "object_type": "Subject",
            "subject_id": "780327",
            "subject_details": {"sex": "Male"},
        }

        with patch(
            "scripts.fetch_aind_subjects.requests.get",
            return_value=FakeResponse(400, payload),
        ):
            subject = fetch_service_resource(self.args, "subject", "780327")

        self.assertEqual(payload, subject)

    def test_raises_for_400_error_payload(self) -> None:
        payload = {"detail": "bad request"}

        with patch(
            "scripts.fetch_aind_subjects.requests.get",
            return_value=FakeResponse(400, payload),
        ):
            with self.assertRaises(requests.HTTPError):
                fetch_service_resource(self.args, "subject", "780327")
