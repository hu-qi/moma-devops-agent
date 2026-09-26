# 26 — Industry Engineering Packs Architecture and Reference Implementation

Date: 2026-09-25  
Status: **Local prototype; production gate integration and CI evidence pending**

## 2026-09-26 Evidence Correction

The current local environment cannot run this smoke without installing the undeclared PyYAML dependency. The smoke uses an example command that prints PASS; it does not verify audit integrity in the target repository. Pack selection, persistence, remediation propagation and a mandatory gate runner are not integrated end to end. Prompt context currently includes rules/checklists but omits test gate commands. Standard references below describe prototype intent and require source/applicability review; they are not compliance verification. See [assessment](../project-assessment-2026-09-26.md).

## Purpose

DevOpsPilot serves as a horizontal intelligent software delivery foundation across sectors such as government, finance, manufacturing, and healthcare. Per architectural decision **D-002**, the core platform must strictly decouple from domain-specific rules. Industry-specific compliance, architectural constraints, review checklists, and test gates are encapsulated within **Industry Engineering Packs**.

## Architecture & Decoupling Principle

```text
┌────────────────────────────────────────────────────────┐
│                   DevOpsPilot Core                     │
│  (Delivery Loop, AgentTeam, Remediation Control Plane) │
└──────────────────────────┬─────────────────────────────┘
                           │ Task Context Injection
                           ▼
┌────────────────────────────────────────────────────────┐
│             Industry Engineering Engine                │
│  (Pack Contracts, InMemoryRegistry, Directory Loader)  │
└──────────────────────────┬─────────────────────────────┘
                           │ Loads
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
┌───────────────┐  ┌───────────────┐  ┌───────────────┐
│  Government   │  │    Finance    │  │  Industrial   │
│     Pack      │  │     Pack      │  │     Pack      │
└───────────────┘  └───────────────┘  └───────────────┘
```

## Contract Specification

Contracts defined in `src/devopspilot/contracts/industry.py`:

- **ComplianceRule**: Regulatory or standard compliance rule (e.g., GB/T 22239-2019 / DJCP 等保 2.0, PCI-DSS) with severity levels (`INFO`, `WARNING`, `CRITICAL`, `BLOCKER`) and remediation guidance.
- **ArchitectureConstraint**: Domain-specific architectural guidelines, including forbidden code patterns (e.g., dynamic remote script fetches in air-gapped networks) and allowed cryptographic algorithms.
- **ReviewChecklistItem**: Targeted review checklist prompts injected into the Review Specialist's evaluation phase.
- **IndustryTestGate**: Automated test gates executed before change requests or deployments.
- **IndustryEngineeringPack**: The canonical composite object binding domain rules and metadata.

## Reference Pack: Government (政务行业工程包)

Located at `industry-packs/government/pack.yaml`:
- **Compliance**:
  - `GOV-COMP-001`: GB/T 22239-2019 critical audit logging for all business transactions.
  - `GOV-COMP-002`: GB/T 35273-2020 mandatory data masking for citizen ID, phone, and unified social credit codes.
  - `GOV-COMP-003`: Xinchuang (信创) multi-architecture compatibility (AArch64/ARM64 and LoongArch).
- **Architecture Constraints**:
  - `GOV-ARCH-001`: Prohibition of runtime external CDN / script loading in isolated government intranets.
  - `GOV-ARCH-002`: Preferred adoption of State Commercial Cryptography (SM2, SM3, SM4).
- **Review Checklist & Gates**:
  - Hard blockers on hardcoded credentials and token leakage.
  - Automated audit log integrity test gate.

## Verification Evidence

- `experiments/industry-pack-smoke/main.py` covers prototype contracts, loading, registry, context rendering and execution of an example command. This is not proof of an effective industry gate; the 2026-09-26 environment check failed at `import yaml`.
