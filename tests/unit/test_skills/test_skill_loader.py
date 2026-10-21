"""Tests for skill_loader.py and skill_service.py."""

import unittest
from pathlib import Path

from app.knowledge.skill_service import skill_service, SkillService
from app.utils.skill_loader import load_skill_file, extract_stage_instructions, SkillParseError


class TestSkillLoader(unittest.TestCase):
    def test_catalog_discovery(self):
        issues = skill_service.list_supported_issues()
        self.assertIn("LOGIN-4", issues)
        self.assertIn("LOGIN-3", issues)
        self.assertIn("OBJECT-1", issues)

    def test_load_diagnosis_stage(self):
        loaded = skill_service.load("LOGIN-4", stage="diagnosis")
        self.assertEqual(loaded.issue_code, "LOGIN-4")
        self.assertEqual(loaded.version, 1)
        self.assertEqual(loaded.stage, "diagnosis")
        self.assertIn("LOGIN", loaded.domains)

        # Instructions must contain Purpose, Stage Instructions, and Safety Rules
        self.assertIn("## Purpose", loaded.instructions)
        self.assertIn("## Stage Instructions: DIAGNOSIS", loaded.instructions)
        self.assertIn("## Safety Rules", loaded.instructions)
        self.assertIn("FederationIdentifier", loaded.instructions)

        # Diagnosis must NOT contain resolution procedure
        self.assertNotIn("## Stage Instructions: RESOLUTION", loaded.instructions)

    def test_load_resolution_stage(self):
        loaded = skill_service.load("LOGIN-4", stage="resolution")
        self.assertEqual(loaded.stage, "resolution")
        self.assertIn("## Stage Instructions: RESOLUTION", loaded.instructions)
        self.assertIn("Remediation Procedure", loaded.instructions)
        self.assertIn("## Safety Rules", loaded.instructions)

    def test_load_unknown_issue_raises_key_error(self):
        with self.assertRaises(KeyError):
            skill_service.load("UNKNOWN-999", stage="diagnosis")

    def test_invalid_stage_raises_error(self):
        with self.assertRaises(SkillParseError):
            skill_service.load("LOGIN-4", stage="non_existent_stage")


if __name__ == "__main__":
    unittest.main()
