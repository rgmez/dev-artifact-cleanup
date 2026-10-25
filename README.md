# Development Artifact Cleanup

An audit-first Codex skill for identifying safe cleanup candidates in local development environments.

It is designed for Git repositories and has dedicated guidance for Xcode artifacts. It inventories build outputs, caches, logs, and worktrees, then separates candidates that can be safely acted on from local work, test evidence, archives, simulators, and ambiguous ignored files.

## Safety model

- Audit is the default; it does not delete, commit, fetch, or modify branches.
- Execution requires explicit approval for exact manifest candidates and revalidates every target immediately before action.
- Worktrees use Git lifecycle commands rather than manual deletion.
- Local branches require separate authorization. Remote branches are never in scope by default.

## Status

This repository is in private pre-release development. The current work and public-release gates are documented in [PLAN.md](PLAN.md).

The skill source is at [skills/dev-artifact-cleanup](skills/dev-artifact-cleanup).
