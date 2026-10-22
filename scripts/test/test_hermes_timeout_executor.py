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
    def run_batch(self, timeout, *, function_name="delegate_task", legacy_guard=False):
        sys.path.insert(0, "/opt/hermes")
        from agent import tool_executor as executor
        agent = SimpleNamespace(_tool_worker_threads_lock=threading.Lock(),
                                _tool_worker_threads=set(), _interrupt_requested=False)

        finished = threading.Event()

        def simulated_research(*args, **kwargs):
            try:
                time.sleep(0.09)  # A 900-second source batch, scaled to 90 ms.
                return SimpleNamespace(result="all_children_finished")
            finally:
                finished.set()

        from contextlib import ExitStack
        with ExitStack() as stack:
            if legacy_guard:
                # Reproduce the old runtime explicitly. Patching only the resolver
                # cannot enable a deadline for a tool now exempt from that deadline.
                stack.enter_context(patch.object(executor, "_SEQUENTIAL_DEADLINE_EXEMPT_TOOLS",
                                                 frozenset(), create=True))
            stack.enter_context(patch.object(executor, "_resolve_sequential_tool_timeout", return_value=timeout))
            stack.enter_context(patch.object(executor, "_run_agent_tool_execution_middleware",
                                             side_effect=simulated_research))
            stack.enter_context(patch.object(executor, "_emit_terminal_post_tool_call"))
            stack.enter_context(patch.object(executor, "_ra", return_value=SimpleNamespace(
                _set_interrupt=lambda *a, **k: None)))
            try:
                result = executor._run_sequential_tool_execution_middleware(
                    agent, function_name=function_name, function_args={"tasks": [{"goal": "fixture"}]},
                    effective_task_id="briefing-timeout-regression", tool_call_id="fixture", execute=lambda: None)
            finally:
                # A returned timeout is not evidence that the child has stopped.
                self.assertTrue(finished.wait(2), "Fixture child must finish before mocks are removed")
        return result.result

    def test_old_seven_minute_guard_reproduces_premature_batch_timeout(self):
        self.assertIn("timed out", self.run_batch(420 / 10000, legacy_guard=True))

    def test_current_delegate_waits_past_generic_deadline(self):
        self.assertEqual(self.run_batch(420 / 10000), "all_children_finished")

    def test_ordinary_tools_still_obey_generic_deadline(self):
        self.assertIn("timed out", self.run_batch(420 / 10000, function_name="web_search"))

    def test_active_persistent_deadline_waits_for_the_actual_batch_result(self):
        sys.path.insert(0, "/opt/hermes")
        from agent.tool_executor import _resolve_sequential_tool_timeout
        active = _resolve_sequential_tool_timeout()
        self.assertIsNotNone(active, "Keep a finite safety deadline")
        assert active is not None  # Narrow the runtime resolver's optional type.
        self.assertEqual(self.run_batch(active / 10000, function_name="web_search"), "all_children_finished")


if __name__ == "__main__":
    unittest.main()
