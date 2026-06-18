from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from aind_data_access_api.document_db import MetadataDbClient


DEFAULT_API_HOST = "api.allenneuraldynamics.org"
DEFAULT_SUBJECT_ID = "805749"


def main() -> None:
    args = parse_args()
    client = MetadataDbClient(
        host=args.host,
        database=args.database,
        collection=args.collection,
        version=args.version,
    )

    records = client.retrieve_docdb_records(
        filter_query={"subject.subject_id": args.subject_id},
        projection={
            "subject.subject_id": 1,
            "subject.sex": 1,
            "subject.date_of_birth": 1,
            "subject.genotype": 1,
            "data_description.project_name": 1,
            "procedures.subject_procedures": 1,
        },
        sort={"created": -1},
        limit=args.limit,
    )
    if not records:
        raise SystemExit(f"No AIND metadata records found for subject {args.subject_id}.")

    example = build_example(records)
    output = json.dumps(example, indent=2, sort_keys=True)

    if args.output:
        args.output.write_text(output + "\n", encoding="utf-8")
        print(f"Wrote example metadata to {args.output}")
    else:
        print(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch AIND metadata that maps to db/migrations/000_core.sql."
    )
    parser.add_argument(
        "--subject-id",
        default=DEFAULT_SUBJECT_ID,
        help=f"Subject ID to fetch. Defaults to the AIND docs example subject {DEFAULT_SUBJECT_ID}.",
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
        "--output",
        type=Path,
        help="Optional path to write the extracted example JSON.",
    )
    return parser.parse_args()


def build_example(records: list[dict[str, Any]]) -> dict[str, Any]:
    record = records[0]
    subject = record.get("subject") or {}
    data_description = record.get("data_description") or {}
    procedures = record.get("procedures") or {}
    subject_procedures = procedures.get("subject_procedures") or []
    surgical_procedures = [
        procedure
        for procedure in subject_procedures
        if is_surgical_procedure(procedure)
    ]
    implant_id = find_first_nested_value(surgical_procedures, "implant_part_number")
    subject_id = parse_subject_id(subject.get("subject_id"))

    return {
        "subject": {
            "birth_date": subject.get("date_of_birth"),
            "genotype": subject.get("genotype"),
            "implant_id": implant_id,
            "perfusion_date": find_procedure_date(surgical_procedures, "Perfusion"),
            "project": normalize_project(data_description.get("project_name")),
            "sex": normalize_sex(subject.get("sex")),
        },
        "surgical_procedures": build_surgical_procedure_rows(
            subject_id, surgical_procedures
        ),
    }


def is_surgical_procedure(procedure: dict[str, Any]) -> bool:
    procedure_type = procedure.get("procedure_type")
    if isinstance(procedure_type, str) and procedure_type.lower() == "surgery":
        return True

    nested_procedures = procedure.get("procedures") or []
    return any(
        isinstance(nested, dict)
        and isinstance(nested.get("procedure_type"), str)
        and "surg" in nested["procedure_type"].lower()
        for nested in nested_procedures
    )


def parse_subject_id(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def normalize_sex(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if normalized == "male":
        return "M"
    if normalized == "female":
        return "F"
    return None


def normalize_project(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().replace(" ", "")
    if normalized in {"DynamicRouting", "Templeton"}:
        return normalized
    return value


def find_first_nested_value(procedures: list[dict[str, Any]], key: str) -> Any:
    for procedure in procedures:
        for nested in procedure.get("procedures") or []:
            if isinstance(nested, dict) and nested.get(key) is not None:
                return nested[key]
    return None


def build_surgical_procedure_rows(
    subject_id: int | None, procedures: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for procedure in procedures:
        for nested in procedure.get("procedures") or []:
            if not isinstance(nested, dict):
                continue
            rows.append(
                {
                    "id": subject_id,
                    "procedure": nested.get("procedure_type"),
                    "date": procedure.get("start_date"),
                }
            )
    return rows


def find_procedure_date(
    procedures: list[dict[str, Any]], procedure_type: str
) -> str | None:
    for procedure in procedures:
        for nested in procedure.get("procedures") or []:
            if not isinstance(nested, dict):
                continue
            if nested.get("procedure_type") == procedure_type:
                return procedure.get("start_date")
    return None


if __name__ == "__main__":
    main()
