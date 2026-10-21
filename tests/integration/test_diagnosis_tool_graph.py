"""Integration tests for the diagnosis tool-calling graph.

Verifies:
- LLM → ToolNode → LLM loop works end-to-end with fixtures
- Tool results are correctly appended to state
- Investigation rounds are bounded
- Structured diagnosis output is validated
"""
