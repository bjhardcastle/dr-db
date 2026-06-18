from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from aind_data_access_api.document_db import MetadataDbClient


DEFAULT_API_HOST = "api.allenneuraldynamics.org"
DEFAULT_SUBJECT_ID = "731015"


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
            "name": 1,
            "created": 1,
            "location": 1,
            "subject": 1,
            "procedures.subject_id": 1,
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
        description=(
            "Fetch example AIND subject metadata and surgical procedures "
            "from the DocDB REST API."
        )
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
    procedures = record.get("procedures") or {}
    subject_procedures = procedures.get("subject_procedures") or []

    return {
        "asset": {
            "id": record.get("_id"),
            "name": record.get("name"),
            "created": record.get("created"),
            "location": record.get("location"),
        },
        "subject": record.get("subject"),
        "surgical_procedures": [
            procedure
            for procedure in subject_procedures
            if is_surgical_procedure(procedure)
        ],
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


if __name__ == "__main__":
    main()
