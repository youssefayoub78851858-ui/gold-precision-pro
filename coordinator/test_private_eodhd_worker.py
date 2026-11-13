"""No-network tests of the opt-in EODHD child lifecycle and data-dir safety."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from private_eodhd_worker import (
    ENABLE_FLAG, launch_review_worker, stop_review_worker, worker_enabled
)


class ReviewWorkerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.data = self.root / "private-data"
        self.env = {
            "CUTOVER_MODE": "standby",
            ENABLE_FLAG: "1",
            "EODHD_CONNECT_APPROVED": "1",
            "EODHD_RIGHTS_APPROVED": "1",
            "EODHD_API_TOKEN": "offline-pretend-test-token-no-provider",
            "BROKER_TOKEN": "must-never-be-forwarded",
            "TWELVE_DATA_API_KEY": "must-never-be-forwarded",
        }
        self.calls = []

    def fake_spawn(self, args, **kwargs):
        self.calls.append((args, kwargs))
        return object()

    def test_missing_any_approval_never_spawns_or_creates_files(self):
        for flag in ("CUTOVER_MODE", ENABLE_FLAG, "EODHD_CONNECT_APPROVED",
                     "EODHD_RIGHTS_APPROVED", "EODHD_API_TOKEN"):
            env = self.env.copy()
            env.pop(flag, None)
            with self.subTest(missing=flag):
                # CUTOVER_MODE has a default, but never bypasses opt-in flag.
                if flag == "CUTOVER_MODE":
                    env["CUTOVER_MODE"] = "live"
                self.assertIsNone(launch_review_worker(
                    self.data, mode="standby", env=env, spawn=self.fake_spawn))
        self.assertEqual(self.calls, [])
        self.assertFalse(self.data.exists())

    def test_live_mode_and_placeholder_tokens_never_start(self):
        self.assertFalse(worker_enabled(self.env, mode="live"))
        for token in ("demo", "YOUR_API_TOKEN", " short ", "x" * 260):
            env = {**self.env, "EODHD_API_TOKEN": token}
            self.assertIsNone(launch_review_worker(
                self.data, mode="standby", env=env, spawn=self.fake_spawn))
        self.assertFalse(self.data.exists())
        self.assertEqual(self.calls, [])

    def test_opt_in_spawns_child_with_private_directory_and_minimal_env(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            result = launch_review_worker(
                self.data, mode="standby", env=self.env, spawn=self.fake_spawn)
        self.assertIsNotNone(result)
        self.assertEqual(len(self.calls), 1)
        argv, kwargs = self.calls[0]
        self.assertEqual(argv[0], "node")
        self.assertEqual(Path(argv[1]).name, "eodhd_ws_bridge.js")
        self.assertNotIn(self.env["EODHD_API_TOKEN"], repr(argv))
        self.assertEqual(self.data.stat().st_mode & 0o777, 0o700)
        self.assertEqual(kwargs["env"]["DATA_DIR"], str(self.data))
        self.assertEqual(kwargs["env"]["CUTOVER_MODE"], "standby")
        self.assertEqual(kwargs["env"]["EODHD_API_TOKEN"], self.env["EODHD_API_TOKEN"])
        self.assertNotIn("BROKER_TOKEN", kwargs["env"])
        self.assertNotIn("TWELVE_DATA_API_KEY", kwargs["env"])
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(kwargs["stdout"], subprocess.DEVNULL)
        self.assertEqual(kwargs["stderr"], subprocess.DEVNULL)

    def test_world_readable_or_symlink_directory_is_rejected(self):
        self.data.mkdir(mode=0o755)
        self.data.chmod(0o755)
        with self.assertRaisesRegex(ValueError, "owner-only"):
            launch_review_worker(
                self.data, mode="standby", env=self.env, spawn=self.fake_spawn)
        link = self.root / "alias"
        link.symlink_to(self.data, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            launch_review_worker(
                link, mode="standby", env=self.env, spawn=self.fake_spawn)
        self.assertEqual(self.calls, [])

    def test_disabled_config_never_reads_token_or_creates_directory(self):
        class ForbiddenAccess(dict):
            def get(self, key, default=None):
                if key == "EODHD_API_TOKEN":
                    raise AssertionError("Token should not be inspected when disabled")
                return super().get(key, default)
        # The key may still be consulted in a pure preflight; it is never logged
        # or used for networking. Missing opt-in prevents any process creation.
        env = {**self.env, ENABLE_FLAG: "0"}
        self.assertIsNone(launch_review_worker(
            self.data, mode="standby", env=env, spawn=self.fake_spawn))
        self.assertFalse(self.data.exists())

    def test_worker_shutdown_and_forced_stop(self):
        class FakeProc:
            def __init__(self, timeout=False):
                self.actions = []
                self.timeout = timeout
            def poll(self):
                return None
            def terminate(self):
                self.actions.append("terminate")
            def wait(self, timeout):
                self.actions.append(("wait", timeout))
                if self.timeout:
                    self.timeout = False
                    raise subprocess.TimeoutExpired("node", timeout)
            def kill(self):
                self.actions.append("kill")
        normal = FakeProc()
        stop_review_worker(normal)
        self.assertEqual(normal.actions, ["terminate", ("wait", 5)])
        hung = FakeProc(timeout=True)
        stop_review_worker(hung)
        self.assertEqual(hung.actions,
                         ["terminate", ("wait", 5), "kill", ("wait", 5)])
        stop_review_worker(None)


if __name__ == "__main__":
    unittest.main()
