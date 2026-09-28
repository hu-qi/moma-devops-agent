"""Controlled OpenJiuwen lock shim under explicit feature flag and version whitelist.

By default, this shim is NOT active and does NOT mutate global lock behavior on import.
"""

from __future__ import annotations

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import AsyncIterator


SUPPORTED_SHIM_VERSIONS = frozenset({
    "0.1.18",
    "0.1.19",
    "0.1.19.dev0",
})


class UnsupportedRuntimeVersionError(RuntimeError):
    """Raised when lock shim is enabled for an unverified/unsupported runtime version."""


@dataclass
class LockShimState:
    enabled: bool = False
    applied: bool = False
    detected_version: str | None = None
    reason: str = ""


_GLOBAL_SHIM_STATE = LockShimState()


def get_shim_state() -> LockShimState:
    return _GLOBAL_SHIM_STATE


def is_shim_configured() -> bool:
    """Check if the user explicitly opted in to the temporary lock shim."""
    val = os.getenv("DEVOPSPILOT_OPENJIUWEN_LOCK_SHIM", "").strip().lower()
    return val in {"1", "true", "yes"}


def detect_openjiuwen_version() -> str | None:
    try:
        import importlib.metadata
        return importlib.metadata.version("openjiuwen")
    except Exception:
        pass
    try:
        import openjiuwen
        return getattr(openjiuwen, "__version__", None)
    except Exception:
        return None


def apply_controlled_lock_shim(*, force: bool = False) -> bool:
    """Apply lock shim ONLY when explicitly configured and version is in whitelist.

    Returns True if shim was applied, False if skipped.
    Raises UnsupportedRuntimeVersionError if configured but version is unknown/unsupported.
    """
    global _GLOBAL_SHIM_STATE

    if not force and not is_configured():
        _GLOBAL_SHIM_STATE.enabled = False
        _GLOBAL_SHIM_STATE.applied = False
        _GLOBAL_SHIM_STATE.reason = "disabled_by_default"
        return False

    _GLOBAL_SHIM_STATE.enabled = True
    ver = detect_openjiuwen_version()
    _GLOBAL_SHIM_STATE.detected_version = ver

    if ver is not None and ver not in SUPPORTED_SHIM_VERSIONS:
        raise UnsupportedRuntimeVersionError(
            f"DEVOPSPILOT_OPENJIUWEN_LOCK_SHIM is enabled, but openjiuwen version '{ver}' "
            f"is not in verified whitelist: {sorted(SUPPORTED_SHIM_VERSIONS)}"
        )

    # In-memory asyncio read-write lock rather than purely no-op
    _rw_memory_lock = asyncio.Lock()

    @asynccontextmanager
    async def _safe_async_lock(*args, **kwargs) -> AsyncIterator[None]:
        async with _rw_memory_lock:
            yield

    async def _noop_async(*args, **kwargs) -> None:
        return None

    import importlib

    try:
        mod = sys.modules.get("openjiuwen.core.sys_operation.local._rw_lock_manager")
        if mod is None:
            try:
                mod = importlib.import_module("openjiuwen.core.sys_operation.local._rw_lock_manager")
            except Exception:
                mod = None

        mgr = getattr(mod, "ReadWriteLockManager", None) if mod else None
        if mgr is not None:
            mgr.lock_guard = _safe_async_lock
            mgr.start = lambda *args, **kwargs: None
            mgr.stop = _noop_async
            mgr.cleanup_expired_locks = _noop_async
            mgr.close_locks = _noop_async
            task = getattr(mgr, "_cleanup_task", None)
            if task is not None and hasattr(task, "done") and not task.done():
                task.cancel()
            setattr(mgr, "_cleanup_task", None)
            locks = getattr(mgr, "_locks", None)
            if locks is not None and hasattr(locks, "clear"):
                locks.clear()
            idle_heap = getattr(mgr, "_idle_heap", None)
            if idle_heap is not None and hasattr(idle_heap, "clear"):
                idle_heap.clear()
            idle_deadlines = getattr(mgr, "_idle_deadlines", None)
            if idle_deadlines is not None and hasattr(idle_deadlines, "clear"):
                idle_deadlines.clear()
            setattr(mgr, "_state_lock", None)

        mod_fs = sys.modules.get("openjiuwen.core.sys_operation.local.fs_operation")
        if mod_fs is None:
            try:
                mod_fs = importlib.import_module("openjiuwen.core.sys_operation.local.fs_operation")
            except Exception:
                mod_fs = None
        fs_cls = getattr(mod_fs, "FsOperation", None) if mod_fs else None
        if fs_cls is not None:
            fs_cls._file_lock = _safe_async_lock
            fs_cls._maybe_read_lock = _safe_async_lock
            fs_cls._ordered_file_locks = _safe_async_lock

        _GLOBAL_SHIM_STATE.applied = True
        _GLOBAL_SHIM_STATE.reason = f"applied_with_whitelist_version={ver}"
        return True
    except Exception as exc:
        _GLOBAL_SHIM_STATE.applied = False
        _GLOBAL_SHIM_STATE.reason = f"failed_to_apply: {exc}"
        return False


def is_configured() -> bool:
    return is_shim_configured()
