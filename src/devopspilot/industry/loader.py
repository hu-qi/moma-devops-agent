"""Loader and serializer for Industry Engineering Packs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from devopspilot.contracts.industry import (
    ArchitectureConstraint,
    ComplianceRule,
    IndustryEngineeringPack,
    IndustryTestGate,
    ReviewChecklistItem,
    RuleSeverity,
)


def load_pack_from_dict(data: dict[str, Any]) -> IndustryEngineeringPack:
    """Parse dictionary data into an IndustryEngineeringPack."""
    compliance_rules = tuple(
        ComplianceRule(
            rule_id=r["rule_id"],
            name=r["name"],
            description=r["description"],
            severity=RuleSeverity(r.get("severity", "warning")),
            standard=r.get("standard"),
            remediation_guidance=r.get("remediation_guidance"),
        )
        for r in data.get("compliance_rules", [])
    )

    architecture_constraints = tuple(
        ArchitectureConstraint(
            constraint_id=c["constraint_id"],
            name=c["name"],
            description=c["description"],
            allowed_patterns=tuple(c.get("allowed_patterns", ())),
            forbidden_patterns=tuple(c.get("forbidden_patterns", ())),
            rationale=c.get("rationale"),
        )
        for c in data.get("architecture_constraints", [])
    )

    review_checklist = tuple(
        ReviewChecklistItem(
            item_id=i["item_id"],
            category=i["category"],
            prompt=i["prompt"],
            must_pass=bool(i.get("must_pass", False)),
        )
        for i in data.get("review_checklist", [])
    )

    test_gates = tuple(
        IndustryTestGate(
            gate_id=g["gate_id"],
            name=g["name"],
            command=g["command"],
            timeout_seconds=int(g.get("timeout_seconds", 120)),
            required=bool(g.get("required", True)),
        )
        for g in data.get("test_gates", [])
    )

    return IndustryEngineeringPack(
        pack_id=data["pack_id"],
        industry=data["industry"],
        version=data["version"],
        title=data.get("title", data["pack_id"]),
        description=data.get("description", ""),
        compliance_rules=compliance_rules,
        architecture_constraints=architecture_constraints,
        review_checklist=review_checklist,
        test_gates=test_gates,
        metadata=data.get("metadata", {}),
    )


def load_pack_from_file(path: Path | str) -> IndustryEngineeringPack:
    """Load an IndustryEngineeringPack from a YAML or JSON file."""
    path = Path(path)
    content = path.read_text(encoding="utf-8")
    if path.suffix in {".yaml", ".yml"}:
        data = yaml.safe_load(content)
    elif path.suffix == ".json":
        data = json.loads(content)
    else:
        try:
            data = yaml.safe_load(content)
        except Exception:
            data = json.loads(content)
    return load_pack_from_dict(data)


def load_pack_from_directory(directory: Path | str) -> IndustryEngineeringPack:
    """Load a pack from a directory containing pack.yaml or pack.json."""
    directory = Path(directory)
    yaml_file = directory / "pack.yaml"
    if not yaml_file.exists():
        yaml_file = directory / "pack.yml"
    if yaml_file.exists():
        return load_pack_from_file(yaml_file)

    json_file = directory / "pack.json"
    if json_file.exists():
        return load_pack_from_file(json_file)

    raise FileNotFoundError(
        f"No pack.yaml or pack.json found in directory: {directory}"
    )


def build_industry_context(pack: IndustryEngineeringPack) -> str:
    """Build a structured Markdown instruction snippet to inject into Agent context."""
    sections = [
        f"### Industry Engineering Pack: {pack.title} (Industry: {pack.industry}, v{pack.version})",
        "",
        pack.description,
        "",
    ]

    if pack.compliance_rules:
        sections.append("#### Compliance Rules:")
        for r in pack.compliance_rules:
            std = f" [{r.standard}]" if r.standard else ""
            sections.append(f"- **[{r.severity.upper()}] {r.name}**{std}: {r.description}")
            if r.remediation_guidance:
                sections.append(f"  *Guidance*: {r.remediation_guidance}")
        sections.append("")

    if pack.architecture_constraints:
        sections.append("#### Architecture Constraints:")
        for c in pack.architecture_constraints:
            sections.append(f"- **{c.name}**: {c.description}")
            if c.forbidden_patterns:
                sections.append(f"  *Forbidden*: {', '.join(c.forbidden_patterns)}")
        sections.append("")

    if pack.review_checklist:
        sections.append("#### Review Checklist:")
        for item in pack.review_checklist:
            req = " [MUST PASS]" if item.must_pass else ""
            sections.append(f"- [{item.category}] {item.prompt}{req}")
        sections.append("")

    return "\n".join(sections)
