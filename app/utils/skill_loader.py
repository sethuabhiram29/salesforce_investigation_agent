"""Skill file loader utility.

Parses canonical skill markdown files with YAML frontmatter.
Extracts stage-specific sections and shared safety rules.
Validates metadata (issue_code, title, domains, version).
"""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class SkillParseError(Exception):
    """Raised when a skill markdown file cannot be parsed or is invalid."""
    pass


def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter delimited by triple-dashes (---).

    Returns a tuple of (metadata_dict, body_text).
    """
    pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        raise SkillParseError("Skill file is missing valid YAML frontmatter (--- ... ---).")

    raw_yaml = match.group(1)
    body = match.group(2)

    metadata: Dict[str, Any] = {}
    current_list_key = None

    for line in raw_yaml.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("- ") and current_list_key:
            metadata[current_list_key].append(line[2:].strip())
            continue

        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            if not val:
                metadata[key] = []
                current_list_key = key
            else:
                current_list_key = None
                # parse numeric if possible
                if val.isdigit():
                    metadata[key] = int(val)
                else:
                    metadata[key] = val

    # Validate required frontmatter keys
    required_keys = ["issue_code", "title", "domains", "version"]
    for rk in required_keys:
        if rk not in metadata:
            raise SkillParseError(f"Missing mandatory frontmatter field: '{rk}'.")

    return metadata, body


def parse_sections(body: str) -> Dict[str, str]:
    """Split markdown body into sections by top-level H1 headers (# Section)."""
    sections: Dict[str, str] = {}
    current_title = "preamble"
    lines: List[str] = []

    for line in body.splitlines():
        header_match = re.match(r"^#\s+(.+)$", line)
        if header_match:
            if lines:
                sections[current_title.lower()] = "\n".join(lines).strip()
                lines = []
            current_title = header_match.group(1).strip()
        else:
            lines.append(line)

    if lines:
        sections[current_title.lower()] = "\n".join(lines).strip()

    return sections


def load_skill_file(file_path: Path) -> Dict[str, Any]:
    """Load and parse a canonical skill markdown file."""
    if not file_path.exists():
        raise FileNotFoundError(f"Skill file not found at {file_path}")

    content = file_path.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(content)
    sections = parse_sections(body)

    return {
        "metadata": metadata,
        "sections": sections,
        "raw_body": body,
        "file_path": str(file_path),
    }


def extract_stage_instructions(
    parsed_skill: Dict[str, Any],
    stage: str,
) -> str:
    """Extract stage-specific instructions accompanied by Purpose and Safety Rules.

    Supported stages: 'diagnosis', 'resolution', 'hitl', 'verification'.
    """
    sections = parsed_skill.get("sections", {})
    stage_key = stage.lower()

    if stage_key not in sections:
        raise SkillParseError(
            f"Stage '{stage}' not found in canonical skill sections: {list(sections.keys())}"
        )

    parts = []

    # Metadata Header
    meta = parsed_skill.get("metadata", {})
    parts.append(
        f"# Canonical Skill: {meta.get('title')} ({meta.get('issue_code')}) [v{meta.get('version')}]"
    )

    # Purpose
    if "purpose" in sections:
        parts.append(f"## Purpose\n{sections['purpose']}")

    # Requested Stage Content
    parts.append(f"## Stage Instructions: {stage.upper()}\n{sections[stage_key]}")

    # Shared Safety Rules
    if "safety rules" in sections:
        parts.append(f"## Safety Rules\n{sections['safety rules']}")

    return "\n\n".join(parts)
