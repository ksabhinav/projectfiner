import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROVENANCE = ROOT / "public" / "data-contracts" / "north-east-provenance.json"
INVENTORY = ROOT / "public" / "data-contracts" / "north-east-indicator-inventory.json"
BUILDER = ROOT / "db" / "build_north_east_provenance.py"


def git_blob_sha(path):
    content = path.read_bytes()
    payload = b"blob " + str(len(content)).encode("ascii") + b"\0" + content
    return hashlib.sha1(payload).hexdigest()


class NorthEastProvenanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.provenance = json.loads(PROVENANCE.read_text(encoding="utf-8"))

    def test_committed_registry_is_reproducible(self):
        subprocess.run(
            [sys.executable, str(BUILDER), "--check"],
            cwd=ROOT,
            check=True,
        )

    def test_all_eight_artifact_inputs_are_content_addressed(self):
        artifacts = self.provenance["artifactInputs"]
        self.assertEqual(len(artifacts), 8)
        self.assertEqual(len({item["stateSlug"] for item in artifacts}), 8)
        self.assertEqual(len({item["artifactId"] for item in artifacts}), 8)
        for item in artifacts:
            path = ROOT / "public" / item["artifactPath"].lstrip("/")
            self.assertEqual(item["artifactBytes"], path.stat().st_size)
            self.assertEqual(
                item["artifactSha256"],
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
            self.assertEqual(item["artifactGitBlobSha"], git_blob_sha(path))
            self.assertEqual(item["sourceDocumentStatus"], "not-linked")
            self.assertEqual(item["sourcePageStatus"], "not-linked")
            self.assertEqual(item["upstreamExtractionRunStatus"], "not-recorded")
            self.assertEqual(item["rightsReviewStatus"], "not-legally-reviewed")

    def test_inventory_linkage_and_limits_are_explicit(self):
        product = self.provenance["product"]
        self.assertEqual(
            product["artifactSha256"],
            hashlib.sha256(INVENTORY.read_bytes()).hexdigest(),
        )
        self.assertEqual(product["artifactBytes"], INVENTORY.stat().st_size)
        self.assertEqual(
            product["schemaVersion"], "north-east-field-inventory-v1"
        )
        build = self.provenance["build"]
        self.assertTrue(build["reproducibleFromCommittedArtifacts"])
        self.assertFalse(build["sourceArtifactExtractionReproducible"])
        self.assertEqual(build["inputArtifactCount"], 8)


if __name__ == "__main__":
    unittest.main()
