#!/usr/bin/env python3
"""Durable, source-owned research packets for the Hermes briefing editor.

No model calls or publication side effects. Workers use record/reserve-search;
only the editor runs assemble/check-editor. All dates are Europe/Berlin days.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import date, datetime, timedelta
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import re
from statistics import median
import tempfile
import subprocess
from urllib.request import Request, urlopen
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from validate_research_audit import SOURCES, validate

TOPICS = (
    "AI News", "Lokale LLMs", "Agentic Engineering / Vibe Coding", "AI Tools",
    "Context Engineering", "AI Security", "AI Governance", "Enterprise",
)
PACKET_SIZE = 9
SEARCH_BUDGET = 35
MAX_PARALLEL = 3
URL_OVERRIDES = {
    "anthropic.com": "https://www.anthropic.com/news",
    "openai.com": "https://openai.com/news/",
    "openrouter.ai": "https://openrouter.ai/blog/",
    "blog.google": "https://blog.google/innovation-and-ai/",
    "microsoft.ai": "https://microsoft.ai/news/",
    "arxiv.org": "https://arxiv.org/list/cs.AI/recent",
    "ollama.com": "https://ollama.com/blog",
    "huggingface.co": "https://huggingface.co/blog",
    "techcrunch.com": "https://techcrunch.com/category/artificial-intelligence/",
    "theverge.com": "https://www.theverge.com/ai-artificial-intelligence",
    "heise.de": "https://www.heise.de/thema/Kuenstliche-Intelligenz",
    "arstechnica.com": "https://arstechnica.com/ai/",
    "github.blog": "https://github.blog/changelog/",
    "importai.substack.com": "https://importai.substack.com/archive",
    "ai.meta.com": "https://ai.meta.com/blog/",
    "mistral.ai": "https://mistral.ai/news/",
    "x.ai": "https://x.ai/news/",
    "openclaw.ai": "https://openclaw.ai/blog/",
    "cohere.com": "https://cohere.com/blog",
    "aws.amazon.com": "https://aws.amazon.com/blogs/machine-learning/",
    "deepmind.google": "https://deepmind.google/discover/blog/",
    "research.google": "https://research.google/blog/",
    "nist.gov": "https://www.nist.gov/artificial-intelligence",
}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write(path, value):
    """Atomic checkpoints: interruption never leaves a half-written JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".checkpoint-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


@contextmanager
def locked(run):
    with (Path(run) / ".lock").open("a") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def require(condition, message):
    if not condition:
        raise ValueError(message)


def http_url(value):
    p = urlparse(value if isinstance(value, str) else "")
    return p.scheme in {"http", "https"} and bool(p.hostname) and not p.username


def stamp():
    return datetime.now(ZoneInfo("Europe/Berlin")).isoformat(timespec="seconds")


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def item_fingerprint(item):
    return fingerprint({k: v for k, v in item.items() if k != "n"})


def source_windows(root, day, sources):
    """Failed days do not advance a source watermark; overlap protects late indexing."""
    latest = {}
    for path in sorted((Path(root) / "data/research-audit").glob("*.json")):
        try:
            audit = read(path)
            when = date.fromisoformat(audit["date"])
            if when > day:
                continue
            for entry in audit.get("sources", []):
                if entry.get("status") == "checked":
                    latest[entry["domain"]] = max(when, latest.get(entry["domain"], when))
        except (ValueError, KeyError, TypeError):
            continue
    return {
        domain: min(day - timedelta(days=2), latest.get(domain, day - timedelta(days=6)) - timedelta(days=1)).isoformat()
        for domain, _ in sources
    }


def historical_source_weights(root, run, day, sources):
    """Estimate source workload from completed packets in recent daily runs.

    Old runs don't have per-source timers, so each source gets its packet's
    elapsed time divided by its source count. A median across days limits the
    effect of a single slow site or delayed agent release. Missing history
    never removes a source from the next run.
    """
    domains = {domain for domain, _ in sources}
    samples = {domain: [] for domain in domains}
    seen_dates = set()
    manifests = []
    for path in run.parent.glob("*/manifest.json"):
        try:
            prior = read(path)
            if not isinstance(prior, dict):
                continue
            prior_day = date.fromisoformat(prior["date"])
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if prior.get("root") != str(root) or not day - timedelta(days=14) <= prior_day < day:
            continue
        manifests.append((prior_day, path, prior))
    for prior_day, _, prior in sorted(manifests, key=lambda item: (item[0], str(item[1])), reverse=True):
        if prior_day in seen_dates:
            continue
        seen_dates.add(prior_day)
        for task in prior.get("tasks", []):
            if task.get("kind") != "sources" or task.get("attempt") != 1 or task.get("state") != "complete":
                continue
            assigned = task.get("sources", [])
            if not assigned:
                continue
            try:
                elapsed = (datetime.fromisoformat(task["finished_at"]) - datetime.fromisoformat(task["dispatched_at"])).total_seconds()
            except (KeyError, TypeError, ValueError):
                continue
            if not 0 < elapsed <= 7200:
                continue
            weight = elapsed / len(assigned)
            for source in assigned:
                domain = source.get("domain") if isinstance(source, dict) else None
                if domain in domains:
                    samples[domain].append(weight)
    return {domain: median(values) for domain, values in samples.items() if values}


def source_packets(specs, weights):
    """Keep every source once, distributing historically slow sources evenly."""
    if not weights:
        return [specs[i:i + PACKET_SIZE] for i in range(0, len(specs), PACKET_SIZE)]
    packet_count = math.ceil(len(specs) / PACKET_SIZE)
    packets = [[] for _ in range(packet_count)]
    totals = [0.0] * packet_count
    fallback = median(weights.values())
    ordered = sorted(enumerate(specs), key=lambda pair: (-weights.get(pair[1]["domain"], fallback), pair[0]))
    for index, spec in ordered:
        slot = min((i for i in range(packet_count) if len(packets[i]) < PACKET_SIZE),
                   key=lambda i: (totals[i], len(packets[i]), i))
        packets[slot].append((index, spec))
        totals[slot] += weights.get(spec["domain"], fallback)
    return [[spec for _, spec in sorted(packet)] for packet in packets]


def prepare(root, run, day, sources=None):
    root, run = Path(root).resolve(), Path(run).resolve()
    sources = list(SOURCES if sources is None else sources)
    date.fromisoformat(day)
    require(len({d for d, _ in sources}) == len(sources), "Duplicate source domains")
    require(bool(sources), "Empty source registry")
    run.mkdir(parents=True, exist_ok=True)
    with locked(run):
        if (run / "manifest.json").exists():
            old = read(run / "manifest.json")
            require(old["date"] == day and old["root"] == str(root), "Run belongs to another date/root")
            require(old["registry"] == sources or old["registry"] == [list(s) for s in sources], "Source registry changed: use a new run directory")
            return old
        windows = source_windows(root, date.fromisoformat(day), sources)
        specs = [{"domain": d, "name": n, "url": URL_OVERRIDES.get(d, f"https://{d}/"), "since": windows[d]} for d, n in sources]
        weights = historical_source_weights(root, run, date.fromisoformat(day), sources)
        packets = source_packets(specs, weights)
        tasks = [{"id": f"sources-{i + 1:02}", "kind": "sources", "sources": packet, "attempt": 1} for i, packet in enumerate(packets)]
        tasks.append({"id": "discovery", "kind": "discovery", "topics": list(TOPICS), "since": min(windows.values()), "attempt": 1})
        manifest = {"schema_version": 1, "date": day, "root": str(root), "registry": sources, "created_at": stamp(), "max_parallel": MAX_PARALLEL, "search_budget_per_task": SEARCH_BUDGET, "historical_weights_used": len(weights), "tasks": tasks}
        write(run / "manifest.json", manifest)
        if (root / "data/briefing.json").exists():
            write(run / "briefing-before.json", read(root / "data/briefing.json"))
        return manifest


def task_for(run, task_id):
    manifest = read(Path(run) / "manifest.json")
    task = next((t for t in manifest["tasks"] if t["id"] == task_id), None)
    require(task is not None, "Unknown task")
    return manifest, task


def checkpoint_path(run, domain):
    return Path(run) / "sources" / (hashlib.sha256(domain.encode()).hexdigest()[:24] + ".json")


def reserve(run, task_id, query):
    _, task = task_for(run, task_id)
    require(isinstance(query, str) and bool(query.strip()), "Empty query")
    with locked(run):
        path = Path(run) / "searches" / f"{task['id']}.json"
        calls = read(path) if path.exists() else []
        require(query.strip() not in [c["query"] for c in calls], "Duplicate query: use the saved result")
        require(len(calls) < SEARCH_BUDGET, "Task search budget reached: checkpoint and report pending work")
        calls.append({"query": query.strip(), "at": stamp()})
        write(path, calls)
        return {"allowed": True, "used": len(calls), "remaining": SEARCH_BUDGET - len(calls)}


def validate_candidates(candidates, day, since):
    require(isinstance(candidates, list), "candidates must be a list")
    normalized = []
    for candidate in candidates:
        require(isinstance(candidate, dict), "Candidate must be an object")
        for field in ["title", "summary", "published_at", "url"]:
            require(isinstance(candidate.get(field), str) and bool(candidate[field].strip()), f"Candidate missing {field}")
        require(http_url(candidate["url"]), "Invalid candidate URL")
        published = date.fromisoformat(candidate["published_at"])
        require(date.fromisoformat(since) <= published <= date.fromisoformat(day), "Candidate outside research window")
        evidence = candidate.get("evidence")
        require(isinstance(evidence, list) and bool(evidence), "Candidate needs retrieved evidence")
        for item in evidence:
            require(isinstance(item, dict) and http_url(item.get("url")), "Evidence needs a URL")
            require(isinstance(item.get("excerpt"), str) and len(item["excerpt"].strip()) >= 20, "Evidence needs an actual retrieved excerpt")
            require(item.get("method") in {"web_extract", "direct", "feed"}, "Search snippets alone are not article evidence")
            require(isinstance(item.get("retrieved_at"), str) and bool(item["retrieved_at"]), "Evidence needs retrieval time")
        require(any(e["url"] == candidate["url"] for e in evidence), "Read the candidate original URL")
        normalized.append({**candidate, "id": fingerprint([candidate["url"], candidate["title"]])[:20]})
    return normalized


def record(run, task_id, entry):
    manifest, task = task_for(run, task_id)
    if task["kind"] == "discovery":
        require(set(entry.get("topics_checked", [])) == set(TOPICS), "Discovery must cover all eight topics")
        require(bool(str(entry.get("result", "")).strip()), "Discovery needs a result, including when empty")
        candidates = validate_candidates(entry.get("candidates"), manifest["date"], task["since"])
        value = {**entry, "candidates": candidates, "task_id": task_id, "completed_at": stamp()}
        destination = Path(run) / "discovery.json"
    else:
        source = next((s for s in task["sources"] if s["domain"] == entry.get("domain")), None)
        require(source is not None, "Source does not belong to this task")
        probe = {"schema_version": 1, "date": manifest["date"], "sources": [entry]}
        errors = [e for e in validate(probe, manifest["date"]) if not e.startswith("fehlende Quellen:")]
        require(not errors, "; ".join(errors))
        require(http_url(entry.get("checked_url")), "Source needs an HTTP(S) URL")
        candidates = validate_candidates(entry.get("candidates"), manifest["date"], source["since"])
        require(entry["status"] != "unavailable" or not candidates, "Unavailable source cannot supply verified candidates")
        value = {**entry, "name": source["name"], "candidates": candidates, "since": source["since"], "task_id": task_id, "completed_at": stamp()}
        destination = checkpoint_path(run, source["domain"])
    with locked(run):
        require(not destination.exists(), "Checkpoint already exists; preserve the original result")
        write(destination, value)
    return {"saved": str(destination), "candidates": len(candidates)}


def missing(run, task):
    if task["kind"] == "discovery":
        return [] if (Path(run) / "discovery.json").exists() else ["discovery"]
    return [s["domain"] for s in task["sources"] if not checkpoint_path(run, s["domain"]).exists()]


def task_payload(run, task):
    manifest = read(Path(run) / "manifest.json")
    pending = missing(run, task)
    spec = {**task, "sources": [s for s in task.get("sources", []) if s["domain"] in pending], "date": manifest["date"], "run_dir": str(Path(run).resolve()), "root": manifest["root"], "search_budget": SEARCH_BUDGET}
    return {"goal": f"Briefing research: complete task {task['id']} and checkpoint every result.", "context": f"Read {manifest['root']}/docs/briefing-research-worker.md in full, then execute this exact assignment. Assignment JSON:\n" + json.dumps(spec, ensure_ascii=False), "output_schema": {"type": "object", "properties": {"task_id": {"type": "string"}, "status": {"type": "string", "enum": ["complete", "partial", "failed"]}, "pending": {"type": "array", "items": {"type": "string"}}, "summary": {"type": "string"}}, "required": ["task_id", "status", "pending", "summary"]}}


def dispatch(run, task_id):
    with locked(run):
        manifest, task = task_for(run, task_id)
        require(task.get("state", "pending") == "pending", "Task already dispatched; inspect its subagent")
        require(sum(t.get("state") == "running" for t in manifest["tasks"]) < MAX_PARALLEL, "Three tasks already running; wait for completion")
        require(bool(missing(run, task)), "Task already complete")
        task["state"] = "running"
        task["dispatched_at"] = stamp()
        write(Path(run) / "manifest.json", manifest)
    return task_payload(run, task)


def dispatch_next(run):
    """Atomically fill one free research slot, prioritizing retry and discovery."""
    with locked(run):
        manifest = read(Path(run) / "manifest.json")
        running = sum(task.get("state") == "running" for task in manifest["tasks"])
        if running >= MAX_PARALLEL:
            return {"status": "capacity_full", "running": running}
        pending = [task for task in manifest["tasks"]
                   if task.get("state", "pending") == "pending" and missing(run, task)]
        if not pending:
            return {"status": "waiting_for_running" if running else "no_pending_tasks", "running": running}
        task = min(pending, key=lambda item: (0 if item.get("attempt", 1) > 1 else
                                             1 if item["kind"] == "discovery" else 2,
                                             manifest["tasks"].index(item)))
        task["state"] = "running"
        task["dispatched_at"] = stamp()
        write(Path(run) / "manifest.json", manifest)
    return {"task_id": task["id"], **task_payload(run, task)}


def release(run, task_id):
    with locked(run):
        manifest, task = task_for(run, task_id)
        require(task.get("state") == "running", "Task was not running")
        task["state"] = "partial" if missing(run, task) else "complete"
        task["finished_at"] = stamp()
        write(Path(run) / "manifest.json", manifest)
    return {"task_id": task_id, "state": task["state"], "pending": missing(run, task)}


def retry(run, task_id):
    """One bounded recovery task, only for unresolved sources; no endless respawns."""
    with locked(run):
        manifest, task = task_for(run, task_id)
        require(task.get("state") != "running", "Original agent is still running")
        require(task["attempt"] == 1, "Recovery already attempted; report an incomplete run")
        require(bool(missing(run, task)), "Task already complete")
        retry_id = task_id + "-retry"
        require(not any(t["id"] == retry_id for t in manifest["tasks"]), "Recovery task already exists")
        recovered = {**task, "id": retry_id, "attempt": 2, "retry_of": task_id, "state": "pending"}
        if task["kind"] == "sources":
            recovered["sources"] = [s for s in task["sources"] if s["domain"] in missing(run, task)]
        manifest["tasks"].append(recovered)
        write(Path(run) / "manifest.json", manifest)
    return task_payload(run, recovered)


def assemble(run):
    run = Path(run)
    manifest = read(run / "manifest.json")
    require(not any(t.get("state") == "running" for t in manifest["tasks"]), "Research agents still running")
    require(manifest["registry"] == [list(s) for s in SOURCES], "Source registry changed during run")
    absent = [d for d, _ in SOURCES if not checkpoint_path(run, d).exists()]
    require(not absent, "Missing source checkpoints: " + ", ".join(absent))
    require((run / "discovery.json").exists(), "Missing discovery research")
    entries = [read(checkpoint_path(run, d)) for d, _ in SOURCES]
    source_specs = {s["domain"]: s for t in manifest["tasks"] if t["kind"] == "sources" for s in t["sources"]}
    for (domain, _), entry in zip(SOURCES, entries):
        require(entry.get("domain") == domain, "Checkpoint source ownership changed")
        validate_candidates(entry.get("candidates"), manifest["date"], source_specs[domain]["since"])
    discovery = read(run / "discovery.json")
    require(set(discovery.get("topics_checked", [])) == set(TOPICS), "Incomplete discovery topics")
    discovery_task = next(t for t in manifest["tasks"] if t["id"] == "discovery")
    validate_candidates(discovery.get("candidates"), manifest["date"], discovery_task["since"])
    audit = {"schema_version": 1, "date": manifest["date"], "sources": [{k: e[k] for k in ["domain", "name", "status", "checked_url", "result"]} for e in entries]}
    require(not validate(audit, manifest["date"]), "Invalid source audit")
    candidates = {}
    for entry in entries + [discovery]:
        for candidate in entry["candidates"]:
            if candidate["id"] in candidates:
                prior = candidates[candidate["id"]]
                seen = {fingerprint(e) for e in prior["evidence"]}
                prior["evidence"].extend(e for e in candidate["evidence"] if fingerprint(e) not in seen)
            else:
                candidates[candidate["id"]] = candidate
    if (run / "editor-evidence.json").exists():
        for addition in read(run / "editor-evidence.json"):
            require(addition["id"] in candidates, "Editor evidence references an unknown candidate")
            candidates[addition["id"]]["evidence"].extend(addition["evidence"])
    write(run / "candidates.json", list(candidates.values()))
    write(Path(manifest["root"]) / "data/research-audit" / (manifest["date"] + ".json"), audit)
    status_path = run / "research-status.json"
    prior_status = read(status_path) if status_path.exists() else {}
    result = {"status": "research_complete", "sources": len(entries), "unavailable": [e["domain"] for e in entries if e["status"] == "unavailable"], "candidates": len(candidates), "discovery_complete": True, "completed_at": prior_status.get("completed_at") or stamp()}
    write(status_path, result)
    return result


def add_evidence(run, addition):
    run = Path(run)
    assemble(run)
    candidate = next((c for c in read(run / "candidates.json") if c["id"] == addition.get("id")), None)
    require(candidate is not None, "Unknown candidate")
    manifest = read(run / "manifest.json")
    updated = {**candidate, "evidence": candidate["evidence"] + addition.get("evidence", [])}
    validate_candidates([updated], manifest["date"], candidate["published_at"])
    path = run / "editor-evidence.json"
    additions = read(path) if path.exists() else []
    additions.append(addition)
    write(path, additions)
    return assemble(run)


def check_editor(run):
    run = Path(run)
    assemble(run)
    manifest = read(run / "manifest.json")
    candidates = {c["id"]: c for c in read(run / "candidates.json")}
    decisions = read(run / "editor-decisions.json")
    require(isinstance(decisions, list), "Editorial decisions must be a list")
    require(len(decisions) == len(candidates) and {d.get("id") for d in decisions} == set(candidates), "Every candidate needs exactly one editorial decision")
    for d in decisions:
        require(d.get("decision") in {"selected", "duplicate", "unverified", "below_threshold", "out_of_window"} and bool(str(d.get("reason", "")).strip()), "Invalid editorial decision")
    briefing = read(Path(manifest["root"]) / "data/briefing.json")
    require(briefing.get("meta", {}).get("generated") == manifest["date"], "Briefing date was not updated")
    topics = briefing.get("topics", [])
    before = read(run / "briefing-before.json")
    require([t.get("id") for t in topics] == [t.get("id") for t in before.get("topics", [])] and len(topics) == 8, "Preserve all eight topic IDs")
    selected = [candidates[d["id"]] for d in decisions if d["decision"] == "selected"]
    evidence_urls = {e["url"] for c in selected for e in c["evidence"]}
    old_items = {item_fingerprint(i) for t in before.get("topics", []) for i in t.get("items", [])}
    new_urls = set()
    for topic in topics:
        for item in topic.get("items", []):
            urls = {s.get("url") for s in item.get("sources", [])}
            new_urls.update(urls)
            if item_fingerprint(item) in old_items:
                continue
            require(urls and urls <= evidence_urls, "New briefing item contains an unverified source URL")
            require(2 <= item.get("impact", 0) <= 5, "Invalid impact")
            require(date.fromisoformat(item.get("date", "")) <= date.fromisoformat(manifest["date"]), "Briefing item has a future date")
    require(all(c["url"] in new_urls for c in selected), "Selected candidate is missing from the briefing")
    status_path = run / "editor-status.json"
    prior_status = read(status_path) if status_path.exists() else {}
    briefing_sha256 = fingerprint(briefing)
    decisions_sha256 = fingerprint(decisions)
    same_editorial = (prior_status.get("briefing_sha256") == briefing_sha256
                      and prior_status.get("decisions_sha256") == decisions_sha256)
    checked_at = prior_status.get("checked_at") if same_editorial else None
    result = {"status": "ready_to_publish", "date": manifest["date"], "candidates_reviewed": len(decisions), "selected": len(selected), "briefing_sha256": briefing_sha256, "decisions_sha256": decisions_sha256, "checked_at": checked_at or stamp()}
    write(status_path, result)
    return result


def elapsed_minutes(start, end):
    if not start or not end:
        return None
    try:
        return round((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() / 60, 2)
    except (TypeError, ValueError):
        return None


def timings(run):
    """Read-only phase and task timings for comparing daily runs."""
    run = Path(run)
    manifest = read(run / "manifest.json")
    research = read(run / "research-status.json") if (run / "research-status.json").exists() else {}
    editor = read(run / "editor-status.json") if (run / "editor-status.json").exists() else {}
    publication = read(run / "publication.json") if (run / "publication.json").exists() else {}
    starts = [task["dispatched_at"] for task in manifest["tasks"] if task.get("dispatched_at")]
    searches = sum(len(read(path)) for path in (run / "searches").glob("*.json"))
    return {
        "date": manifest["date"],
        "sources": len(manifest["registry"]),
        "searches": searches,
        "historical_weights_used": manifest.get("historical_weights_used", 0),
        "research_minutes": elapsed_minutes(min(starts) if starts else None, research.get("completed_at")),
        "editorial_minutes": elapsed_minutes(research.get("completed_at"), editor.get("checked_at")),
        "publication_minutes": elapsed_minutes(editor.get("checked_at"), publication.get("verified_at")),
        "tasks": [{"id": task["id"], "state": task.get("state", "pending"),
                   "minutes": elapsed_minutes(task.get("dispatched_at"), task.get("finished_at"))}
                  for task in manifest["tasks"]],
    }


def verify_publication(run):
    """Receipt is produced from git and GitHub evidence, not a model's success text."""
    run = Path(run)
    editor = check_editor(run)
    manifest = read(run / "manifest.json")
    root = manifest["root"]
    def git(*args):
        return subprocess.run(["git", "-C", root, *args], check=True, capture_output=True, text=True).stdout.strip()
    head = git("rev-parse", "HEAD")
    remote = git("ls-remote", "origin", "refs/heads/main").split()[0]
    require(head == remote, "Local HEAD is not the remote main commit")
    tracked = json.loads(git("show", head + ":data/briefing.json"))
    require(fingerprint(tracked) == editor["briefing_sha256"], "Reviewed briefing is not committed")
    audit_path = "data/research-audit/" + manifest["date"] + ".json"
    committed_audit = json.loads(git("show", head + ":" + audit_path))
    require(committed_audit == read(Path(root) / audit_path), "Reviewed audit is not committed")
    api = "https://api.github.com/repos/nklausni/ai-briefing/actions/workflows/pages.yml/runs?head_sha=" + head
    request = Request(api, headers={"Accept": "application/vnd.github+json", "User-Agent": "ai-briefing-publication-check"})
    with urlopen(request, timeout=30) as response:
        runs = json.load(response).get("workflow_runs", [])
    matching = [r for r in runs if r.get("head_sha") == head]
    require(bool(matching), "No Pages workflow for this commit")
    latest = max(matching, key=lambda r: (r.get("run_number", 0), r.get("run_attempt", 0)))
    require(latest.get("status") == "completed" and latest.get("conclusion") == "success", "Pages workflow has not succeeded")
    url = "https://nklausni.github.io/ai-briefing/"
    with urlopen(Request(url, headers={"User-Agent": "ai-briefing-publication-check"}), timeout=30) as response:
        require(response.status == 200, "Briefing page did not return HTTP 200")
    result = {"status": "published", "date": manifest["date"], "commit": head, "workflow_url": latest["html_url"], "url": url, "verified_at": stamp(), "briefing_sha256": editor["briefing_sha256"]}
    write(run / "publication.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["prepare", "tasks", "dispatch", "dispatch-next", "release", "reserve-search", "record", "retry", "assemble", "add-evidence", "check-editor", "verify-publication", "status", "timings"])
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--date", default=datetime.now(ZoneInfo("Europe/Berlin")).date().isoformat())
    parser.add_argument("--task")
    parser.add_argument("--query")
    parser.add_argument("--input", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "prepare": result = prepare(args.root, args.run_dir, args.date)
        elif args.action == "tasks":
            manifest = read(args.run_dir / "manifest.json")
            result = [{"id": t["id"], "kind": t["kind"], "state": t.get("state", "pending"), "pending": missing(args.run_dir, t)} for t in manifest["tasks"] if missing(args.run_dir, t)]
        elif args.action == "dispatch": result = dispatch(args.run_dir, args.task)
        elif args.action == "dispatch-next": result = dispatch_next(args.run_dir)
        elif args.action == "release": result = release(args.run_dir, args.task)
        elif args.action == "reserve-search": result = reserve(args.run_dir, args.task, args.query)
        elif args.action == "record": result = record(args.run_dir, args.task, read(args.input))
        elif args.action == "retry": result = retry(args.run_dir, args.task)
        elif args.action == "assemble": result = assemble(args.run_dir)
        elif args.action == "add-evidence": result = add_evidence(args.run_dir, read(args.input))
        elif args.action == "check-editor": result = check_editor(args.run_dir)
        elif args.action == "verify-publication": result = verify_publication(args.run_dir)
        elif args.action == "timings": result = timings(args.run_dir)
        else:
            manifest = read(args.run_dir / "manifest.json")
            result = {"tasks": [{"id": t["id"], "attempt": t["attempt"], "pending": missing(args.run_dir, t)} for t in manifest["tasks"]], "publication_verified": (args.run_dir / "publication.json").exists()}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as exc:
        print(json.dumps({"status": "incomplete", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
