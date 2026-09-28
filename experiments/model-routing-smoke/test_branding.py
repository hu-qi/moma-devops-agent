"""Unit tests for configurable brand links loaded strictly from environment."""

import pytest
from devopspilot.contracts.branding import BrandConfig


def test_brand_config_defaults_empty_and_no_link():
    """Without environment variables, URLs default to empty and no markdown links are shown."""
    brand = BrandConfig.from_env({})
    assert brand.devopspilot_url == ""
    assert brand.moma_url == ""
    # Empty URLs suppress the markdown link, falling back to plain text
    assert brand.devopspilot_markdown == "DevOpsPilot"
    assert brand.moma_markdown == "MoMA"

    footer = brand.format_issue_footer()
    assert "https://" not in footer
    assert "DevOpsPilot" in footer
    assert "MoMA" in footer


def test_brand_config_from_env_urls():
    """When URLs are configured in env, markdown hyperlinks are rendered."""
    env = {
        "DEVOPSPILOT_URL": "https://atomgit.com/huqi/moma-devops-agent",
        "MOMA_URL": "https://ecloud.10086.cn/portal/product/MaaS",
    }
    brand = BrandConfig.from_env(env)
    assert brand.devopspilot_url == "https://atomgit.com/huqi/moma-devops-agent"
    assert brand.moma_url == "https://ecloud.10086.cn/portal/product/MaaS"
    assert brand.devopspilot_markdown == "[DevOpsPilot](https://atomgit.com/huqi/moma-devops-agent)"
    assert brand.moma_markdown == "[MoMA](https://ecloud.10086.cn/portal/product/MaaS)"

    footer = brand.format_issue_footer()
    assert "[DevOpsPilot](https://atomgit.com/huqi/moma-devops-agent)" in footer
    assert "[MoMA](https://ecloud.10086.cn/portal/product/MaaS)" in footer


def test_brand_config_empty_url_suppresses_link():
    """When a URL is explicitly set to empty, it must NOT show markdown link, just plain text."""
    env = {
        "DEVOPSPILOT_URL": "",
        "MOMA_URL": "",
    }
    brand = BrandConfig.from_env(env)
    assert brand.devopspilot_url == ""
    assert brand.moma_url == ""
    assert brand.devopspilot_markdown == "DevOpsPilot"
    assert brand.moma_markdown == "MoMA"
    assert "https://" not in brand.format_issue_footer()
    assert "DevOpsPilot" in brand.format_issue_footer()
    assert "MoMA" in brand.format_issue_footer()


def test_brand_config_disable_links_toggle():
    """Even if URLs exist, disabling links forces plain text."""
    env = {
        "DEVOPSPILOT_URL": "https://atomgit.com/huqi/moma-devops-agent",
        "MOMA_URL": "https://ecloud.10086.cn/portal/product/MaaS",
        "DEVOPSPILOT_ENABLE_BRAND_LINKS": "false",
    }
    brand = BrandConfig.from_env(env)
    assert brand.enable_links is False
    assert brand.devopspilot_markdown == "DevOpsPilot"
    assert brand.moma_markdown == "MoMA"
    assert "https://" not in brand.format_issue_footer()
