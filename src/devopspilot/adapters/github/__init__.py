"""GitHub reference adapters."""

from .ci import GitHubCIProvider
from .client import GitHubAPIClient, GitHubHTTPClient
from .scm import GitHubSCMProvider

__all__ = [
    "GitHubAPIClient",
    "GitHubHTTPClient",
    "GitHubSCMProvider",
    "GitHubCIProvider",
]
