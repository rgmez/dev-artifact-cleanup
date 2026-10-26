# Execution rules

Execution is a second pass over a reviewed audit. It is not a continuation of discovery.

## Execution scope

Execution supports an eligible **ordinary secondary Git worktree**, or the four dedicated cache directories covered by the macOS-only [Xcode adapter](xcode-cache-adapter.md). Other generated directories, caches, archives, test results, and simulators remain audit-only. Generic shell deletion is deliberately out of scope.

## Accept only explicit candidates

The user must identify an `auditId` and exact candidate IDs to execute. For worktrees, record them in the execution manifest's `approvedCandidateIds`. For Xcode caches, preserve the audit bytes and record a separate approval with their digest, IDs, timestamp, and a reference to the user's authorization. State the closed list before mutation; never add siblings, parents, matching names, or another repository. IDs must be unique and exist in the audit.

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

The [dedicated Xcode cache adapter](xcode-cache-adapter.md) uses descriptor-relative operations, exclusive staging, and an immutable recovery journal. Follow its narrower ownership, path, approval, and activity checks. Failed checks do not authorize a fallback deletion.

Report every other class as audit-only. New adapters require separate review and tests; never add execution through interpolated shell text.

For Xcode outcome review, preserve the exact audit, approval, result, and journal bytes and run the [execution evidence checker](execution-evidence.md). Keep the trusted runner's stdout/stderr and exit status separately. Its consistency result does not authenticate execution or replace human authorization and host permissions.

## Outcome

Measure the same data volume before and after execution. Mark every approved candidate as removed, skipped, retained, partially removed, or failed, with reasons. A partial purge is not full retention; restoration can only move back what remains. Treat observed free-space variation as a measurement, not a guaranteed reclaim amount.
