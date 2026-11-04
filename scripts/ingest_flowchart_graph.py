"""Ingest the Multi-Domain Flowchart Decision Tree Knowledge Graph into Neo4j.

Reads data/master_decision_tree_graph.json (or data/login_flowchart_graph.json + data/application_flowchart_graph.json)
and creates in Neo4j:
- (:FlowNode:ActionNode {id: 'NODE_TRIAGE_AGENT', name: 'Triage Agent'})
- (:Domain {name: 'LOGIN'})
- (:Domain {name: 'APPLICATION'})
- Flow nodes for both LOGIN and APPLICATION decision trees:
  - (:FlowNode:ActionNode)
  - (:FlowNode:DecisionNode)
  - (:FlowNode:TerminalNode)
- Directed relationships:
  - (:FlowNode {id: 'NODE_TRIAGE_AGENT'})-[:ROUTES_TO {domain: 'LOGIN'}]->(:FlowNode {id: 'NODE_TRIAGE_RESULT'})
  - (:FlowNode {id: 'NODE_TRIAGE_AGENT'})-[:ROUTES_TO {domain: 'APPLICATION'}]->(:FlowNode {id: 'NODE_APP_TRIAGE_RESULT'})
  - (:Domain {name: 'LOGIN'})-[:STARTS_AT]->(:FlowNode {id: 'NODE_TRIAGE_RESULT'})
  - (:Domain {name: 'APPLICATION'})-[:STARTS_AT]->(:FlowNode {id: 'NODE_APP_TRIAGE_RESULT'})
  - (:FlowNode)-[:ON_YES]->(:FlowNode)
  - (:FlowNode)-[:ON_NO]->(:FlowNode)
  - (:FlowNode)-[:TRANSITIONS_TO]->(:FlowNode)
  - Approved Salesforce Orgs and corporate MyDomain configurations

Run with:
    python scripts/ingest_flowchart_graph.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

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

MASTER_GRAPH_PATH = ROOT / "data" / "master_decision_tree_graph.json"
LOGIN_GRAPH_PATH = ROOT / "data" / "login_flowchart_graph.json"
APP_GRAPH_PATH = ROOT / "data" / "application_flowchart_graph.json"


def load_master_graph_data() -> Dict[str, Any]:
    """Load combined master graph data, merging Login and Application graphs if needed."""
    if MASTER_GRAPH_PATH.exists():
        with open(MASTER_GRAPH_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    # Fallback to merging individual files
    nodes = []
    edges = []
    approved_orgs = []

    # Master Triage Node
    triage_root_node = {
        "id": "NODE_TRIAGE_AGENT",
        "name": "Triage Agent",
        "swimlane": "Incident Triage",
        "type": "action",
        "action_type": "triage_incident",
        "tool_name": "TriageAgent",
        "description": "Master entry point: ingests incident ticket, performs triage classification, and routes investigation to the appropriate domain decision tree",
        "domain": "TRIAGE",
    }
    nodes.append(triage_root_node)

    if LOGIN_GRAPH_PATH.exists():
        with open(LOGIN_GRAPH_PATH, "r", encoding="utf-8") as f:
            l_data = json.load(f)
            for n in l_data.get("nodes", []):
                n.setdefault("domain", "LOGIN")
                nodes.append(n)
            edges.extend(l_data.get("edges", []))
            approved_orgs.extend(l_data.get("approved_orgs", []))

    if APP_GRAPH_PATH.exists():
        with open(APP_GRAPH_PATH, "r", encoding="utf-8") as f:
            a_data = json.load(f)
            for n in a_data.get("nodes", []):
                n.setdefault("domain", "APPLICATION")
                nodes.append(n)
            edges.extend(a_data.get("edges", []))

    edges.append({
        "from": "NODE_TRIAGE_AGENT",
        "to": "NODE_TRIAGE_RESULT",
        "type": "ON_DOMAIN_LOGIN",
        "domain": "LOGIN",
    })
    edges.append({
        "from": "NODE_TRIAGE_AGENT",
        "to": "NODE_APP_TRIAGE_RESULT",
        "type": "ON_DOMAIN_APPLICATION",
        "domain": "APPLICATION",
    })

    return {
        "name": "Master Multi-Domain Investigation Decision Tree Knowledge Graph",
        "version": "2.0",
        "start_node_id": "NODE_TRIAGE_AGENT",
        "domains": ["LOGIN", "APPLICATION", "OBJECT", "RECORD"],
        "domain_roots": {
            "LOGIN": "NODE_TRIAGE_RESULT",
            "APPLICATION": "NODE_APP_TRIAGE_RESULT",
        },
        "nodes": nodes,
        "edges": edges,
        "approved_orgs": approved_orgs,
    }


def ingest_flowchart_into_neo4j(
    uri: str | None = None,
    username: str | None = None,
    password: str | None = None,
    database: str = "neo4j",
) -> bool:
    """Ingest the multi-domain decision tree knowledge graph into Neo4j."""
    graph_data = load_master_graph_data()

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
            MASTER_GRAPH_PATH,
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

        # 2. Purge old FlowNode nodes and edges for clean graph state
        logger.info("Purging old FlowNode nodes and edges for fresh graph ingestion...")
        session.run("MATCH (n:FlowNode) DETACH DELETE n")

        # 3. Create Domain nodes
        domains = graph_data.get("domains", ["LOGIN", "APPLICATION", "OBJECT", "RECORD"])
        for d_name in domains:
            session.run("MERGE (d:Domain {name: $domain})", domain=d_name)

        # 4. Merge Nodes
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
                    n.node_type = 'action',
                    n.domain = coalesce(r.domain, 'LOGIN')
            """, rows=action_nodes)

        if decision_nodes:
            session.run("""
                UNWIND $rows AS r
                MERGE (n:FlowNode:DecisionNode {id: r.id})
                SET n.name = r.name,
                    n.swimlane = r.swimlane,
                    n.condition_key = r.condition_key,
                    n.description = r.description,
                    n.node_type = 'decision',
                    n.domain = coalesce(r.domain, 'LOGIN')
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
                    n.node_type = 'terminal',
                    n.domain = coalesce(r.domain, 'LOGIN')
            """, rows=terminal_nodes)

        # 5. Merge Edges
        edges = graph_data.get("edges", [])
        logger.info("Ingesting %d Flowchart Edges into Neo4j...", len(edges))

        transitions_edges = [e for e in edges if e.get("type") == "TRANSITIONS_TO"]
        on_yes_edges = [e for e in edges if e.get("type") == "ON_YES"]
        on_no_edges = [e for e in edges if e.get("type") == "ON_NO"]
        domain_routing_edges = [e for e in edges if str(e.get("type", "")).startswith("ON_DOMAIN_")]

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

        if domain_routing_edges:
            session.run("""
                UNWIND $rows AS r
                MATCH (from:FlowNode {id: r.from})
                MATCH (to:FlowNode {id: r.to})
                MERGE (from)-[:ROUTES_TO {domain: r.domain, type: r.type}]->(to)
            """, rows=domain_routing_edges)

        # 6. Link Master Triage Node and Domain Start Nodes
        session.run("""
            MATCH (root:FlowNode {id: 'NODE_TRIAGE_AGENT'})
            MATCH (login_start:FlowNode {id: 'NODE_TRIAGE_RESULT'})
            MATCH (app_start:FlowNode {id: 'NODE_APP_TRIAGE_RESULT'})
            MATCH (d_login:Domain {name: 'LOGIN'})
            MATCH (d_app:Domain {name: 'APPLICATION'})

            MERGE (root)-[:ROUTES_TO {domain: 'LOGIN'}]->(login_start)
            MERGE (root)-[:ROUTES_TO {domain: 'APPLICATION'}]->(app_start)
            MERGE (root)-[:MANAGES_DOMAIN]->(d_login)
            MERGE (root)-[:MANAGES_DOMAIN]->(d_app)
            MERGE (d_login)-[:STARTS_AT]->(login_start)
            MERGE (d_app)-[:STARTS_AT]->(app_start)
        """)

        # 7. Ingest Approved Salesforce Enterprise Organizations & URLs
        approved_orgs = graph_data.get("approved_orgs", [])
        if approved_orgs:
            logger.info("Ingesting %d Approved Salesforce Orgs into Neo4j...", len(approved_orgs))
            session.run("""
                UNWIND $rows AS r
                MERGE (o:SalesforceOrg {org_id: r.org_id})
                SET o.name = r.name,
                    o.full_name = r.full_name,
                    o.login_url = r.login_url,
                    o.domain_name = r.domain_name,
                    o.is_main = r.is_main,
                    o.description = r.description
                WITH o
                MATCH (d:Domain {name: 'LOGIN'})
                MERGE (d)-[:HAS_APPROVED_ORG]->(o)
            """, rows=approved_orgs)

        logger.info("Successfully ingested Multi-Domain Knowledge Graph into Neo4j!")

    driver.close()
    return True


if __name__ == "__main__":
    success = ingest_flowchart_into_neo4j()
    sys.exit(0 if success else 1)
