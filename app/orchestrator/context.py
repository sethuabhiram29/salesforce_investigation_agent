"""Execution context for the investigation workflow.

Manages:
- Tool binding per stage (diagnosis gets read-only, resolution gets write)
- Knowledge service access (PostgreSQL, Neo4j, skills)
- Attempt counting and loop bounds
- Trace recording
"""
