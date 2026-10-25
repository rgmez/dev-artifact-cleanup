---
name: dev-artifact-cleanup
description: Audit local development artifacts and plan safe cleanup for Git repositories, especially Xcode projects. Use to inventory builds, caches, logs, and worktrees before an explicitly authorized removal; do not use as a general disk cleaner.
---

# Development Artifact Cleanup

Produce an evidence-backed cleanup plan without treating developer work as disposable.

## Modes and authorization

- **Audit (default):** inspect and classify candidates. Do not delete, archive, reset, commit, fetch, or modify branches.
- **Execute:** act only when the user explicitly authorizes the exact candidate paths or identifiers from an audit. Revalidate every candidate immediately before mutation.

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

- Reject empty paths, roots, unresolved variables, globs, and symbolic links that point outside the approved target.
- Recheck the candidate's type, size, ownership, Git state, and active-build status immediately before removal.
- Remove ordinary Git worktrees with `git worktree remove <path>`; never replace that lifecycle with manual deletion. Do not use `--force` to bypass pending work.
- Treat local-branch deletion as a separate, explicitly authorized action. Never delete remote branches without explicit authorization.
- Prefer a project-specific build-output directory only when its configuration proves it is regenerated. Do not remove dependency directories, environments, secrets, user documents, screenshots, archives, or evidence by default.
- Measure space again and report removed, retained, skipped, and failed candidates separately.

## Stop conditions

Stop and report instead of deleting when any of these is true:

- Git state includes tracked or untracked work.
- Ignored content is not explicitly classified as regenerated output.
- The integration branch or remote evidence is ambiguous or unavailable.
- The target is a Codex-managed worktree not clearly owned by the current task.
- An Xcode build, test, or simulator is active, or activity cannot be safely checked.
