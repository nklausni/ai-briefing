"""Explicit development-to-publication coverage, independent of shared URLs.

Headline anchors are a structural guard, not a semantic fact checker. The editor
still verifies the development, release milestone, and equivalence of duplicates.
"""
import hashlib
import json
import re

CHANGE_TYPES = {"announcement", "preview", "public_beta", "general_availability",
                "update", "integration", "research", "security", "policy", "business", "other"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def normalize(value):
    return re.sub(r"[\W_]+", " ", value.casefold()).strip()


def history_id(item):
    # Numbering, first_seen and coverage metadata change without a new story.
    identity = {key: item.get(key) for key in ("title", "date", "summary", "sources")}
    identity["topic_id"] = item.get("topic_id", item.get("topic"))
    return "h-" + hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]


def validate_development(candidate):
    require(candidate.get("change_type") in CHANGE_TYPES, "Candidate needs a valid change_type")
    require(isinstance(candidate.get("development"), str) and
            10 <= len(candidate["development"].strip()) <= 800,
            "Candidate needs one atomic development (10..800 characters)")
    terms = candidate.get("headline_terms")
    require(isinstance(terms, list) and 1 <= len(terms) <= 4 and
            all(isinstance(term, str) and 2 <= len(term.strip()) <= 100 and normalize(term)
                for term in terms), "Candidate needs 1..4 specific headline_terms")
    check_headline(candidate, candidate)


def check_headline(candidate, item):
    title = " " + normalize(item.get("title", "")) + " "
    for term in candidate["headline_terms"]:
        require(" " + normalize(term) + " " in title,
                f"Candidate {candidate['id'] if 'id' in candidate else candidate['title']} "
                f"is missing headline anchor {term!r} in {item.get('title')!r}")


def validate_coverage(candidates, decisions, topics, preserved_items, history):
    selected = {d["id"] for d in decisions if d["decision"] == "selected"}
    mapped = {}
    for topic in topics:
        for item in topic.get("items", []):
            unchanged = item in preserved_items
            ids = item.get("candidate_ids", [])
            if unchanged and not any(i in selected for i in ids):
                continue
            require(isinstance(ids, list) and ids and all(isinstance(i, str) for i in ids)
                    and len(ids) == len(set(ids)), "New briefing item needs distinct candidate_ids")
            require(set(ids) <= selected, "Briefing item references an unknown or unselected candidate")
            urls = {s.get("url") for s in item.get("sources", [])}
            allowed = {e["url"] for i in ids for e in candidates[i]["evidence"]}
            require(urls and urls <= allowed, "Briefing item has unverified evidence for its mapped candidates")
            for candidate_id in ids:
                require(candidate_id not in mapped, "Selected candidate is mapped more than once")
                candidate = candidates[candidate_id]
                require(item.get("change_type") == candidate["change_type"],
                        "Mapped briefing item must preserve candidate change_type")
                require(candidate["url"] in urls, "Mapped candidate original URL is missing from its briefing item")
                check_headline(candidate, item)
                mapped[candidate_id] = {"topic_id": topic.get("id"), "title": item["title"],
                                        "date": item.get("date"), "change_type": item["change_type"]}
    require(set(mapped) == selected, "Selected candidate is not mapped to a concrete briefing item: " +
            ", ".join(sorted(selected - set(mapped))))
    history_by_id = {history_id(item): item for item in history}
    for decision in decisions:
        if decision["decision"] != "duplicate":
            continue
        target = decision.get("duplicate_of")
        require(isinstance(target, dict) and len(target) == 1 and
                next(iter(target), None) in {"candidate_id", "history_id"},
                "Duplicate decision needs concrete duplicate_of candidate_id or history_id")
        if "candidate_id" in target:
            require(isinstance(target["candidate_id"], str) and target["candidate_id"] in mapped,
                    "duplicate_of must reference a selected, published candidate; no duplicate chains")
            item = mapped[target["candidate_id"]]
        else:
            require(isinstance(target["history_id"], str) and target["history_id"] in history_by_id,
                    "duplicate_of references unknown history_id")
            item = history_by_id[target["history_id"]]
        covered_type = item.get("change_type")
        if covered_type is None:
            covered_type = decision.get("covered_change_type")
            require(covered_type in CHANGE_TYPES,
                    "Legacy history duplicate needs reviewed covered_change_type")
        require(covered_type == candidates[decision["id"]]["change_type"],
                "Duplicate change_type differs: preview, beta and GA are separate developments")
        check_headline(candidates[decision["id"]], item)
    return {"mapped": mapped, "duplicates": sum(d["decision"] == "duplicate" for d in decisions)}
