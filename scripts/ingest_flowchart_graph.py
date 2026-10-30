"""Ingest the Flowchart Decision Tree Knowledge Graph into Neo4j.

Reads data/login_flowchart_graph.json and creates:
- (:Domain {name: 'LOGIN'})
- (:FlowNode:ActionNode)
- (:FlowNode:DecisionNode)
- (:FlowNode:TerminalNode)
and their directed relationships:
- (:FlowNode)-[:ON_YES]->(:FlowNode)
- (:FlowNode)-[:ON_NO]->(:FlowNode)
- (:FlowNode)-[:TRANSITIONS_TO]->(:FlowNode)
- (:Domain)-[:STARTS_AT]->(:FlowNode)

Run with:
    python scripts/ingest_flowchart_graph.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=True)
except ImportError:
    pass

from neo4j import GraphDatabase

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

GRAPH_JSON_PATH = ROOT / "data" / "login_flowchart_graph.json"


def ingest_flowchart_into_neo4j(
    uri: str | None = None,
    username: str | None = None,
    password: str | None = None,
    database: str = "neo4j",
) -> bool:
    """Ingest the decision tree knowledge graph into Neo4j."""
    if not GRAPH_JSON_PATH.exists():
        logger.error("Knowledge graph file %s not found!", GRAPH_JSON_PATH)
        return False

    with open(GRAPH_JSON_PATH, "r", encoding="utf-8") as f:
        graph_data: Dict[str, Any] = json.load(f)

    neo4j_uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = username or os.environ.get("NEO4J_USERNAME") or os.environ.get("NEO4J_USER", "neo4j")
    neo4j_password = password or os.environ.get("NEO4J_PASSWORD")
    auth = (neo4j_user, neo4j_password) if neo4j_password else None

    logger.info("Connecting to Neo4j at %s ...", neo4j_uri)
    try:
        driver = GraphDatabase.driver(neo4j_uri, auth=auth)
        driver.verify_connectivity()
    except Exception as exc:
        logger.warning(
            "Neo4j instance is not currently running (%s). "
            "Graph dataset is verified and stored in %s for local engine query and offline fallback.",
            exc,
            GRAPH_JSON_PATH,
        )
        return False

    with driver.session(database=database) as session:
        # 1. Create constraints
        logger.info("Creating graph schema constraints...")
        try:
            session.run("CREATE CONSTRAINT flow_node_id IF NOT EXISTS FOR (n:FlowNode) REQUIRE n.id IS UNIQUE")
            session.run("CREATE CONSTRAINT domain_name IF NOT EXISTS FOR (d:Domain) REQUIRE d.name IS UNIQUE")
        except Exception as e:
            logger.info("Constraints note: %s", e)

        # 2. Merge Domain
        domain_name = graph_data.get("domain", "LOGIN")
        session.run("MERGE (d:Domain {name: $domain})", domain=domain_name)

        # 2b. Clean existing FlowNode nodes and edges to avoid stale connections
        logger.info("Purging old FlowNode nodes and edges for fresh graph ingestion...")
        session.run("MATCH (n:FlowNode) DETACH DELETE n")

        # 3. Merge Nodes
        nodes = graph_data.get("nodes", [])
        logger.info("Ingesting %d Flowchart Nodes into Neo4j...", len(nodes))

        action_nodes = [n for n in nodes if n.get("type") == "action"]
        decision_nodes = [n for n in nodes if n.get("type") == "decision"]
        terminal_nodes = [n for n in nodes if n.get("type") == "terminal"]

        if action_nodes:
            session.run("""
                UNWIND $rows AS r
                MERGE (n:FlowNode:ActionNode {id: r.id})
                SET n.name = r.name,
                    n.swimlane = r.swimlane,
                    n.action_type = r.action_type,
                    n.tool_name = r.tool_name,
                    n.description = r.description,
                    n.node_type = 'action'
            """, rows=action_nodes)

        if decision_nodes:
            session.run("""
                UNWIND $rows AS r
                MERGE (n:FlowNode:DecisionNode {id: r.id})
                SET n.name = r.name,
                    n.swimlane = r.swimlane,
                    n.condition_key = r.condition_key,
                    n.description = r.description,
                    n.node_type = 'decision'
            """, rows=decision_nodes)

        if terminal_nodes:
            session.run("""
                UNWIND $rows AS r
                MERGE (n:FlowNode:TerminalNode {id: r.id})
                SET n.name = r.name,
                    n.swimlane = r.swimlane,
                    n.status = r.status,
                    n.issue_code = r.issue_code,
                    n.decision_basis = r.decision_basis,
                    n.expected_criteria = r.expected_criteria,
                    n.skill_file = r.skill_file,
                    n.node_type = 'terminal'
            """, rows=terminal_nodes)

        # 4. Merge Edges
        edges = graph_data.get("edges", [])
        logger.info("Ingesting %d Flowchart Edges into Neo4j...", len(edges))

        transitions_edges = [e for e in edges if e.get("type") == "TRANSITIONS_TO"]
        on_yes_edges = [e for e in edges if e.get("type") == "ON_YES"]
        on_no_edges = [e for e in edges if e.get("type") == "ON_NO"]

        if transitions_edges:
            session.run("""
                UNWIND $rows AS r
                MATCH (from:FlowNode {id: r.from})
                MATCH (to:FlowNode {id: r.to})
                MERGE (from)-[:TRANSITIONS_TO]->(to)
            """, rows=transitions_edges)

        if on_yes_edges:
            session.run("""
                UNWIND $rows AS r
                MATCH (from:FlowNode {id: r.from})
                MATCH (to:FlowNode {id: r.to})
                MERGE (from)-[:ON_YES]->(to)
            """, rows=on_yes_edges)

        if on_no_edges:
            session.run("""
                UNWIND $rows AS r
                MATCH (from:FlowNode {id: r.from})
                MATCH (to:FlowNode {id: r.to})
                MERGE (from)-[:ON_NO]->(to)
            """, rows=on_no_edges)

        # 5. Link Domain to Start Node
        start_node_id = graph_data.get("start_node_id", "NODE_TRIAGE_RESULT")
        session.run("""
            MATCH (d:Domain {name: $domain})
            MATCH (start:FlowNode {id: $start_id})
            MERGE (d)-[:STARTS_AT]->(start)
        """, domain=domain_name, start_id=start_node_id)

        logger.info("Successfully ingested Knowledge Graph for Domain '%s' into Neo4j!", domain_name)

    driver.close()
    return True


if __name__ == "__main__":
    success = ingest_flowchart_into_neo4j()
    sys.exit(0 if success else 1)
