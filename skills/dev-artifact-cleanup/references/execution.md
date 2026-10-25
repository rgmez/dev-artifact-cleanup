# Execution rules

Execution is a second pass over a reviewed audit. It is not a continuation of discovery.

## Version 1 execution scope

Version 1 executes only removal of an eligible **ordinary secondary Git worktree**. Generated directories, caches, archives, test results, and simulators remain audit-only. A generic shell deletion command is not a safe cross-platform removal adapter and is deliberately out of scope.

## Accept only explicit candidates

The user must identify an `auditId` and exact candidate IDs to execute. Record the IDs in `approvedCandidateIds` and state the resulting closed list before mutation. Do not extend it to siblings, parents, matching names, or another repository. Candidate IDs must be unique and must exist in the referenced audit manifest.

## Revalidate

Immediately before every mutation, confirm:

1. The resolved path still equals the audited resolved path and is physically contained by the audited resolved root.
2. The candidate and its path components contain no symbolic links. Reject the candidate if this cannot be established.
3. Its class, ownership, and reason for eligibility still match the audit.
4. Its Git state, secondary-worktree registration, HEAD OID, branch-tip OID, and base OID are unchanged when applicable.
5. No active build, test, simulator, or other process makes the action unsafe.

If any check is unavailable or changed, skip the candidate and report it. Do not use force options to work around a failed check.

## Approved actions

### Ordinary Git worktree

Remove only with `git worktree remove <exact-path>` through an argument-safe tool invocation. The exact path must still be registered as a **secondary** worktree by `git worktree list --porcelain`; the primary checkout is never eligible. Verify submodules and nested Git repositories recursively, and stop if any state cannot be verified. Keep the branch unless its deletion was independently authorized and verified. Do not manually remove a worktree directory.

### Agent-managed worktree

Use the host's supported archive lifecycle when the task owns it and that capability is available. If ownership or the lifecycle cannot be verified, preserve it. This exception applies to any agent that manages checkout lifetimes; another host must not bypass it through manual Git removal.

### Other artifact classes

Report as audit-only. Add execution only through a separately reviewed platform adapter that accepts a resolved directory descriptor or an equivalently race-safe primitive, not through interpolated shell text.

## Outcome

Measure the same data volume before and after execution. Mark every approved candidate as removed, skipped, or failed, and include the reason for anything not removed. Treat observed free-space variation as a measurement, not a guaranteed reclaim amount.
