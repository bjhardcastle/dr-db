from __future__ import annotations

import argparse
import json
import sqlite3
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import urljoin

import requests


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DBS = (
    REPO_ROOT / "training_dbs" / "DynamicRoutingTraining.sqlite",
    REPO_ROOT / "training_dbs" / "DynamicRoutingTrainingNSB.sqlite",
)
DEFAULT_OUTPUT_DIR = REPO_ROOT / "training_dbs"
DEFAULT_API_HOST = "http://aind-metadata-service/"
DEFAULT_API_PREFIX = "api/v2"
SUBJECT_OUTPUT_FILENAME = "subject.json"
SURGICAL_RECORDS_OUTPUT_FILENAME = "surgical_records.json"

SUBJECT_COLUMNS = (
    "id",
    "status",
    "purpose",
    "project",
    "nsb",
    "genotype",
    "sex",
    "birth_date",
    "surgery_prep",
    "surgery_notes",
    "implant_id",
    "cannula_location",
    "virus",
    "virus_location",
    "regimen",
    "timeouts",
    "trainer",
    "next_task_version",
    "duragel",
    "notes",
)
SURGICAL_RECORD_COLUMNS = ("subject_id", "procedure", "date")
MetadataSource = Path | Sequence[Path]
FetchRows = tuple[list[dict[str, Any]], str]
FetchRowsFn = Callable[[str, argparse.Namespace], FetchRows]
SortKeyFn = Callable[[dict[str, Any]], tuple[Any, ...]]


def main() -> None:
    args = parse_args()
    if args.workers < 1:
        raise SystemExit("--workers must be at least 1.")

    source: MetadataSource
    if args.subject_ids:
        source = args.subject_ids
        subject_ids = read_subject_ids(args.subject_ids)
    else:
        source = args.source_dbs
        subject_ids = read_subject_ids_from_dbs(args.source_dbs)

    if not subject_ids:
        raise SystemExit(f"No subject IDs found in {describe_source(source)}.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    subject_output = args.output_dir / SUBJECT_OUTPUT_FILENAME
    surgical_records_output = args.output_dir / SURGICAL_RECORDS_OUTPUT_FILENAME

    subject_rows = fetch_subject_records(subject_ids, args, subject_output)
    surgical_record_rows = fetch_surgical_records(
        subject_ids,
        args,
        surgical_records_output,
    )

    print(f"Wrote {len(subject_rows)} subject records to {subject_output}")
    print(
        "Wrote "
        f"{len(surgical_record_rows)} surgical records to {surgical_records_output}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fetch AIND subject and procedure metadata and write row-shaped JSON."
        )
    )
    parser.add_argument(
        "--subject-ids",
        type=Path,
        default=None,
        help=(
            "Optional path to a newline-delimited subject ID file. "
            "When omitted, IDs are read from the training SQLite DBs."
        ),
    )
    parser.add_argument(
        "--source-db",
        dest="source_dbs",
        type=Path,
        action="append",
        default=None,
        help=(
            "SQLite training DB to read all_mice from. May be passed more than once. "
            f"Defaults to {', '.join(str(path) for path in DEFAULT_SOURCE_DBS)}."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=(
            "Directory to write subject.json and surgical_records.json. "
            f"Defaults to {DEFAULT_OUTPUT_DIR}."
        ),
    )
    parser.add_argument("--host", default=DEFAULT_API_HOST)
    parser.add_argument("--api-prefix", default=DEFAULT_API_PREFIX)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument(
        "--workers",
        type=int,
        default=16,
        help="Number of parallel fetch workers. Use 1 to fetch serially.",
    )
    args = parser.parse_args()
    args.source_dbs = tuple(args.source_dbs or DEFAULT_SOURCE_DBS)
    return args


def read_subject_ids(path: Path) -> list[str]:
    subject_ids: list[str] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        subject_id = line.strip().lstrip("\ufeff")
        if not subject_id or subject_id.startswith("#") or subject_id in seen:
            continue
        seen.add(subject_id)
        subject_ids.append(subject_id)
    return subject_ids


def read_subject_ids_from_dbs(source_dbs: Sequence[Path]) -> list[str]:
    subject_ids: list[str] = []
    seen: dict[str, Path] = {}
    for path in source_dbs:
        if not path.exists():
            raise FileNotFoundError(path)

        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            for row in conn.execute("SELECT mouse_id FROM all_mice ORDER BY rowid"):
                parsed_subject_id = parse_subject_id(row["mouse_id"])
                if parsed_subject_id is None:
                    continue

                subject_id = str(parsed_subject_id)
                if subject_id in seen:
                    raise ValueError(
                        "Duplicate subject_id across source DBs: "
                        f"{subject_id} ({seen[subject_id]} and {path})"
                    )

                seen[subject_id] = path
                subject_ids.append(subject_id)

    return subject_ids


def fetch_subject_records(
    subject_ids: list[str],
    args: argparse.Namespace,
    output: Path,
) -> list[dict[str, Any]]:
    return fetch_records(
        subject_ids=subject_ids,
        args=args,
        output=output,
        label="subject",
        fetcher=fetch_subject_record_rows,
        sort_key=subject_sort_key,
    )


def fetch_surgical_records(
    subject_ids: list[str],
    args: argparse.Namespace,
    output: Path,
) -> list[dict[str, Any]]:
    return fetch_records(
        subject_ids=subject_ids,
        args=args,
        output=output,
        label="procedures",
        fetcher=fetch_surgical_record_rows,
        sort_key=surgical_record_sort_key,
    )


def fetch_records(
    subject_ids: list[str],
    args: argparse.Namespace,
    output: Path,
    label: str,
    fetcher: FetchRowsFn,
    sort_key: SortKeyFn,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    output_lock = Lock()
    write_json_records(output, rows, sort_key)
    completed_subjects = 0

    if args.workers == 1:
        for subject_id in subject_ids:
            fetched_rows, message = fetcher(subject_id, args)
            completed_subjects += 1
            append_fetched_rows(
                rows,
                output,
                output_lock,
                sort_key,
                label,
                subject_id,
                fetched_rows,
                message,
                completed_subjects,
                len(subject_ids),
            )
        return rows

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(fetcher, subject_id, args): subject_id
            for subject_id in subject_ids
        }
        for future in as_completed(futures):
            subject_id = futures[future]
            fetched_rows, message = future.result()
            completed_subjects += 1
            append_fetched_rows(
                rows,
                output,
                output_lock,
                sort_key,
                label,
                subject_id,
                fetched_rows,
                message,
                completed_subjects,
                len(subject_ids),
            )

    return rows


def append_fetched_rows(
    rows: list[dict[str, Any]],
    output: Path,
    output_lock: Lock,
    sort_key: SortKeyFn,
    label: str,
    subject_id: str,
    fetched_rows: list[dict[str, Any]],
    message: str,
    completed_subjects: int,
    total_subjects: int,
) -> None:
    with output_lock:
        rows.extend(fetched_rows)
        write_json_records(output, rows, sort_key)
        print(f"[{completed_subjects}/{total_subjects}] {label} {subject_id}: {message}")


def write_json_records(
    output: Path,
    rows: list[dict[str, Any]],
    sort_key: SortKeyFn,
) -> None:
    output.write_text(
        json.dumps(sorted(rows, key=sort_key), indent=2) + "\n",
        encoding="utf-8",
    )


def describe_source(source: MetadataSource) -> str:
    if isinstance(source, Path):
        return str(source)
    return ", ".join(str(path) for path in source)


def fetch_subject_record_rows(subject_id: str, args: argparse.Namespace) -> FetchRows:
    try:
        subject = fetch_service_resource(args, "subject", subject_id)
        if not subject:
            return [], "not found"

        return [build_subject_record(subject_id, subject)], "1 record"
    except Exception as exc:
        return [], f"error: {exc}"


def fetch_surgical_record_rows(subject_id: str, args: argparse.Namespace) -> FetchRows:
    try:
        procedures = fetch_service_resource(args, "procedures", subject_id)
        if not procedures:
            return [], "not found"

        rows = build_surgical_record_rows(parse_subject_id(subject_id), procedures)
        record_label = "record" if len(rows) == 1 else "records"
        return rows, f"{len(rows)} {record_label}"
    except Exception as exc:
        return [], f"error: {exc}"


def fetch_service_resource(
    args: argparse.Namespace, resource: str, subject_id: str
) -> dict[str, Any] | None:
    url = build_resource_url(args.host, args.api_prefix, resource, subject_id)
    response = requests.get(url, timeout=args.timeout)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict) and "data" in payload and payload["data"] is None:
        return None
    if not isinstance(payload, dict):
        raise ValueError(
            f"Expected object response from {url}, got {type(payload).__name__}"
        )
    return payload


def build_resource_url(
    host: str, api_prefix: str, resource: str, subject_id: str
) -> str:
    base_url = host.rstrip("/") + "/"
    path = f"{api_prefix.strip('/')}/{resource}/{subject_id}"
    return urljoin(base_url, path)


def build_subject_record(
    requested_subject_id: str,
    subject: dict[str, Any],
) -> dict[str, Any]:
    details = subject_details(subject)
    subject_id = parse_subject_id(
        subject.get("subject_id")
        or details.get("subject_id")
        or requested_subject_id
    )
    record = empty_subject_record(subject_id)
    record["genotype"] = details.get("genotype")
    record["sex"] = normalize_sex(details.get("sex"))
    record["birth_date"] = details.get("date_of_birth")
    record["implant_id"] = details.get("implant_id") or subject.get("implant_id")
    return record


def subject_details(subject: dict[str, Any]) -> dict[str, Any]:
    details = subject.get("subject_details") or subject.get("subject") or subject
    if not isinstance(details, dict):
        return {}
    return details


def empty_subject_record(subject_id: int | None) -> dict[str, Any]:
    return dict.fromkeys(SUBJECT_COLUMNS) | {"id": subject_id}


def build_surgical_record_rows(
    subject_id: int | None, procedures: dict[str, Any]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for procedure in iter_subject_procedures(procedures):
        if not isinstance(procedure, dict):
            continue

        nested_procedures = [
            nested
            for nested in procedure.get("procedures") or []
            if isinstance(nested, dict)
        ]
        if nested_procedures and is_surgical_procedure_container(
            procedure,
            nested_procedures,
        ):
            for nested in nested_procedures:
                rows.append(
                    surgical_record(
                        subject_id,
                        nested.get("procedure_type"),
                        procedure.get("start_date"),
                    )
                )
            continue

        if is_surgical_procedure_name(procedure.get("procedure_type")):
            rows.append(
                surgical_record(
                    subject_id,
                    procedure.get("procedure_type"),
                    procedure.get("start_date"),
                )
            )

    return dedupe_surgical_records(rows)


def iter_subject_procedures(procedures: dict[str, Any]) -> list[Any]:
    if isinstance(procedures.get("subject_procedures"), list):
        return procedures["subject_procedures"]

    nested_procedures = procedures.get("procedures")
    if isinstance(nested_procedures, dict) and isinstance(
        nested_procedures.get("subject_procedures"),
        list,
    ):
        return nested_procedures["subject_procedures"]

    return []


def is_surgical_procedure_container(
    procedure: dict[str, Any],
    nested_procedures: list[dict[str, Any]],
) -> bool:
    if is_surgical_procedure_name(procedure.get("procedure_type")):
        return True
    return any(
        is_surgical_procedure_name(nested.get("procedure_type"))
        for nested in nested_procedures
    )


def is_surgical_procedure_name(value: Any) -> bool:
    return isinstance(value, str) and "surg" in value.lower()


def surgical_record(
    subject_id: int | None,
    procedure: Any,
    date: Any,
) -> dict[str, Any]:
    record = dict.fromkeys(SURGICAL_RECORD_COLUMNS)
    record["subject_id"] = subject_id
    record["procedure"] = procedure
    record["date"] = date
    return record


def dedupe_surgical_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any, Any]] = set()
    for row in rows:
        key = (row["subject_id"], row["procedure"], row["date"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def parse_subject_id(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    return int(text)


def normalize_sex(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized == "male":
        return "M"
    if normalized == "female":
        return "F"
    return None


def subject_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (row["id"] is None, row["id"])


def surgical_record_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row["subject_id"] is None,
        row["subject_id"],
        row["date"] or "",
        row["procedure"] or "",
    )


if __name__ == "__main__":
    main()
