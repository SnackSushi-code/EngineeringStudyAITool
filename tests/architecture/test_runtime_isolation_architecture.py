import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class RuntimeIsolationArchitectureTests(unittest.TestCase):
    def test_phase_0_4_6_documents_exist(self):
        required = (
            ROOT / "docs/adr/ADR-0013-runtime-isolation-and-process-supervision.md",
            ROOT / "docs/architecture/PHASE-0.4.6-RUNTIME-ISOLATION.md",
            ROOT / "docs/architecture/PHASE-0.4.6-ISOLATION-STATES.md",
            ROOT / "docs/threat-model/PHASE-0.4.6-ISOLATION-THREAT-MODEL.md",
        )
        for path in required:
            self.assertTrue(path.exists(), path)

    def test_architecture_separates_authorization_from_isolation(self):
        text = (
            ROOT / "docs/architecture/PHASE-0.4.6-RUNTIME-ISOLATION.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Authorization", text)
        self.assertIn("Execution Supervisor", text)
        self.assertIn("Worker", text)

    def test_process_failure_is_explicitly_contained(self):
        text = (
            ROOT / "docs/adr/ADR-0013-runtime-isolation-and-process-supervision.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Worker crashes must not crash the core runtime", text)
        self.assertIn("TIMED_OUT", text)

    def test_network_defaults_to_disabled(self):
        text = (
            ROOT / "docs/architecture/PHASE-0.4.6-RUNTIME-ISOLATION.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Network access defaults to disabled.", text)

    def test_credentials_are_not_inherited_by_default(self):
        text = (
            ROOT / "docs/architecture/PHASE-0.4.6-RUNTIME-ISOLATION.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Credentials must never be inherited", text)

    def test_platform_enforcement_is_not_overclaimed(self):
        text = (
            ROOT / "docs/architecture/PHASE-0.4.6-RUNTIME-ISOLATION.md"
        ).read_text(encoding="utf-8")
        self.assertIn("must not claim identical sandbox strength", text)


if __name__ == "__main__":
    unittest.main()
