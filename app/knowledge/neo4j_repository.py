"""Neo4j Knowledge Graph Repository.

Provides read-only access to investigation knowledge, scenario DAGs,
and step-by-step tool dependencies stored in Neo4j (with seamless in-memory CSV fallback).

API:
- get_domain_plan(domain: str) -> dict[str, Any]
- get_scenario_plan(scenario_id: str) -> dict[str, Any] | None
- close()
"""

from __future__ import annotations

import csv
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass

logger = logging.getLogger(__name__)

CSV_PATH = ROOT / "data" / "investigation.csv"
FLOWCHART_JSON_PATH = ROOT / "data" / "login_flowchart_graph.json"


class Neo4jKnowledgeRepository:
    """Read-only access to investigation knowledge in Neo4j with local fallback."""

    def __init__(
        self,
        uri: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        driver: Any | None = None,
    ) -> None:
        self._owns_driver = driver is None
        self._is_connected = False
        self.driver = None

        if driver is not None:
            self.driver = driver
            self._is_connected = True
        else:
            resolved_uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
            resolved_user = username or os.environ.get("NEO4J_USERNAME") or os.environ.get("NEO4J_USER", "neo4j")
            resolved_password = password or os.environ.get("NEO4J_PASSWORD")

            auth = (resolved_user, resolved_password) if resolved_password else None
            try:
                from neo4j import GraphDatabase
                self.driver = GraphDatabase.driver(
                    resolved_uri,
                    auth=auth,
                )
                self.driver.verify_connectivity()
                self._is_connected = True
                logger.info("Successfully connected to Neo4j at %s", resolved_uri)
            except Exception as exc:
                logger.info("Neo4j connectivity not active (%s). Using local CSV knowledge graph fallback.", exc)
                self._is_connected = False

    def is_live(self) -> bool:
        """Return True if connected to a live Neo4j database."""
        return self._is_connected

    # ------------------------------------------------------------------
    # 1. Neo4j Cypher Implementation
    # ------------------------------------------------------------------

    def get_domain_plan(self, domain: str) -> dict[str, Any]:
        """Return all investigation scenarios available for a domain."""
        normalized_domain = domain.strip().upper()

        if self._is_connected and self.driver:
            try:
                with self.driver.session() as session:
                    result = session.run(
                        """
                        MATCH (d:Domain {name: $domain})
                              -[:HAS_SCENARIO]->(s:Scenario)
                        OPTIONAL MATCH (s)-[:GOVERNED_BY]->(sk:Skill)
                        RETURN
                            d.name AS domain,
                            s.id AS scenario_id,
                            s.name AS scenario_name,
                            s.description AS description,
                            sk.id AS skill_id,
                            sk.file AS skill_file,
                            sk.status AS skill_status
                        ORDER BY s.name
                        """,
                        domain=normalized_domain,
                    )
                    scenarios = [record.data() for record in result]

                for scenario in scenarios:
                    scenario["steps"] = self._get_steps(scenario["scenario_id"])

                if scenarios:
                    return {
                        "domain": normalized_domain,
                        "scenarios": scenarios,
                        "source": "neo4j",
                    }
            except Exception as exc:
                logger.warning("Neo4j query error in get_domain_plan: %s. Using fallback.", exc)

        # Fallback to local CSV store
        return self._get_domain_plan_fallback(normalized_domain)

    def get_scenario_plan(self, scenario_id: str) -> dict[str, Any] | None:
        """Return one scenario and its ordered investigation steps."""
        clean_id = scenario_id.strip()

        if self._is_connected and self.driver:
            try:
                with self.driver.session() as session:
                    result = session.run(
                        """
                        MATCH (s:Scenario {id: $scenario_id})
                        OPTIONAL MATCH (d:Domain)-[:HAS_SCENARIO]->(s)
                        OPTIONAL MATCH (s)-[:GOVERNED_BY]->(sk:Skill)
                        RETURN
                            d.name AS domain,
                            s.id AS scenario_id,
                            s.name AS scenario_name,
                            s.description AS description,
                            sk.id AS skill_id,
                            sk.file AS skill_file,
                            sk.status AS skill_status
                        """,
                        scenario_id=clean_id,
                    )
                    record = result.single()

                if record:
                    scenario = record.data()
                    scenario["steps"] = self._get_steps(clean_id)
                    scenario["source"] = "neo4j"
                    return scenario
            except Exception as exc:
                logger.warning("Neo4j query error in get_scenario_plan: %s. Using fallback.", exc)

        # Fallback to local CSV store
        return self._get_scenario_plan_fallback(clean_id)

    def _get_steps(self, scenario_id: str) -> list[dict[str, Any]]:
        with self.driver.session() as session:
            result = session.run(
                """
                MATCH (s:Scenario {id: $scenario_id})
                      -[:HAS_STEP]->(step:InvestigationStep)
                OPTIONAL MATCH (step)-[:MAY_USE_TOOL]->(tool:Tool)
                OPTIONAL MATCH
                    (step)-[:REQUIRES_EVIDENCE]->(e:EvidenceType)
                OPTIONAL MATCH
                    (step)-[:DEPENDS_ON]->(dependency:InvestigationStep)
                RETURN
                    step.id AS step_id,
                    step.name AS name,
                    step.order AS step_order,
                    step.instruction AS instruction,
                    step.stage AS stage,
                    step.execution_mode AS execution_mode,
                    step.approval_required AS approval_required,
                    collect(DISTINCT tool.name) AS tools,
                    collect(DISTINCT e.name) AS evidence_required,
                    collect(DISTINCT dependency.id) AS depends_on
                ORDER BY step_order
                """,
                scenario_id=scenario_id,
            )
            steps = [record.data() for record in result]

        for step in steps:
            for key in ("tools", "evidence_required", "depends_on"):
                step[key] = [value for value in step[key] if value is not None]

        return steps

    # ------------------------------------------------------------------
    # 2. In-Memory CSV Fallback (Guarantees zero downtime offline)
    # ------------------------------------------------------------------

    def _load_csv_rows(self) -> List[Dict[str, Any]]:
        if not CSV_PATH.exists():
            return []

        rows = []
        with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for r in reader:
                rows.append({
                    "domain": (r.get("domain") or "").strip().upper(),
                    "scenario_id": (r.get("scenario_id") or "").strip(),
                    "scenario_name": (r.get("scenario_name") or "").strip(),
                    "scenario_description": (r.get("scenario_description") or "").strip(),
                    "skill_id": (r.get("skill_id") or "").strip(),
                    "skill_file": (r.get("skill_file") or "").strip(),
                    "skill_status": (r.get("skill_status") or "").strip(),
                    "stage": (r.get("stage") or "").strip(),
                    "step_id": (r.get("step_id") or "").strip(),
                    "step_order": int(r.get("step_order") or 0),
                    "step_name": (r.get("step_name") or "").strip(),
                    "instruction": (r.get("instruction") or "").strip(),
                    "tools": [t.strip() for t in (r.get("tools") or "").split("|") if t.strip()],
                    "depends_on": [d.strip() for d in (r.get("depends_on") or "").split("|") if d.strip()],
                    "evidence_required": [e.strip() for e in (r.get("evidence_required") or "").split("|") if e.strip()],
                    "execution_mode": (r.get("execution_mode") or "").strip(),
                    "approval_required": (r.get("approval_required") or "").strip().lower() in ("true", "1", "yes"),
                })
        return rows

    def _get_domain_plan_fallback(self, domain: str) -> dict[str, Any]:
        rows = self._load_csv_rows()
        norm_domain = domain.upper()
        # Handle aliases e.g. OBJECT vs OBJECT_ACCESS
        matching_rows = [
            r for r in rows
            if r["domain"] == norm_domain or r["domain"].replace("_ACCESS", "") == norm_domain
        ]

        scenarios_dict: Dict[str, Dict[str, Any]] = {}
        for r in matching_rows:
            sc_id = r["scenario_id"]
            if sc_id not in scenarios_dict:
                scenarios_dict[sc_id] = {
                    "domain": r["domain"],
                    "scenario_id": sc_id,
                    "scenario_name": r["scenario_name"],
                    "description": r["scenario_description"],
                    "skill_id": r["skill_id"],
                    "skill_file": r["skill_file"],
                    "skill_status": r["skill_status"],
                    "steps": [],
                }
            scenarios_dict[sc_id]["steps"].append({
                "step_id": r["step_id"],
                "name": r["step_name"],
                "step_order": r["step_order"],
                "instruction": r["instruction"],
                "stage": r["stage"],
                "execution_mode": r["execution_mode"],
                "approval_required": r["approval_required"],
                "tools": r["tools"],
                "evidence_required": r["evidence_required"],
                "depends_on": r["depends_on"],
            })

        for sc in scenarios_dict.values():
            sc["steps"].sort(key=lambda x: x["step_order"])

        return {
            "domain": norm_domain,
            "scenarios": list(scenarios_dict.values()),
            "source": "csv_fallback",
        }

    def _get_scenario_plan_fallback(self, scenario_id: str) -> dict[str, Any] | None:
        rows = self._load_csv_rows()
        matching_rows = [r for r in rows if r["scenario_id"].lower() == scenario_id.lower()]
        if not matching_rows:
            return None

        first = matching_rows[0]
        steps = []
        for r in matching_rows:
            steps.append({
                "step_id": r["step_id"],
                "name": r["step_name"],
                "step_order": r["step_order"],
                "instruction": r["instruction"],
                "stage": r["stage"],
                "execution_mode": r["execution_mode"],
                "approval_required": r["approval_required"],
                "tools": r["tools"],
                "evidence_required": r["evidence_required"],
                "depends_on": r["depends_on"],
            })
        steps.sort(key=lambda x: x["step_order"])

        return {
            "domain": first["domain"],
            "scenario_id": first["scenario_id"],
            "scenario_name": first["scenario_name"],
            "description": first["scenario_description"],
            "skill_id": first["skill_id"],
            "skill_file": first["skill_file"],
            "skill_status": first["skill_status"],
            "steps": steps,
            "source": "csv_fallback",
        }

    # ------------------------------------------------------------------
    # 3. Decision Tree Flowchart Knowledge Graph Traversal API
    # ------------------------------------------------------------------

    def _load_local_flowchart_graph(self) -> Dict[str, Any]:
        if not hasattr(self, "_flowchart_cache") or self._flowchart_cache is None:
            if FLOWCHART_JSON_PATH.exists():
                try:
                    with open(FLOWCHART_JSON_PATH, "r", encoding="utf-8") as f:
                        self._flowchart_cache = json.load(f)
                except Exception as e:
                    logger.warning("Error reading %s: %s", FLOWCHART_JSON_PATH, e)
                    self._flowchart_cache = {"nodes": [], "edges": []}
            else:
                self._flowchart_cache = {"nodes": [], "edges": []}
        return self._flowchart_cache

    def get_flowchart_start_node(self, domain: str = "LOGIN") -> Dict[str, Any]:
        """Retrieve root starting node of the decision tree from Neo4j (or local graph)."""
        normalized = domain.strip().upper()
        if self._is_connected and self.driver:
            try:
                with self.driver.session() as session:
                    res = session.run("""
                        MATCH (d:Domain {name: $domain})-[:STARTS_AT]->(start:FlowNode)
                        RETURN properties(start) AS node
                    """, domain=normalized)
                    rec = res.single()
                    if rec and rec["node"]:
                        node_data = dict(rec["node"])
                        node_data["source"] = "neo4j"
                        return node_data
            except Exception as e:
                logger.warning("Neo4j error in get_flowchart_start_node: %s. Using local graph store.", e)

        # Fallback to local graph store
        graph = self._load_local_flowchart_graph()
        start_id = graph.get("start_node_id", "NODE_TRIAGE_RESULT")
        node = self.get_flowchart_node(start_id)
        if node:
            node["source"] = "local_knowledge_graph"
            return node
        return {
            "id": start_id,
            "name": "Triage Result Ingestion",
            "type": "action",
            "swimlane": "Wrong Login Url",
            "source": "local_knowledge_graph",
        }

    def get_flowchart_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve node attributes by ID from Neo4j (or local graph)."""
        if self._is_connected and self.driver:
            try:
                with self.driver.session() as session:
                    res = session.run("""
                        MATCH (n:FlowNode {id: $id})
                        RETURN properties(n) AS node
                    """, id=node_id)
                    rec = res.single()
                    if rec and rec["node"]:
                        node_dict = dict(rec["node"])
                        node_dict["source"] = "neo4j"
                        return node_dict
            except Exception as e:
                logger.warning("Neo4j error in get_flowchart_node: %s. Using local graph store.", e)

        # Local fallback
        graph = self._load_local_flowchart_graph()
        for n in graph.get("nodes", []):
            if n.get("id") == node_id:
                res_node = dict(n)
                res_node["source"] = "local_knowledge_graph"
                return res_node
        return None

    def get_node_transitions(self, node_id: str) -> Dict[str, Optional[str]]:
        """Retrieve outgoing edges (ON_YES, ON_NO, TRANSITIONS_TO) for a node."""
        if self._is_connected and self.driver:
            try:
                with self.driver.session() as session:
                    res = session.run("""
                        MATCH (curr:FlowNode {id: $id})
                        OPTIONAL MATCH (curr)-[:ON_YES]->(yes:FlowNode)
                        OPTIONAL MATCH (curr)-[:ON_NO]->(no:FlowNode)
                        OPTIONAL MATCH (curr)-[:TRANSITIONS_TO]->(nxt:FlowNode)
                        RETURN yes.id AS yes_target, no.id AS no_target, nxt.id AS next_target
                    """, id=node_id)
                    rec = res.single()
                    if rec:
                        return {
                            "yes_target": rec["yes_target"],
                            "no_target": rec["no_target"],
                            "next_target": rec["next_target"],
                            "source": "neo4j",
                        }
            except Exception as e:
                logger.warning("Neo4j error in get_node_transitions: %s. Using local graph store.", e)

        # Local fallback
        graph = self._load_local_flowchart_graph()
        yes_target = None
        no_target = None
        next_target = None

        for edge in graph.get("edges", []):
            if edge.get("from") == node_id:
                e_type = edge.get("type")
                if e_type == "ON_YES":
                    yes_target = edge.get("to")
                elif e_type == "ON_NO":
                    no_target = edge.get("to")
                elif e_type == "TRANSITIONS_TO":
                    next_target = edge.get("to")

        return {
            "yes_target": yes_target,
            "no_target": no_target,
            "next_target": next_target,
            "source": "local_knowledge_graph",
        }

    def close(self) -> None:
        """Close only a driver created by this repository."""
        if self._owns_driver and self.driver is not None:
            try:
                self.driver.close()
            except Exception:
                pass


# Global singleton instance for shared usage
neo4j_repository = Neo4jKnowledgeRepository()
