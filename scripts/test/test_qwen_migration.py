import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import research_pipeline as pipeline
import validate_research_audit as validator


class TestQwenMigration(unittest.TestCase):
    def test_current_registry_uses_qwen_ai(self):
        domains = dict(validator.SOURCES)
        self.assertIn("qwen.ai", domains)
        self.assertNotIn("qwenlm.github.io", domains)

    def test_historical_registries_preserve_old_qwen(self):
        for version in (1, 2):
            registry = [
                ("qwenlm.github.io" if domain == "qwen.ai" else domain, name)
                for domain, name in validator.SOURCES
            ]
            if version == 1:
                registry.append(("reuters.com", "Reuters AI"))
            audit = {
                "schema_version": 1, "registry_version": version, "date": "2026-10-05",
                "sources": [
                    {"domain": domain, "name": name, "status": "checked",
                     "checked_url": f"https://{domain}/", "result": "Historical check."}
                    for domain, name in registry
                ],
            }
            self.assertEqual(validator.validate(audit, "2026-10-05"), [])
            self.assertEqual(pipeline.registry_for_manifest({"registry": registry})[0], version)


if __name__ == "__main__":
    unittest.main()
