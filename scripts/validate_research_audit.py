#!/usr/bin/env python3
"""Validate the auditable source sweep created by the daily briefing run."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

SOURCES = (
    ("simonwillison.net", "Simon Willison"),
    ("testingcatalog.com", "TestingCatalog"),
    ("the-decoder.com", "The Decoder"),
    ("marktechpost.com", "MarkTechPost"),
    ("venturebeat.com", "VentureBeat"),
    ("anthropic.com", "Anthropic"),
    ("openai.com", "OpenAI"),
    ("openrouter.ai", "OpenRouter Blog"),
    ("blog.google", "Google AI Blog"),
    ("microsoft.ai", "Microsoft AI"),
    ("arxiv.org", "arXiv"),
    ("llm-stats.com", "LLM Stats"),
    ("ollama.com", "Ollama"),
    ("huggingface.co", "Hugging Face"),
    ("techcrunch.com", "TechCrunch"),
    ("theverge.com", "The Verge"),
    ("heise.de", "heise online"),
    ("arstechnica.com", "Ars Technica"),
    ("computerworld.com", "Computerworld"),
    ("cnbc.com", "CNBC"),
    ("github.blog", "GitHub Blog"),
    ("thenewstack.io", "The New Stack"),
    ("semianalysis.com", "SemiAnalysis"),
    ("embracethered.com", "Embrace The Red"),
    ("importai.substack.com", "Import AI"),
    ("interconnects.ai", "Interconnects"),
    ("latent.space", "Latent Space"),
    ("chinatalk.media", "ChinaTalk"),
    ("artificialanalysis.ai", "Artificial Analysis"),
    ("ai.meta.com", "Meta AI"),
    ("mistral.ai", "Mistral"),
    ("x.ai", "xAI"),
    ("openclaw.ai", "OpenClaw Blog"),
    ("shopify.engineering", "Shopify Engineering"),
    ("technologyreview.com", "MIT Technology Review"),
    ("cohere.com", "Cohere"),
    ("qwen.ai", "Qwen"),
    ("aws.amazon.com", "AWS Machine Learning"),
    ("deepmind.google", "Google DeepMind"),
    ("research.google", "Google Research"),
    ("nist.gov", "NIST AI"),
)
REGISTRY_VERSION = 4
# Published audits retain their original source domains and source count.
V3_SOURCES = tuple(("latentspace.com" if domain == "latent.space" else domain, name)
                   for domain, name in SOURCES)
V2_SOURCES = tuple(("qwenlm.github.io" if domain == "qwen.ai" else domain, name)
                   for domain, name in V3_SOURCES)
LEGACY_SOURCES = V2_SOURCES + (("reuters.com", "Reuters AI"),)
SOURCE_REGISTRIES = {1: LEGACY_SOURCES, 2: V2_SOURCES, 3: V3_SOURCES, REGISTRY_VERSION: SOURCES}

VALID_STATUS = {"checked", "unavailable"}


def domain_matches(url: str, domain: str) -> bool:
    host = urlparse(url).hostname or ""
    return host == domain or host.endswith(f".{domain}")


def validate(audit: dict, expected_date: str | None = None) -> list[str]:
    errors: list[str] = []
    expected_date = expected_date or date.today().isoformat()

    if audit.get("schema_version") != 1:
        errors.append("schema_version muss 1 sein")
    if audit.get("date") != expected_date:
        errors.append(f"date muss {expected_date} sein")

    entries = audit.get("sources")
    if not isinstance(entries, list):
        return errors + ["sources muss eine Liste sein"]

    registry_version = audit.get("registry_version", 1)
    registry = SOURCE_REGISTRIES.get(registry_version)
    if registry is None:
        errors.append("registry_version muss 1, 2, 3 oder 4 sein")
        registry = SOURCES
    expected = {domain: name for domain, name in registry}
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append("jeder sources-Eintrag muss ein Objekt sein")
            continue
        domain = entry.get("domain")
        status = entry.get("status")
        checked_url = entry.get("checked_url")
        result = entry.get("result")

        if domain not in expected:
            errors.append(f"unerwartete Quelle: {domain!r}")
            continue
        if domain in seen:
            errors.append(f"Quelle doppelt protokolliert: {domain}")
        seen.add(domain)
        if status not in VALID_STATUS:
            errors.append(f"{domain}: status muss checked oder unavailable sein")
        if not isinstance(checked_url, str) or not domain_matches(checked_url, domain):
            errors.append(f"{domain}: checked_url muss eine URL der Quelle sein")
        if not isinstance(result, str) or not result.strip():
            errors.append(f"{domain}: result darf nicht leer sein")

    missing = sorted(set(expected) - seen)
    if missing:
        errors.append("fehlende Quellen: " + ", ".join(missing))
    return errors


def main() -> int:
    if len(sys.argv) != 3:
        print("Aufruf: validate_research_audit.py AUDIT.json YYYY-MM-DD", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    try:
        audit = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Ungültiges Quellenprotokoll: {exc}", file=sys.stderr)
        return 1

    errors = validate(audit, sys.argv[2])
    if errors:
        print("Quellenprotokoll ungültig:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    source_count = len(SOURCE_REGISTRIES[audit.get("registry_version", 1)])
    print(f"Quellenprotokoll gültig: {source_count}/{source_count} Quellen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
