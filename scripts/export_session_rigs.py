#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "lazynwb==1.0.0.dev3",
#     "obstore>=0.11.1",
#     "pydantic-settings>=2.14.1",
#     "sqlite-utils>=3.39",
# ]
# ///

from __future__ import annotations

import asyncio
import os
import sqlite3
import sys
import tempfile
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

import lazynwb
from obstore.store import S3Store
from pydantic import Field
from pydantic_settings import BaseSettings

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from dr_db.hdf5 import read_rig

# Task-data objects are public; let lazynwb read them without signing requests.
lazynwb.config.anon = True


DEFAULT_S3_URI = "s3://aind-scratch-data/dynamic-routing/DynamicRoutingTask/Data"
DEFAULT_AWS_REGION = "us-west-2"
SKIPPED_SUBJECT_DIRECTORIES = frozenset({"000000", "366122", "555555"})
TABLE_NAME = "session"


class Settings(BaseSettings, cli_parse_args=True, cli_kebab_case="all"):
    """Command-line settings for the session-rig export."""

    s3_uri: str = Field(default=DEFAULT_S3_URI)
    endpoint_url: str | None = Field(
        default=None,
        description="Optional S3-compatible endpoint URL.",
    )
    output: Path = Field(
        default=Path("sessions.db"),
        description=(
            "Output database path. By default a new file is made in the OS temp directory."
        ),
    )
    readers: int = Field(
        default=16,
        ge=1,
        description="Number of concurrent HDF5 readers.",
    )
    queue_size: int = Field(
        default=64,
        ge=1,
        description="Maximum task-data files waiting for a reader.",
    )
    limit: int | None = Field(
        default=None,
        ge=1,
        description="Process only the first N sessions; useful for checking credentials.",
    )


@dataclass(frozen=True)
class TaskData:
    subject_id: str
    date: str
    task_data_s3_path: str


@dataclass(frozen=True)
class SessionRig:
    subject_id: str
    date: str
    task_data_s3_path: str
    rig_id: str | None
    task_data_read_error: str | None


def extract_subject_id(session_id: str) -> str:
    return session_id.split("_", 1)[0]


def extract_date(session_id: str) -> str:
    return date.fromisoformat(session_id.split("_", 1)[1]).isoformat()


async def main() -> None:
    settings = parse_args()

    bucket, prefix = parse_s3_uri(settings.s3_uri)
    # FileAccessor otherwise retains one closed accessor for every HDF5 path.
    lazynwb.config.disable_cache = True
    s3_options: dict[str, Any] = {
        "region": DEFAULT_AWS_REGION,
        "skip_signature": True,
    }
    if settings.endpoint_url:
        s3_options["endpoint"] = settings.endpoint_url
    s3 = S3Store(bucket, prefix=prefix, **s3_options)

    task_datas = discover_task_datas(s3, bucket)
    if settings.limit is not None:
        task_datas = task_datas[: settings.limit]

    database_path = settings.output or temporary_database_path()
    existing_sessions = read_existing_session_keys(database_path)
    skipped = sum(
        (task.subject_id, task.date) in existing_sessions for task in task_datas
    )
    task_datas = [
        task
        for task in task_datas
        if (task.subject_id, task.date) not in existing_sessions
    ]
    print(
        f"Discovered {len(task_datas) + skipped} task-data files under {settings.s3_uri}; "
        f"skipping {skipped} already in {database_path}."
    )
    print(f"Writing {TABLE_NAME} to {database_path}")

    written, errors = await export_session_rigs(
        task_datas,
        database_path,
        reader_count=settings.readers,
        queue_size=settings.queue_size,
    )
    print(f"Wrote {written} sessions ({errors} rig-read errors) to {database_path}")


def parse_args() -> Settings:
    return Settings()


def parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError(f"Expected an S3 URI like s3://bucket/prefix, got {uri!r}")
    prefix = parsed.path.lstrip("/")
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    return parsed.netloc, prefix


def discover_task_datas(client: Any, bucket: str) -> list[TaskData]:
    """Return the last DynamicRouting1 HDF5 file for each subject/date."""
    task_datas: dict[tuple[str, str], tuple[tuple[int, str], TaskData]] = {}
    prefix = client.prefix or ""
    objects: Iterable[Mapping[str, Any]] = client.list().collect()
    for item in objects:
        key = item.get("path")
        if not key:
            continue
        relative_path = PurePosixPath(str(key))
        path_parts = relative_path.parts
        if len(path_parts) != 2:
            continue
        subject_name, filename = path_parts
        if subject_name in SKIPPED_SUBJECT_DIRECTORIES:
            continue
        subject_id = parse_subject_id(subject_name)
        if subject_id is None:
            continue
        session_id = parse_task_data_filename(subject_id, filename)
        if session_id is None:
            continue

        session_key = (extract_subject_id(session_id), extract_date(session_id))
        candidate = TaskData(
            subject_id=session_key[0],
            date=session_key[1],
            task_data_s3_path=(
                f"s3://{bucket}/{prefix.rstrip('/') + '/' if prefix else ''}{key}"
            ),
        )
        candidate_key = (extract_task_timestamp(filename), str(key))
        current = task_datas.get(session_key)
        if current is None or candidate_key > current[0]:
            task_datas[session_key] = (candidate_key, candidate)
    return [
        task_data
        for _, task_data in sorted(
            task_datas.values(), key=lambda item: (item[1].subject_id, item[1].date)
        )
    ]


def parse_subject_id(value: str) -> int | None:
    try:
        subject_id = int(value)
    except ValueError:
        return None
    return subject_id if subject_id > 0 and str(subject_id) == value else None


def parse_task_data_filename(subject_id: int, filename: str) -> str | None:
    if not filename.lower().endswith(".hdf5"):
        return None
    parts = Path(filename).stem.split("_")
    if not parts or parts[0] != "DynamicRouting1":
        return None
    subject_text = str(subject_id)
    try:
        subject_index = parts.index(subject_text)
    except ValueError:
        return None
    for date_text in parts[subject_index + 1 :]:
        parsed_date = parse_date_text(date_text)
        if parsed_date is not None:
            return f"{subject_text}_{parsed_date.isoformat()}"
    return None


def extract_task_timestamp(filename: str) -> int:
    """Return the HHMMSS timestamp used to select the last file of a day."""
    parts = PurePosixPath(filename).stem.split("_")
    for index, value in enumerate(parts[:-1]):
        if parse_date_text(value) is not None:
            timestamp = parts[index + 1]
            if len(timestamp) == 6 and timestamp.isdecimal():
                return int(timestamp)
            break
    return -1


def parse_date_text(value: str) -> date | None:
    if len(value) != 8 or not value.isdecimal():
        return None
    try:
        return date(int(value[0:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return None


def temporary_database_path() -> Path:
    descriptor, name = tempfile.mkstemp(prefix="dr-db-session-rigs-", suffix=".sqlite")
    os.close(descriptor)
    return Path(name)


def read_existing_session_keys(database_path: Path) -> set[tuple[str, str]]:
    """Return ``(subject_id, date)`` keys already exported to an existing database."""
    if not database_path.exists():
        return set()
    with sqlite3.connect(database_path) as database:
        table_exists = database.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (TABLE_NAME,),
        ).fetchone()
        if table_exists is None:
            return set()
        return {
            (str(subject_id), str(session_date))
            for subject_id, session_date in database.execute(
                f"SELECT subject_id, date FROM {TABLE_NAME}"
            )
        }


async def export_session_rigs(
    task_datas: Iterable[TaskData],
    database_path: Path,
    *,
    reader_count: int,
    queue_size: int,
    rig_reader: Callable[[str], Awaitable[str | None]] = read_rig,
) -> tuple[int, int]:
    read_queue: asyncio.Queue[TaskData | None] = asyncio.Queue(queue_size)
    # Keep completed reads in their own queue so only one coroutine ever writes
    # SQLite. This queue is unbounded so a writer failure cannot deadlock readers.
    write_queue: asyncio.Queue[SessionRig | None] = asyncio.Queue()
    writer = asyncio.create_task(write_results(write_queue, database_path))
    readers = [
        asyncio.create_task(read_worker(read_queue, write_queue, rig_reader))
        for _ in range(reader_count)
    ]

    try:
        for task_data in task_datas:
            await read_queue.put(task_data)
        for _ in readers:
            await read_queue.put(None)
        await asyncio.gather(*readers)
        await write_queue.put(None)
        return await writer
    except BaseException:
        writer.cancel()
        for reader in readers:
            reader.cancel()
        await asyncio.gather(writer, *readers, return_exceptions=True)
        raise


async def read_worker(
    read_queue: asyncio.Queue[TaskData | None],
    write_queue: asyncio.Queue[SessionRig | None],
    rig_reader: Callable[[str], Awaitable[str | None]],
) -> None:
    while True:
        task_data = await read_queue.get()
        if task_data is None:
            return
        try:
            try:
                rig_id = await rig_reader(task_data.task_data_s3_path)
                error = None
            except Exception as exc:  # noqa: BLE001 - retain rows for unreadable files
                rig_id = None
                error = f"{type(exc).__name__}: {exc}"
            await write_queue.put(
                SessionRig(
                    subject_id=task_data.subject_id,
                    date=task_data.date,
                    task_data_s3_path=task_data.task_data_s3_path,
                    rig_id=rig_id,
                    task_data_read_error=error,
                )
            )
        finally:
            read_queue.task_done()


async def write_results(
    write_queue: asyncio.Queue[SessionRig | None],
    database_path: Path,
) -> tuple[int, int]:
    import sqlite_utils

    database = sqlite_utils.Database(database_path)
    table = database[TABLE_NAME].create(
        {
            "subject_id": str,
            "date": str,
            "task_data_s3_path": str,
            "rig_id": str,
            "task_data_read_error": str,
        },
        pk=("subject_id", "date"),
        not_null=("subject_id", "date", "task_data_s3_path"),
        if_not_exists=True,
    )
    batch: list[dict[str, Any]] = []
    written = 0
    errors = 0
    try:
        while True:
            result = await write_queue.get()
            if result is None:
                break
            row = asdict(result)
            batch.append(row)
            errors += result.task_data_read_error is not None
            if len(batch) >= 100:
                table.insert_all(batch, replace=True)
                written += len(batch)
                batch.clear()
                if written % 500 == 0:
                    print(f"Wrote {written} sessions...", flush=True)
        if batch:
            table.insert_all(batch, replace=True)
            written += len(batch)
        return written, errors
    finally:
        database.close()


if __name__ == "__main__":
    asyncio.run(main())
