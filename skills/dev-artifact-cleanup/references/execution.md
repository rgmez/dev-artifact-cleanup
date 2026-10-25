# Execution rules

Execution is a second pass over a reviewed audit. It is not a continuation of discovery.

## Accept only explicit candidates

The user must identify the audit candidate IDs or exact absolute paths to execute. Translate that approval into a closed list and state the list before mutation. Do not extend it to siblings, parents, matching names, or another repository.

## Revalidate

Immediately before every mutation, confirm:

1. The path still exists and is not a symbolic link escaping the approved root.
2. Its class, ownership, and reason for eligibility still match the audit.
3. Its Git state, worktree registration, and integration evidence are unchanged when applicable.
4. No active build, test, simulator, or other process makes the action unsafe.

If any check is unavailable or changed, skip the candidate and report it. Do not use force options to work around a failed check.

## Approved actions

### Dedicated generated directory

Remove only the exact directory proven to be regenerated output. Never target a repository root, a shared cache, a dependency directory, or a parent selected only because one child was eligible.

### Ordinary Git worktree

Remove only with `git worktree remove <exact-path>`. Keep the branch unless its deletion was independently authorized and verified. Do not manually remove a worktree directory.

### Codex-managed worktree

Use its managed archive lifecycle when the task owns it. If ownership is not provable, preserve it.

## Outcome

Measure the same data volume before and after execution. Mark every approved candidate as removed, skipped, or failed, and include the reason for anything not removed. Treat observed free-space variation as a measurement, not a guaranteed reclaim amount.
