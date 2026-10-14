from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class LayoutTest(unittest.TestCase):
    def test_required_policy_directories_exist(self):
        for relative in (
            ".github/workflows",
            "dependency-policy/lib",
            "dependency-policy/scripts",
            "dependency-policy/templates",
            "dependency-policy/fixtures",
            "docs",
            "reports",
        ):
            self.assertTrue((ROOT / relative).is_dir(), relative)


if __name__ == "__main__":
    unittest.main()
