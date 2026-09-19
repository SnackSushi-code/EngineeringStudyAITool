from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parents[2]


class RepositoryLayoutTests(unittest.TestCase):
    def test_no_secret_files_are_added_to_repository(self):
        forbidden_names = {".env", ".env.local", ".env.production", "id_rsa", "id_ed25519"}
        found = [
            str(path.relative_to(REPO_ROOT))
            for path in REPO_ROOT.rglob("*")
            if path.is_file() and path.name in forbidden_names
        ]
        self.assertEqual([], found, f"Potential secret files found: {found}")

    def test_required_top_level_architecture_directories_exist(self):
        required = ["apps", "agents", "services", "packages", "integrations", "infra", "docs", "tests"]
        missing = [name for name in required if not (REPO_ROOT / name).is_dir()]
        self.assertEqual([], missing, f"Missing top-level directories: {missing}")


if __name__ == "__main__":
    unittest.main()
