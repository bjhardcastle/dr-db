from __future__ import annotations

import asyncio
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from scripts.export_session_rigs import (
    SessionRig,
    TaskStim,
    discover_task_stims,
    export_session_rigs,
    parse_task_stim_filename,
)


class FakePaginator:
    def __init__(self, pages: list[dict[str, object]]) -> None:
        self.pages = pages

    def paginate(self, **_: object) -> list[dict[str, object]]:
        return self.pages


class FakeS3Client:
    def __init__(self, pages: list[dict[str, object]]) -> None:
        self.paginator = FakePaginator(pages)

    def get_paginator(self, name: str) -> FakePaginator:
        if name != "list_objects_v2":
            raise AssertionError(name)
        return self.paginator


class TaskStimDiscoveryTests(TestCase):
    def test_discovers_one_task_stim_path_per_session(self) -> None:
        prefix = "data/"
        first_path = "data/123/DynamicRouting1_123_20260822_114534.hdf5"
        client = FakeS3Client(
            [
                {
                    "Contents": [
                        {"Key": first_path},
                        {"Key": ("data/123/DynamicRouting1_123_20260822_120000.hdf5")},
                        {"Key": "data/123/OptoTagging_123_20260822_130000.hdf5"},
                        {
                            "Key": (
                                "data/000000/"
                                "DynamicRouting1_000000_20260822_130000.hdf5"
                            )
                        },
                        {
                            "Key": (
                                "data/test/DynamicRouting1_test_20260822_130000.hdf5"
                            )
                        },
                    ]
                }
            ]
        )

        self.assertEqual(
            [TaskStim("123_20260822", f"s3://bucket/{first_path}")],
            discover_task_stims(client, "bucket", prefix),
        )

    def test_parses_only_dynamic_routing_task_stim_names(self) -> None:
        self.assertEqual(
            "123_20260822",
            parse_task_stim_filename(
                123,
                "DynamicRouting1_123_20260822_114534.hdf5",
            ),
        )
        self.assertIsNone(
            parse_task_stim_filename(123, "OptoTagging_123_20260822_114534.hdf5")
        )


class QueuePipelineTests(TestCase):
    def test_reads_concurrently_and_serializes_results_through_writer(self) -> None:
        task_stims = [
            TaskStim("1_20260822", "s3://bucket/good.hdf5"),
            TaskStim("2_20260822", "s3://bucket/bad.hdf5"),
        ]
        rows: list[SessionRig] = []

        async def rig_reader(path: str) -> str | None:
            await asyncio.sleep(0)
            if path.endswith("bad.hdf5"):
                raise ValueError("broken fixture")
            return "E1"

        async def writer(
            queue: asyncio.Queue[SessionRig | None], _: Path
        ) -> tuple[int, int]:
            while (row := await queue.get()) is not None:
                rows.append(row)
            return len(rows), sum(row.read_error is not None for row in rows)

        with patch("scripts.export_session_rigs.write_results", new=writer):
            counts = asyncio.run(
                export_session_rigs(
                    task_stims,
                    Path("unused.sqlite"),
                    reader_count=2,
                    queue_size=1,
                    rig_reader=rig_reader,
                )
            )

        self.assertEqual((2, 1), counts)
        self.assertEqual("E1", rows[0].rig_id)
        self.assertIsNone(rows[0].read_error)
        self.assertIsNone(rows[1].rig_id)
        self.assertEqual("ValueError: broken fixture", rows[1].read_error)
