from __future__ import annotations

import argparse
import os
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import boto3
import psycopg
from psycopg import sql

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_S3_URI = "s3://aind-scratch-data/dynamic-routing/DynamicRoutingTask/Data"


@dataclass(frozen=True)
class S3Session:
    subject_id: int
    session_id: str
    date: date


@dataclass(frozen=True)
class S3Inventory:
    subject_ids: tuple[int, ...]
    sessions: tuple[S3Session, ...]


def main() -> None:
    args = parse_args()
    bucket, prefix = parse_s3_uri(args.s3_uri)

    s3 = boto3.client("s3", endpoint_url=args.endpoint_url)
    inventory = discover_inventory(s3, bucket, prefix)

    print(
        f"Discovered {len(inventory.subject_ids)} subjects and "
        f"{len(inventory.sessions)} sessions "
        f"under {args.s3_uri}."
    )
    if args.dry_run:
        for session in inventory.sessions:
            print(f"{session.subject_id}\t{session.session_id}")
        return

    env_file = read_env_file(args.env_file)
    with connect(args, env_file) as conn:
        inserted_subjects, inserted_sessions = insert_s3_ids(
            conn,
            args.schema,
            inventory.subject_ids,
            inventory.sessions,
        )
        conn.commit()

    print(
        f"Inserted {inserted_subjects} subjects and "
        f"{inserted_sessions} sessions."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Add subject and session IDs found in Dynamic Routing S3 data "
            "to Postgres."
        )
    )
    parser.add_argument("--s3-uri", default=DEFAULT_S3_URI)
    parser.add_argument(
        "--endpoint-url",
        default=None,
        help="Optional S3-compatible endpoint URL.",
    )
    parser.add_argument("--schema", default="sam")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=REPO_ROOT / ".env",
        help="Optional .env file for DR_DB_POSTGRES_* values.",
    )
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--dbname", default=None)
    parser.add_argument("--user", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List discovered IDs without connecting to Postgres.",
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


def discover_inventory(client: Any, bucket: str, prefix: str) -> S3Inventory:
    subject_ids: set[int] = set()
    sessions: dict[str, S3Session] = {}
    for subject_prefix in common_prefixes(client, bucket, prefix):
        subject_name = relative_prefix(subject_prefix, prefix)
        if not subject_name or "/" in subject_name:
            continue

        subject_id = parse_subject_id(subject_name)
        if subject_id is None:
            print(f"Skipping non-numeric subject directory: {subject_name}")
            continue
        subject_ids.add(subject_id)

        subject_root = prefix + subject_name + "/"
        for session_prefix in common_prefixes(client, bucket, subject_root):
            session_name = relative_prefix(session_prefix, subject_root)
            session = parse_session(subject_id, session_name)
            if session is None:
                print(
                    f"Skipping session directory that does not match "
                    f"<subject>_<YYYY-MM-DD>: {session_name}"
                )
                continue
            sessions[session.session_id] = session

    sorted_sessions = sorted(
        sessions.values(),
        key=lambda item: (item.subject_id, item.date, item.session_id),
    )
    return S3Inventory(tuple(sorted(subject_ids)), tuple(sorted_sessions))


def discover_sessions(client: Any, bucket: str, prefix: str) -> list[S3Session]:
    """Return discovered sessions; kept as a small convenience for callers."""
    return list(discover_inventory(client, bucket, prefix).sessions)


def common_prefixes(client: Any, bucket: str, prefix: str) -> Iterator[str]:
    paginator = client.get_paginator("list_objects_v2")
    seen: set[str] = set()
    pages: Iterable[Mapping[str, Any]] = paginator.paginate(
        Bucket=bucket,
        Prefix=prefix,
        Delimiter="/",
    )
    for page in pages:
        for item in page.get("CommonPrefixes", []):
            value = item.get("Prefix")
            if value and value not in seen:
                seen.add(value)
                yield value


def relative_prefix(value: str, parent: str) -> str:
    if not value.startswith(parent):
        raise ValueError(f"S3 prefix {value!r} is not below {parent!r}")
    return value[len(parent) :].rstrip("/")


def parse_subject_id(value: str) -> int | None:
    try:
        subject_id = int(value)
    except ValueError:
        return None
    return subject_id if subject_id > 0 and str(subject_id) == value else None


def parse_session(subject_id: int, value: str) -> S3Session | None:
    expected_prefix = f"{subject_id}_"
    if not value.startswith(expected_prefix):
        return None

    session_id = value
    date_text = value[len(expected_prefix) :]
    try:
        session_date = date.fromisoformat(date_text)
    except ValueError:
        return None
    return S3Session(subject_id, session_id, session_date)


def insert_s3_ids(
    conn: psycopg.Connection[Any],
    schema: str,
    subject_ids: Iterable[int],
    sessions: Iterable[S3Session],
) -> tuple[int, int]:
    if not schema.replace("_", "").isalnum():
        raise ValueError(f"Invalid schema name: {schema!r}")

    records = list(sessions)
    subject_ids = sorted(set(subject_ids))
    subject_query = sql.SQL(
        "INSERT INTO {}.subjects (id, project) VALUES (%s, 'DynamicRouting') "
        "ON CONFLICT (id) DO NOTHING"
    ).format(sql.Identifier(schema))
    session_query = sql.SQL(
        "INSERT INTO {}.sessions "
        "(subject_id, date, session_kind, external_session_ids) "
        "SELECT %s, %s, 'training', ARRAY[%s]::text[] "
        "WHERE NOT EXISTS ("
        "SELECT 1 FROM {}.sessions "
        "WHERE external_session_ids @> ARRAY[%s]::text[]"
        ") RETURNING id"
    ).format(sql.Identifier(schema), sql.Identifier(schema))

    inserted_subjects = 0
    inserted_sessions = 0
    with conn.cursor() as cursor:
        for subject_id in subject_ids:
            cursor.execute(subject_query, (subject_id,))
            inserted_subjects += cursor.rowcount

        for session in records:
            cursor.execute(
                session_query,
                (
                    session.subject_id,
                    session.date,
                    session.session_id,
                    session.session_id,
                ),
            )
            inserted_sessions += cursor.rowcount

    return inserted_subjects, inserted_sessions


def read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def connect(
    args: argparse.Namespace,
    env_file: Mapping[str, str],
) -> psycopg.Connection[Any]:
    def setting(name: str, argument: Any, default: Any = None) -> Any:
        if argument is not None:
            return argument
        return os.getenv(name, env_file.get(name, default))

    return psycopg.connect(
        host=setting("DR_DB_POSTGRES_HOST", args.host, "localhost"),
        port=int(setting("DR_DB_POSTGRES_PORT", args.port, 5432)),
        dbname=setting("DR_DB_POSTGRES_DB", args.dbname, "dr_db"),
        user=setting("DR_DB_POSTGRES_USER", args.user),
        password=setting("DR_DB_POSTGRES_PASSWORD", args.password),
        connect_timeout=10,
        application_name="dr-db-s3-id-import",
    )


if __name__ == "__main__":
    main()
