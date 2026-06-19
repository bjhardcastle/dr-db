from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import urljoin

import requests

from fetch_aind_subject_example import normalize_sex, parse_subject_id


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUBJECT_IDS = REPO_ROOT / "training_dbs" / "subject_ids.txt"
DEFAULT_OUTPUT = REPO_ROOT / "training_dbs" / "aind_subject_metadata.json"
DEFAULT_API_HOST = "http://aind-metadata-service/"
DEFAULT_API_PREFIX = "api/v2"


def main() -> None:
    args = parse_args()
    if args.workers < 1:
        raise SystemExit("--workers must be at least 1.")

    subject_ids = read_subject_ids(args.subject_ids)
    if not subject_ids:
        raise SystemExit(f"No subject IDs found in {args.subject_ids}.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    output_lock = Lock()
    write_results(args.output, args.subject_ids, len(subject_ids), results, output_lock)

    if args.workers == 1:
        for subject_id in subject_ids:
            result = fetch_subject_metadata(subject_id, args)
            append_result(result, results, args, len(subject_ids), output_lock)
    else:
        fetch_subjects_in_parallel(subject_ids, args, results, output_lock)

    print(f"Wrote AIND metadata for {len(results)} subjects to {args.output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch AIND metadata for subject IDs and write extracted JSON."
    )
    parser.add_argument(
        "--subject-ids",
        type=Path,
        default=DEFAULT_SUBJECT_IDS,
        help=f"Path to a newline-delimited subject ID file. Defaults to {DEFAULT_SUBJECT_IDS}.",
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
        "--include-procedures",
        action="store_true",
        help="Also fetch procedure metadata. This can be slow for some subjects.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Number of parallel fetch workers. Use 1 to fetch serially.",
    )
    return parser.parse_args()


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


def fetch_subjects_in_parallel(
    subject_ids: list[str],
    args: argparse.Namespace,
    results: list[dict[str, Any]],
    output_lock: Lock,
) -> None:
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(fetch_subject_metadata, subject_id, args): subject_id
            for subject_id in subject_ids
        }
        for future in as_completed(futures):
            append_result(
                future.result(),
                results,
                args,
                len(subject_ids),
                output_lock,
            )


def append_result(
    result: dict[str, Any],
    results: list[dict[str, Any]],
    args: argparse.Namespace,
    total_subjects: int,
    output_lock: Lock,
) -> None:
    with output_lock:
        results.append(result)
        write_results_unlocked(
            args.output,
            args.subject_ids,
            total_subjects,
            results,
        )
        print(
            f"[{len(results)}/{total_subjects}] {result['subject_id']}: {result['status']}"
        )


def write_results(
    output: Path,
    source: Path,
    total_subjects: int,
    results: list[dict[str, Any]],
    output_lock: Lock,
) -> None:
    with output_lock:
        write_results_unlocked(output, source, total_subjects, results)


def write_results_unlocked(
    output: Path,
    source: Path,
    total_subjects: int,
    results: list[dict[str, Any]],
) -> None:
    payload = {
        "source": str(source),
        "total_subjects": total_subjects,
        "completed_count": len(results),
        "results": sorted(results, key=lambda result: result["subject_id"]),
    }
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def fetch_subject_metadata(
    subject_id: str, args: argparse.Namespace
) -> dict[str, Any]:
    try:
        subject = fetch_service_resource(args, "subject", subject_id)
        if not subject:
            return {
                "subject_id": subject_id,
                "status": "not_found",
                "metadata": None,
            }
        procedures = (
            fetch_optional_service_resource(args, "procedures", subject_id)
            if args.include_procedures
            else None
        )
        return {
            "subject_id": subject_id,
            "status": "ok",
            "metadata": build_metadata(subject, procedures),
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
    subject: dict[str, Any], procedures: dict[str, Any] | None
) -> dict[str, Any]:
    details = subject.get("subject_details") or {}
    subject_id = parse_subject_id(subject.get("subject_id"))
    surgical_procedures = build_surgical_procedure_rows(subject_id, procedures)
    return {
        "subject": {
            "birth_date": details.get("date_of_birth"),
            "genotype": details.get("genotype"),
            "implant_id": find_first_nested_value(
                surgical_procedures, "implant_part_number"
            ),
            "perfusion_date": find_procedure_date(surgical_procedures, "Perfusion"),
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
