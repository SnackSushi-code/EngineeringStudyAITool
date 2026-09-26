from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parents[2]


class RepositoryBoundaryTests(unittest.TestCase):
    def test_required_architecture_documents_exist(self):
        required = [
            "docs/technology/PHASE-0.1-TECHNOLOGY-ARCHITECTURE.md",
            "docs/contracts/PHASE-0.2-SYSTEM-CONTRACTS.md",
            "docs/architecture/PHASE-0.3-ARCHITECTURE-HARDENING.md",
            "docs/architecture/BOUNDARY-MATRIX.md",
            "docs/threat-model/PHASE-0.3-THREAT-MODEL.md",
            "docs/adr/ADR-0005-process-boundaries.md",
            "docs/adr/ADR-0006-configuration-and-secrets.md",
            "docs/adr/ADR-0007-observability-and-audit.md",
        ]
        missing = [p for p in required if not (REPO_ROOT / p).is_file()]
        self.assertEqual([], missing, f"Missing architecture documents: {missing}")

    def test_phase_0_3_hardening_mentions_fail_closed(self):
        document = (REPO_ROOT / "docs/architecture/PHASE-0.3-ARCHITECTURE-HARDENING.md").read_text(encoding="utf-8")
        self.assertIn("fail closed", document.lower())
        self.assertIn("policy broker", document.lower())
        self.assertIn("secrets", document.lower())

    def test_threat_model_contains_security_invariants(self):
        document = (REPO_ROOT / "docs/threat-model/PHASE-0.3-THREAT-MODEL.md").read_text(encoding="utf-8")
        for phrase in (
            "No agent can directly grant itself permission.",
            "Policy failure denies privileged actions.",
            "Secrets are never serialized into model-visible state.",
            "Colony cannot authorize operations.",
        ):
            self.assertIn(phrase, document)

    def test_phase_0_2_contracts_remain_present(self):
        self.assertTrue((REPO_ROOT / "docs/contracts/PHASE-0.2-SYSTEM-CONTRACTS.md").is_file())
        self.assertTrue((REPO_ROOT / "packages/schemas").is_dir())


if __name__ == "__main__":
    unittest.main()
