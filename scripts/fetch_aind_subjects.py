from __future__ import annotations

import argparse
import json
import sqlite3
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import urljoin

import requests

from fetch_aind_subject_example import normalize_sex, parse_subject_id


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DBS = (
    REPO_ROOT / "training_dbs" / "DynamicRoutingTraining.sqlite",
    REPO_ROOT / "training_dbs" / "DynamicRoutingTrainingNSB.sqlite",
)
DEFAULT_OUTPUT = REPO_ROOT / "training_dbs" / "aind_subject_metadata.json"
DEFAULT_API_HOST = "http://aind-metadata-service/"
DEFAULT_API_PREFIX = "api/v2"
SubjectRecord = tuple[str, bool | None]
MetadataSource = Path | Sequence[Path]


def main() -> None:
    args = parse_args()
    if args.workers < 1:
        raise SystemExit("--workers must be at least 1.")

    source: MetadataSource
    if args.subject_ids:
        source = args.subject_ids
        subject_records = [
            (subject_id, None) for subject_id in read_subject_ids(args.subject_ids)
        ]
    else:
        source = args.source_dbs
        subject_records = read_subject_records(args.source_dbs)

    if not subject_records:
        raise SystemExit(f"No subject IDs found in {describe_source(source)}.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    output_lock = Lock()
    write_results(args.output, source, len(subject_records), results, output_lock)

    if args.workers == 1:
        for subject_id, is_alive in subject_records:
            result = fetch_subject_metadata(subject_id, args, is_alive)
            append_result(
                result,
                results,
                source,
                args,
                len(subject_records),
                output_lock,
            )
    else:
        fetch_subjects_in_parallel(subject_records, source, args, results, output_lock)

    print(f"Wrote AIND metadata for {len(results)} subjects to {args.output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch AIND metadata for subject IDs and write extracted JSON."
    )
    parser.add_argument(
        "--subject-ids",
        type=Path,
        default=None,
        help=(
            "Optional path to a newline-delimited subject ID file. "
            "When omitted, IDs and alive flags are read from the training SQLite DBs."
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
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Path to write JSON output. Defaults to {DEFAULT_OUTPUT}.",
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


def read_subject_records(source_dbs: Sequence[Path]) -> list[SubjectRecord]:
    subject_records: list[SubjectRecord] = []
    seen: dict[str, Path] = {}
    for path in source_dbs:
        if not path.exists():
            raise FileNotFoundError(path)

        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            for row in conn.execute(
                "SELECT mouse_id, alive FROM all_mice ORDER BY rowid"
            ):
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
                subject_records.append((subject_id, parse_alive(row["alive"])))

    return subject_records


def parse_alive(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)

    text = str(value).strip().lower()
    if text == "":
        return None
    if text in {"1", "true", "t", "yes", "y"}:
        return True
    if text in {"0", "false", "f", "no", "n"}:
        return False
    raise ValueError(f"Expected boolean alive value, got {value!r}")


def fetch_subjects_in_parallel(
    subject_records: list[SubjectRecord],
    source: MetadataSource,
    args: argparse.Namespace,
    results: list[dict[str, Any]],
    output_lock: Lock,
) -> None:
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(fetch_subject_metadata, subject_id, args, is_alive): subject_id
            for subject_id, is_alive in subject_records
        }
        for future in as_completed(futures):
            append_result(
                future.result(),
                results,
                source,
                args,
                len(subject_records),
                output_lock,
            )


def append_result(
    result: dict[str, Any],
    results: list[dict[str, Any]],
    source: MetadataSource,
    args: argparse.Namespace,
    total_subjects: int,
    output_lock: Lock,
) -> None:
    with output_lock:
        results.append(result)
        write_results_unlocked(
            args.output,
            source,
            total_subjects,
            results,
        )
        print(
            f"[{len(results)}/{total_subjects}] {result['subject_id']}: {result['status']}"
        )


def write_results(
    output: Path,
    source: MetadataSource,
    total_subjects: int,
    results: list[dict[str, Any]],
    output_lock: Lock,
) -> None:
    with output_lock:
        write_results_unlocked(output, source, total_subjects, results)


def write_results_unlocked(
    output: Path,
    source: MetadataSource,
    total_subjects: int,
    results: list[dict[str, Any]],
) -> None:
    payload = {
        "source": format_source(source),
        "total_subjects": total_subjects,
        "completed_count": len(results),
        "results": sorted(results, key=lambda result: result["subject_id"]),
    }
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def format_source(source: MetadataSource) -> str | list[str]:
    if isinstance(source, Path):
        return str(source)
    return [str(path) for path in source]


def describe_source(source: MetadataSource) -> str:
    if isinstance(source, Path):
        return str(source)
    return ", ".join(str(path) for path in source)


def fetch_subject_metadata(
    subject_id: str, args: argparse.Namespace, is_alive: bool | None = None,
) -> dict[str, Any]:
    try:
        subject = fetch_service_resource(args, "subject", subject_id)
        if not subject:
            return {
                "subject_id": subject_id,
                "status": "not_found",
                "metadata": None,
            }
        should_fetch_procedures = is_alive is True
        procedures = (
            fetch_optional_service_resource(args, "procedures", subject_id)
            if should_fetch_procedures
            else None
        )
        return {
            "subject_id": subject_id,
            "status": "ok",
            "metadata": build_metadata(
                subject,
                procedures,
                procedures_checked=should_fetch_procedures,
            ),
        }
    except Exception as exc:
        return {
            "subject_id": subject_id,
            "status": "error",
            "error": str(exc),
            "metadata": None,
        }


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


def fetch_optional_service_resource(
    args: argparse.Namespace, resource: str, subject_id: str
) -> dict[str, Any] | None:
    try:
        return fetch_service_resource(args, resource, subject_id)
    except requests.RequestException:
        return None


def build_resource_url(
    host: str, api_prefix: str, resource: str, subject_id: str
) -> str:
    base_url = host.rstrip("/") + "/"
    path = f"{api_prefix.strip('/')}/{resource}/{subject_id}"
    return urljoin(base_url, path)


def build_metadata(
    subject: dict[str, Any],
    procedures: dict[str, Any] | None,
    procedures_checked: bool,
) -> dict[str, Any]:
    details = subject.get("subject_details") or {}
    subject_id = parse_subject_id(subject.get("subject_id"))
    surgical_procedures = (
        build_surgical_procedure_rows(subject_id, procedures)
        if procedures_checked
        else None
    )
    return {
        "subject": {
            "birth_date": details.get("date_of_birth"),
            "genotype": details.get("genotype"),
            "implant_id": (
                find_first_nested_value(surgical_procedures, "implant_part_number")
                if surgical_procedures is not None
                else None
            ),
            "perfusion_date": (
                find_procedure_date(surgical_procedures, "Perfusion")
                if surgical_procedures is not None
                else None
            ),
            "sex": normalize_sex(details.get("sex")),
        },
        "surgical_procedures": surgical_procedures,
    }


def build_surgical_procedure_rows(
    subject_id: int | None, procedures: dict[str, Any] | None
) -> list[dict[str, Any]]:
    if not procedures:
        return []

    rows: list[dict[str, Any]] = []
    for procedure in procedures.get("subject_procedures") or []:
        procedure_type = procedure.get("procedure_type")
        if isinstance(procedure_type, str) and "surg" not in procedure_type.lower():
            continue
        rows.append(
            {
                "id": subject_id,
                "procedure": procedure_type,
                "date": procedure.get("start_date"),
            }
        )
    return rows


def find_first_nested_value(rows: list[dict[str, Any]], key: str) -> Any:
    for row in rows:
        if row.get(key) is not None:
            return row[key]
    return None


def find_procedure_date(
    rows: list[dict[str, Any]], procedure_type: str
) -> str | None:
    for row in rows:
        if row.get("procedure") == procedure_type:
            return row.get("date")
    return None


if __name__ == "__main__":
    main()
