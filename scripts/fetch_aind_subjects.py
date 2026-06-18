from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import urljoin

import requests

from fetch_aind_subject_example import build_example


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SUBJECT_IDS = REPO_ROOT / "training_dbs" / "subject_ids.txt"
DEFAULT_OUTPUT = REPO_ROOT / "training_dbs" / "aind_subject_metadata.json"
DEFAULT_API_HOST = "http://aind-metadata-service/"

PROJECTION = {
    "subject.subject_id": 1,
    "subject.sex": 1,
    "subject.date_of_birth": 1,
    "subject.genotype": 1,
    "procedures.subject_procedures": 1,
}


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
    parser.add_argument("--database", default="metadata_index")
    parser.add_argument("--collection", default="data_assets")
    parser.add_argument("--version", default="v1")
    parser.add_argument(
        "--limit",
        type=int,
        default=1,
        help="Number of matching data asset records to fetch before selecting an example.",
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
        records = fetch_docdb_records(subject_id, args)
        if not records:
            return {
                "subject_id": subject_id,
                "status": "not_found",
                "metadata": None,
            }
        return {
            "subject_id": subject_id,
            "status": "ok",
            "metadata": build_example(records),
        }
    except Exception as exc:
        return {
            "subject_id": subject_id,
            "status": "error",
            "error": str(exc),
            "metadata": None,
        }


def fetch_docdb_records(subject_id: str, args: argparse.Namespace) -> list[dict[str, Any]]:
    url = build_find_url(args.host, args.version, args.database, args.collection)
    params = {
        "filter": json.dumps({"subject.subject_id": subject_id}),
        "projection": json.dumps(PROJECTION),
        "sort": json.dumps({"created": -1}),
        "limit": str(args.limit),
        "skip": "0",
    }
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    records = response.json()
    if not isinstance(records, list):
        raise ValueError(f"Expected list response from {url}, got {type(records).__name__}")
    return records


def build_find_url(host: str, version: str, database: str, collection: str) -> str:
    base_url = host.rstrip("/") + "/"
    return urljoin(base_url, f"{version}/{database}/{collection}/find")


if __name__ == "__main__":
    main()
