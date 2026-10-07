#!/usr/bin/env python3
"""Read-only, paginated editorial context; complete evidence stays on disk."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from research_pipeline import read, require
from editorial_coverage import history_id

MAX_OUTPUT_CHARS = 12000
PAGE_SIZE = 8


def short(value, maximum):
    return str(value or "")[:maximum]


def root_for(run):
    return Path(read(Path(run) / "manifest.json")["root"])


def page(items, offset=0, limit=PAGE_SIZE, **metadata):
    require(isinstance(offset, int) and 0 <= offset <= len(items), "Invalid page offset")
    require(isinstance(limit, int) and 1 <= limit <= 20, "Page size must be 1..20")
    end = min(len(items), offset + limit)
    while True:
        result = {**metadata, "total": len(items), "offset": offset,
                  "items": items[offset:end], "next_offset": end if end < len(items) else None}
        if len(json.dumps(result, ensure_ascii=False)) <= MAX_OUTPUT_CHARS:
            return result
        require(end > offset + 1, "One record exceeds the context budget; use evidence windows")
        end -= 1


def history_file_for(run):
    path = Path(run) / "history-before.json"
    if not path.exists():
        path = root_for(run) / "data/history.json"
    return path


def history_items(run):
    path = history_file_for(run)
    value = read(path) if path.exists() else {}
    return value.get("items", []) if isinstance(value, dict) else value


def history_view(item):
    return {"history_id": history_id(item), "title": short(item.get("title"), 500), "date": item.get("date"),
            "change_type": item.get("change_type"),
            "topic": short(item.get("topic", item.get("topic_id")), 100),
            "summary": short(item.get("summary"), 1000),
            "sources": [{"url": short(s.get("url"), 800)} for s in item.get("sources", [])[:4]],
            "sources_count": len(item.get("sources", []))}


def history(run, offset=0, limit=PAGE_SIZE, query=None):
    items = history_items(run)
    if query:
        items = [i for i in items if query.lower() in json.dumps(i, ensure_ascii=False).lower()]
    return page([history_view(i) for i in items], offset, limit,
                file=str(history_file_for(run)), query=query)


def history_matches(run, candidate):
    urls = {candidate["url"], *(e["url"] for e in candidate["evidence"])}
    normalize = lambda s: re.sub(r"\W+", " ", s.lower()).strip()
    return [history_view(i) for i in history_items(run)
            if urls & {s.get("url") for s in i.get("sources", [])}
            or normalize(i.get("title", "")) == normalize(candidate["title"])]


def overview(run):
    root = root_for(run)
    briefing = read(root / "data/briefing.json")
    return {"root": str(root), "date": read(Path(run) / "manifest.json")["date"],
            "meta": briefing.get("meta", {}), "history_items": len(history_items(run)),
            "topics": [{"id": t.get("id"), "title": t.get("title"),
                        "summary": short(t.get("summary"), 800),
                        "items": len(t.get("items", []))} for t in briefing.get("topics", [])],
            "briefing_file": str(root / "data/briefing.json"),
            "history_file": str(history_file_for(run))}


def all_candidates(run):
    return read(Path(run) / "candidates.json")


def find_candidate(run, candidate_id):
    result = next((c for c in all_candidates(run) if c["id"] == candidate_id), None)
    require(result is not None, "Unknown candidate")
    return result


def candidate_view(candidate):
    return {"id": candidate["id"], "title": short(candidate["title"], 500),
            "development": short(candidate.get("development"), 800),
            "headline_terms": candidate.get("headline_terms", []),
            "change_type": candidate.get("change_type"),
            "summary": short(candidate["summary"], 1200),
            "summary_truncated": len(candidate["summary"]) > 1200,
            "url": short(candidate["url"], 800), "published_at": candidate["published_at"],
            "evidence_count": len(candidate["evidence"]),
            "first_excerpt": short(candidate["evidence"][0]["excerpt"], 600)}


def candidates(run, offset=0, limit=PAGE_SIZE):
    return page([candidate_view(c) for c in all_candidates(run)], offset, limit,
                file=str(Path(run) / "candidates.json"),
                detail_command="candidate --id ID; evidence --id ID --evidence-index INDEX")


def candidate(run, candidate_id, offset=0, limit=4):
    value = find_candidate(run, candidate_id)
    items = [{"index": i, "url": short(e["url"], 800),
              "method": e["method"], "retrieved_at": e["retrieved_at"],
              "excerpt": short(e["excerpt"], 1200), "excerpt_chars": len(e["excerpt"]),
              "excerpt_truncated": len(e["excerpt"]) > 1200}
             for i, e in enumerate(value["evidence"])]
    matches = history_matches(run, value)
    return page(items, offset, limit, candidate=candidate_view(value),
                history_matches=matches[:4], history_matches_count=len(matches),
                full_record_file=str(Path(run) / "candidates.json"))


def cached_article(run, url):
    """Only inspect this run's worker/editor JSON caches, never fetch again."""
    run = Path(run)
    folders = sorted(p for p in run.glob("worker-*") if p.is_dir())
    if (run / "editor-cache").is_dir():
        folders.append(run / "editor-cache")
    for folder in folders:
        for path in sorted(folder.rglob("*.json")):
            try:
                value = read(path)
            except (OSError, ValueError):
                continue
            if isinstance(value, dict) and value.get("url") == url:
                text = value.get("text")
                if isinstance(text, str) and text.strip():
                    return path, text
    return None, None


def evidence(run, candidate_id, evidence_index=0, offset=0, query=None, max_chars=4000):
    value = find_candidate(run, candidate_id)
    require(0 <= evidence_index < len(value["evidence"]), "Invalid evidence index")
    require(1 <= max_chars <= 6000, "Evidence window must be 1..6000 characters")
    entry = value["evidence"][evidence_index]
    path, text = cached_article(run, entry["url"])
    source = "cached_article" if text is not None else "stored_excerpt"
    text = text if text is not None else entry["excerpt"]
    if query:
        pos = text.lower().find(query.lower())
        require(pos >= 0, "Query not found in available evidence")
        offset = max(0, pos - 500)
    require(0 <= offset <= len(text), "Invalid evidence offset")
    end = min(len(text), offset + max_chars)
    return {"candidate_id": candidate_id, "evidence_index": evidence_index,
            "url": entry["url"], "source": source,
            "cache_file": str(path) if path else None, "total_chars": len(text),
            "offset": offset, "next_offset": end if end < len(text) else None,
            "text": text[offset:end],
            "note": "Full text remains on disk. If source=stored_excerpt, this is not a complete article."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["overview", "candidates", "candidate", "evidence", "history"])
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--id")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--evidence-index", type=int, default=0)
    parser.add_argument("--query")
    args = parser.parse_args()
    try:
        if args.action == "overview": result = overview(args.run_dir)
        elif args.action == "candidates": result = candidates(args.run_dir, args.offset, args.limit or PAGE_SIZE)
        elif args.action == "candidate": result = candidate(args.run_dir, args.id, args.offset, args.limit or 4)
        elif args.action == "history": result = history(args.run_dir, args.offset, args.limit or PAGE_SIZE, args.query)
        else: result = evidence(args.run_dir, args.id, args.evidence_index, args.offset, args.query)
        output = json.dumps(result, ensure_ascii=False)
        require(len(output) <= MAX_OUTPUT_CHARS, "Output exceeds context budget; use a smaller page")
        print(output)
        return 0
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
