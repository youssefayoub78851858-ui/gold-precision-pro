"""Offline-only process supervisor for an original FXCM-shaped C++ test fixture.

Never runs a vendor SDK and cannot take a real FXCM mode or account. This
does not authorize FXCM usage. Program integrity is pinned to the binary
compiled from our own fixture source by the caller's isolated test.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
import pathlib
import selectors
import signal
import subprocess
import time

from fxcm_native_pipeline_bridge import review_fxcm_native_standby

ALLOWED = frozenset({"--fixture", "--fixture-crossed", "--fixture-stale",
    "--fixture-missing-h1", "--fixture-unclosed", "--fixture-gap",
    "--fixture-forged-rights", "--fixture-hang", "--fixture-large",
    "--fixture-malformed", "--fixture-exit"})
MAX_OUTPUT_BYTES = 48_000
MAX_BINARY_BYTES = 1_000_000


def _pairs_unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError("NONFINITE_JSON_NUMBER")


def _read_fixture_stdout(executable: pathlib.Path, mode: str, deadline_seconds: float):
    # This is only used after SHA-256 verification of our own C++ test emitter.
    proc = subprocess.Popen([str(executable), mode],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL, start_new_session=True,
        cwd=str(executable.parent),
        env={"PATH": "/usr/bin:/bin", "LANG": "C", "HOME": "/nonexistent"},
        shell=False, close_fds=True)
    data = bytearray()
    selector = selectors.DefaultSelector()
    deadline = time.monotonic() + deadline_seconds
    try:
        selector.register(proc.stdout, selectors.EVENT_READ)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("OFFLINE_FIXTURE_TIMEOUT")
            ready = selector.select(remaining)
            if not ready:
                raise TimeoutError("OFFLINE_FIXTURE_TIMEOUT")
            chunk = os.read(proc.stdout.fileno(), 8192)
            if not chunk:
                break
            if len(data) + len(chunk) > MAX_OUTPUT_BYTES:
                raise ValueError("OFFLINE_FIXTURE_OUTPUT_EXCEEDED_LIMIT")
            data.extend(chunk)
        remaining = max(0.001, deadline - time.monotonic())
        code = proc.wait(timeout=remaining)
        if code != 0:
            raise ValueError("OFFLINE_FIXTURE_PROCESS_EXIT_NONZERO")
        return bytes(data)
    finally:
        selector.close()
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        proc.wait(timeout=3)
        if proc.stdout is not None:
            proc.stdout.close()


def review_pinned_cpp_fixture(
    binary: pathlib.Path, expected_sha256: str, mode: str,
    now: dt.datetime, *, timeout_seconds: float = 2.0
) -> dict:
    """Run only a known synthetic binary. Failures never reach real research."""
    reason = "OFFLINE_FIXTURE_NOT_VERIFIED"
    bridge = None
    try:
        if mode not in ALLOWED:
            raise ValueError("OFFLINE_MODE_NOT_ALLOWED")
        if not (0.05 <= timeout_seconds <= 5):
            raise ValueError("OFFLINE_TIMEOUT_OUT_OF_RANGE")
        binary = pathlib.Path(binary)
        if binary.is_symlink() or not binary.is_file():
            raise ValueError("OFFLINE_BINARY_NOT_REGULAR")
        if not (0 < binary.stat().st_size <= MAX_BINARY_BYTES):
            raise ValueError("OFFLINE_BINARY_SIZE_INVALID")
        digest = hashlib.sha256(binary.read_bytes()).hexdigest()
        if not isinstance(expected_sha256, str) or len(expected_sha256) != 64 \
                or digest != expected_sha256:
            raise ValueError("OFFLINE_BINARY_HASH_MISMATCH")
        raw = _read_fixture_stdout(binary.resolve(), mode, timeout_seconds)
        packet = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs_unique,
                            parse_constant=_invalid_constant)
        if not isinstance(packet, dict) or \
                packet.get("dataOrigin") != "SYNTHETIC_CPP_OFFLINE_TEST_ONLY":
            raise ValueError("NON_SYNTHETIC_SOURCE_REJECTED")
        bridge = review_fxcm_native_standby(packet, now)
        if bridge.get("signal") != "WAIT" or bridge.get("executable") is not False \
                or bridge.get("researchEligible") is not False \
                or bridge.get("paperOrdersAllowed") is not False \
                or bridge.get("sourcePolicyAuthorized") is not False \
                or bridge.get("providerRequestsMade") != 0 \
                or set(bridge.get("engines", {}).values()) != {"SKIPPED"}:
            raise ValueError("SHARED_RESEARCH_GATE_UNEXPECTEDLY_ACTIVE")
        reason = ("GEOMETRY_CHECK_ONLY_UNLICENSED_SOURCE"
                  if bridge.get("structuralAuditPassed") is True
                  else "CANDIDATE_REJECTED_BY_OFFLINE_INTAKE")
    except (TypeError, ValueError, UnicodeError, TimeoutError, OSError,
            subprocess.SubprocessError) as exc:
        reason = str(exc) if str(exc) in {
            "OFFLINE_MODE_NOT_ALLOWED", "OFFLINE_TIMEOUT_OUT_OF_RANGE",
            "OFFLINE_BINARY_NOT_REGULAR", "OFFLINE_BINARY_SIZE_INVALID",
            "OFFLINE_BINARY_HASH_MISMATCH", "OFFLINE_FIXTURE_TIMEOUT",
            "OFFLINE_FIXTURE_OUTPUT_EXCEEDED_LIMIT",
            "OFFLINE_FIXTURE_PROCESS_EXIT_NONZERO", "DUPLICATE_JSON_KEY",
            "NONFINITE_JSON_NUMBER", "NON_SYNTHETIC_SOURCE_REJECTED",
            "SHARED_RESEARCH_GATE_UNEXPECTEDLY_ACTIVE"
        } else "OFFLINE_BINARY_OR_PAYLOAD_FAILURE"
    return {
        "status": "WAIT_FXCM_CPP_SUPERVISOR_TEST_ONLY",
        "signal": "WAIT", "researchCandidate": "NONE",
        "executable": False, "researchEligible": False,
        "paperOrdersAllowed": False, "tradingEnabled": False,
        "providerRequestsMade": 0, "credentialsRead": 0,
        "sdkLoaded": False, "rightsVerified": False,
        "dataOrigin": "SYNTHETIC_CPP_OFFLINE_TEST_ONLY",
        "bridgeStatus": bridge.get("status") if bridge else "SKIPPED",
        "structuralAuditPassed": bridge.get("structuralAuditPassed") is True if bridge else False,
        "blockingReason": reason,
        "rawCandlesIncluded": False,
        "engineInvoked": False,
    }
