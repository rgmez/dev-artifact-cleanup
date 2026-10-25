---
name: dev-artifact-cleanup
description: Audit local development artifacts and plan safe cleanup for Git repositories, especially Xcode projects. Use to inventory builds, caches, logs, and worktrees before an explicitly authorized removal; do not use as a general disk cleaner.
license: MIT
compatibility: Requires local filesystem inspection and Git in a macOS or Linux workspace. The optional Xcode cache adapter requires Python 3.9+; execution and restoration require macOS with exclusive rename support. Execution requires safe command arguments and process inspection.
metadata:
  version: "0.2.0"
  supported-runtimes: "claude-code, github-copilot, cursor, codex, skills.sh"
---

# Development Artifact Cleanup

Produce an evidence-backed cleanup plan without treating developer work as disposable.

This is a portable Agent Skill. Read [agent capabilities](references/agent-capabilities.md) when choosing tools or when the host has limited filesystem access. All references are relative to this installed skill directory. Host-specific UI metadata is optional; the workflow does not require a particular agent or MCP server.

## Modes and authorization

- **Audit (default):** inspect and classify candidates. Do not delete, archive, reset, commit, fetch, or modify branches.
- **Execute:** remove an eligible ordinary secondary Git worktree or use the macOS-only [dedicated Xcode cache adapter](references/xcode-cache-adapter.md), after explicit authorization of exact manifest IDs. All other artifact classes remain audit-only.

Never infer authorization to clean a broader directory, delete a branch, change a remote, or remove a simulator from an audit request.

## Audit workflow

1. Confirm the requested roots and measure available space on the relevant user-data volume.
2. Build a candidate manifest using exact paths, sizes, artifact class, evidence, risk, and recommended action. Read [audit manifests](references/audit-manifest.md) for the required fields.
3. Classify artifacts as **safe candidate**, **requires review**, or **retain**. Directory names and ignored status are only clues, not proof.
4. For Git worktrees, read [Git worktree guidance](references/git-worktrees.md). Inspect Git metadata, tracked/untracked/ignored state, ownership, and integration evidence before recommending removal.
5. For Xcode artifacts, read [Xcode artifact guidance](references/xcode-artifacts.md). Keep dedicated build output separate from shared caches, archives, test evidence, and simulators.
6. Report the proposed recovery as an estimate; `du` and filesystem snapshots do not guarantee reclaimable bytes.

## Execution workflow

Use the audit manifest as a closed list of targets.

Read [execution rules](references/execution.md) before performing an execution request. For worktrees, the execution manifest's `approvedCandidateIds` field names the exact IDs the user authorized. The Xcode adapter instead keeps its audit manifest immutable and binds a separate approval to its SHA-256 digest and IDs. A broad approval such as “clean everything” does not add new paths to either closed list.

- Reject empty paths, roots, unresolved variables, globs, and symbolic links that point outside the approved target.
- Recheck the candidate's type, size, ownership, Git state, and active-build status immediately before removal.
- Remove ordinary Git worktrees with `git worktree remove <path>` only after the secondary-worktree registration, resolved path, and Git snapshot still match. Never replace that lifecycle with manual deletion. Do not use `--force` to bypass pending work.
- Treat local-branch deletion as a separate, explicitly authorized action. Never delete remote branches without explicit authorization.
- Prefer a project-specific build-output directory only when its configuration proves it is regenerated. Do not remove dependency directories, environments, secrets, user documents, screenshots, archives, or evidence by default.
- For Xcode execution, read the [adapter contract](references/xcode-cache-adapter.md) and run the bundled script without bypasses. It supports only four direct cache children of dedicated DerivedData inside a primary Git checkout. Never substitute a generic recursive deletion command.
- Measure space again and report removed, retained, skipped, and failed candidates separately.

## Stop conditions

Stop and report instead of deleting when any of these is true:

- Git state includes tracked or untracked work.
- Ignored content is not explicitly classified as regenerated output.
- The integration branch or remote evidence is ambiguous or unavailable.
- The target is an agent-managed worktree whose ownership or supported lifecycle cannot be verified.
- An Xcode build, test, or simulator is active, or activity cannot be safely checked.
- The manifest cannot prove an approved root, resolved path, unique candidate ID, or unchanged snapshot.

## Example requests

- "Audit build artifacts and worktrees in this repository and report cleanup candidates."
- "Use audit audit-123 and remove only worktree-feature-a after revalidation."

## Version

0.2.0. Git worktree execution, a bounded macOS dedicated-Xcode-cache adapter, and Xcode/Swift artifact audits; installation through skills.sh.
