# CNB CLI Surface Spike

Purpose: inspect the current official CNB CLI command surface before implementing the first domestic SCM/CI adapter.

Why CLI first:

- CNB documents `@cnbcool/cnb-cli` as the command-line interface for its full OpenAPI surface.
- It covers source control, Issues/PRs, builds and artifacts.
- The CLI can later be replaced by direct OpenAPI calls without changing DevOpsPilot's `SCMProvider` / `CIProvider` contracts.

This spike requires no CNB token. It only records help/version output.

Captured modules:

- `cnb repos --help`
- `cnb issues --help`
- `cnb pulls --help`
- `cnb build --help`

The resulting artifact is evidence for the adapter implementation.
