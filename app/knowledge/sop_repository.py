"""Knowledge Base SOP Repository.

Dynamically loads canonical Standard Operating Procedures (SOPs) and historical
incidents directly from the user's Excel files in data/:
- data/sop_scenarios_selected_sheets.xlsx (Sheet: 'sop_scenarios')
- data/historical_incidents.xlsx
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent.parent
SOP_EXCEL_PATH = ROOT / "data" / "sop_scenarios_selected_sheets.xlsx"
HIST_EXCEL_PATH = ROOT / "data" / "historical_incidents.xlsx"


def normalize_issue_code(code: str) -> str:
    """Normalize issue code format between 3-digit and standard:
    e.g. 'LOGIN-001' -> 'LOGIN-1', 'LOGIN-003A' -> 'LOGIN-3A', 'OBJECT-002' -> 'OBJECT-2'.
    """
    if not code:
        return ""
    code_clean = str(code).strip().upper()

    # Specific normalization: Unify delegated admin deactivation (LOGIN-3A) into canonical LOGIN-3
    if code_clean in ["LOGIN-3A", "LOGIN-003A"]:
        return "LOGIN-3"
    if code_clean in ["LOGIN-1B", "LOGIN-001B"]:
        return "LOGIN-1"

    # Pattern for DOMAIN-00X(A)
    m = re.match(r"^([A-Z]+)-0*(\d+)([A-Z]*)$", code_clean)
    if m:
        prefix, num, suffix = m.groups()
        if prefix == "LOGIN" and num == "3" and suffix == "A":
            return "LOGIN-3"
        return f"{prefix}-{num}{suffix}"

    return code_clean


def denormalize_issue_code(code: str) -> str:
    """Convert standard issue code to 3-digit format:
    e.g. 'LOGIN-1' -> 'LOGIN-001', 'OBJECT-2' -> 'OBJECT-002'.
    """
    if not code:
        return ""
    code_clean = str(code).strip().upper()
    m = re.match(r"^([A-Z]+)-(\d+)([A-Z]*)$", code_clean)
    if m:
        prefix, num, suffix = m.groups()
        return f"{prefix}-{int(num):03d}{suffix}"
    return code_clean


class SOPKnowledgeRepository:
    """Repository that dynamically loads SOPs and historical incidents from Excel knowledge base."""

    def __init__(self, sop_path: Path = SOP_EXCEL_PATH, hist_path: Path = HIST_EXCEL_PATH):
        self.sop_path = sop_path
        self.hist_path = hist_path
        self._sops_by_code: Dict[str, Dict[str, Any]] = {}
        self._sops_by_domain: Dict[str, List[Dict[str, Any]]] = {
            "LOGIN": [],
            "OBJECT": [],
            "RECORD": [],
            "APPLICATION": [],
        }
        self._domain_catalog: Dict[str, List[str]] = {
            "LOGIN": [],
            "OBJECT": [],
            "RECORD": [],
            "APPLICATION": [],
        }
        self._historical_incidents: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        """Load and index SOPs and historical incidents from the user's Excel files."""
        # 1. Load SOP Scenarios Excel
        if self.sop_path.exists():
            try:
                df = pd.read_excel(self.sop_path, sheet_name="sop_scenarios")
                for _, row in df.iterrows():
                    raw_id = str(row.get("id", "")).strip()
                    norm_code = normalize_issue_code(raw_id)
                    domain = str(row.get("domain", "")).strip().upper()
                    if not domain:
                        domain = self._code_to_domain(norm_code)

                    sop_item = {
                        "id": raw_id,
                        "code": norm_code,
                        "domain": domain,
                        "description": str(row.get("description", "")).strip(),
                        "prerequisites": str(row.get("prerequisites", "")).strip(),
                        "resolution_steps": str(row.get("resolution_steps", "")).strip(),
                    }

                    # Index by both raw_id (e.g. LOGIN-001) and norm_code (e.g. LOGIN-1)
                    self._sops_by_code[raw_id.upper()] = sop_item
                    self._sops_by_code[norm_code.upper()] = sop_item

                    self._sops_by_domain.setdefault(domain, []).append(sop_item)
                    if norm_code not in self._domain_catalog.setdefault(domain, []):
                        self._domain_catalog[domain].append(norm_code)

                # Ensure LOGIN-3A is aliased to canonical LOGIN-3 in sops_by_code without creating duplicate catalog entry
                if "LOGIN-3" in self._sops_by_code:
                    self._sops_by_code["LOGIN-3A"] = self._sops_by_code["LOGIN-3"]
                    self._sops_by_code["LOGIN-003A"] = self._sops_by_code["LOGIN-3"]

                logger.info(
                    "SOPKnowledgeRepository loaded %d SOPs from %s across domains: %s",
                    len(df),
                    self.sop_path,
                    {k: len(v) for k, v in self._domain_catalog.items()},
                )
            except Exception as exc:
                logger.error("Failed to load SOP scenarios from %s: %s", self.sop_path, exc)
                self._load_fallback_catalog()
        else:
            logger.warning("SOP Excel file not found at %s. Using default catalog.", self.sop_path)
            self._load_fallback_catalog()

        # 2. Load Historical Incidents Excel
        if self.hist_path.exists():
            try:
                df_hist = pd.read_excel(self.hist_path)
                for _, row in df_hist.iterrows():
                    self._historical_incidents.append({
                        "incident_id": str(row.get("incident_id", "")).strip(),
                        "domain": str(row.get("domain", "")).strip().capitalize(),
                        "summary": str(row.get("summary", "")).strip(),
                        "description": str(row.get("description", "")).strip(),
                        "root_cause": str(row.get("root_cause", "")).strip(),
                        "resolution": str(row.get("resolution", "")).strip(),
                        "similarity": 0.85,
                    })
                logger.info("Loaded %d historical incidents from %s", len(self._historical_incidents), self.hist_path)
            except Exception as exc:
                logger.error("Failed to load historical incidents from %s: %s", self.hist_path, exc)

    def _load_fallback_catalog(self):
        self._domain_catalog = {
            "LOGIN": ["LOGIN-1", "LOGIN-2", "LOGIN-3", "LOGIN-4", "LOGIN-5", "LOGIN-6", "LOGIN-7", "LOGIN-8", "LOGIN-9"],
            "OBJECT": ["OBJECT-1", "OBJECT-2", "OBJECT-3"],
            "RECORD": ["RECORD-1", "RECORD-2", "RECORD-3"],
            "APPLICATION": ["APPLICATION-1", "APPLICATION-2", "APPLICATION-3", "APPLICATION-4"],
        }

    def _code_to_domain(self, code: str) -> str:
        code_u = code.upper()
        if "LOGIN" in code_u:
            return "LOGIN"
        if "OBJECT" in code_u:
            return "OBJECT"
        if "RECORD" in code_u:
            return "RECORD"
        if "APPLICATION" in code_u or "APP" in code_u:
            return "APPLICATION"
        return "LOGIN"

    def get_domain_catalog(self, domain: str) -> List[str]:
        """Return all SOP issue codes for a domain loaded directly from knowledge base."""
        dom = domain.strip().upper()
        return list(self._domain_catalog.get(dom, []))

    def get_all_sops(self) -> Dict[str, Dict[str, Any]]:
        """Return mapping of issue code to SOP details."""
        return self._sops_by_code

    def get_sop(self, code: str) -> Optional[Dict[str, Any]]:
        """Retrieve SOP details by issue code (accepts LOGIN-001 or LOGIN-1)."""
        norm = normalize_issue_code(code)
        return self._sops_by_code.get(norm) or self._sops_by_code.get(code.upper())

    def get_historical_incidents(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return historical incidents from knowledge base, optionally filtered by domain."""
        if not domain:
            return list(self._historical_incidents)
        dom_u = domain.strip().upper()
        return [c for c in self._historical_incidents if str(c.get("domain", "")).strip().upper() == dom_u]


# Singleton instance
sop_repository = SOPKnowledgeRepository()
