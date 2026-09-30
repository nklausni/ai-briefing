"""Exercise Hermes's real wait loop at 1/10,000 scale; no API/tool side effects."""
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch


@unittest.skipUnless(Path("/opt/hermes/agent/tool_executor.py").exists(), "Hermes VPS runtime only")
class HermesTimeoutExecutorTests(unittest.TestCase):
    def run_batch(self, timeout):
        sys.path.insert(0, "/opt/hermes")
        from agent import tool_executor as executor
        agent = SimpleNamespace(_tool_worker_threads_lock=threading.Lock(),
                                _tool_worker_threads=set(), _interrupt_requested=False)

        def simulated_research(*args, **kwargs):
            time.sleep(0.09)  # A 900-second source batch, scaled to 90 ms.
            return SimpleNamespace(result="all_children_finished")

        with patch.object(executor, "_resolve_sequential_tool_timeout", return_value=timeout), \
             patch.object(executor, "_run_agent_tool_execution_middleware", side_effect=simulated_research), \
             patch.object(executor, "_emit_terminal_post_tool_call"), \
             patch.object(executor, "_ra", return_value=SimpleNamespace(_set_interrupt=lambda *a, **k: None)):
            result = executor._run_sequential_tool_execution_middleware(
                agent, function_name="delegate_task", function_args={"tasks": [{"goal": "fixture"}]},
                effective_task_id="briefing-timeout-regression", tool_call_id="fixture", execute=lambda: None)
        return result.result

    def test_old_seven_minute_guard_reproduces_premature_batch_timeout(self):
        self.assertIn("timed out", self.run_batch(420 / 10000))

    def test_active_persistent_deadline_waits_for_the_actual_batch_result(self):
        sys.path.insert(0, "/opt/hermes")
        from agent.tool_executor import _resolve_sequential_tool_timeout
        active = _resolve_sequential_tool_timeout()
        self.assertIsNotNone(active, "Keep a finite safety deadline")
        self.assertEqual(self.run_batch(active / 10000), "all_children_finished")


if __name__ == "__main__":
    unittest.main()
