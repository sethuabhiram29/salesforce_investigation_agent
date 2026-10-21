"""Knowledge graph query tools.

Tools:
- find_diagnostic_paths: Get investigation paths for a symptom
- get_issue_relationships: Retrieve related issues, evidence, checks
- find_remediation_prerequisites: Get prerequisites for a remediation

These tools wrap the Neo4j repository with parameterized, read-only queries.
Never expose raw Cypher execution to the LLM.
"""
