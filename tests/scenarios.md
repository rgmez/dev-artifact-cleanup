# Behavior scenarios

These scenarios describe decision boundaries. Contract fixtures are non-mutating; native adapter tests remove only synthetic data created in disposable temporary repositories.

## 1. Dedicated DerivedData audit

Given a repository with a custom DerivedData directory whose workspace metadata points to that repository, no active build, and no retained test evidence, the audit should produce a **safe candidate** with an exact path and rebuild cost. It must not delete the directory in audit mode.

The DerivedData root itself has no execution adapter. Only the four direct cache children supported by the Xcode adapter can become executable after its narrower checks and a separate hash-bound approval.

## 2. Clean integrated worktree

Given a clean ordinary **secondary** Git worktree whose branch is integrated into the approved base branch and whose ignored contents are only a known build cache, the audit should mark it `eligible-for-execution`. Only an execution manifest with the exact approved candidate ID may invoke `git worktree remove`. Branch deletion is a separate action.

## 3. Ignored settings safety stop

Given a clean worktree containing an ignored `settings.local.json` or `.env` file, the audit should classify it as **requires review** and not recommend removal based solely on ignored status.

## 4. Unique commit safety stop

Given a clean worktree with a commit that is neither reachable from nor patch-equivalent to the approved base, the audit should retain it and report the integration decision needed.

## 5. Simulator safety stop

Given a CoreSimulator device directory, the audit should retain it unless the user explicitly identifies the device as disposable and authorizes its deletion through the simulator lifecycle.

## 6. Closed-list execution

Given two safe candidates in an audit manifest and approval for one candidate ID, execution should revalidate and act only on that ID. It must not infer approval for the other candidate or a sibling directory.

## 7. Changed candidate safety stop

Given an approved candidate that becomes a symbolic link, gains untracked Git files, or changes ownership after audit, execution should skip it and report the failed revalidation.

## 8. Primary checkout safety stop

Given a path registered as the primary worktree, the audit should classify it as **retain** even when its Git state is clean and integrated.

## 9. Shared DerivedData safety stop

Given a `DerivedData` directory whose workspace metadata is missing or points to another checkout, the audit should classify it as **requires review**. It must not assume that a local-looking path belongs to the requested project.

## 10. Test-evidence retention

Given an `.xcresult` bundle or screenshots used for a release or QA decision, the audit should retain it unless the user supplies a retention decision and explicitly authorizes removal.

## 11. Xcode adapter recovery

Given an eligible dedicated cache and exact approval, exclusive staging precedes purge. If process activity starts after staging, retain the payload and journal. Restoration must not replace a cache recreated by a newer build. A partial purge must be reported as partial, not successful removal or complete retention.

## 12. Process inspection unavailable

Given a host that cannot inspect processes, the Xcode audit must report affected candidates as `requires-review`, and execution must stop. A direct command succeeding with different permissions does not establish that a sandboxed child process has the same capability.

## 13. Ambiguous approval safety stop

Given JSON records with duplicate keys, non-finite numbers, or a non-object root, reject them before staging. A hash matching ambiguous bytes is not enough. Candidate class, ownership, Git state, ID syntax, approved-root array, and measured size must agree with the dedicated-cache execution contract. A successful result and its immutable journal must bind the exact approval bytes, timestamp, and reference.

## 14. Unknown content safety stop

Given an otherwise eligible dedicated cache with a manually authored README, RTF document, unknown file, or unknown layout, the entire candidate requires review and its bytes remain unchanged. A known name or ignored state is not enough. The narrow positive IndexStore profile is also exercised with real Clang output; other nonempty cache formats remain non-executable until separately validated.

## 15. Execution-specific journal evidence

Given two attempts under the same audit and approval, their execution IDs and journals are distinct. Reviewing the second result with the first journal fails, even if all audit/approval identifiers and payload identities match. Journal whitespace changes also fail its recorded digest. Do not backfill missing fields in legacy evidence.

## 16. Recovery after an ambiguous durability failure

Given a retained payload, recovery persists a prepared receipt before its native rename. If directory fsync fails after that rename, report an unknown outcome, the renamed phase and unconfirmed durability; do not imply that no movement happened or retry automatically. If the final result write fails, capture the truthful stdout receipt and reportError alongside the stale saved file. Initial persistence failure must leave the payload staged.
