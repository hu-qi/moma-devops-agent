"""Generic Git transport primitives."""

from .existing_branch import GitExistingBranchWorkspaceProvider
from .publisher import GitChangePublisher
from .workspace import AutoCloningWorktreeWorkspaceProvider, GitWorktreeWorkspaceProvider

__all__ = [
    "GitChangePublisher",
    "GitWorktreeWorkspaceProvider",
    "AutoCloningWorktreeWorkspaceProvider",
    "GitExistingBranchWorkspaceProvider",
]
