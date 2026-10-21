import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from neo4j import GraphDatabase
from scripts.ingest_knowledge_graph import (
    read_csv,
    create_constraints,
    write_batches,
    unique_records,
)

def ingest_into_database(db_name: str = "graphkb"):
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=None)
    with driver.session(database=db_name) as session:
        rows = read_csv()
        create_constraints(session)
        
        domains = [{"name": name} for name in sorted({r["domain"] for r in rows})]
        write_batches(session, "UNWIND $rows AS row MERGE (:Domain {name: row.name})", domains)

        skills = unique_records(rows, "skill_id")
        write_batches(session, "UNWIND $rows AS row MERGE (skill:Skill {id: row.id}) SET skill.file = row.file, skill.status = row.status", skills)

        scenarios = unique_records(rows, "scenario_id")
        write_batches(session, """
            UNWIND $rows AS row
            MATCH (domain:Domain {name: row.domain})
            MATCH (skill:Skill {id: row.skill_id})
            MERGE (scenario:Scenario {id: row.id})
            SET scenario.name = row.name, scenario.description = row.description
            MERGE (domain)-[:HAS_SCENARIO]->(scenario)
            MERGE (scenario)-[:GOVERNED_BY]->(skill)
        """, scenarios)

        steps = [{
            "id": r["step_id"], "scenario_id": r["scenario_id"], "order": r["step_order"],
            "name": r["step_name"], "instruction": r["instruction"], "stage": r["stage"],
            "execution_mode": r["execution_mode"], "approval_required": r["approval_required"]
        } for r in rows]
        write_batches(session, """
            UNWIND $rows AS row
            MATCH (scenario:Scenario {id: row.scenario_id})
            MERGE (step:InvestigationStep {id: row.id})
            SET step.name = row.name, step.order = row.order, step.instruction = row.instruction,
                step.stage = row.stage, step.execution_mode = row.execution_mode, step.approval_required = row.approval_required
            MERGE (scenario)-[:HAS_STEP]->(step)
        """, steps)

        evidence_records = [{"step_id": r["step_id"], "name": ev} for r in rows for ev in r["evidence_required"]]
        write_batches(session, "UNWIND $rows AS row MATCH (step:InvestigationStep {id: row.step_id}) MERGE (evidence:EvidenceType {name: row.name}) MERGE (step)-[:REQUIRES_EVIDENCE]->(evidence)", evidence_records)

        tool_records = [{"step_id": r["step_id"], "name": tool} for r in rows for tool in r["tools"]]
        write_batches(session, "UNWIND $rows AS row MATCH (step:InvestigationStep {id: row.step_id}) MERGE (tool:Tool {name: row.name}) MERGE (step)-[:MAY_USE_TOOL]->(tool)", tool_records)

        dependency_records = [{"step_id": r["step_id"], "dependency_id": dep} for r in rows for dep in r["depends_on"]]
        write_batches(session, "UNWIND $rows AS row MATCH (step:InvestigationStep {id: row.step_id}) MATCH (dep:InvestigationStep {id: row.dependency_id}) MERGE (step)-[:DEPENDS_ON]->(dep)", dependency_records)

        c = session.run("MATCH (n) RETURN count(n) as cnt").single()["cnt"]
        print(f"SUCCESS: Database [{db_name}] contains {c} nodes!")

    driver.close()

if __name__ == "__main__":
    ingest_into_database("graphkb")
