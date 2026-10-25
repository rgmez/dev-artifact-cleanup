# Git worktrees

Use Git metadata, not directory names, to identify worktrees:

```sh
git -C <repository> worktree list --porcelain
```

## Evidence for a removable ordinary worktree

1. It is registered as a secondary worktree, not the repository's primary checkout.
2. Its tracked and untracked state is clean.
3. Ignored paths have been inspected and are known regenerated output, not settings, secrets, evidence, or user files.
4. Every nested repository and submodule is clean, initialized as expected, and has no unverified local state.
5. Its committed work is integrated into the intended base branch. Resolve the base from repository policy, upstream configuration, or the reviewed pull request; do not assume a branch name. When allowed, refresh remote evidence first.
6. Its audited HEAD OID, branch-tip OID, and base OID still match during execution.
7. It is not an agent-managed worktree owned by another task. Preserve unknown managed worktrees, regardless of the product that created them.

An ancestor check proves direct integration. `git cherry -v <base> <branch>` can show patch equivalence after a rebase or cherry-pick, but it is not sufficient evidence for merge-only history or an unknown base. Report those cases for review.

## Removal

For an eligible ordinary worktree, use:

```sh
git -C <repository> worktree remove <exact-path>
```

Do not use `--force`. If it fails, preserve the worktree and report why. Removing the checkout does not authorize deleting its local branch; verify that branch separately and require explicit authorization. Remote branches are always out of scope without explicit authorization.

`git worktree prune` changes local metadata. Use it only after confirming the recorded paths no longer exist and no managed-worktree lifecycle should preserve them.
