#!/usr/bin/env python3
import importlib.util
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "validate_research_audit.py"
spec = importlib.util.spec_from_file_location("validate_research_audit", SCRIPT)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Validator konnte nicht geladen werden: {SCRIPT}")
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class TestResearchAuditValidation(unittest.TestCase):
    def valid_audit(self):
        return {
            "schema_version": 1,
            "registry_version": validator.REGISTRY_VERSION,
            "date": "2026-09-07",
            "sources": [
                {
                    "domain": domain,
                    "name": name,
                    "status": "checked",
                    "checked_url": f"https://{domain}/ai-news",
                    "result": "Keine neue, verifizierbare AI-Meldung im Zeitraum.",
                }
                for domain, name in validator.SOURCES
            ],
        }

    def test_expected_source_set_includes_expanded_coverage(self):
        domains = {domain for domain, _ in validator.SOURCES}
        self.assertEqual(len(domains), 41)
        self.assertNotIn("reuters.com", domains)
        self.assertTrue(
            {
                "openrouter.ai",
                "heise.de",
                "openclaw.ai",
                "shopify.engineering",
                "technologyreview.com",
                "cohere.com",
                "qwen.ai",
                "aws.amazon.com",
                "deepmind.google",
                "research.google",
                "nist.gov",
            }.issubset(domains)
        )

    def test_valid_complete_audit(self):
        self.assertEqual(validator.validate(self.valid_audit(), "2026-09-07"), [])

    def test_legacy_audit_with_reuters_remains_valid(self):
        audit = self.valid_audit()
        del audit["registry_version"]
        for entry in audit["sources"]:
            if entry["domain"] == "qwen.ai":
                entry["domain"] = "qwenlm.github.io"
                entry["checked_url"] = "https://qwenlm.github.io/"
        audit["sources"].append({
            "domain": "reuters.com", "name": "Reuters AI", "status": "checked",
            "checked_url": "https://www.reuters.com/technology/",
            "result": "Historischer Reuters-Check.",
        })
        self.assertEqual(validator.validate(audit, "2026-09-07"), [])

    def test_reuters_is_not_allowed_in_current_audit(self):
        audit = self.valid_audit()
        audit["sources"].append({
            "domain": "reuters.com", "name": "Reuters AI", "status": "checked",
            "checked_url": "https://www.reuters.com/technology/",
            "result": "Should not be requested.",
        })
        self.assertIn("unerwartete Quelle: 'reuters.com'", validator.validate(audit, "2026-09-07"))

    def test_missing_source_fails(self):
        audit = self.valid_audit()
        audit["sources"].pop()
        errors = validator.validate(audit, "2026-09-07")
        self.assertTrue(any(error.startswith("fehlende Quellen:") for error in errors))

    def test_cross_domain_url_fails(self):
        audit = self.valid_audit()
        audit["sources"][0]["checked_url"] = "https://example.com/not-the-source"
        errors = validator.validate(audit, "2026-09-07")
        self.assertIn("simonwillison.net: checked_url muss eine URL der Quelle sein", errors)

    def test_empty_result_fails(self):
        audit = self.valid_audit()
        audit["sources"][0]["result"] = ""
        errors = validator.validate(audit, "2026-09-07")
        self.assertIn("simonwillison.net: result darf nicht leer sein", errors)


if __name__ == "__main__":
    unittest.main()
