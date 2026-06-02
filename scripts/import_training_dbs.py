from __future__ import annotations

import argparse
import math
import os
import re
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DBS = (
    (False, REPO_ROOT / "training_dbs" / "DynamicRoutingTraining.sqlite"),
    (True, REPO_ROOT / "training_dbs" / "DynamicRoutingTrainingNSB.sqlite"),
)

SUBJECT_COLUMNS = (
    "nsb",
    "mouse_id",
    "status",
    "purpose",
    "alive",
    "genotype",
    "sex",
    "birthdate",
    "whc",
    "dhc",
    "implant",
    "cannula",
    "cannula_loc",
    "virus",
    "virus_loc",
    "regimen",
    "timeouts",
    "trainer",
    "next_task_version",
    "data_path",
)

SESSION_COLUMNS = (
    "mouse_id",
    "start_time",
    "rig_name",
    "computer_name",
    "task_version",
    "hits",
    "dprime_same_modality",
    "dprime_other_modality_go_stim",
    "quiescent_violations",
    "pass",
    "ignore",
    "hab",
    "ephys",
    "muscimol",
)

ARRAY_COLUMNS = {
    "hits",
    "dprime_same_modality",
    "dprime_other_modality_go_stim",
}

FLOAT_TOKEN_RE = re.compile(
    r"[+-]?(?:nan|inf|(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ImportRows:
    subjects: list[tuple[Any, ...]]
    sessions: list[tuple[Any, ...]]
    skipped_session_header_rows: int


def main() -> None:
    args = parse_args()
    env_file = read_env_file(args.env_file)
    rows = collect_import_rows(DEFAULT_SOURCE_DBS)

    print(
        "Prepared "
        f"{len(rows.subjects)} subjects and {len(rows.sessions)} sessions "
        f"({rows.skipped_session_header_rows} legacy header rows skipped)."
    )

    if args.dry_run:
        return

    with connect(args, env_file) as conn:
        if args.apply_schema:
            apply_schema(conn, args.schema)

        existing_counts = get_target_counts(conn, args.schema)
        print(
            "Target counts before import: "
            f"training_subjects={existing_counts[0]}, "
            f"training_sessions={existing_counts[1]}."
        )

        if not args.append:
            truncate_training_tables(conn, args.schema)

        insert_subjects(conn, args.schema, rows.subjects)
        insert_sessions(conn, args.schema, rows.sessions)
        conn.commit()

        final_counts = get_target_counts(conn, args.schema)
        print(
            "Target counts after import: "
            f"training_subjects={final_counts[0]}, "
            f"training_sessions={final_counts[1]}."
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import legacy Dynamic Routing training SQLite DBs into Postgres."
    )
    parser.add_argument("--host", default=os.getenv("DR_DB_POSTGRES_HOST", "dr-db"))
    parser.add_argument("--port", type=int, default=int(os.getenv("DR_DB_POSTGRES_PORT", "5432")))
    parser.add_argument("--dbname", default=os.getenv("DR_DB_POSTGRES_DB", "dr_db"))
    parser.add_argument("--user", default=os.getenv("DR_DB_POSTGRES_USER"))
    parser.add_argument("--password", default=os.getenv("DR_DB_POSTGRES_PASSWORD"))
    parser.add_argument("--schema", default="sam")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=REPO_ROOT / ".env",
        help="Optional .env file for DR_DB_POSTGRES_* values.",
    )
    parser.add_argument(
        "--apply-schema",
        action="store_true",
        help="Run sql/*.sql before importing.",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append rows instead of replacing sam.training_subjects and sam.training_sessions.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read and transform the SQLite data without connecting to Postgres.",
    )
    return parser.parse_args()


def read_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        value = value.strip().strip("\"'")
        values[key.strip()] = value

    return values


def connect(args: argparse.Namespace, env_file: dict[str, str]) -> psycopg.Connection:
    user = args.user or env_file.get("DR_DB_POSTGRES_USER")
    password = args.password or env_file.get("DR_DB_POSTGRES_PASSWORD")

    return psycopg.connect(
        host=args.host,
        port=args.port,
        dbname=args.dbname,
        user=user,
        password=password,
        connect_timeout=10,
        application_name="dr-db-training-import",
    )


def collect_import_rows(source_dbs: Iterable[tuple[bool, Path]]) -> ImportRows:
    subjects: list[tuple[Any, ...]] = []
    sessions: list[tuple[Any, ...]] = []
    skipped_header_rows = 0
    known_mouse_ids: set[int] = set()

    for nsb, path in source_dbs:
        if not path.exists():
            raise FileNotFoundError(path)

        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row

            for row in conn.execute("SELECT * FROM all_mice"):
                subject = subject_row(nsb, row)
                mouse_id = subject[SUBJECT_COLUMNS.index("mouse_id")]
                if mouse_id in known_mouse_ids:
                    raise ValueError(f"Duplicate mouse_id across source DBs: {mouse_id}")
                known_mouse_ids.add(mouse_id)
                subjects.append(subject)

            for table_name in session_table_names(conn):
                mouse_id = parse_int(table_name)
                if mouse_id not in known_mouse_ids:
                    raise ValueError(f"Session table {table_name} has no all_mice row")

                for row in conn.execute(f'SELECT * FROM "{table_name}"'):
                    if is_legacy_header_row(row):
                        skipped_header_rows += 1
                        continue
                    sessions.append(session_row(mouse_id, row))

    return ImportRows(
        subjects=subjects,
        sessions=sessions,
        skipped_session_header_rows=skipped_header_rows,
    )


def subject_row(nsb: bool, row: sqlite3.Row) -> tuple[Any, ...]:
    return (
        nsb,
        parse_int(row["mouse_id"]),
        clean_text(row["status"]),
        clean_text(row["purpose"]),
        parse_bool(row["alive"]),
        clean_text(row["genotype"]),
        parse_sex(row["sex"]),
        parse_date(row["birthdate"]),
        parse_bool(row["whc"]),
        parse_bool(row["dhc"]),
        clean_text(row["implant"]),
        parse_bool(row["cannula"]),
        clean_text(row["cannula_loc"]),
        clean_text(row["virus"]),
        clean_text(row["virus_loc"]),
        clean_text(row["regimen"]),
        clean_text(row["timeouts"] if "timeouts" in row.keys() else None),
        clean_text(row["trainer"] if "trainer" in row.keys() else None),
        clean_text(row["next_task_version"] if "next_task_version" in row.keys() else None),
        clean_text(row["data_path"] if "data_path" in row.keys() else None),
    )


def session_row(mouse_id: int, row: sqlite3.Row) -> tuple[Any, ...]:
    return (
        mouse_id,
        clean_text(row["start_time"]),
        clean_text(row["rig_name"]),
        clean_text(row["computer_name"] if "computer_name" in row.keys() else None),
        clean_text(row["task_version"]),
        parse_float_array(row["hits"]),
        parse_float_array(row["dprime_same_modality"]),
        parse_float_array(row["dprime_other_modality_go_stim"]),
        parse_int(row["quiescent_violations"]),
        parse_bool(row["pass"] if "pass" in row.keys() else None),
        parse_bool(row["ignore"]),
        parse_bool(row["hab"]),
        parse_bool(row["ephys"]),
        parse_bool(row["muscimol"]),
    )


def session_table_names(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    return [row[0] for row in rows if row[0].isdigit()]


def is_legacy_header_row(row: sqlite3.Row) -> bool:
    start_time = clean_text(row["start_time"])
    return start_time == "start_time"


def clean_text(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    if text == "":
        return None
    return text


def parse_int(value: Any) -> int | None:
    text = clean_text(value)
    if text is None:
        return None

    if text.lower() in {"id", "quiescent_violations"}:
        return None

    numeric = float(text)
    if not numeric.is_integer():
        raise ValueError(f"Expected integer, got {value!r}")
    return int(numeric)


def parse_bool(value: Any) -> bool | None:
    text = clean_text(value)
    if text is None:
        return None

    normalized = text.lower()
    if normalized in {"true", "t", "yes", "y", "1"}:
        return True
    if normalized in {"false", "f", "no", "n", "0"}:
        return False

    if normalized in {"-1", "alive", "whc", "dhc", "cannula", "pass", "ignore", "hab", "ephys", "muscimol"}:
        return None

    raise ValueError(f"Expected boolean-like value, got {value!r}")


def parse_sex(value: Any) -> str | None:
    text = clean_text(value)
    if text is None:
        return None

    normalized = text.lower()
    if normalized in {"male", "female"}:
        return normalized

    raise ValueError(f"Expected sex enum value, got {value!r}")


def parse_date(value: Any) -> date | None:
    text = clean_text(value)
    if text is None:
        return None

    return date.fromisoformat(text[:10])


def parse_float_array(value: Any) -> list[float | None] | None:
    text = clean_text(value)
    if text is None:
        return None

    normalized = text.strip()
    if normalized in ARRAY_COLUMNS:
        return None

    tokens = FLOAT_TOKEN_RE.findall(normalized)
    if not tokens:
        return None

    values: list[float | None] = []
    for token in tokens:
        lower_token = token.lower()
        if "nan" in lower_token:
            values.append(None)
        elif "inf" in lower_token:
            values.append(math.inf if not lower_token.startswith("-") else -math.inf)
        else:
            values.append(float(token))
    return values


def apply_schema(conn: psycopg.Connection, schema: str) -> None:
    if schema != "sam":
        raise ValueError("sql/*.sql currently creates the hard-coded sam schema")

    for path in sorted((REPO_ROOT / "sql").glob("*.sql")):
        conn.execute(path.read_text())


def get_target_counts(conn: psycopg.Connection, schema: str) -> tuple[int, int]:
    query = sql.SQL(
        "SELECT "
        "(SELECT count(*) FROM {}.training_subjects), "
        "(SELECT count(*) FROM {}.training_sessions)"
    ).format(sql.Identifier(schema), sql.Identifier(schema))
    with conn.cursor() as cur:
        cur.execute(query)
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("Could not read target counts")
        return int(row[0]), int(row[1])


def truncate_training_tables(conn: psycopg.Connection, schema: str) -> None:
    query = sql.SQL(
        "TRUNCATE TABLE {}.training_sessions, {}.training_subjects RESTART IDENTITY"
    ).format(sql.Identifier(schema), sql.Identifier(schema))
    conn.execute(query)


def insert_subjects(
    conn: psycopg.Connection, schema: str, rows: list[tuple[Any, ...]]
) -> None:
    query = sql.SQL("INSERT INTO {}.training_subjects ({}) VALUES ({})").format(
        sql.Identifier(schema),
        sql.SQL(", ").join(sql.Identifier(column) for column in SUBJECT_COLUMNS),
        sql.SQL(", ").join(sql.Placeholder() for _ in SUBJECT_COLUMNS),
    )
    with conn.cursor() as cur:
        cur.executemany(query, rows)


def insert_sessions(
    conn: psycopg.Connection, schema: str, rows: list[tuple[Any, ...]]
) -> None:
    placeholders = []
    for column in SESSION_COLUMNS:
        placeholder = sql.Placeholder()
        if column in ARRAY_COLUMNS:
            placeholder = sql.SQL("{}::double precision[]").format(placeholder)
        placeholders.append(placeholder)

    query = sql.SQL("INSERT INTO {}.training_sessions ({}) VALUES ({})").format(
        sql.Identifier(schema),
        sql.SQL(", ").join(sql.Identifier(column) for column in SESSION_COLUMNS),
        sql.SQL(", ").join(placeholders),
    )
    with conn.cursor() as cur:
        cur.executemany(query, rows)


if __name__ == "__main__":
    main()
