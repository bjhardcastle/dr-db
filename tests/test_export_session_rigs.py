from __future__ import annotations

import asyncio
import sqlite3
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from scripts.export_session_rigs import (
    SessionRig,
    TaskData,
    discover_task_datas,
    export_session_rigs,
    extract_task_filename,
    parse_task_data_filename,
    read_existing_session_keys,
    write_results,
)


class FakeListStream:
    def __init__(self, objects: list[dict[str, object]]) -> None:
        self.objects = objects

    def collect(self) -> list[dict[str, object]]:
        return self.objects


class FakeS3Store:
    prefix = "data"

    def __init__(self, objects: list[dict[str, object]]) -> None:
        self.objects = objects

    def list(self) -> FakeListStream:
        return FakeListStream(self.objects)


class TaskDataDiscoveryTests(TestCase):
    def test_reads_existing_session_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "sessions.sqlite"
            with sqlite3.connect(database_path) as database:
                database.execute(
                    "CREATE TABLE session (subject_id TEXT, date TEXT, PRIMARY KEY (subject_id, date))"
                )
                database.executemany(
                    "INSERT INTO session (subject_id, date) VALUES (?, ?)",
                    [("123", "2026-08-22"), ("456", "2026-08-22")],
                )

            self.assertEqual(
                {("123", "2026-08-22"), ("456", "2026-08-22")},
                read_existing_session_keys(database_path),
            )

    def test_discovers_last_task_data_path_per_day(self) -> None:
        last_path = "data/123/DynamicRouting1_123_20260822_120000.hdf5"
        client = FakeS3Store(
            [
                {"path": "123/DynamicRouting1_123_20260822_120000.hdf5"},
                {"path": "123/DynamicRouting1_123_20260822_114534.hdf5"},
                {"path": "123/OptoTagging_123_20260822_130000.hdf5"},
                {"path": "000000/DynamicRouting1_000000_20260822_130000.hdf5"},
                {"path": "test/DynamicRouting1_test_20260822_130000.hdf5"},
            ]
        )

        self.assertEqual(
            [
                TaskData(
                    "123",
                    "2026-08-22",
                    f"s3://bucket/{last_path}",
                )
            ],
            discover_task_datas(client, "bucket"),
        )

    def test_parses_only_dynamic_routing_task_data_names(self) -> None:
        self.assertEqual(
            "123_2026-08-22",
            parse_task_data_filename(
                123,
                "DynamicRouting1_123_20260822_114534.hdf5",
            ),
        )
        self.assertIsNone(parse_task_data_filename(123, "OptoTagging_123_20260822_114534.hdf5"))

    def test_extracts_task_filename_from_s3_path(self) -> None:
        self.assertEqual(
            "DynamicRouting1_123_20260822_114534.hdf5",
            extract_task_filename(
                "s3://bucket/data/123/DynamicRouting1_123_20260822_114534.hdf5"
            ),
        )


class WriteResultsTests(TestCase):
    def test_stores_task_filename_instead_of_s3_path(self) -> None:
        async def write_database(database_path: Path) -> tuple[int, int]:
            queue: asyncio.Queue[SessionRig | None] = asyncio.Queue()
            await queue.put(
                SessionRig(
                    "123",
                    "2026-08-22",
                    "DynamicRouting1_123_20260822_114534.hdf5",
                    "E1",
                    None,
                )
            )
            await queue.put(None)
            return await write_results(queue, database_path)

        with tempfile.TemporaryDirectory() as directory:
            database_path = Path(directory) / "sessions.sqlite"
            self.assertEqual((1, 0), asyncio.run(write_database(database_path)))
            with sqlite3.connect(database_path) as database:
                self.assertEqual(
                    ("DynamicRouting1_123_20260822_114534.hdf5",),
                    database.execute("SELECT task_filename FROM session").fetchone(),
                )


class QueuePipelineTests(TestCase):
    def test_reads_concurrently_and_serializes_results_through_writer(self) -> None:
        task_datas = [
            TaskData("1", "2026-08-22", "s3://bucket/good.hdf5"),
            TaskData("2", "2026-08-22", "s3://bucket/bad.hdf5"),
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
            return len(rows), sum(
                row.task_data_read_error is not None for row in rows
            )

        with patch("scripts.export_session_rigs.write_results", new=writer):
            counts = asyncio.run(
                export_session_rigs(
                    task_datas,
                    Path("unused.sqlite"),
                    reader_count=2,
                    queue_size=1,
                    rig_reader=rig_reader,
                )
            )

        self.assertEqual((2, 1), counts)
        self.assertEqual("E1", rows[0].rig_id)
        self.assertIsNone(rows[0].task_data_read_error)
        self.assertIsNone(rows[1].rig_id)
        self.assertEqual(
            "ValueError: broken fixture",
            rows[1].task_data_read_error,
        )
