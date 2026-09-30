#!/usr/bin/env python3
"""Nonmutating deployment check, run with the VPS's Hermes venv Python."""
from pathlib import Path
import json
import sys

from research_pipeline import MAX_PARALLEL

JOB_ID = "a4f79267477a"
TOOL_TIMEOUT_S = 1800
REPO = Path(__file__).resolve().parents[1]


def checks(config, job, sequential_timeout, concurrent_timeout, expected_prompt):
    return {
        "pipeline_capacity": MAX_PARALLEL == 10,
        "hermes_capacity": (config.get("delegation") or {}).get("max_concurrent_children") == MAX_PARALLEL,
        "sequential_timeout_resolves": sequential_timeout == TOOL_TIMEOUT_S,
        "concurrent_timeout_resolves": concurrent_timeout == TOOL_TIMEOUT_S,
        "cron_prompt_matches_repo": (job.get("prompt") or "").strip() == expected_prompt.strip(),
        "cron_enabled": job.get("enabled") is True,
        "cron_workdir": job.get("workdir") == "/opt/data/ai-briefing",
        "cron_schedule_unchanged": (job.get("schedule") or {}).get("expr") == "0 6,7 * * *",
        "berlin_gate_present": job.get("script") == "ai-briefing-berlin-gate.py",
    }


def main():
    sys.path.insert(0, "/opt/hermes")
    from hermes_cli.config import load_config_readonly
    from hermes_cli.config import get_hermes_home
    from agent.tool_executor import _resolve_concurrent_tool_timeout, _resolve_sequential_tool_timeout
    home = Path(get_hermes_home())
    jobs = json.loads((home / "cron/jobs.json").read_text())["jobs"]
    job = next(j for j in jobs if j["id"] == JOB_ID)
    expected = (REPO / "ops/ai-briefing-cron-prompt.txt").read_text()
    result = checks(load_config_readonly(), job, _resolve_sequential_tool_timeout(),
                    _resolve_concurrent_tool_timeout(), expected)
    print(json.dumps({"status": "pass" if all(result.values()) else "fail", "checks": result}))
    return 0 if all(result.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
