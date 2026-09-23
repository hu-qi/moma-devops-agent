"""DevOpsPilot core package.

The domain package intentionally stays independent from concrete Agent runtime,
MaaS, SCM and CI SDKs. Integrations belong in adapter modules.
"""

__all__ = ["contracts"]
