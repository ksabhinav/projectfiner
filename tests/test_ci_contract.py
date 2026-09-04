import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class CiContractTests(unittest.TestCase):
    def test_pull_requests_run_every_release_gate(self):
        workflow = (REPO_ROOT / ".github/workflows/deploy.yml").read_text()
        self.assertIn("pull_request:", workflow)
        for command in (
            "npm test",
            "npm audit --omit=dev --audit-level=critical",
            "npm run check:data-quality",
            "npm run check:meghalaya-contract",
            "npm run check:release-manifest",
            "npm run check:release-data",
            "npm run check:versioned-release",
            "npm run build",
            "npm run check:site",
            "npm sbom --sbom-format cyclonedx",
        ):
            self.assertIn(command, workflow)

    def test_pull_requests_never_reach_the_deploy_job(self):
        workflow = (REPO_ROOT / ".github/workflows/deploy.yml").read_text()
        self.assertIn("deploy:\n    needs: quality\n    if: github.event_name != 'pull_request'", workflow)
        self.assertNotIn("actions/dependency-review-action", workflow)

    def test_no_report_quality_command_is_the_package_contract(self):
        package = json.loads((REPO_ROOT / "package.json").read_text())
        self.assertEqual(
            package["scripts"]["check:data-quality"],
            "python3 validate_data.py --waivers .github/validation-waivers --no-report",
        )


if __name__ == "__main__":
    unittest.main()
