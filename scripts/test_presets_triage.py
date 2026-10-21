import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.agents.triage.agent import TriageAgent
from app.ui.streamlit_app import SAMPLE_SCENARIOS

agent = TriageAgent()
for name, ticket in SAMPLE_SCENARIOS.items():
    if "CUSTOM" in name:
        continue
    state = {"incident": ticket}
    res = agent.run(state)
    triage = res.get("triage_result", {})
    affected = res.get("affected_user", {})
    mirror = res.get("mirror_user")
    print(f"Preset: {name}")
    print(f"  -> Domain: {triage.get('domain')} (Ambiguous: {triage.get('is_ambiguous')})")
    print(f"  -> Affected User: {affected.get('Email')} | Mirror User: {mirror.get('Email') if mirror else None}")
    print(f"  -> Reasoning: {triage.get('reasoning')}")
    print()
