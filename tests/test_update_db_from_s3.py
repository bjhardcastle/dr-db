from __future__ import annotations

from datetime import date
from unittest import TestCase

from scripts.update_db_from_s3 import (
    S3Session,
    discover_inventory,
    discover_sessions,
    parse_s3_uri,
    parse_session,
)


class FakePaginator:
    def __init__(self, pages_by_prefix: dict[str, list[dict[str, object]]]) -> None:
        self.pages_by_prefix = pages_by_prefix

    def paginate(self, *, Prefix: str, **_: object) -> list[dict[str, object]]:
        return self.pages_by_prefix.get(Prefix, [])


class FakeS3Client:
    def __init__(self, pages_by_prefix: dict[str, list[dict[str, object]]]) -> None:
        self.paginator = FakePaginator(pages_by_prefix)

    def get_paginator(self, name: str) -> FakePaginator:
        self.assert_name(name)
        return self.paginator

    @staticmethod
    def assert_name(name: str) -> None:
        if name != "list_objects_v2":
            raise AssertionError(name)


class S3DiscoveryTests(TestCase):
    def test_parses_uri_and_session_names(self) -> None:
        self.assertEqual(
            ("bucket", "path/to/data/"),
            parse_s3_uri("s3://bucket/path/to/data"),
        )
        self.assertEqual(
            S3Session(123, "123_20260822", date(2026, 8, 22)),
            parse_session(123, "123_20260822"),
        )
        session = parse_session(123, "123_20260822")
        assert session is not None
        self.assertEqual(date(2026, 8, 22), session.date)
        hyphenated_session = parse_session(123, "123_2026-08-22")
        assert hyphenated_session is not None
        self.assertEqual(date(2026, 8, 22), hyphenated_session.date)

    def test_discovers_subject_and_session_directories(self) -> None:
        client = FakeS3Client(
            {
                "data/": [
                    {"CommonPrefixes": [{"Prefix": "data/123/"}]},
                    {"CommonPrefixes": [{"Prefix": "data/456/"}]},
                    {"CommonPrefixes": [{"Prefix": "data/not-a-subject/"}]},
                ],
                "data/123/": [
                    {
                        "CommonPrefixes": [
                            {"Prefix": "data/123/123_20260822/"},
                            {"Prefix": "data/123/123_bad-date/"},
                        ]
                    }
                ],
            }
        )

        self.assertEqual(
            [
                parse_session(123, "123_20260822"),
            ],
            discover_sessions(client, "bucket", "data/"),
        )
        inventory = discover_inventory(client, "bucket", "data/")
        self.assertEqual((123, 456), inventory.subject_ids)
