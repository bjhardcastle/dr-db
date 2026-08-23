#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "boto3>=1.43.33",
#     "lazynwb==1.0.0.dev3",
#     "sqlite-utils>=3.39",
# ]
# ///

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import tempfile
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse

import boto3
import lazynwb

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from dr_db.hdf5 import read_rig

DEFAULT_S3_URI = "s3://aind-scratch-data/dynamic-routing/DynamicRoutingTask/Data"
DEFAULT_AWS_PROFILE = "aind"
SKIPPED_SUBJECT_DIRECTORIES = frozenset({"000000", "366122", "555555"})
TABLE_NAME = "session_rigs"


@dataclass(frozen=True)
class TaskStim:
    session_id: str
    task_stim_s3_path: str


@dataclass(frozen=True)
class SessionRig:
    session_id: str
    task_stim_s3_path: str
    rig_id: str | None
    read_error: str | None


async def main() -> None:
    args = parse_args()
    if args.readers < 1:
        raise ValueError("--readers must be at least 1")
    if args.queue_size < 1:
        raise ValueError("--queue-size must be at least 1")
    if args.limit is not None and args.limit < 1:
        raise ValueError("--limit must be at least 1")

    bucket, prefix = parse_s3_uri(args.s3_uri)
    aws_session = boto3.Session(profile_name=args.profile)
    expose_aws_credentials(aws_session)
    # FileAccessor otherwise retains one closed accessor for every HDF5 path.
    lazynwb.config.disable_cache = True
    if args.endpoint_url:
        os.environ["AWS_ENDPOINT_URL"] = args.endpoint_url
    s3 = aws_session.client("s3", endpoint_url=args.endpoint_url)

    task_stims = discover_task_stims(s3, bucket, prefix)
    if args.limit is not None:
        task_stims = task_stims[: args.limit]
    print(f"Discovered {len(task_stims)} task-stim files under {args.s3_uri}.")

    database_path = args.output or temporary_database_path()
    if args.output is not None and database_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing file: {database_path}")
    print(f"Writing {TABLE_NAME} to {database_path}")

    written, errors = await export_session_rigs(
        task_stims,
        database_path,
        reader_count=args.readers,
        queue_size=args.queue_size,
    )
    print(f"Wrote {written} sessions ({errors} rig-read errors) to {database_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Discover Dynamic Routing task-stim files, read their rig IDs, and "
            "write one row per session to a temporary SQLite database."
        )
    )
    parser.add_argument("--s3-uri", default=DEFAULT_S3_URI)
    parser.add_argument(
        "--profile",
        default=os.getenv("AWS_PROFILE", DEFAULT_AWS_PROFILE),
        help="AWS profile to use (default: %(default)s).",
    )
    parser.add_argument(
        "--endpoint-url",
        default=None,
        help="Optional S3-compatible endpoint URL.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output database path. By default a new file is made in the OS temp directory.",
    )
    parser.add_argument(
        "--readers",
        type=int,
        default=16,
        help="Number of concurrent HDF5 readers (default: %(default)s).",
    )
    parser.add_argument(
        "--queue-size",
        type=int,
        default=64,
        help="Maximum task-stim files waiting for a reader (default: %(default)s).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Process only the first N sessions; useful for checking credentials.",
    )
    return parser.parse_args()


def parse_s3_uri(uri: str) -> tuple[str, str]:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc:
        raise ValueError(f"Expected an S3 URI like s3://bucket/prefix, got {uri!r}")
    prefix = parsed.path.lstrip("/")
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    return parsed.netloc, prefix


def expose_aws_credentials(session: boto3.Session) -> None:
    """Make boto3's resolved SSO credentials available to lazynwb's S3 clients."""
    credentials = session.get_credentials()
    if credentials is None:
        raise RuntimeError("AWS credentials were not found")
    frozen = credentials.get_frozen_credentials()
    os.environ["AWS_ACCESS_KEY_ID"] = frozen.access_key
    os.environ["AWS_SECRET_ACCESS_KEY"] = frozen.secret_key
    if frozen.token:
        os.environ["AWS_SESSION_TOKEN"] = frozen.token
    else:
        os.environ.pop("AWS_SESSION_TOKEN", None)
    os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
    if session.region_name:
        os.environ["AWS_REGION"] = session.region_name


def discover_task_stims(client: Any, bucket: str, prefix: str) -> list[TaskStim]:
    """Return the first DynamicRouting1 HDF5 file found for each session."""
    task_stims: dict[str, TaskStim] = {}
    paginator = client.get_paginator("list_objects_v2")
    pages: Iterable[Mapping[str, Any]] = paginator.paginate(
        Bucket=bucket,
        Prefix=prefix,
    )
    for page in pages:
        for item in page.get("Contents", []):
            key = item.get("Key")
            if not key or not key.startswith(prefix):
                continue
            relative_path = key[len(prefix) :]
            path_parts = PurePosixPath(relative_path).parts
            if len(path_parts) != 2:
                continue
            subject_name, filename = path_parts
            if subject_name in SKIPPED_SUBJECT_DIRECTORIES:
                continue
            subject_id = parse_subject_id(subject_name)
            if subject_id is None:
                continue
            session_id = parse_task_stim_filename(subject_id, filename)
            if session_id is None:
                continue
            task_stims.setdefault(
                session_id,
                TaskStim(session_id, f"s3://{bucket}/{key}"),
            )
    return sorted(task_stims.values(), key=lambda item: item.session_id)


def parse_subject_id(value: str) -> int | None:
    try:
        subject_id = int(value)
    except ValueError:
        return None
    return subject_id if subject_id > 0 and str(subject_id) == value else None


def parse_task_stim_filename(subject_id: int, filename: str) -> str | None:
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
        if parse_date_text(date_text) is not None:
            return f"{subject_text}_{date_text}"
    return None


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


async def export_session_rigs(
    task_stims: Iterable[TaskStim],
    database_path: Path,
    *,
    reader_count: int,
    queue_size: int,
    rig_reader: Callable[[str], Awaitable[str | None]] = read_rig,
) -> tuple[int, int]:
    read_queue: asyncio.Queue[TaskStim | None] = asyncio.Queue(queue_size)
    # Keep completed reads in their own queue so only one coroutine ever writes
    # SQLite. This queue is unbounded so a writer failure cannot deadlock readers.
    write_queue: asyncio.Queue[SessionRig | None] = asyncio.Queue()
    writer = asyncio.create_task(write_results(write_queue, database_path))
    readers = [
        asyncio.create_task(read_worker(read_queue, write_queue, rig_reader))
        for _ in range(reader_count)
    ]

    try:
        for task_stim in task_stims:
            await read_queue.put(task_stim)
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
    read_queue: asyncio.Queue[TaskStim | None],
    write_queue: asyncio.Queue[SessionRig | None],
    rig_reader: Callable[[str], Awaitable[str | None]],
) -> None:
    while True:
        task_stim = await read_queue.get()
        if task_stim is None:
            return
        try:
            try:
                rig_id = await rig_reader(task_stim.task_stim_s3_path)
                error = None
            except Exception as exc:  # noqa: BLE001 - retain rows for unreadable files
                rig_id = None
                error = f"{type(exc).__name__}: {exc}"
            await write_queue.put(
                SessionRig(
                    session_id=task_stim.session_id,
                    task_stim_s3_path=task_stim.task_stim_s3_path,
                    rig_id=rig_id,
                    read_error=error,
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
            "session_id": str,
            "task_stim_s3_path": str,
            "rig_id": str,
            "read_error": str,
        },
        pk="session_id",
        not_null=("session_id", "task_stim_s3_path"),
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
            errors += result.read_error is not None
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
