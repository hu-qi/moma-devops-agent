"""Shared path policy enforcement used by every executor (native and runtime).

C09: path constraints come from trusted operator config but must still be
normalized defensively, and changed paths must be validated against the real
workspace filesystem so absolute paths, '..' components, and symlink escapes
cannot bypass the allow/forbidden policy.
"""

from __future__ import annotations

from pathlib import Path


class PathPolicyError(RuntimeError):
    """Raised when a changed path violates the trusted path policy."""


class PathPolicyConfigError(PathPolicyError):
    """Raised when the configured policy itself is unsafe (absolute, '..', symlink)."""


def _split(config_value: str) -> list[str]:
    return [x.strip() for x in (config_value or "").split(",") if x.strip()]


def normalize_policy_paths(
    allowed_config: str,
    forbidden_config: str,
    *,
    workspace_path: Path | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Normalize configured policy paths and reject unsafe entries.

    Rejects absolute paths and any path containing a '..' component. When a
    workspace is supplied, also rejects entries that resolve through an
    existing symlink to outside the workspace.
    """
    normalized: list[str] = []
    for raw in (*_split(allowed_config), *_split(forbidden_config)):
        candidate = Path(raw)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise PathPolicyConfigError(
                f"Unsafe path policy entry: '{raw}' (absolute paths and '..' are not allowed)"
            )
        if workspace_path is not None:
            resolved = (workspace_path / candidate).resolve()
            try:
                resolved.relative_to(workspace_path.resolve())
            except ValueError:
                raise PathPolicyConfigError(
                    f"Path policy entry '{raw}' resolves outside the workspace (symlink escape)"
                ) from None
        normalized.append(candidate.as_posix())
    kept = normalized[: len(_split(allowed_config))]
    forbidden = normalized[len(_split(allowed_config)):]
    return tuple(kept), tuple(forbidden)


def _hits(changed: set[str], entries: tuple[str, ...]) -> set[str]:
    """Return changed paths matched by policy entries.

    An entry ending with '/' matches every path under that directory prefix;
    any other entry matches exactly.
    """
    hits: set[str] = set()
    for entry in entries:
        if entry.endswith("/"):
            hits.update(p for p in changed if p.startswith(entry) or p == entry.rstrip("/"))
        elif entry in changed:
            hits.add(entry)
    return hits


def validate_changed_paths(
    changed: set[str],
    *,
    allowed: tuple[str, ...],
    forbidden: tuple[str, ...],
) -> None:
    """Enforce the normalized policy over actual changed paths.

    Every changed path must be a safe relative path; forbidden entries are
    always rejected; if an allow-list exists, all changes must be inside it.
    Directory entries (ending with '/') match by prefix.
    """
    for path in changed:
        candidate = Path(path)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise PathPolicyError(f"Changed path escapes workspace: '{path}'")

    hit_forbidden = sorted(_hits(changed, forbidden))
    if hit_forbidden:
        raise PathPolicyError(f"AgentTeam modified forbidden paths: {hit_forbidden}")
    if allowed:
        outside = sorted(set(changed) - _hits(changed, allowed))
        if outside:
            raise PathPolicyError(
                f"AgentTeam modified paths outside allow-list: {outside}"
            )
