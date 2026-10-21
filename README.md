# Salesforce Investigation Agent

AI-driven Salesforce incident investigation agent using LangGraph.

## Architecture

- **Outer Graph**: Investigation lifecycle orchestration (Triage → Diagnosis → Resolution → HITL → Verification)
- **Inner Graph**: LLM ↔ ToolNode tool-calling loop within each stage
- **Canonical Skills**: Markdown files with stage-specific procedures per issue type
- **Knowledge Layer**: PostgreSQL (historical incidents) + Neo4j (diagnostic relationships)

## Setup

```bash
pip install -e ".[dev]"
cp .env.example .env
# Edit .env with your credentials
pytest
```

## Project Structure

See `docs/architecture.md` for full details.
