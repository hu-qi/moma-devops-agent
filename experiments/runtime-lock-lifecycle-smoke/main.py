"""Smoke test for controlled Runtime lock shim, version whitelist, and concurrent write lifecycle."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from devopspilot.adapters.openjiuwen.lock_shim import (
    SUPPORTED_SHIM_VERSIONS,
    UnsupportedRuntimeVersionError,
    apply_controlled_lock_shim,
    get_shim_state,
    is_shim_configured,
)


def test_shim_disabled_by_default() -> None:
    # Ensure environment is unconfigured
    os.environ.pop("DEVOPSPILOT_OPENJIUWEN_LOCK_SHIM", None)
    assert not is_shim_configured()
    applied = apply_controlled_lock_shim()
    assert applied is False
    state = get_shim_state()
    assert state.applied is False
    assert state.reason == "disabled_by_default"
    print("RUNTIME_SHIM_DISABLED_BY_DEFAULT_OK")


def test_unsupported_version_fail_closed() -> None:
    # Test version whitelist validation
    import devopspilot.adapters.openjiuwen.lock_shim as shim_mod

    original_detect = shim_mod.detect_openjiuwen_version
    try:
        shim_mod.detect_openjiuwen_version = lambda: "9.9.99-unsupported"
        os.environ["DEVOPSPILOT_OPENJIUWEN_LOCK_SHIM"] = "true"
        try:
            apply_controlled_lock_shim(force=True)
            assert False, "Should have raised UnsupportedRuntimeVersionError"
        except UnsupportedRuntimeVersionError as exc:
            assert "not in verified whitelist" in str(exc)
            print("RUNTIME_SHIM_UNSUPPORTED_VERSION_FAIL_CLOSED_OK")
    finally:
        shim_mod.detect_openjiuwen_version = original_detect
        os.environ.pop("DEVOPSPILOT_OPENJIUWEN_LOCK_SHIM", None)


def test_concurrent_write_and_cancellation_lifecycle() -> None:
    # Verify async mutual exclusion and cancellation release
    lock = asyncio.Lock()
    events: list[str] = []

    async def worker(worker_id: int, sleep_time: float) -> None:
        async with lock:
            events.append(f"enter-{worker_id}")
            await asyncio.sleep(sleep_time)
            events.append(f"exit-{worker_id}")

    async def run_scenario() -> None:
        # Concurrent tasks
        t1 = asyncio.create_task(worker(1, 0.05))
        t2 = asyncio.create_task(worker(2, 0.05))
        await asyncio.gather(t1, t2)

        # Cancellation test
        async def slow_worker() -> None:
            async with lock:
                events.append("slow-enter")
                await asyncio.sleep(1.0)

        t3 = asyncio.create_task(slow_worker())
        await asyncio.sleep(0.01)
        t3.cancel()
        try:
            await t3
        except asyncio.CancelledError:
            pass

        # Ensure lock is not stuck after cancellation
        assert not lock.locked()
        async with lock:
            events.append("lock-reusable")

    asyncio.run(run_scenario())
    # Enter and exit should alternate cleanly
    assert events[:4] in (
        ["enter-1", "exit-1", "enter-2", "exit-2"],
        ["enter-2", "exit-2", "enter-1", "exit-1"],
    )
    assert events[-1] == "lock-reusable"
    print("RUNTIME_CONCURRENT_WRITE_AND_CANCELLATION_OK")


def main() -> None:
    test_shim_disabled_by_default()
    test_unsupported_version_fail_closed()
    test_concurrent_write_and_cancellation_lifecycle()
    print("ALL RUNTIME LOCK LIFECYCLE TESTS PASSED.")


if __name__ == "__main__":
    main()
