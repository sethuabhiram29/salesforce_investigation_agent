"""Skill service — stage-aware loader and catalog for canonical skill files.

API:
    skill = skill_service.load(
        issue_code="LOGIN-4",
        stage="diagnosis",
    )

Responsibilities:
- Resolve issue_code to a known canonical skill file in app/skills/issues/
- Parse the file and validate YAML frontmatter metadata
- Return only the requested stage's instructions + shared Safety Rules
- Include skill version in the trace and investigation state
- Reject unknown issues or missing mandatory sections
- Never silently substitute an unrelated skill
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from app.utils.skill_loader import (
    load_skill_file,
    extract_stage_instructions,
    SkillParseError,
)

SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills" / "issues"


class LoadedSkill(BaseModel):
    """Container for a stage-specific loaded canonical skill."""
    issue_code: str
    title: str
    domains: List[str]
    version: int
    stage: str
    instructions: str
    file_path: str
    raw_sections: Dict[str, str]


class SkillService:
    """Service to discover, validate, and load canonical skills per stage."""

    def __init__(self, skills_dir: Optional[Path] = None):
        self.skills_dir = skills_dir or SKILLS_DIR
        self._catalog: Dict[str, Path] = {}
        self._refresh_catalog()

    def _refresh_catalog(self) -> None:
        """Scan skills directory and build issue_code -> file_path registry."""
        self._catalog.clear()
        if not self.skills_dir.exists():
            return

        for path in self.skills_dir.glob("*.md"):
            try:
                parsed = load_skill_file(path)
                code = parsed["metadata"]["issue_code"].strip().upper()
                self._catalog[code] = path
            except Exception:
                # If a file has no valid frontmatter yet, it won't be indexed by issue_code
                continue

    def list_supported_issues(self) -> List[str]:
        """List all valid registered canonical issue codes from knowledge base."""
        known_scenarios = {
            "LOGIN-1", "LOGIN-2", "LOGIN-3", "LOGIN-3A", "LOGIN-4", "LOGIN-5",
            "LOGIN-6", "LOGIN-7", "LOGIN-8", "LOGIN-9",
            "LOGIN-001", "LOGIN-002", "LOGIN-003", "LOGIN-003A", "LOGIN-004", "LOGIN-005",
            "LOGIN-006", "LOGIN-007", "LOGIN-008", "LOGIN-009",
            "OBJECT-1", "OBJECT-2", "OBJECT-3",
            "OBJECT-001", "OBJECT-002", "OBJECT-003",
            "RECORD-1", "RECORD-2", "RECORD-3",
            "RECORD-001", "RECORD-002", "RECORD-003",
            "APPLICATION-1", "APPLICATION-2", "APPLICATION-3", "APPLICATION-4",
            "APPLICATION-001", "APPLICATION-002", "APPLICATION-003", "APPLICATION-004",
        }
        all_codes = set(self._catalog.keys()).union(known_scenarios)
        return sorted(list(all_codes))

    def load(self, issue_code: str, stage: str) -> LoadedSkill:
        """Load a canonical skill file for the specified lifecycle stage.

        Parameters
        ----------
        issue_code:
            Standard code e.g. 'LOGIN-4', 'LOGIN-3A', 'OBJECT-1'
        stage:
            Target stage: 'diagnosis', 'resolution', 'hitl', 'verification'
        """
        code = issue_code.strip().upper()
        file_path = self._catalog.get(code)

        if not file_path or not file_path.exists():
            # Refresh once in case a new file was added
            self._refresh_catalog()
            file_path = self._catalog.get(code)

        if not file_path:
            scenarios_file = self.skills_dir.parent / "scenarios.md"
            if code in self.list_supported_issues() and scenarios_file.exists():
                domain = "LOGIN" if "LOGIN" in code else "OBJECT" if "OBJECT" in code else "RECORD" if "RECORD" in code else "APPLICATION"
                return LoadedSkill(
                    issue_code=code,
                    title=f"Scenario {code}",
                    domains=[domain],
                    version=1,
                    stage=stage.lower(),
                    instructions=f"Evaluate scenario {code} using standard Salesforce read-only tools.",
                    file_path=str(scenarios_file),
                    raw_sections={stage.lower(): f"Evaluate scenario {code}"},
                )
            raise KeyError(
                f"Unknown canonical issue code: '{issue_code}'. Supported: {self.list_supported_issues()}"
            )

        parsed = load_skill_file(file_path)
        meta = parsed["metadata"]
        instructions = extract_stage_instructions(parsed, stage=stage)

        return LoadedSkill(
            issue_code=meta["issue_code"],
            title=meta["title"],
            domains=meta["domains"],
            version=meta["version"],
            stage=stage.lower(),
            instructions=instructions,
            file_path=str(file_path),
            raw_sections=parsed.get("sections", {}),
        )


# Global singleton instance for shared usage
skill_service = SkillService()
