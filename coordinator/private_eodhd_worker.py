"""Opt-in, research-only EODHD private WebSocket child process.

Importing this module or starting the coordinator must never contact a vendor.
An operator must explicitly enable this dedicated worker AND separately
authorize the EODHD connection and licence. This module never places orders.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess

ENABLE_FLAG = "PRIVATE_EODHD_REVIEW_WORKER_ENABLED"


def worker_enabled(env: dict, *, mode: str) -> bool:
    """Fail closed by default, even if an old token or licence flag exists."""
    # Do not even inspect the credential unless every independent gate is on.
    if not (mode == "standby"
            and env.get("CUTOVER_MODE", "standby") == "standby"
            and env.get(ENABLE_FLAG) == "1"
            and env.get("EODHD_CONNECT_APPROVED") == "1"
            and env.get("EODHD_RIGHTS_APPROVED") == "1"):
        return False
    token = env.get("EODHD_API_TOKEN", "")
    return (isinstance(token, str) and 12 <= len(token) <= 256
            and token.strip() == token
            and token.lower() not in ("demo", "your_api_token"))


def launch_review_worker(data_dir, *, mode: str, env=None, spawn=None):
    """Start only with four independent opt-ins; no secrets in argv or logs.

    When disabled: no filesystem changes, process creation, or socket activity.
    The worker itself continues to enforce connection/rights flags and WAIT.
    """
    source = os.environ if env is None else env
    if not worker_enabled(source, mode=mode):
        return None

    directory = Path(data_dir)
    if directory.is_symlink():
        raise ValueError("Private review data directory must not be a symlink")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = directory.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise ValueError("Private review data directory must be owner-only")

    bridge = Path(__file__).resolve().with_name("eodhd_ws_bridge.js")
    if not bridge.is_file() or bridge.is_symlink():
        raise ValueError("Private EODHD bridge script is unavailable")

    # Only pass the minimal variables required by the research-only child.
    child_env = {
        "PATH": source.get("PATH", os.defpath),
        "DATA_DIR": str(directory),
        "CUTOVER_MODE": "standby",
        "EODHD_CONNECT_APPROVED": "1",
        "EODHD_RIGHTS_APPROVED": "1",
        "EODHD_API_TOKEN": source["EODHD_API_TOKEN"],
    }
    runner = subprocess.Popen if spawn is None else spawn
    return runner(
        ["node", str(bridge)],
        cwd=str(bridge.parent),
        env=child_env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )


def stop_review_worker(process) -> None:
    """Stop the private worker during coordinator shutdown, without waiting forever."""
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
