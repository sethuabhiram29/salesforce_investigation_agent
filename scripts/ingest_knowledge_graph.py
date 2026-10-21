"""Knowledge Graph Ingestion Script for Neo4j.

Loads data/investigation.csv into Neo4j graph database modeling:
- Domain
- Scenario
- Skill
- InvestigationStep
- Tool
- EvidenceType
and their dependency and governance relationships.

Run with:
    python scripts/ingest_knowledge_graph.py
"""

from __future__ import annotations

import csv
import logging
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass

from neo4j import GraphDatabase

logger = logging.getLogger(__name__)

CSV_PATH = ROOT / "data" / "investigation.csv"
BATCH_SIZE = 200

ALLOWED_DOMAINS = {
    "LOGIN",
    "OBJECT",
    "RECORD",
    "APPLICATION",
    "OBJECT_ACCESS",
    "RECORD_ACCESS",
    "APPLICATION_ACCESS",
}

REQUIRED_COLUMNS = {
    "domain",
    "scenario_id",
    "scenario_name",
    "scenario_description",
    "skill_id",
    "skill_file",
    "skill_status",
    "stage",
    "step_id",
    "step_order",
    "step_name",
    "instruction",
    "tools",
    "depends_on",
    "evidence_required",
    "execution_mode",
    "approval_required",
    "source_reference",
}


def split_values(value: str | None) -> list[str]:
    """Parse pipe-separated CSV values."""
    if not value:
        return []

    return [
        item.strip()
        for item in value.split("|")
        if item.strip()
    ]


def parse_bool(value: str, row_number: int) -> bool:
    normalized = value.strip().lower()

    if normalized in {"true", "yes", "1"}:
        return True

    if normalized in {"false", "no", "0"}:
        return False

    raise ValueError(
        f"CSV row {row_number}: "
        f"approval_required must be true or false"
    )


def read_csv(path: Path = CSV_PATH) -> list[dict[str, Any]]:
    """Load and validate the complete CSV before database writes."""
    if not path.is_file():
        raise FileNotFoundError(
            f"Investigation CSV not found: {path}"
        )

    with path.open(
        "r",
        newline="",
        encoding="utf-8-sig",
    ) as file:
        reader = csv.DictReader(file)

        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                "Missing CSV columns: "
                + ", ".join(sorted(missing))
            )

        rows = []
        seen_step_ids = set()

        for row_number, raw in enumerate(reader, start=2):
            row = {
                key: (value or "").strip()
                for key, value in raw.items()
                if key is not None
            }

            if not any(row.values()):
                continue

            for field in (
                "domain",
                "scenario_id",
                "scenario_name",
                "skill_id",
                "skill_file",
                "skill_status",
                "source_reference",
            ):
                if not row.get(field):
                    raise ValueError(
                        f"CSV row {row_number}: "
                        f"{field} cannot be blank"
                    )

            if row["domain"] not in ALLOWED_DOMAINS:
                raise ValueError(
                    f"CSV row {row_number}: "
                    f"unsupported domain {row['domain']!r}"
                )

            for field in (
                "step_id",
                "step_order",
                "step_name",
                "instruction",
                "stage",
                "execution_mode",
            ):
                if not row.get(field):
                    raise ValueError(
                        f"CSV row {row_number}: "
                        f"{field} cannot be blank"
                    )

            if row["step_id"] in seen_step_ids:
                raise ValueError(
                    f"Duplicate step_id: {row['step_id']}"
                )

            seen_step_ids.add(row["step_id"])

            try:
                row["step_order"] = int(row["step_order"])
            except ValueError as exc:
                raise ValueError(
                    f"CSV row {row_number}: "
                    "step_order must be an integer"
                ) from exc

            row["tools"] = split_values(row["tools"])
            row["depends_on"] = split_values(row["depends_on"])
            row["evidence_required"] = split_values(
                row["evidence_required"]
            )
            row["approval_required"] = parse_bool(
                row["approval_required"],
                row_number,
            )
            row["_row_number"] = row_number

            rows.append(row)

    if not rows:
        raise ValueError("The investigation CSV contains no rows")

    # Scenario and skill metadata consistency check
    scenario_metadata = {}
    skill_metadata = {}

    for row in rows:
        scenario_key = row["scenario_id"]
        scenario_value = (
            row["domain"],
            row["scenario_name"],
            row["scenario_description"],
            row["skill_id"],
            row["skill_file"],
            row["skill_status"],
        )

        if (
            scenario_key in scenario_metadata
            and scenario_metadata[scenario_key] != scenario_value
        ):
            raise ValueError(
                f"Inconsistent metadata for scenario {scenario_key!r}"
            )

        scenario_metadata[scenario_key] = scenario_value

        skill_key = row["skill_id"]
        skill_value = (row["skill_file"], row["skill_status"])

        if (
            skill_key in skill_metadata
            and skill_metadata[skill_key] != skill_value
        ):
            raise ValueError(
                f"Inconsistent metadata for skill {skill_key!r}"
            )

        skill_metadata[skill_key] = skill_value

    step_ids = {
        row["step_id"]
        for row in rows
    }

    for row in rows:
        for dependency in row["depends_on"]:
            if dependency not in step_ids:
                raise ValueError(
                    f"Step {row['step_id']!r} references "
                    f"unknown dependency {dependency!r}"
                )

            if dependency == row["step_id"]:
                raise ValueError(
                    f"Step {row['step_id']!r} cannot depend on itself"
                )

    return rows


def create_constraints(session) -> None:
    """Create stable identity constraints for graph entities."""
    statements = [
        """
        CREATE CONSTRAINT domain_name IF NOT EXISTS
        FOR (n:Domain) REQUIRE n.name IS UNIQUE
        """,
        """
        CREATE CONSTRAINT scenario_id IF NOT EXISTS
        FOR (n:Scenario) REQUIRE n.id IS UNIQUE
        """,
        """
        CREATE CONSTRAINT skill_id IF NOT EXISTS
        FOR (n:Skill) REQUIRE n.id IS UNIQUE
        """,
        """
        CREATE CONSTRAINT step_id IF NOT EXISTS
        FOR (n:InvestigationStep) REQUIRE n.id IS UNIQUE
        """,
        """
        CREATE CONSTRAINT tool_name IF NOT EXISTS
        FOR (n:Tool) REQUIRE n.name IS UNIQUE
        """,
        """
        CREATE CONSTRAINT evidence_name IF NOT EXISTS
        FOR (n:EvidenceType) REQUIRE n.name IS UNIQUE
        """,
    ]

    for statement in statements:
        session.run(statement).consume()


def chunks(items: list[dict], size: int = BATCH_SIZE):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def write_batches(session, query: str, records: list[dict]) -> None:
    for batch in chunks(records):
        session.run(query, rows=batch).consume()


def unique_records(rows: list[dict], key: str) -> list[dict]:
    """Return one metadata record for each scenario or skill."""
    records = {}

    for row in rows:
        if key == "scenario_id":
            record = {
                "id": row["scenario_id"],
                "domain": row["domain"],
                "name": row["scenario_name"],
                "description": row["scenario_description"],
                "skill_id": row["skill_id"],
            }
        else:
            record = {
                "id": row["skill_id"],
                "file": row["skill_file"],
                "status": row["skill_status"],
            }

        records[record["id"]] = record

    return list(records.values())


def load_knowledge_graph(
    csv_path: Path = CSV_PATH,
    uri: str | None = None,
    username: str | None = None,
    password: str | None = None,
) -> dict[str, int]:
    rows = read_csv(csv_path)

    neo4j_uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = username or os.environ.get("NEO4J_USERNAME") or os.environ.get("NEO4J_USER", "neo4j")
    neo4j_password = password or os.environ.get("NEO4J_PASSWORD")

    auth = (neo4j_user, neo4j_password) if neo4j_password else None
    driver = GraphDatabase.driver(neo4j_uri, auth=auth)

    try:
        driver.verify_connectivity()

        with driver.session() as session:
            create_constraints(session)

            domains = [
                {"name": name}
                for name in sorted(
                    {row["domain"] for row in rows}
                )
            ]

            write_batches(
                session,
                """
                UNWIND $rows AS row
                MERGE (:Domain {name: row.name})
                """,
                domains,
            )

            skills = unique_records(rows, "skill_id")

            write_batches(
                session,
                """
                UNWIND $rows AS row
                MERGE (skill:Skill {id: row.id})
                SET skill.file = row.file,
                    skill.status = row.status
                """,
                skills,
            )

            scenarios = unique_records(rows, "scenario_id")

            write_batches(
                session,
                """
                UNWIND $rows AS row
                MATCH (domain:Domain {name: row.domain})
                MATCH (skill:Skill {id: row.skill_id})
                MERGE (scenario:Scenario {id: row.id})
                SET scenario.name = row.name,
                    scenario.description = row.description
                MERGE (domain)-[:HAS_SCENARIO]->(scenario)
                MERGE (scenario)-[:GOVERNED_BY]->(skill)
                """,
                scenarios,
            )

            steps = [
                {
                    "id": row["step_id"],
                    "scenario_id": row["scenario_id"],
                    "order": row["step_order"],
                    "name": row["step_name"],
                    "instruction": row["instruction"],
                    "stage": row["stage"],
                    "execution_mode": row["execution_mode"],
                    "approval_required": row["approval_required"],
                }
                for row in rows
            ]

            write_batches(
                session,
                """
                UNWIND $rows AS row
                MATCH (scenario:Scenario {id: row.scenario_id})
                MERGE (step:InvestigationStep {id: row.id})
                SET step.name = row.name,
                    step.order = row.order,
                    step.instruction = row.instruction,
                    step.stage = row.stage,
                    step.execution_mode = row.execution_mode,
                    step.approval_required = row.approval_required
                MERGE (scenario)-[:HAS_STEP]->(step)
                """,
                steps,
            )

            evidence_records = [
                {"step_id": row["step_id"], "name": evidence}
                for row in rows
                for evidence in row["evidence_required"]
            ]

            write_batches(
                session,
                """
                UNWIND $rows AS row
                MATCH (step:InvestigationStep {id: row.step_id})
                MERGE (evidence:EvidenceType {name: row.name})
                MERGE (step)-[:REQUIRES_EVIDENCE]->(evidence)
                """,
                evidence_records,
            )

            tool_records = [
                {"step_id": row["step_id"], "name": tool}
                for row in rows
                for tool in row["tools"]
            ]

            write_batches(
                session,
                """
                UNWIND $rows AS row
                MATCH (step:InvestigationStep {id: row.step_id})
                MERGE (tool:Tool {name: row.name})
                MERGE (step)-[:MAY_USE_TOOL]->(tool)
                """,
                tool_records,
            )

            dependency_records = [
                {
                    "step_id": row["step_id"],
                    "dependency_id": dependency,
                }
                for row in rows
                for dependency in row["depends_on"]
            ]

            write_batches(
                session,
                """
                UNWIND $rows AS row
                MATCH (step:InvestigationStep {id: row.step_id})
                MATCH (
                    dependency:InvestigationStep {
                        id: row.dependency_id
                    }
                )
                MERGE (step)-[:DEPENDS_ON]->(dependency)
                """,
                dependency_records,
            )

            counts = {}
            for label, variable in [
                ("Domain", "domains"),
                ("Scenario", "scenarios"),
                ("Skill", "skills"),
                ("InvestigationStep", "steps"),
                ("Tool", "tools"),
                ("EvidenceType", "evidence_types"),
            ]:
                record = session.run(
                    f"MATCH (n:{label}) RETURN count(n) AS total"
                ).single()
                counts[variable] = record["total"]

        logger.info("Knowledge graph loaded: %s", counts)
        print(f"Knowledge graph loaded successfully: {counts}")
        return counts

    finally:
        driver.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        load_knowledge_graph()
    except Exception as exc:
        print(f"Ingestion warning: {exc}")
